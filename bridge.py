"""Local orchestration: validated CSV -> classifier -> facts -> guarded summary.

No network clients, training, uploads or arbitrary model selection at runtime.
"""
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
import psutil
import sklearn
from threadpoolctl import threadpool_limits

import ai4i
import pump

ROOT = Path(__file__).resolve().parent


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def release_files(root):
    """Check transport integrity before deserializing a trusted local bundle.

    Hashes detect corruption, not a malicious publisher. Only use trusted releases.
    """
    root = Path(root).resolve()
    manifest = read_json(root / 'manifest.json')
    for name in ('release.json', 'requirements-pi.txt'):
        if name not in manifest['sha256']:
            raise ValueError(f'Untracked release file: {name}')
    for name, expected in manifest['sha256'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f'Invalid or missing release file: {name}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Release checksum mismatch: {name}')
    config = read_json(root / 'release.json')
    for field in ('model', 'csv', 'parity_csv', 'parity_expected'):
        name = config[field]
        if name not in manifest['sha256']:
            raise ValueError(f'Untracked release input: {name}')
        config[field] = root / name
    return config


def verify_runtime(root, config):
    versions = {}
    for line in (Path(root)/'requirements-pi.txt').read_text(encoding='utf-8').splitlines():
        name, expected = line.split('==')
        actual = importlib.metadata.version(name)
        if actual != expected:
            raise ValueError(f'{name}: expected {expected}, installed {actual}')
        versions[name] = actual
    current = f'{sys.version_info.major}.{sys.version_info.minor}'
    if current != config['python_major_minor']:
        raise ValueError(f"Use Python {config['python_major_minor']} for this release; got {current}")
    return versions


def resource_snapshot():
    total = 0
    proc = psutil.Process()
    for item in [proc] + proc.children(recursive=True):
        try:
            total += item.memory_info().rss
        except psutil.Error:
            pass
    temp = None
    try:
        temp = float(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000
    except (OSError, ValueError):
        pass
    return dict(process_tree_rss_bytes=total, system_used_bytes=psutil.virtual_memory().used,
                temperature_c=temp, machine=platform.machine(), host=platform.platform())


class InferenceBridge:
    def __init__(self, dataset, model, csv, llama_cli=None, gguf=None):
        if dataset not in {'ai4i', 'pump'}:
            raise ValueError('dataset must be ai4i or pump')
        if bool(llama_cli) != bool(gguf):
            raise ValueError('Specify both --llama-cli and --gguf')
        for path in (model, csv, llama_cli, gguf):
            if path and not Path(path).is_file():
                raise ValueError(f'Missing file: {path}. See docs/PI_HANDOFF.md')
        # Pickle-based files must come from a trusted source.
        self.bundle = joblib.load(model)
        if self.bundle['sklearn_version'] != sklearn.__version__:
            raise ValueError('scikit-learn version mismatch; use the release requirements')
        self.dataset = dataset
        self.inputs = ai4i.INPUTS if dataset == 'ai4i' else pump.FEATURES
        if self.bundle.get('inputs', self.bundle.get('features')) != self.inputs:
            raise ValueError('Model schema does not match dataset')
        self.frame = (ai4i.load if dataset == 'ai4i' else pump.load_frame)(csv)
        if self.frame.empty:
            raise ValueError('Replay CSV is empty')
        self.args = SimpleNamespace(llama_cli=llama_cli, gguf=gguf)
        self.model_path = str(Path(model).resolve())
        self.csv_path = str(Path(csv).resolve())
        self.threshold = float(self.bundle['threshold'])
        if not 0 <= self.threshold <= 1:
            raise ValueError('Invalid model threshold')

    def metadata(self):
        report = self.bundle['report']
        return dict(dataset=self.dataset, model=report['selected'], threshold=self.threshold,
                    rows=len(self.frame), inputs=self.inputs, model_path=self.model_path,
                    csv_path=self.csv_path, split=report.get('split', 'pump_original'),
                    test_metrics=report['test'], llm_configured=bool(self.args.gguf),
                    warning=('ข้อมูลสังเคราะห์ AI4I • เดโมจำแนก snapshot ไม่ใช่ปั๊มจริง'
                             if self.dataset == 'ai4i' else
                             'ชุดปั๊มเดิมยังไม่ชนะ baseline อย่างน่าเชื่อถือ • ใช้สาธิตเท่านั้น'),
                    hardware_acceptance_verified=False)

    def evaluate(self, index, progress=None):
        row = self.frame.iloc[index]
        readings = {c: (None if pd.isna(row[c]) else
                       str(row[c]) if c == 'Type' else float(row[c])) for c in self.inputs}
        valid = all(v is not None for v in readings.values())
        start = time.perf_counter()
        value = None
        if valid:
            with threadpool_limits(limits=2):
                value = float(pump.score(self.bundle['model'], row[self.inputs].to_frame().T)[0])
            if not np.isfinite(value) or not 0 <= value <= 1:
                raise ValueError('Model returned an invalid score')
        status = int(value >= self.threshold) if valid else None
        event = dict(row=index + 1, at=datetime.now(timezone.utc).isoformat(), readings=readings,
                     status=status, score=value, threshold=self.threshold,
                     inference_seconds=time.perf_counter()-start, summary=None,
                     summary_method='pending', llm_seconds=0.0,
                     stage='summarizing' if valid else 'validating')
        # This is the complete facts boundary. Labels and failure modes are never passed.
        event['handoff'] = dict(dataset=self.dataset, model=self.bundle['report']['selected'],
                                status=status, score=value, threshold=self.threshold,
                                readings=readings, score_is_calibrated_probability=False,
                                remaining_life_available=False)
        if progress:
            progress(event)
        if self.dataset == 'ai4i':
            text = ai4i.summary_text(row, value, status)
        else:
            text = pump.template(status, row, value)
            if not self.bundle['report']['beats_baseline']:
                text = 'คำเตือน: โมเดลไม่ชนะ baseline ใช้สาธิตระบบเท่านั้น\n' + text
        event['summary'], event['summary_method'], event['llm_seconds'] = (
            pump.summarize(self.args, text) if valid else (text, 'template_missing_data', 0.0))
        event['stage'] = 'complete'
        return event

    def verify(self, csv, expected):
        frame = (ai4i.load if self.dataset == 'ai4i' else pump.load_frame)(csv)
        reference = read_json(expected)
        if self.threshold != reference['threshold']:
            raise ValueError('Reference threshold differs from bundle')
        with threadpool_limits(limits=2):
            actual = pump.score(self.bundle['model'], frame[self.inputs])
        np.testing.assert_allclose(actual, reference['scores'], rtol=0, atol=1e-9)
        np.testing.assert_array_equal(actual >= self.threshold,
                                     np.array(reference['scores']) >= reference['threshold'])
        return dict(passed=True, rows=len(frame), atol=1e-9)


def add_arguments(parser):
    parser.add_argument('--release', type=Path, help='Verified directory produced by prepare_pi.py')
    parser.add_argument('--dataset', choices=['ai4i', 'pump'], default='ai4i')
    parser.add_argument('--model', type=Path)
    parser.add_argument('--csv', type=Path)
    parser.add_argument('--llama-cli')
    parser.add_argument('--gguf')


def resolve_config(args):
    release = args.release
    if not release and not args.model and not args.csv and args.dataset == 'ai4i':
        release = next((folder for folder in (ROOT/'runtime', ROOT)
                        if (folder/'manifest.json').is_file()), None)
    if release:
        if args.model or args.csv or args.dataset != 'ai4i':
            raise ValueError('Use --release alone for dataset/model/CSV selection')
        config = release_files(release)
        config['dependency_versions'] = verify_runtime(release, config)
        return config
    base = ROOT / ('ai4i-artifacts/ordered_primary' if args.dataset == 'ai4i' else 'artifacts')
    return dict(dataset=args.dataset, model=args.model or base/'model.joblib',
                csv=args.csv or base/'parity_inputs.csv', parity_csv=base/'parity_inputs.csv',
                parity_expected=base/'parity_expected.json')


def build_bridge(args):
    config = resolve_config(args)
    return InferenceBridge(config['dataset'], config['model'], config['csv'],
                           args.llama_cli, args.gguf), config
