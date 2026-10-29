"""Real versioned model -> HTTP -> SQLite -> cited answer; optional real GGUF.

Run with the installed venv. No mocks, downloads, physical-offline attestation or
hardware acceptance. Use --network none externally for an isolated network test.
"""
import argparse
import json
import platform
import subprocess
import sys
import tempfile
import time
import psutil
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18080)
    parser.add_argument('--llm', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT/'evidence/ready-smoke.json')
    args = parser.parse_args()
    result = dict(machine=platform.machine(), platform=platform.platform(), python=platform.python_version(),
                  llm_requested=args.llm, hardware_acceptance_verified=False, checks={})
    base = f'http://127.0.0.1:{args.port}'

    def request(path, data=None):
        payload = None if data is None else json.dumps(data).encode()
        with urlopen(Request(base+path, payload, {'Content-Type': 'application/json'}), timeout=45) as response:
            return json.load(response)

    with tempfile.TemporaryDirectory(prefix='pump-smoke-') as temp:
        database = Path(temp)/'history.sqlite3'
        command = [sys.executable, str(ROOT/'dashboard.py'), '--port', str(args.port),
                   '--interval', '.2', '--database', str(database)]
        if args.llm:
            lock = json.loads((ROOT/'deploy/pi-lock.json').read_text())
            command += ['--llama-cli', str(ROOT/'deploy/llama-local'),
                        '--gguf', str(ROOT/'models'/lock['model_file']), '--llm-questions']
        # Fail on an occupied port rather than testing someone else's server.
        import socket
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', args.port))
        log_path = args.output.with_suffix('.log')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('w', encoding='utf-8') as log:
            def start():
                process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=log)
                deadline = time.monotonic()+90
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(f'Dashboard exited; inspect {log_path}')
                    try:
                        request('/api/state')
                        return process
                    except (URLError, OSError):
                        time.sleep(.2)
                process.terminate()
                process.wait(timeout=10)
                raise TimeoutError('Dashboard startup')

            def stop(process):
                children = psutil.Process(process.pid).children(recursive=True) if process.poll() is None else []
                for child in children:
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
                _, alive = psutil.wait_procs(children, timeout=5)
                for child in alive:
                    child.kill()

            process = start()
            try:
                request('/api/action', {'action': 'start'})
                deadline = time.monotonic()+480
                while time.monotonic() < deadline:
                    state = request('/api/state')
                    if state.get('error'):
                        raise RuntimeError(state['error'])
                    if state['position'] == 12 and not state['busy']:
                        break
                    time.sleep(.2)
                else:
                    raise TimeoutError('12-row replay')
                records = request('/api/records')
                result['checks']['normal_alert'] = records['stats']['normal'] == records['stats']['alerts'] == 6
                exported = request('/api/export')
                result['summary_methods'] = [event['summary_method'] for event in exported['history']]
                result['checks']['export_12'] = len(exported['history']) == 12
                result['checks']['summaries'] = all(method == ('local_llm_validated' if args.llm else 'template')
                                                   for method in result['summary_methods'])
                result['questions'] = []
                for question, intent in [('สรุปข้อมูล', 'summary'), ('มีรายการเตือนอะไร', 'alerts'),
                                         ('อุณหภูมิสูงสุด', 'temperature'), ('ค่าล่าสุด', 'latest')]:
                    answer = request('/api/ask', {'question': question})
                    result['questions'].append(answer)
                    result['checks'][f'question_{intent}'] = (answer['intent'] == intent and bool(answer['citations'])
                        and answer['stats']['total'] == 12 and (not args.llm or answer['method'] == 'local_llm_intent_validated'))
                result['checks']['no_invented_time'] = request('/api/ask', {'question': 'วันนี้เครื่องไหนเสีย'})['intent'] == 'time_unavailable'
            finally:
                stop(process)
            process = start()
            try:
                result['checks']['restart_new_session'] = request('/api/records')['stats']['total'] == 0
                result['checks']['restart_preserves_history'] = request('/api/records?scope=all')['stats']['total'] == 12
            finally:
                stop(process)
    result['passed'] = all(result['checks'].values())
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'], checks=result['checks'], output=str(args.output)), indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
