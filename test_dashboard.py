"""Boundary tests use small generated fixtures, never ignored trained artifacts."""
import hashlib
import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import make_pipeline

import ai4i
import bridge
import dashboard
import pump


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.frame = pd.DataFrame([
            ['L', 300, 310, 1500, 20, 20], ['M', 301, 312, 1400, 25, 30],
            ['H', 302, 314, 1300, 70, 180], ['L', 303, 315, 1200, 80, 200]], columns=ai4i.INPUTS)
        self.frame['Machine failure'] = [0, 0, 1, 1]
        self.frame['TWF'] = [0, 0, 1, 1]
        model = make_pipeline(ai4i.AI4IFeatures(), RandomForestClassifier(n_estimators=8, random_state=4))
        model.fit(self.frame[ai4i.INPUTS], self.frame['Machine failure'])
        self.bundle = dict(model=model, inputs=ai4i.INPUTS, threshold=.5,
                           sklearn_version=sklearn.__version__, report=dict(selected='fixture', test={}, split='fixture'))
        self.model = self.root/'model.joblib'
        self.csv = self.root/'input.csv'
        self.frame.to_csv(self.csv, index=False)
        joblib.dump(self.bundle, self.model)
        self.inference = bridge.InferenceBridge('ai4i', self.model, self.csv)

    def tearDown(self):
        self.temp.cleanup()

    def wait_position(self, controller, count):
        deadline = time.monotonic()+3
        while time.monotonic() < deadline:
            if controller.snapshot()['position'] >= count:
                return
            time.sleep(.01)
        self.fail(f'Replay stalled: {controller.snapshot()}')

    def test_real_model_to_facts_to_template(self):
        progress = []
        result = self.inference.evaluate(2, lambda event: progress.append(json.loads(json.dumps(event))))
        self.assertEqual(result['score'], float(pump.score(self.bundle['model'], self.frame[ai4i.INPUTS].iloc[[2]])[0]))
        self.assertEqual(result['status'], 1)
        self.assertEqual(result['summary_method'], 'template')
        self.assertEqual(progress[0]['stage'], 'summarizing')
        self.assertIsNone(progress[0]['summary'])
        self.assertNotIn('Machine failure', result['handoff']['readings'])
        self.assertNotIn('TWF', result['handoff']['readings'])
        self.assertIn('ควรตรวจบำรุงรักษา', result['summary'])

    def test_llm_cannot_override_classifier_and_timeout_falls_back(self):
        args = SimpleNamespace(llama_cli='local-executable', gguf='local-gguf')
        self.inference.args = args
        with patch('pump.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='B')):
            result = self.inference.evaluate(2)
        self.assertEqual(result['status'], 1)
        self.assertEqual(result['summary_method'], 'template_inconsistent_llm')
        import subprocess
        with patch('pump.subprocess.run', side_effect=subprocess.TimeoutExpired('llama', 30)):
            timeout = self.inference.evaluate(2)
        self.assertEqual(timeout['score'], result['score'])
        self.assertEqual(timeout['summary'], result['summary'])
        self.assertEqual(timeout['summary_method'], 'template_timeout')

    def test_parity_and_bad_threshold(self):
        expected = self.root/'expected.json'
        pump.save_json(expected, dict(scores=pump.score(self.bundle['model'], self.frame[ai4i.INPUTS]).tolist(), threshold=.5))
        self.assertTrue(self.inference.verify(self.csv, expected)['passed'])
        reference = bridge.read_json(expected)
        reference['threshold'] = .6
        pump.save_json(expected, reference)
        with self.assertRaisesRegex(ValueError, 'threshold'):
            self.inference.verify(self.csv, expected)

    def test_missing_pump_input_skips_classifier_and_llm(self):
        frame = pd.DataFrame([[1, None, 1, 2, 3, 4, 5]], columns=['Pump_ID']+pump.FEATURES)
        csv = self.root/'pump.csv'; frame.to_csv(csv, index=False)
        bundle = dict(model=self.bundle['model'], features=pump.FEATURES, threshold=.5,
                      sklearn_version=sklearn.__version__, report=dict(selected='fixture', test={}, beats_baseline=False))
        joblib.dump(bundle, self.model)
        inference = bridge.InferenceBridge('pump', self.model, csv)
        with patch('pump.score', side_effect=AssertionError('must not run')), patch('pump.summarize', side_effect=AssertionError('must not run')):
            event = inference.evaluate(0)
        self.assertIsNone(event['status'])
        self.assertEqual(event['summary_method'], 'template_missing_data')

    def test_no_overlapping_jobs_pause_and_reset(self):
        entered, finish = threading.Event(), threading.Event()
        original = self.inference.evaluate
        def slow(index, progress):
            entered.set(); finish.wait(3)
            return original(index, progress)
        self.inference.evaluate = slow
        controller = dashboard.ReplayController(self.inference, .01)
        try:
            controller.action('start')
            self.assertTrue(entered.wait(2))
            with self.assertRaises(ValueError): controller.action('step')
            with self.assertRaises(ValueError): controller.action('reset')
            controller.action('pause'); finish.set()
            self.wait_position(controller, 1)
            self.assertFalse(controller.snapshot()['running'])
            controller.action('reset')
            self.assertEqual(controller.snapshot()['position'], 0)
        finally:
            finish.set(); controller.close()

    def test_http_actions_real_model_export_and_origin_guard(self):
        controller = dashboard.ReplayController(self.inference, .01)
        server = ThreadingHTTPServer(('127.0.0.1', 0), dashboard.handler_for(controller))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        def post(action, origin=None):
            headers = {'Content-Type': 'application/json'}
            if origin: headers['Origin'] = origin
            return urlopen(Request(base+'/api/action', json.dumps(dict(action=action)).encode(), headers), timeout=3)
        try:
            with urlopen(base) as response:
                self.assertIn('PUMP LAB', response.read().decode())
                self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])
            with post('step') as response: self.assertEqual(response.status, 200)
            self.wait_position(controller, 1)
            with urlopen(base+'/api/export') as response: state = json.load(response)
            self.assertEqual(state['history'][0]['summary_method'], 'template')
            with self.assertRaises(HTTPError) as caught: post('step', 'https://external.invalid')
            self.assertEqual(caught.exception.code, 403)
            with self.assertRaises(HTTPError) as caught: post('invalid')
            self.assertEqual(caught.exception.code, 400)
            with urlopen(base+'/api/state') as response: self.assertEqual(json.load(response)['position'], 1)
        finally:
            server.shutdown(); server.server_close(); thread.join(); controller.close()

    def test_release_checksum_catches_corruption_and_escape(self):
        pump.save_json(self.root/'release.json', dict(model='model.joblib', csv='input.csv',
                      parity_csv='input.csv', parity_expected='expected.json'))
        (self.root/'requirements-pi.txt').write_text('scikit-learn=='+sklearn.__version__+'\n')
        pump.save_json(self.root/'expected.json', {})
        manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()}
        pump.save_json(self.root/'manifest.json', dict(sha256=manifest))
        self.assertEqual(bridge.release_files(self.root)['csv'], self.csv)
        self.csv.write_text('corrupt')
        with self.assertRaisesRegex(ValueError, 'checksum'): bridge.release_files(self.root)
        manifest['../escaped'] = 'bad'
        manifest.pop('input.csv')
        pump.save_json(self.root/'manifest.json', dict(sha256=manifest))
        with self.assertRaisesRegex(ValueError, 'Invalid or missing'): bridge.release_files(self.root)


if __name__ == '__main__':
    unittest.main()
