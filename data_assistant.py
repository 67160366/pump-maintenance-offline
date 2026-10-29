"""SQLite evidence and bounded local questions. LLMs never generate SQL or facts."""
import json
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

INTENTS = {'summary', 'alerts', 'temperature', 'latest', 'unknown'}


def temperature(event, dataset):
    readings = event['readings']
    if dataset == 'ai4i':
        value = readings.get('Process temperature [K]')
        return (None if value is None else value - 273.15), '°C (กระบวนการ)'
    return readings.get('Temperature'), 'หน่วยยังไม่ยืนยัน'


class RecordStore:
    def __init__(self, path=':memory:'):
        if str(path) != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.db:
            self.db.execute('''CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY, session TEXT NOT NULL, dataset TEXT NOT NULL,
                recorded_at TEXT NOT NULL, measured_at TEXT, machine_id TEXT,
                status INTEGER, temperature REAL, temperature_unit TEXT,
                payload TEXT NOT NULL)''')
            self.db.execute('CREATE INDEX IF NOT EXISTS snapshots_scope ON snapshots(dataset, session, id)')
            self.db.execute('CREATE INDEX IF NOT EXISTS snapshots_temperature ON snapshots(dataset, temperature)')

    def append(self, session, dataset, event):
        value, unit = temperature(event, dataset)
        with self.lock, self.db:
            cursor = self.db.execute('''INSERT INTO snapshots
                (session,dataset,recorded_at,measured_at,machine_id,status,temperature,temperature_unit,payload)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                (session, dataset, event['at'], event.get('measured_at'), event.get('machine_id'),
                 event['status'], value, unit, json.dumps(event, ensure_ascii=False, allow_nan=False)))
            return cursor.lastrowid

    def scope(self, dataset, session, scope='session', today=False, now=None):
        if scope not in {'session', 'all'}:
            raise ValueError('scope must be session or all')
        clause, params = 'dataset=?', [dataset]
        if scope == 'session':
            clause += ' AND session=?'; params.append(session)
        if today:
            local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo('Asia/Bangkok'))
            start = local.replace(hour=0, minute=0, second=0, microsecond=0)
            clause += ' AND measured_at>=? AND measured_at<?'
            params += [start.astimezone(timezone.utc).isoformat(),
                       (start + timedelta(days=1)).astimezone(timezone.utc).isoformat()]
        return clause, params

    def read(self, dataset, session, scope='session', intent='latest', today=False, now=None, limit=100):
        clause, params = self.scope(dataset, session, scope, today, now)
        extra, order = '', 'id DESC'
        if intent == 'alerts':
            extra = ' AND status=1'
        elif intent == 'temperature':
            extra, order = ' AND temperature IS NOT NULL', 'temperature DESC, id DESC'
        with self.lock:
            rows = self.db.execute(f'SELECT * FROM snapshots WHERE {clause}{extra} ORDER BY {order} LIMIT ?',
                                   params + [min(max(int(limit), 1), 100)]).fetchall()
        results = []
        for row in rows:
            item = json.loads(row['payload'])
            item.update(record_id=row['id'], session=row['session'], temperature=row['temperature'],
                        temperature_unit=row['temperature_unit'], dataset=row['dataset'])
            results.append(item)
        return results

    def stats(self, dataset, session, scope='session', today=False, now=None):
        clause, params = self.scope(dataset, session, scope, today, now)
        with self.lock:
            row = self.db.execute(f'''SELECT COUNT(*) AS total, COALESCE(SUM(status=1),0) AS alerts,
                COALESCE(SUM(status=0),0) AS normal, COALESCE(SUM(status IS NULL),0) AS missing,
                COUNT(measured_at) AS timestamped, COUNT(DISTINCT machine_id) AS machines
                FROM snapshots WHERE {clause}''', params).fetchone()
        return dict(row)

    def close(self):
        with self.lock:
            self.db.close()


def local_intent(question):
    text = question.casefold()
    if any(word in text for word in ('ร้อน', 'อุณหภูมิ', 'temperature', 'hottest', 'hot')):
        return 'temperature'
    if any(word in text for word in ('ปัญหา', 'เตือน', 'ผิดปกติ', 'เสีย', 'alert', 'problem', 'fault')):
        return 'alerts'
    if any(word in text for word in ('ล่าสุด', 'latest')):
        return 'latest'
    if any(word in text for word in ('สรุป', 'ภาพรวม', 'summary', 'overview')):
        return 'summary'
    return 'unknown'


def route_question(question, args, use_llm=False):
    fallback = local_intent(question)
    if not use_llm or not args.llama_cli or not args.gguf:
        return fallback, 'local_data_query', 0.0
    start = time.perf_counter()
    prompt = ('/no_think\nClassify the question. Output exactly one intent. '
              'summary=overview, alerts=machine problems, temperature=hot machines, '
              'latest=latest reading, unknown=anything else. Do not answer the question.\n'
              'Question: ' + question)
    grammar = 'root ::= "summary" | "alerts" | "temperature" | "latest" | "unknown"'
    try:
        result = subprocess.run([str(Path(args.llama_cli).resolve()), '-m', str(Path(args.gguf).resolve()),
                                 '-c', '1024', '-n', '16', '-t', '2', '--single-turn',
                                 '--no-display-prompt', '--grammar', grammar, '-p', prompt],
                                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
        intent = result.stdout.strip()
        if result.returncode == 0 and intent in INTENTS and (fallback == 'unknown' or intent == fallback):
            return intent, 'local_llm_intent_validated', time.perf_counter()-start
        reason = 'local_query_rejected_llm'
    except subprocess.TimeoutExpired:
        reason = 'local_query_llm_timeout'
    except OSError:
        reason = 'local_query_llm_unavailable'
    return fallback, reason, time.perf_counter()-start


def answer(store, session, dataset, question, args, scope='session', use_llm=False):
    if not isinstance(question, str) or not question.strip() or len(question) > 400:
        raise ValueError('กรุณาใส่คำถาม 1–400 ตัวอักษร')
    question = question.strip()
    # Exact counts are computed over the full SQL scope, never a truncated LLM context.
    stats = store.stats(dataset, session, scope)
    today = any(word in question.casefold() for word in ('วันนี้', 'today'))
    scope_label = 'ข้อมูลรอบนี้' if scope == 'session' else 'ทั้งหมดที่บันทึกในชุดข้อมูลนี้'
    caveat = ('ข้อมูลจำลองนี้ไม่มีรหัสเครื่องจริง แต่ละรายการเป็นเพียงตัวอย่างสำหรับทดลอง'
              if dataset == 'ai4i' else 'ผลทำนายของชุดปั๊มนี้ยังไม่น่าเชื่อถือเพียงพอ และยังไม่ยืนยันหน่วยอุณหภูมิ')
    base = dict(scope=scope, scope_label=scope_label, caveat=caveat, stats=stats,
                citations=[], method='local_data_query', llm_seconds=0.0)
    if today and (dataset == 'ai4i' or stats['timestamped'] == 0):
        return dict(base, intent='time_unavailable', answer='ยังบอกไม่ได้ว่าเครื่องไหนมีปัญหาวันนี้ เพราะข้อมูลไม่มีเวลาที่วัดจริง\nเวลาที่บันทึกตัวอย่างเป็นคนละเวลากับเวลาวัด\nลองถาม “รายการเตือนในรอบนี้” แทนได้')
    if today:
        scope_label = 'เวลาวัดวันนี้ (Asia/Bangkok) · ' + scope_label
        stats = store.stats(dataset, session, scope, today=True)
        base.update(stats=stats, scope_label=scope_label)
    intent, method, elapsed = route_question(question, args, use_llm)
    base.update(intent=intent, method=method, llm_seconds=elapsed)
    if intent == 'unknown':
        return dict(base, answer='ลองถามว่า “สรุปข้อมูล” “มีรายการเตือนอะไรบ้าง” “อุณหภูมิสูงสุด” หรือ “ค่าล่าสุด” ได้เลย\nตอนนี้ยังบอกสาเหตุหรือเวลาที่เครื่องจะเสียไม่ได้')
    if not stats['total']:
        return dict(base, answer='ยังไม่มีข้อมูลในช่วงที่เลือก ไปที่ “ภาพรวม” แล้วกด “ดูรายการถัดไป” หรือ “ดูอัตโนมัติ” ก่อน จากนั้นกลับมาถามได้เลย')
    rows = store.read(dataset, session, scope, intent, today=today, limit=3)
    lines = []
    if intent == 'summary':
        lines.append(f"มี {stats['total']} รายการ: ควรตรวจสอบ {stats['alerts']}, ไม่พบสัญญาณเตือน {stats['normal']}, ประเมินไม่ได้ {stats['missing']}")
    elif intent == 'alerts':
        lines.append(f"พบ {stats['alerts']} รายการที่ควรตรวจสอบเพิ่มเติม (ยังไม่ได้ยืนยันว่าเครื่องเสีย)")
    elif intent == 'temperature':
        lines.append('อุณหภูมิสูงสุดในข้อมูลที่เลือก • ยังไม่มีเกณฑ์บอกว่าร้อนเกินไป'
                     if rows else 'ยังไม่มีค่าอุณหภูมิในช่วงที่เลือก จึงบอกค่าสูงสุดไม่ได้')
    else:
        lines.append('ข้อมูลล่าสุดที่บันทึกไว้:')
    for row in rows:
        identity = f"ปั๊ม {row['machine_id']}" if row.get('machine_id') else f"รายการที่ {row['row']}"
        detail = (f"{row['temperature']:.2f} {row['temperature_unit']}" if intent == 'temperature'
                  else ('ควรตรวจสอบ' if row['status'] == 1 else 'ไม่พบสัญญาณเตือน' if row['status'] == 0 else 'ประเมินไม่ได้'))
        lines.append(f"• {identity}: {detail} [#{row['record_id']}]")
        base['citations'].append(dict(record_id=row['record_id'], row=row['row'], machine_id=row.get('machine_id'),
                                      recorded_at=row['at'], measured_at=row.get('measured_at'),
                                      temperature=row['temperature'], temperature_unit=row['temperature_unit'], status=row['status']))
        base['citations'][-1]['event'] = row
    base['display_limit'] = 3
    return dict(base, answer='\n'.join(lines))
