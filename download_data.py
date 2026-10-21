"""Explicit online dataset download; inference scripts never call this helper."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

DATASETS = {
    'ai4i': ('https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip',
             'ai4i2020.csv', 'data/ai4i/ai4i2020.csv'),
    'pump': ('https://www.kaggle.com/api/v1/datasets/download/selonamaris/large-industrial-pump-maintenance-dataset',
             'Large_Industrial_Pump_Maintenance_Dataset.csv', 'data/Large_Industrial_Pump_Maintenance_Dataset.csv'),
}


def download(dataset):
    url, member, target = DATASETS[dataset]
    path = Path(target)
    if path.exists():
        raise ValueError(f'{path} already exists; keeping existing file. Move it explicitly before downloading again.')
    request = urllib.request.Request(url, headers={'User-Agent': 'pump-maintenance-offline/1.0'})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read(25_000_001)
    if len(payload) > 25_000_000:
        raise ValueError('Download exceeds expected archive size')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        matches = [info for info in archive.infolist() if Path(info.filename).name == member]
        if len(matches) != 1 or matches[0].file_size > 25_000_000:
            raise ValueError('Archive does not contain exactly the expected CSV at an acceptable size')
        data = archive.read(matches[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    manifest = {'url': url, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    path.with_suffix('.source.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Saved {path} ({len(data):,} bytes), SHA-256: {manifest["sha256"]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', choices=DATASETS)
    args = parser.parse_args()
    try:
        download(args.dataset)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.exit(1, f'Download failed: {exc}\nUse the dataset page linked in README to download manually.\n')


if __name__ == '__main__':
    main()
