"""Provisioning must reject tampered bytes/pins before it can execute a wheel."""
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform == 'linux' and platform.machine() in {'aarch64', 'arm64'}, 'Linux ARM64 installer')
class SetupIntegrityTests(unittest.TestCase):
    def test_corrupt_wheel_and_mismatched_pins_do_not_create_venv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy2(Path(__file__).parent/'setup_pi.py', root/'setup_pi.py')
            (root/'deploy').mkdir()
            (root/'runtime').mkdir()
            wheels = root/'wheels/pi4-cp312'
            wheels.mkdir(parents=True)
            wheel = wheels/'fixture.whl'
            wheel.write_bytes(b'expected')
            manifest = {wheel.name: hashlib.sha256(wheel.read_bytes()).hexdigest()}
            (root/'deploy/wheels-sha256.json').write_text(json.dumps(manifest))
            (root/'requirements-pi.txt').write_text('fixture==1\n')
            (root/'runtime/requirements-pi.txt').write_text('fixture==2\n')
            wheel.write_bytes(b'corrupt')
            for expected in ('corrupt ARM64 wheel', 'requirements differ'):
                result = subprocess.run([sys.executable, root/'setup_pi.py'], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn(expected, result.stderr)
                self.assertFalse((root/'.venv').exists())
                wheel.write_bytes(b'expected')


if __name__ == '__main__':
    unittest.main()
