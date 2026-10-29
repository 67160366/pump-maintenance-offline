"""Build a self-contained, trusted Pi demo release from existing PC artifacts."""
import argparse
import hashlib
import importlib.metadata
import itertools
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

import bridge
import pump

PACKAGES = ['numpy', 'pandas', 'scipy', 'scikit-learn', 'joblib', 'psutil',
            'threadpoolctl', 'python-dateutil', 'pytz', 'tzdata', 'six']


def prepare(args):
    out = args.out.resolve()
    if out.exists() or out.with_suffix('.zip').exists():
        raise ValueError('Output already exists. Choose a new --out directory; releases are immutable.')
    source = bridge.ROOT
    if any(out.is_relative_to(source/name) for name in ('docs', 'web', 'deploy')):
        raise ValueError('Output cannot be inside a directory included in the release')
    wheels_dir = getattr(args, 'wheels_dir', None)
    wheels = sorted(wheels_dir.glob('*.whl')) if wheels_dir else []
    if wheels_dir and not wheels:
        raise ValueError('No wheels found in --wheels-dir')
    for wheel in wheels:
        filename = wheel.name
        if not ('none-any.whl' in filename or 'aarch64' in filename):
            raise ValueError(f'Expected ARM64 or universal wheel: {filename}')
        if 'aarch64' in filename and 'abi3' not in filename and f'cp{sys.version_info.major}{sys.version_info.minor}' not in filename:
            raise ValueError(f'Wheel Python version differs from this runtime: {filename}')
    base = source / ('ai4i-artifacts/ordered_primary' if args.dataset == 'ai4i' else 'artifacts')
    model = args.model or base/'model.joblib'
    # Verify reference inputs before making a distributable release.
    inference = bridge.InferenceBridge(args.dataset, model, base/'parity_inputs.csv')
    parity = inference.verify(base/'parity_inputs.csv', base/'parity_expected.json')
    if args.dataset == 'ai4i':
        import ai4i
        csv = args.source_csv or source/'data/ai4i/ai4i2020.csv'
        # Selection is exclusively from the original held-out partition.
        frame = ai4i.load(csv, training=True)
        audit = bridge.read_json(base.parent/'audit.json')
        if hashlib.sha256(csv.read_bytes()).hexdigest() != audit['sha256']:
            raise ValueError('Source CSV differs from the training audit')
        test = bridge.read_json(base/'split_indices.json')['test']
        frame = frame.loc[test, inference.inputs]
        with threadpool_limits(limits=2):
            scores = pump.score(inference.bundle['model'], frame)
        normal = np.flatnonzero(scores < inference.threshold)
        alert = np.flatnonzero(scores >= inference.threshold)
        # Alternate predicted states for a legible demonstration, without modifying sensors.
        order = []
        for a, b in itertools.zip_longest(normal[:6], alert[:6]):
            order.extend(int(i) for i in (a, b) if i is not None)
        demo = frame.iloc[order]
        provenance = dict(selection='Up to six predicted normal + six predicted alert test snapshots, interleaved; curated demo, not evaluation.',
                          original_row_indices=demo.index.tolist(), source_sha256=audit['sha256'],
                          source=ai4i.SOURCE, license='CC BY 4.0',
                          credit='AI4I 2020 Predictive Maintenance Dataset, UCI Machine Learning Repository; DOI 10.24432/C5HS5C')
    else:
        demo = inference.frame
        provenance = dict(selection='Existing parity snapshots. Original pump model may predict the same status for every row.',
                          source=pump.SOURCE, license='Verify source terms before redistribution.')
    if demo.empty:
        raise ValueError('No demo snapshots available')
    out.mkdir(parents=True)
    for pattern in ('*.py', '*.md', 'requirements.txt', '.dockerignore', '.gitattributes', '.gitignore'):
        for path in source.glob(pattern):
            if path.name == 'PUMP_MAINTENANCE_RESULTS.md':
                continue  # Local imported device notes are not a release input.
            shutil.copy2(path, out/path.name)
    for name in ('docs', 'web', 'deploy'):
        shutil.copytree(source/name, out/name)
    artifacts = out/'runtime'
    artifacts.mkdir()
    shutil.copy2(model, artifacts/'model.joblib')
    for name in ('parity_inputs.csv', 'parity_expected.json', 'report.json'):
        shutil.copy2(base/name, artifacts/name)
    demo.to_csv(artifacts/'demo.csv', index=False)
    pump.save_json(artifacts/'demo_provenance.json', provenance)
    requirements = '\n'.join(f'{name}=={importlib.metadata.version(name)}' for name in PACKAGES) + '\n'
    (out/'requirements-pi.txt').write_text(requirements, encoding='utf-8')
    if wheels:
        (out/'wheels').mkdir()
        for wheel in wheels:
            shutil.copy2(wheel, out/'wheels'/wheel.name)
    try:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=source, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = None, None
    pump.save_json(out/'release.json', dict(dataset=args.dataset, model='runtime/model.joblib',
                   csv='runtime/demo.csv', parity_csv='runtime/parity_inputs.csv',
                   parity_expected='runtime/parity_expected.json',
                   built_at=datetime.now(timezone.utc).isoformat(),
                   python=platform.python_version(), python_major_minor=f'{sys.version_info.major}.{sys.version_info.minor}',
                   source_commit=revision, source_worktree_dirty=dirty, pc_parity=parity,
                   bundled_wheels=len(wheels),
                   hardware_acceptance_verified=False))
    files = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(out.rglob('*')) if p.is_file()}
    pump.save_json(out/'manifest.json', dict(sha256=files,
                   note='Transport integrity only; use trusted publisher. GGUF, llama.cpp and venv are separate; ARM64 wheels are optional.'))
    archive = shutil.make_archive(str(out), 'zip', root_dir=out)
    result = dict(directory=str(out), archive=archive, rows=len(demo), pc_parity=parity,
                  archive_sha256=hashlib.sha256(Path(archive).read_bytes()).hexdigest())
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('pi-release'))
    parser.add_argument('--dataset', choices=['ai4i', 'pump'], default='ai4i')
    parser.add_argument('--model', type=Path)
    parser.add_argument('--source-csv', type=Path)
    parser.add_argument('--wheels-dir', type=Path, help='Optional predownloaded ARM64/universal wheels for the build Python version')
    args = parser.parse_args()
    try:
        prepare(args)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'{exc}\n')


if __name__ == '__main__':
    main()
