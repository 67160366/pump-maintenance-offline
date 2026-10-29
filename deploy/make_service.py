"""Generate a reviewable systemd unit. Does not install, enable or restart services."""
import argparse
import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llm', action='store_true')
    args = parser.parse_args()
    # systemd has its own escaping rules; reject unusual paths rather than emit a broken unit.
    if any(char in str(ROOT) for char in '\n\r"%\\'):
        parser.error('Move the clone to a path without quotes, percent signs or backslashes')
    python = ROOT/'.venv/bin/python'
    if not python.is_file():
        parser.error('Run setup_pi.py with its default .venv first')
    output = ROOT/'evidence/pump-dashboard.service'
    output.parent.mkdir(exist_ok=True)
    output.write_text(f'''[Unit]
Description=Offline maintenance CSV replay dashboard
After=local-fs.target

[Service]
Type=simple
User={getpass.getuser()}
WorkingDirectory="{ROOT}"
ExecStart="{python}" "{ROOT / 'start_pi.py'}"{' --llm' if args.llm else ''}
Environment=PYTHONUNBUFFERED=1
Environment=OMP_NUM_THREADS=2
Environment=OPENBLAS_NUM_THREADS=2
Restart=on-failure
RestartSec=5
TimeoutStopSec=40
KillMode=control-group
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
''', encoding='utf-8')
    print(f'Generated only: {output}\nStop the manual dashboard, review the unit, then:\n'
          f'sudo cp "{output}" /etc/systemd/system/pump-dashboard.service\n'
          'sudo systemctl daemon-reload\nsudo systemctl enable --now pump-dashboard')


if __name__ == '__main__':
    main()
