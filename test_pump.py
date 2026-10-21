import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import subprocess
import numpy as np
import pandas as pd
import pump

class PumpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        rng = np.random.default_rng(42)
        self.df = pd.DataFrame(rng.normal(size=(240, 6)), columns=pump.FEATURES)
        self.df['Pump_ID'] = np.tile([1, 2, 3], 80)
        self.df[pump.TARGET] = (self.df.Temperature + self.df.Vibration > 0).astype(int)
        self.path = self.root / 'input.csv'
        self.df.to_csv(self.path, index=False)
    def tearDown(self):
        self.temp.cleanup()
    def test_missing_column(self):
        self.df.drop(columns=['RPM']).to_csv(self.path, index=False)
        with self.assertRaisesRegex(ValueError, 'Missing columns'):
            pump.load_frame(self.path)
    def test_non_numeric(self):
        self.df['RPM'] = 'bad'
        self.df.to_csv(self.path, index=False)
        with self.assertRaises(ValueError):
            pump.load_frame(self.path)
    def test_infinity(self):
        self.df.loc[0, 'RPM'] = np.inf
        self.df.to_csv(self.path, index=False)
        with self.assertRaisesRegex(ValueError, 'Infinite'):
            pump.load_frame(self.path)
    def test_bad_label(self):
        self.df.loc[0, pump.TARGET] = 2
        self.df.to_csv(self.path, index=False)
        with self.assertRaisesRegex(ValueError, '0/1'):
            pump.load_frame(self.path, True)
    def test_conflicting_labels(self):
        row = self.df.iloc[[0]].copy()
        row[pump.TARGET] = 1 - row[pump.TARGET]
        pd.concat([self.df, row]).to_csv(self.path, index=False)
        with self.assertRaisesRegex(ValueError, 'contradictory'):
            pump.train(SimpleNamespace(csv=self.path, out=self.root/'out', skip_lopo=True))
    def test_summary_validation_and_timeout(self):
        args = SimpleNamespace(llama_cli='llama-cli', gguf='local.gguf')
        text = pump.template(1, self.df.iloc[0], 0.9)
        with patch('pump.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='A')):
            self.assertEqual(pump.summarize(args, text)[1], 'local_llm_validated')
        with patch('pump.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='B')):
            self.assertEqual(pump.summarize(args, text)[1], 'template_inconsistent_llm')
        with patch('pump.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='99% failure')):
            self.assertEqual(pump.summarize(args, text)[0], text)
        with patch('pump.subprocess.run', side_effect=subprocess.TimeoutExpired('llama', 30)):
            self.assertEqual(pump.summarize(args, text)[1], 'template_timeout')
    def test_training_replay_and_parity(self):
        import json
        import joblib
        out = self.root/'out'
        pump.train(SimpleNamespace(csv=self.path, out=out, skip_lopo=False))
        bundle = joblib.load(out/'model.joblib')
        parity = pd.read_csv(out/'parity_inputs.csv')
        expected = json.loads((out/'parity_expected.json').read_text())
        np.testing.assert_allclose(pump.score(bundle['model'], parity[pump.FEATURES]), expected['scores'], atol=1e-12)
        np.testing.assert_allclose(pump.score(bundle['model'], parity[list(reversed(pump.FEATURES))][pump.FEATURES]), expected['scores'], atol=1e-12)
        # Missing sensor values must produce an explicit unavailable state at runtime.
        self.df.loc[0, 'RPM'] = np.nan
        self.df[list(reversed(self.df.columns))].to_csv(self.path, index=False)
        args = SimpleNamespace(csv=self.path, model=out/'model.joblib', limit=4,
            summary_every_row=False, llama_cli=None, gguf=None, output=self.root/'benchmark.json')
        pump.replay(args)
        result = json.loads(args.output.read_text(encoding='utf-8'))
        self.assertIsNone(result['events'][0]['status'])
        self.assertEqual(result['events'][0]['summary_method'], 'template_missing_data')
        report = json.loads((out/'report.json').read_text(encoding='utf-8'))
        self.assertEqual(len(report['leave_one_pump_out']), 3)
        splits = json.loads((out/'split_indices.json').read_text())
        self.assertFalse(set(splits['train']) & set(splits['test']))
        self.assertFalse(set(splits['validation']) & set(splits['test']))

if __name__ == '__main__':
    unittest.main()
