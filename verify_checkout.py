"""Check the actual shipped model/data/wheel bytes using only the Python stdlib.

Run before installing dependencies. Missing models never trigger training or downloads.
Hashes check transfer integrity; use a trusted Git repository or release publisher.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED = ('ai4i.py', 'pump.py', 'bridge.py', 'dashboard.py', 'data_assistant.py',
            'pi_check.py', 'setup_pi.py', 'start_pi.py', 'web/index.html', 'web/app.js',
            'web/style.css', 'requirements-pi.txt', 'deploy/pi-lock.json',
            'deploy/provision-llm.sh', 'deploy/llama-local', 'deploy/smoke.py')


def check_file(root, name, expected=None):
    path = (root/name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f'Missing/invalid shipped file: {name}. Clone the documented branch again; do not train on Pi.')
    digest = hashlib.sha256()
    with path.open('rb') as source:
        first = source.read(1024*1024)
        if first.startswith(b'version https://git-lfs.github.com/spec/v1'):
            raise ValueError(f'LFS pointer instead of actual bytes: {name}')
        digest.update(first)
        while chunk := source.read(1024*1024):
            digest.update(chunk)
    actual = digest.hexdigest()
    if expected and actual != expected:
        raise ValueError(f'Checksum mismatch: {name}. Restore the matching release; do not retrain or change thresholds.')
    return dict(path=name, bytes=path.stat().st_size, sha256=actual)


def verify(root):
    root = Path(root).resolve()
    for name in REQUIRED:
        check_file(root, name)
    repository_layout = (root/'runtime/manifest.json').is_file()
    runtime = root/'runtime' if repository_layout else root
    manifest = json.loads((runtime/'manifest.json').read_text(encoding='utf-8'))['sha256']
    for key in ('release.json', 'requirements-pi.txt'):
        if key not in manifest:
            raise ValueError(f'Missing runtime manifest entry: {key}')
    for name, expected in manifest.items():
        check_file(runtime, name, expected)
    config = json.loads((runtime/'release.json').read_text(encoding='utf-8'))
    for key in ('model', 'csv', 'parity_csv', 'parity_expected'):
        if config[key] not in manifest:
            raise ValueError(f'Runtime input is not checksummed: {config[key]}')
    model = check_file(runtime, config['model'], manifest[config['model']])
    if model['bytes'] == 0:
        raise ValueError('The shipped model is empty')
    assets = []
    if repository_layout:
        approved = json.loads((root/'deploy/checkout-assets.json').read_text(encoding='utf-8'))
        assets = [check_file(root, name, expected) for name, expected in approved.items()]
    wheels_dir = root/'wheels/pi4-cp312' if repository_layout else root/'wheels'
    wheels = json.loads((root/'deploy/wheels-sha256.json').read_text(encoding='utf-8'))
    for name, expected in wheels.items():
        check_file(wheels_dir, name, expected)
    return dict(passed=True, layout='git-checkout' if repository_layout else 'usb-release',
                primary_model=model, approved_assets=assets, wheel_count=len(wheels),
                runtime_manifest_files=len(manifest), training_required=False,
                llm_required_for_default_demo=False, hardware_acceptance_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = verify(ROOT)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'CHECKOUT FAILED: {exc}\n')
    rendered = json.dumps(result, ensure_ascii=False, indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding='utf-8')
    print(rendered)


if __name__ == '__main__':
    main()
