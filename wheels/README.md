# Bundled Pi wheels

`pi4-cp312/` contains the 11 packages pinned in `requirements-pi.txt`, downloaded from
PyPI for Linux aarch64 / CPython 3.12 (plus architecture-independent wheels).
The SciPy wheel requires glibc >=2.27. Target Raspberry Pi OS 64-bit Bookworm/Trixie.

Install on Pi after creating a Python 3.12 venv:

```bash
.venv/bin/python -m pip install --no-index --find-links wheels/pi4-cp312 -r requirements-pi.txt
```

Do not install these ARM64 wheels on Windows/AMD64. On a PC use PyPI with the same
requirements instead. Each wheel preserves its upstream `.dist-info` license notices.
Resolving from this complete wheel set with `--no-index` was verified on PC using
pip's ARM64 target options. Actual installation/execution on Pi remains pending.
