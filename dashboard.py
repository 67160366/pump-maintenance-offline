"""Offline, single-session replay dashboard. Open http://127.0.0.1:8080."""
import argparse
import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import bridge


class ReplayController:
    def __init__(self, inference, interval=2):
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
        self.worker = threading.Thread(target=self.work, daemon=True)
        self.worker.start()

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(dict(metadata=self.inference.metadata(), running=self.running,
                                      busy=self.busy, position=self.position, current=self.current,
                                      history=self.history[-60:], error=self.error,
                                      resources=bridge.resource_snapshot()))

    def action(self, action):
        with self.lock:
            if action == 'pause':
                self.running = self.pending = False
            elif action == 'reset':
                if self.busy or self.pending:
                    raise ValueError('รอแถวปัจจุบันประมวลผลเสร็จก่อนเริ่มใหม่')
                self.running = False
                self.position, self.current, self.history, self.error = 0, None, [], None
            elif action in {'start', 'step'}:
                if self.error:
                    raise ValueError('แก้สาเหตุที่แสดงและกดเริ่มใหม่ก่อน')
                if self.position >= len(self.inference.frame):
                    raise ValueError('เล่นครบแล้ว กดเริ่มใหม่เพื่อเล่นอีกครั้ง')
                if action == 'step' and (self.busy or self.pending or self.running):
                    raise ValueError('หยุดเล่นอัตโนมัติและรอแถวปัจจุบันก่อน')
                if action == 'start':
                    self.running = True
                else:
                    self.pending = True
            else:
                raise ValueError('Unknown action')
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

    def close(self):
        with self.lock:
            self.running = self.pending = False
        self.stopping.set()
        self.wake.set()
        self.worker.join(timeout=35)


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
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == '/api/state':
                self.send(200, controller.snapshot())
            elif self.path == '/api/export':
                self.send(200, controller.snapshot())
            elif self.path in {'/', '/app.js', '/style.css'}:
                filename, mime = {'/': ('index.html', 'text/html; charset=utf-8'),
                                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                                  '/style.css': ('style.css', 'text/css; charset=utf-8')}[self.path]
                self.send(200, (static/filename).read_bytes(), mime)
            else:
                self.send(404, dict(error='Not found'))

        def do_POST(self):
            if self.path != '/api/action':
                return self.send(404, dict(error='Not found'))
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.send(403, dict(error='Cross-origin action rejected'))
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1024 or self.headers.get_content_type() != 'application/json':
                    raise ValueError('Expected small JSON request')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('Expected JSON object')
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
    args = parser.parse_args()
    if args.interval < .2:
        parser.error('--interval must be at least 0.2 seconds')
    try:
        inference, _ = bridge.build_bridge(args)
        controller = ReplayController(inference, args.interval)
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
