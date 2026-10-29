"""Catch the delivery failures that otherwise only appear after moving to Pi."""
import hashlib
import tempfile
import unittest
from pathlib import Path

import verify_checkout


class CheckoutDeliveryTests(unittest.TestCase):
    def test_missing_model_and_lfs_pointer_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with self.assertRaisesRegex(ValueError, 'Missing/invalid'):
                verify_checkout.check_file(root, 'model.joblib')
            (root/'model.joblib').write_bytes(b'version https://git-lfs.github.com/spec/v1\noid sha256:abc\n')
            with self.assertRaisesRegex(ValueError, 'LFS pointer'):
                verify_checkout.check_file(root, 'model.joblib')

    def test_changed_model_bytes_fail_checksum(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            original = b'approved model bytes'
            expected = hashlib.sha256(original).hexdigest()
            (root/'model.joblib').write_bytes(original)
            self.assertEqual(verify_checkout.check_file(root, 'model.joblib', expected)['bytes'], len(original))
            (root/'model.joblib').write_bytes(b'changed bytes')
            with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
                verify_checkout.check_file(root, 'model.joblib', expected)

    def test_manifest_path_cannot_escape_checkout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()/'checkout'
            root.mkdir()
            (root.parent/'outside.joblib').write_bytes(b'outside')
            with self.assertRaisesRegex(ValueError, 'Missing/invalid'):
                verify_checkout.check_file(root, '../outside.joblib')


if __name__ == '__main__':
    unittest.main()
