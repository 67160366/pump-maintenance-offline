import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import data_assistant as assistant


def snapshot(row=1, status=1, kelvin=310., machine=None, measured=None):
    return dict(row=row, status=status, score=.8 if status else .1, threshold=.5,
                at='2026-10-28T04:00:00+00:00', measured_at=measured, machine_id=machine,
                readings={'Process temperature [K]':kelvin, 'Temperature':40.},
                summary='facts', summary_method='template', inference_seconds=.01,
                llm_seconds=0, handoff={})


class DataAssistantTests(unittest.TestCase):
    def setUp(self):
        self.store = assistant.RecordStore()
        self.args = SimpleNamespace(llama_cli=None, gguf=None)

    def tearDown(self):
        self.store.close()

    def ask(self, question, **kwargs):
        return assistant.answer(self.store, 'session-1', 'ai4i', question, self.args, **kwargs)

    def test_persistence_and_session_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'telemetry.sqlite3'
            store = assistant.RecordStore(path)
            store.append('old', 'ai4i', snapshot())
            store.close()
            store = assistant.RecordStore(path)
            self.assertEqual(store.stats('ai4i','new')['total'], 0)
            self.assertEqual(store.stats('ai4i','new','all')['total'], 1)
            self.assertEqual(store.read('ai4i','new','all')[0]['row'], 1)
            store.close()

    def test_counts_include_all_rows_not_only_citations(self):
        for index in range(130):
            self.store.append('session-1','ai4i',snapshot(index+1, index%2))
        result = self.ask('สรุปข้อมูลรอบนี้')
        self.assertEqual(result['stats']['total'],130)
        self.assertEqual(result['stats']['alerts'],65)
        self.assertIn('130',result['answer'])
        self.assertEqual(len(result['citations']),3)
        self.assertEqual(result['citations'][0]['event']['row'],130)

    def test_temperature_ranking_conversion_and_no_overheating_claim(self):
        self.store.append('session-1','ai4i',snapshot(1,kelvin=300))
        self.store.append('session-1','ai4i',snapshot(2,kelvin=315))
        result=self.ask('เครื่องไหนร้อนที่สุด')
        self.assertEqual(result['citations'][0]['row'],2)
        self.assertAlmostEqual(result['citations'][0]['temperature'],41.85)
        self.assertIn('ยังไม่มีเกณฑ์',result['answer'])
        self.assertIn('ไม่มีรหัสเครื่องจริง',result['caveat'])

    def test_today_never_uses_replay_recording_time(self):
        self.store.append('session-1','ai4i',snapshot())
        result=self.ask('วันนี้เครื่องไหนมีปัญหา')
        self.assertEqual(result['intent'],'time_unavailable')
        self.assertEqual(result['citations'],[])
        self.assertIn('คนละเวลา',result['answer'])

    def test_day_filter_uses_measured_time_and_bangkok_boundary(self):
        self.store.append('s','pump',snapshot(machine='P1',measured='2026-10-27T16:59:59+00:00'))
        self.store.append('s','pump',snapshot(machine='P2',measured='2026-10-27T17:00:00+00:00'))
        self.store.append('s','pump',snapshot(machine='P3',measured=None))
        now=datetime(2026,10,28,4,tzinfo=timezone.utc)
        result=self.store.read('pump','s',today=True,now=now)
        self.assertEqual([r['machine_id'] for r in result],['P2'])
        self.assertEqual(self.store.stats('pump','s',today=True,now=now)['total'],1)

    def test_unknown_empty_and_invalid_scope(self):
        self.assertIn('ยังไม่มีข้อมูล',self.ask('สรุปข้อมูล')['answer'])
        self.assertEqual(self.ask('ขอเลขหวย')['intent'],'unknown')
        with self.assertRaises(ValueError): self.ask('สรุปข้อมูล',scope='malicious')
        with self.assertRaises(ValueError): self.ask('x'*401)

    def test_llm_routes_only_whitelisted_intent_and_never_generates_facts(self):
        self.args=SimpleNamespace(llama_cli='local-cli',gguf='local.gguf')
        self.store.append('session-1','ai4i',snapshot())
        with patch('data_assistant.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='alerts')):
            result=self.ask('มีรายการเตือนอะไร',use_llm=True)
        self.assertEqual(result['method'],'local_llm_intent_validated')
        self.assertEqual(result['stats']['alerts'],1)
        with patch('data_assistant.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='DROP TABLE snapshots')):
            rejected=self.ask('มีรายการเตือนอะไร',use_llm=True)
        self.assertEqual(rejected['method'],'local_query_rejected_llm')
        self.assertEqual(self.store.stats('ai4i','session-1')['total'],1)
        with patch('data_assistant.subprocess.run',side_effect=subprocess.TimeoutExpired('llama',10)):
            timeout=self.ask('มีรายการเตือนอะไร',use_llm=True)
        self.assertEqual(timeout['method'],'local_query_llm_timeout')
        self.assertEqual(timeout['answer'],result['answer'])


if __name__=='__main__':
    unittest.main()
