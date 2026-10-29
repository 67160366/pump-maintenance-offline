"""Offline-first Pi provisioning; no training, sudo, model download or service install."""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(command):
    subprocess.run([str(arg) for arg in command], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--venv', type=Path, default=ROOT/'.venv')
    args = parser.parse_args()
    if sys.platform != 'linux' or platform.machine() not in {'aarch64', 'arm64'}:
        parser.error('Requires Linux ARM64. For emulation see docs/PI_READY.md.')
    if sys.version_info[:2] != (3, 12):
        parser.error('Requires Python 3.12; prepare it while online. See docs/PI_HANDOFF.md.')
    wheels = ROOT/'wheels/pi4-cp312'
    if not wheels.is_dir():
        wheels = ROOT/'wheels'  # Optional USB release layout.
    manifest = json.loads((ROOT/'deploy/wheels-sha256.json').read_text())
    for name, expected in manifest.items():
        path = wheels/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            parser.error(f'Missing or corrupt ARM64 wheel: {name}')
    # Reject stale top-level pins before modifying the environment.
    runtime_pins = ROOT/'runtime/requirements-pi.txt'
    if runtime_pins.is_file() and runtime_pins.read_text().splitlines() != (ROOT/'requirements-pi.txt').read_text().splitlines():
        parser.error('Top-level requirements differ from the versioned runtime')
    # Fail before installing packages if the actual trained model was omitted from Git/ZIP.
    run([sys.executable, ROOT/'verify_checkout.py'])
    target = args.venv.resolve()
    python = target/'bin/python'
    if not target.exists():
        run([sys.executable, '-m', 'venv', target])
    if not python.is_file():
        parser.error(f'Existing directory is not a Linux venv: {target}; choose --venv elsewhere')
    run([python, '-m', 'pip', 'install', '--no-compile', '--no-index', '--find-links', wheels,
         '-r', ROOT/'requirements-pi.txt'])
    run([python, '-m', 'pip', 'check'])
    run([python, 'pi_check.py', '--output', 'evidence/pi-preflight.json'])
    print(f'Ready: {python} start_pi.py\nDashboard: http://127.0.0.1:8080')


if __name__ == '__main__':
    main()
