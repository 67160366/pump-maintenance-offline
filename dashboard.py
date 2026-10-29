"""Offline, single-session replay dashboard. Open http://127.0.0.1:8080."""
import argparse
import copy
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import bridge
import data_assistant


class ReplayController:
    def __init__(self, inference, interval=2, store=None, llm_questions=False):
        self.inference = inference
        self.interval = interval
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.running = self.busy = self.pending = False
        self.position = 0
        self.current = None
        self.history = []
        self.error = None
        self.store = store or data_assistant.RecordStore()
        self.session = uuid.uuid4().hex
        self.ask_busy = False
        self.llm_questions = llm_questions
        self.worker = threading.Thread(target=self.work, daemon=True)
        self.worker.start()

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(dict(metadata=self.inference.metadata(), running=self.running,
                                      busy=self.busy, position=self.position, current=self.current,
                                      history=self.history[-60:], error=self.error,
                                      session=self.session, ask_busy=self.ask_busy,
                                      stored=self.store.stats(self.inference.dataset, self.session),
                                      question_llm_enabled=self.llm_questions,
                                      resources=bridge.resource_snapshot()))

    def action(self, action):
        with self.lock:
            if self.ask_busy and action != 'pause':
                raise ValueError('กำลังตอบคำถาม กรุณารอให้เสร็จก่อน')
            if action == 'pause':
                self.running = self.pending = False
            elif action == 'reset':
                if self.busy or self.pending:
                    raise ValueError('รอให้ระบบดูรายการนี้เสร็จก่อน แล้วกด “เริ่มรอบใหม่” ได้เลย')
                self.running = False
                self.position, self.current, self.history, self.error = 0, None, [], None
                self.session = uuid.uuid4().hex
            elif action in {'start', 'step'}:
                if self.error:
                    raise ValueError('แก้ปัญหาตามข้อความที่แสดง แล้วกด “เริ่มรอบใหม่”')
                if self.position >= len(self.inference.frame):
                    raise ValueError('ดูครบแล้ว กด “เริ่มรอบใหม่” เพื่อดูอีกครั้งได้เลย')
                if action == 'step' and (self.busy or self.pending or self.running):
                    raise ValueError('กด “พักการอ่าน” แล้วรอให้ระบบดูรายการนี้เสร็จก่อน')
                if action == 'start':
                    self.running = True
                else:
                    self.pending = True
            else:
                raise ValueError('ไม่พบคำสั่งนี้ กรุณาเลือกจากปุ่มบนหน้าจอ')
            self.wake.set()

    def progress(self, event):
        with self.lock:
            self.current = copy.deepcopy(event)

    def work(self):
        while not self.stopping.is_set():
            self.wake.wait()
            self.wake.clear()
            if self.stopping.is_set():
                break
            with self.lock:
                if not (self.running or self.pending) or self.position >= len(self.inference.frame):
                    continue
                index = self.position
                self.pending = False
                self.busy = True
            try:
                event = self.inference.evaluate(index, self.progress)
                event['record_id'] = self.store.append(self.session, self.inference.dataset, event)
                with self.lock:
                    self.current = event
                    self.history.append(event)
                    self.history = self.history[-60:]
                    self.position += 1
                    if self.position >= len(self.inference.frame):
                        self.running = False
            except Exception as exc:
                with self.lock:
                    self.error = f'{type(exc).__name__}: {exc}'
                    self.running = False
            finally:
                with self.lock:
                    self.busy = False
            # Pause/reset wakes this wait immediately; no queue of LLM processes.
            self.wake.wait(self.interval)
            with self.lock:
                if self.running:
                    self.wake.set()

    def ask(self, question, scope='session'):
        with self.lock:
            if self.busy or self.pending or self.running or self.ask_busy:
                raise ValueError('พักการอ่านข้อมูลและรอให้ระบบทำรายการนี้เสร็จก่อน แล้วถามได้เลย')
            self.ask_busy = True
            session = self.session
        try:
            return data_assistant.answer(self.store, session, self.inference.dataset,
                                         question, self.inference.args, scope, self.llm_questions)
        finally:
            with self.lock:
                self.ask_busy = False

    def close(self):
        with self.lock:
            self.running = self.pending = False
        self.stopping.set()
        self.wake.set()
        self.worker.join(timeout=35)
        self.store.close()


def handler_for(controller):
    static = Path(__file__).resolve().parent / 'web'

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body, mime='application/json; charset=utf-8'):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'self'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == '/favicon.ico':
                self.send(204, b'', 'image/x-icon')
            elif self.path == '/api/state':
                self.send(200, controller.snapshot())
            elif self.path == '/api/export':
                self.send(200, controller.snapshot())
            elif urlsplit(self.path).path == '/api/records':
                try:
                    scope = parse_qs(urlsplit(self.path).query).get('scope', ['session'])[0]
                    self.send(200, dict(records=controller.store.read(controller.inference.dataset, controller.session, scope),
                                        stats=controller.store.stats(controller.inference.dataset, controller.session, scope)))
                except ValueError as exc:
                    self.send(400, dict(error=str(exc)))
            elif self.path in {'/', '/app.js', '/style.css', '/preview', '/preview.css'}:
                filename, mime = {'/': ('index.html', 'text/html; charset=utf-8'),
                                  '/preview': ('preview.html', 'text/html; charset=utf-8'),
                                  '/preview.css': ('preview.css', 'text/css; charset=utf-8'),
                                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                                  '/style.css': ('style.css', 'text/css; charset=utf-8')}[self.path]
                self.send(200, (static/filename).read_bytes(), mime)
            else:
                self.send(404, dict(error='Not found'))

        def do_POST(self):
            if self.path not in {'/api/action', '/api/ask'}:
                return self.send(404, dict(error='Not found'))
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.send(403, dict(error='Cross-origin action rejected'))
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 4096 or self.headers.get_content_type() != 'application/json':
                    raise ValueError('Expected small JSON request')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('Expected JSON object')
                if self.path == '/api/ask':
                    self.send(200, controller.ask(payload.get('question'), payload.get('scope', 'session')))
                else:
                    controller.action(payload.get('action'))
                    self.send(200, dict(ok=True))
            except (ValueError, TypeError) as exc:
                self.send(400, dict(error=str(exc)))

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    bridge.add_arguments(parser)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--interval', type=float, default=2)
    parser.add_argument('--database', type=Path, default=Path('evidence/telemetry.sqlite3'))
    parser.add_argument('--llm-questions', action='store_true', help='Use configured local LLM to select a whitelisted question intent')
    args = parser.parse_args()
    if args.interval < .2:
        parser.error('--interval must be at least 0.2 seconds')
    try:
        inference, _ = bridge.build_bridge(args)
        if args.llm_questions and not args.gguf:
            raise ValueError('--llm-questions requires --llama-cli and --gguf')
        controller = ReplayController(inference, args.interval, data_assistant.RecordStore(args.database), args.llm_questions)
        server = ThreadingHTTPServer((args.host, args.port), handler_for(controller))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'{exc}\n')
    print(f'Dashboard: http://{args.host}:{args.port} (CSV replay, local inference)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        controller.close()


if __name__ == '__main__':
    main()
