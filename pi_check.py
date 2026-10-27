"""Verify a release and PC parity; optionally collect target-device evidence."""
import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

import bridge
import pump


def check(args):
    # Validate bytes and runtime versions before loading the pickle-based model.
    config = bridge.resolve_config(args)
    version_checks = config.get('dependency_versions', {})
    inference = bridge.InferenceBridge(config['dataset'], config['model'], config['csv'], args.llama_cli, args.gguf)
    parity = inference.verify(config['parity_csv'], config['parity_expected'])
    device = None
    try:
        device = Path('/proc/device-tree/model').read_text().strip('\x00\n')
    except OSError:
        pass
    result = dict(host=platform.platform(), machine=platform.machine(), device_model=device,
                  python=platform.python_version(), dependency_versions=version_checks, parity=parity,
                  model_sha256=hashlib.sha256(Path(config['model']).read_bytes()).hexdigest(),
                  offline_operator_confirmed=args.offline_confirmed,
                  hardware_acceptance_verified=False,
                  note='Evidence only. Manually review offline operation, Pi identity, thermal throttling and fallback before acceptance.')
    if args.benchmark:
        if args.gguf:
            result['gguf_sha256'] = hashlib.sha256(Path(args.gguf).read_bytes()).hexdigest()
            result['llama_cli_path'] = str(Path(args.llama_cli).resolve())
        with pump.Monitor() as monitor:
            events = [inference.evaluate(i) for i in range(min(args.limit, len(inference.frame)))]
        llm_ok = bool(args.gguf) and all(e['summary_method'] == 'local_llm_validated' for e in events)
        result.update(events=events, peak_process_tree_rss_bytes=monitor.peak_rss,
                      peak_system_used_bytes=monitor.peak_system, peak_temperature_c=monitor.peak_temp,
                      classifier_under_1s=all(e['inference_seconds'] < 1 for e in events),
                      summaries_under_30s=all(e['llm_seconds'] <= 30 for e in events),
                      system_ram_under_6gib=monitor.peak_system < 6*1024**3,
                      llm_configured=bool(args.gguf), llm_all_validated=llm_ok,
                      fallback_count=sum(e['summary_method'].startswith('template_') for e in events))
        try:
            result['throttled'] = subprocess.check_output(['vcgencmd', 'get_throttled'], text=True, timeout=5).strip()
        except (OSError, subprocess.SubprocessError):
            result['throttled'] = None
    pump.save_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    bridge.add_arguments(parser)
    parser.add_argument('--benchmark', action='store_true')
    parser.add_argument('--offline-confirmed', action='store_true', help='Operator attests network was physically disconnected')
    parser.add_argument('--limit', type=int, default=12)
    parser.add_argument('--output', type=Path, default=Path('evidence/pi-check.json'))
    args = parser.parse_args()
    if args.limit < 1:
        parser.error('--limit must be positive')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        check(args)
    except (ValueError, OSError, KeyError, AssertionError) as exc:
        parser.exit(2, f'CHECK FAILED: {exc}\n')


if __name__ == '__main__':
    main()
