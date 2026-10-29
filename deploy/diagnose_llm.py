"""Inspect real GGUF stdout/stderr plus the application guards (no mocked LLM)."""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bridge
import data_assistant
import pump


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'evidence/llm-diagnostic.json')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--raw-only', action='store_true', help='Probe transport only; never claims application validation')
    modes.add_argument('--application-only', action='store_true', help='Use the unchanged production guards/timeouts only')
    parser.add_argument('--raw-timeout', type=int, default=60)
    args = parser.parse_args()
    lock = json.loads((ROOT/'deploy/pi-lock.json').read_text())
    model = ROOT/'models'/lock['model_file']
    if hashlib.sha256(model.read_bytes()).hexdigest() != lock['model_sha256']:
        parser.error('GGUF checksum mismatch')
    cli = ROOT/'deploy/llama-local'
    result = dict(machine=platform.machine(), python=platform.python_version(),
                  hardware_acceptance_verified=False, model_sha256=lock['model_sha256'], raw=[],
                  raw_checked=not args.application_only, production_checked=not args.raw_only)
    for prompt, grammar, expected in ([] if args.application_only else [
        ('Output A when status=alert, otherwise B. status=alert. Output one letter.', 'root ::= "A" | "B"', 'A'),
        ('Classify question: summary=overview, alerts=problems, temperature=hot, latest=recent, unknown=other. '
         'Question: สรุปข้อมูล. Output one intent.',
         'root ::= "summary" | "alerts" | "temperature" | "latest" | "unknown"', 'summary')]):
        start = time.monotonic()
        try:
            process = subprocess.run([str(cli), '-m', str(model), '-c', '1024', '-n', '16', '-t', '2',
                                      '--single-turn', '--no-display-prompt', '--grammar', grammar, '-p', prompt],
                                     capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=args.raw_timeout)
            entry = dict(returncode=process.returncode, stdout=process.stdout, stderr_tail=process.stderr[-8000:],
                         expected=expected, passed=process.returncode == 0 and process.stdout.strip() == expected)
        except subprocess.TimeoutExpired as exc:
            entry = dict(passed=False, reason=f'diagnostic_timeout_{args.raw_timeout}s',
                         partial_stdout=(exc.stdout or b'').decode('utf-8', errors='replace'),
                         partial_stderr=(exc.stderr or b'')[-8000:].decode('utf-8', errors='replace'))
        entry['seconds'] = time.monotonic()-start
        result['raw'].append(entry)
        print(json.dumps(dict(raw_passed=entry['passed'], seconds=entry['seconds']), ensure_ascii=False), flush=True)
    if args.raw_only:
        result.update(raw_passed=all(item['passed'] for item in result['raw']),
                      production_checked=False, passed=False)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['raw_passed'] else 1
    inference, _ = bridge.build_bridge(SimpleNamespace(release=None, dataset='ai4i', model=None, csv=None,
                                                       llama_cli=str(cli), gguf=str(model)))
    result['events'] = [inference.evaluate(index) for index in (0, 1)]
    result['questions'] = []
    for question in ('สรุปข้อมูล', 'มีรายการเตือนอะไร', 'อุณหภูมิสูงสุด', 'ค่าล่าสุด'):
        intent, method, seconds = data_assistant.route_question(question, inference.args, True)
        result['questions'].append(dict(question=question, intent=intent, method=method, seconds=seconds))
    # Actual executable failure, not a mock. The real model file is never renamed.
    failed = SimpleNamespace(llama_cli=str(cli), gguf=str(ROOT/'models/nonexistent-for-fallback.gguf'))
    text = result['events'][1]['summary']
    fallback_text, method, _ = pump.summarize(failed, text)
    result['fallback_preserves_facts'] = fallback_text == text and method == 'template_rejected_llm'
    result['passed'] = (all(item['passed'] for item in result['raw']) and
                        all(item['summary_method'] == 'local_llm_validated' for item in result['events']) and
                        all(item['method'] == 'local_llm_intent_validated' for item in result['questions']) and
                        result['fallback_preserves_facts'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'], raw=result['raw'],
                         methods=[item['summary_method'] for item in result['events']],
                         questions=result['questions'], fallback=result['fallback_preserves_facts']), ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
