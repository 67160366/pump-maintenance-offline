"""Train and replay pump snapshots. All runtime inference is local."""
import argparse
import hashlib
import json
import pickle
import platform
import subprocess
import threading
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import psutil
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ['Temperature', 'Vibration', 'Pressure', 'Flow_Rate', 'RPM', 'Operational_Hours']
TARGET = 'Maintenance_Flag'
SOURCE = 'https://www.kaggle.com/datasets/selonamaris/large-industrial-pump-maintenance-dataset'


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def load_frame(path, training=False):
    df = pd.read_csv(path)
    required = FEATURES + (['Pump_ID', TARGET] if training else ['Pump_ID'])
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError('Missing columns: ' + ', '.join(missing))
    for col in FEATURES:
        df[col] = pd.to_numeric(df[col], errors='raise')
    if np.isinf(df[FEATURES].to_numpy(dtype=float)).any():
        raise ValueError('Infinite sensor values are invalid')
    if df['Pump_ID'].isna().any():
        raise ValueError('Pump_ID cannot be missing')
    if training:
        if df[TARGET].isna().any() or not set(df[TARGET].unique()).issubset({0, 1}):
            raise ValueError('Maintenance_Flag must contain only 0/1')
        if df[TARGET].nunique() != 2:
            raise ValueError('Training requires both classes')
        if df[FEATURES].isna().all().any():
            raise ValueError('A sensor column is entirely missing')
    return df


def score(model, x):
    return model.predict_proba(x)[:, list(model.classes_).index(1)]


def metrics(y, scores, threshold):
    pred = scores >= threshold
    p, r, f, _ = precision_recall_fscore_support(y, pred, average='binary', zero_division=0)
    return dict(precision=float(p), recall=float(r), f1=float(f),
                pr_auc=float(average_precision_score(y, scores)) if len(set(y)) == 2 else None,
                confusion_matrix=confusion_matrix(y, pred, labels=[0, 1]).tolist(), rows=len(y))


def tune(model, x, y):
    s = score(model, x)
    candidates = [(metrics(y, s, float(t))['f1'], float(t)) for t in np.linspace(0.05, 0.95, 19)]
    _, threshold = max(candidates, key=lambda item: (item[0], -abs(item[1] - 0.5)))
    return threshold, metrics(y, s, threshold)


def candidates():
    yield 'dummy', make_pipeline(SimpleImputer(), DummyClassifier(strategy='prior'))
    for weight in (None, 'balanced'):
        suffix = 'default' if weight is None else weight
        yield 'logistic_' + suffix, make_pipeline(SimpleImputer(), StandardScaler(),
            LogisticRegression(class_weight=weight, max_iter=2000, random_state=42))
        for depth in (6, 8, 10):
            yield f'forest_{depth}_{suffix}', make_pipeline(SimpleImputer(),
                RandomForestClassifier(n_estimators=100, max_depth=depth, min_samples_leaf=3,
                                       class_weight=weight, random_state=42, n_jobs=1))


def select(train, val):
    fitted = []
    for name, model in candidates():
        model.fit(train[FEATURES], train[TARGET])
        threshold, report = tune(model, val[FEATURES], val[TARGET])
        fitted.append(dict(name=name, model=model, threshold=threshold, validation=report,
                           bytes=len(pickle.dumps(model, protocol=5))))
    baseline = fitted[0]
    best = max(c['validation']['f1'] for c in fitted[1:])
    eligible = [c for c in fitted[1:] if c['validation']['f1'] >= best - 0.02]
    winner = min(eligible, key=lambda c: (c['bytes'], c['name']))
    return winner, baseline, [{k: v for k, v in c.items() if k != 'model'} for c in fitted]


def train(args):
    raw = load_frame(args.csv, True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    key = ['Pump_ID'] + FEATURES
    conflicts = raw.groupby(key, dropna=False)[TARGET].nunique().gt(1).sum()
    if conflicts:
        raise ValueError(f'{conflicts} identical input groups have contradictory labels; resolve before training')
    df = raw.drop_duplicates(subset=key).reset_index(drop=True)
    tr, rest = train_test_split(df, test_size=0.4, stratify=df[TARGET], random_state=42)
    va, te = train_test_split(rest, test_size=0.5, stratify=rest[TARGET], random_state=42)
    if tr[FEATURES].isna().all().any():
        raise ValueError('Training partition has an entirely missing feature')
    winner, baseline, comparison = select(tr, va)
    s = score(winner['model'], te[FEATURES])
    test = metrics(te[TARGET], s, winner['threshold'])
    base_test = metrics(te[TARGET], score(baseline['model'], te[FEATURES]), baseline['threshold'])
    group_metrics = {}
    for pump, indices in te.groupby('Pump_ID').groups.items():
        positions = te.index.get_indexer(indices)
        group_metrics[str(pump)] = metrics(te.loc[indices, TARGET], s[positions], winner['threshold'])
    lopo = []
    if df.Pump_ID.nunique() > 1 and not args.skip_lopo:
        for pump in sorted(df.Pump_ID.unique()):
            held = df[df.Pump_ID == pump]
            pool = df[df.Pump_ID != pump]
            try:
                a, b = train_test_split(pool, test_size=0.25, stratify=pool[TARGET], random_state=42)
                if a[TARGET].nunique() < 2:
                    raise ValueError('Training fold needs both classes')
                w, _, _ = select(a, b)
                lopo.append(dict(pump=str(pump), selected=w['name'],
                    metrics=metrics(held[TARGET], score(w['model'], held[FEATURES]), w['threshold'])))
            except ValueError as exc:
                lopo.append(dict(pump=str(pump), skipped=str(exc)))
    report = dict(source=SOURCE, sha256=hashlib.sha256(Path(args.csv).read_bytes()).hexdigest(),
        rows_raw=len(raw), rows_deduplicated=len(df), duplicates_removed=len(raw)-len(df),
        missing=raw.isna().sum().to_dict(), dtypes={k: str(v) for k,v in raw.dtypes.items()},
        label_counts={str(k): int(v) for k,v in df[TARGET].value_counts().items()},
        sensor_statistics=json.loads(df[FEATURES].describe().to_json()),
        units={k: 'unverified' for k in FEATURES}, label_provenance='unverified',
        splits=dict(train=len(tr), validation=len(va), test=len(te)), candidates=comparison,
        selected=winner['name'], threshold=winner['threshold'], test=test, baseline_test=base_test,
        beats_baseline=test['f1'] > base_test['f1'], per_pump_test=group_metrics,
        leave_one_pump_out=lopo, lopo_skipped=args.skip_lopo,
        limitations=['Snapshot classification only; no remaining-life prediction.',
                    'Synthetic origin and physical units require source verification.',
                    'No real-pump accuracy claim; scores are not calibrated failure probabilities.'])
    bundle = dict(model=winner['model'], threshold=winner['threshold'], features=FEATURES,
                  sklearn_version=sklearn.__version__, report=report)
    joblib.dump(bundle, out / 'model.joblib', compress=3)
    save_json(out / 'report.json', report)
    # Retain split assignments for audit; raw source stays untouched.
    save_json(out / 'split_indices.json', dict(train=tr.index.tolist(), validation=va.index.tolist(), test=te.index.tolist()))
    parity = te.head(20)[['Pump_ID'] + FEATURES].copy()
    parity.to_csv(out / 'parity_inputs.csv', index=False)
    save_json(out / 'parity_expected.json', dict(scores=score(winner['model'], parity[FEATURES]).tolist(), threshold=winner['threshold']))
    print(json.dumps(dict(selected=winner['name'], test=test, beats_baseline=report['beats_baseline']), indent=2))


class Monitor:
    def __init__(self):
        self.stop = threading.Event()
        self.peak_rss = 0
        self.peak_system = 0
        self.peak_temp = None
        self.thread = threading.Thread(target=self.sample, daemon=True)
    def sample(self):
        while not self.stop.is_set():
            proc = psutil.Process()
            processes = [proc] + proc.children(recursive=True)
            total = 0
            for p in processes:
                try:
                    total += p.memory_info().rss
                except psutil.Error:
                    pass
            self.peak_rss = max(self.peak_rss, total)
            self.peak_system = max(self.peak_system, psutil.virtual_memory().used)
            try:
                temp = float(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000
                self.peak_temp = max(self.peak_temp or temp, temp)
            except (OSError, ValueError):
                pass
            self.stop.wait(0.05)
    def __enter__(self):
        self.thread.start()
        return self
    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join()


def template(status, row, value):
    if status is None:
        return 'ข้อมูลไม่ครบ ไม่สามารถประเมินสถานะได้ กรุณาตรวจสอบข้อมูลเซนเซอร์'
    label = 'ควรตรวจบำรุงรักษา' if status else 'ยังไม่พบสัญญาณให้ตรวจบำรุงรักษาจากโมเดล'
    readings = ', '.join(f'{k}={float(row[k]):g}' for k in FEATURES)
    return f'สถานะ: {label}\nคะแนนโมเดล: {value:.4f} (ไม่ใช่โอกาสเสียที่ยืนยันแล้ว)\nค่าที่วัด: {readings}\nควรตรวจสอบค่าที่วัดและคู่มือปั๊มก่อนตัดสินใจ ไม่สามารถระบุสาเหตุเสียหรือเวลาที่เหลือได้'


def summarize(args, text):
    if not args.llama_cli or not args.gguf:
        return text, 'template', 0.0
    start = time.perf_counter()
    # Keep facts in the deterministic template. The LLM chooses a vetted Thai sentence
    # rather than generating facts that a small model may change or invent.
    prompt = ('/no_think\nเลือกข้อความสรุปที่เหมาะสมจาก A หรือ B เท่านั้น ห้ามเพิ่มข้อความ\n'
              'A: ควรตรวจสอบปั๊มตามคู่มือ\nB: ติดตามค่าที่วัดต่อเนื่อง\nข้อมูล:\n' + text)
    try:
        p = subprocess.run([str(Path(args.llama_cli).resolve()), '-m', str(Path(args.gguf).resolve()),
            '-c', '1024', '-n', '128', '-t', '2', '--single-turn',
            '--no-display-prompt', '--grammar', 'root ::= "A" | "B"',
            '-p', prompt], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
            env=__import__('os').environ.copy())
        answer = p.stdout.strip()
        if p.returncode == 0 and answer in {'A', 'B'}:
            suffix = {'A': 'ควรตรวจสอบปั๊มตามคู่มือ', 'B': 'ติดตามค่าที่วัดต่อเนื่อง'}[answer]
            if ('ควรตรวจบำรุงรักษา' in text and answer != 'A'):
                return text, 'template_inconsistent_llm', time.perf_counter()-start
            return text + '\n' + suffix, 'local_llm_validated', time.perf_counter()-start
        reason = 'template_rejected_llm'
    except subprocess.TimeoutExpired:
        reason = 'template_timeout'
    except OSError:
        reason = 'template_llm_unavailable'
    return text, reason, time.perf_counter()-start


def replay(args):
    # Only load trusted joblib files; pickle deserialization can execute code.
    bundle = joblib.load(args.model)
    if bundle['sklearn_version'] != sklearn.__version__:
        raise ValueError('Use the same scikit-learn version as training')
    df = load_frame(args.csv)
    states, events, inference_times, llm_times = {}, [], [], []
    with Monitor() as monitor:
        for _, row in df.head(args.limit).iterrows():
            pump = str(row.Pump_ID)
            start = time.perf_counter()
            valid = not row[FEATURES].isna().any()
            value = float(score(bundle['model'], row[FEATURES].to_frame().T.astype(float))[0]) if valid else None
            status = int(value >= bundle['threshold']) if valid else None
            elapsed = time.perf_counter()-start
            inference_times.append(elapsed)
            changed = pump not in states or states[pump] != status
            if changed or args.summary_every_row or not valid:
                text = template(status, row, value)
                if not bundle['report']['beats_baseline']:
                    text = 'คำเตือน: โมเดลไม่ชนะ baseline ใช้สาธิตระบบเท่านั้น\n' + text
                summary, method, llm_time = summarize(args, text) if valid else (text, 'template_missing_data', 0.0)
                llm_times.append(llm_time)
            else:
                summary, method, llm_time = None, 'unchanged', 0.0
            states[pump] = status
            event = dict(pump=pump, status=status, score=value, inference_seconds=elapsed,
                         summary=summary, summary_method=method, llm_seconds=llm_time)
            events.append(event)
            print(json.dumps(event, ensure_ascii=False))
    result = dict(host=platform.platform(), machine=platform.machine(), events=events,
        peak_process_tree_rss_bytes=monitor.peak_rss, peak_system_used_bytes=monitor.peak_system,
        peak_temperature_c=monitor.peak_temp, sampling_seconds=0.05,
        classifier_under_1s=bool(inference_times) and max(inference_times)<1,
        summaries_under_30s=bool(llm_times) and max(llm_times)<=30,
        system_ram_under_6gb=monitor.peak_system < 6*1024**3,
        hardware_acceptance_verified=False,
        note='Run on target Pi with network physically disconnected. RSS may double-count shared pages; sampling may miss short peaks.')
    save_json(args.output, result)


def verify(args):
    bundle = joblib.load(args.model)
    if bundle['sklearn_version'] != sklearn.__version__:
        raise ValueError('Use the same scikit-learn version as training')
    df = load_frame(args.csv)
    expected = json.loads(Path(args.expected).read_text(encoding='utf-8'))
    actual = score(bundle['model'], df[FEATURES])
    np.testing.assert_allclose(actual, expected['scores'], rtol=0, atol=1e-9)
    np.testing.assert_array_equal(actual >= bundle['threshold'],
                                  np.array(expected['scores']) >= expected['threshold'])
    print('PASS: scores and statuses match reference')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('train')
    p.add_argument('--csv', required=True)
    p.add_argument('--out', default='artifacts')
    p.add_argument('--skip-lopo', action='store_true')
    p.set_defaults(func=train)
    p = subs.add_parser('replay')
    p.add_argument('--csv', required=True)
    p.add_argument('--model', default='artifacts/model.joblib')
    p.add_argument('--llama-cli')
    p.add_argument('--gguf')
    p.add_argument('--limit', type=int, default=100)
    p.add_argument('--summary-every-row', action='store_true')
    p.add_argument('--output', default='benchmark.json')
    p.set_defaults(func=replay)
    p = subs.add_parser('verify')
    p.add_argument('--csv', default='artifacts/parity_inputs.csv')
    p.add_argument('--model', default='artifacts/model.joblib')
    p.add_argument('--expected', default='artifacts/parity_expected.json')
    p.set_defaults(func=verify)
    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc)+'\n')

if __name__ == '__main__':
    main()
