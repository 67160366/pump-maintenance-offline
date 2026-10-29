"""Start the verified template demo, or explicitly opt into the pinned local LLM."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def command(args):
    result = [sys.executable, str(ROOT/'dashboard.py'), '--host', args.host, '--port', str(args.port),
              '--database', str(args.database.resolve())]
    if args.llm:
        lock = json.loads((ROOT/'deploy/pi-lock.json').read_text())
        model = ROOT/'models'/lock['model_file']
        build = os.environ.get('LLAMA_LOCAL_BUILD', 'build')
        if build not in {'build', 'build-cross'}:
            raise ValueError('LLAMA_LOCAL_BUILD must be build or build-cross')
        binary = ROOT/'local/llama.cpp'/build/'bin/llama-completion'
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError('Missing executable llama-completion; run bash deploy/provision-llm.sh while online')
        if not model.is_file() or hashlib.sha256(model.read_bytes()).hexdigest() != lock['model_sha256']:
            raise ValueError('Missing or corrupt pinned GGUF; run deploy/fetch_model.py while online')
        result += ['--llama-cli', str(ROOT/'deploy/llama-local'), '--gguf', str(model), '--llm-questions']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llm', action='store_true')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--database', type=Path, default=ROOT/'evidence/telemetry.sqlite3')
    args = parser.parse_args()
    try:
        argv = command(args)
    except ValueError as exc:
        parser.exit(2, f'{exc}\n')
    os.chdir(ROOT)
    os.environ.setdefault('OMP_NUM_THREADS', '2')
    os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
    os.execv(sys.executable, argv)


if __name__ == '__main__':
    main()
