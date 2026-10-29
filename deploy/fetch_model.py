"""Explicit ONLINE provisioning only. Fetch the official, revision/hash-pinned GGUF."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    lock = json.loads((ROOT/'deploy/pi-lock.json').read_text())
    target = ROOT/'models'/lock['model_file']
    target.parent.mkdir(exist_ok=True)
    if target.is_file():
        if hashlib.sha256(target.read_bytes()).hexdigest() == lock['model_sha256']:
            print(f'Existing GGUF verified: {target}')
            return
        raise ValueError(f'Existing GGUF has wrong hash; preserve/move it before retrying: {target}')
    url = f"https://huggingface.co/{lock['model_repo']}/resolve/{lock['model_revision']}/{lock['model_file']}"
    temp = target.with_suffix('.gguf.part')
    digest, size = hashlib.sha256(), 0
    try:
        with urlopen(url, timeout=120) as response, temp.open('wb') as output:
            while chunk := response.read(1024*1024):
                output.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if size != lock['model_bytes'] or digest.hexdigest() != lock['model_sha256']:
            raise ValueError('GGUF checksum/size mismatch; partial file will be removed')
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    print(f'GGUF verified: {target} ({size} bytes)')


if __name__ == '__main__':
    main()
