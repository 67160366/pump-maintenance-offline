"""Exploratory experiments preserving original target and frozen holdout."""
import argparse
import json
import pickle
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import pointbiserialr
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_selection import mutual_info_classif
from sklearn.impute import SimpleImputer
from sklearn.kernel_approximation import Nystroem
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from threadpoolctl import threadpool_limits

import pump


class SensorFeatures(BaseEstimator, TransformerMixin):
    """Stateless transformations. No label, row position or future samples."""
    def __init__(self, engineered=False, pump_id=False):
        self.engineered = engineered
        self.pump_id = pump_id
    def fit(self, X, y=None):
        self.pumps_ = sorted(X.Pump_ID.dropna().unique()) if self.pump_id else []
        return self
    def transform(self, X):
        raw = X[pump.FEATURES].to_numpy(dtype=float)
        blocks = [raw]
        if self.engineered:
            # Products and squares cover pairwise nonlinear effects. Ratios are
            # exploratory proxies: physical units and sensor placement unverified.
            blocks.append(PolynomialFeatures(2, include_bias=False).fit_transform(raw)[:, 6:])
            safe = np.maximum(np.abs(raw), 1e-6)
            ratios = [raw[:, i] / safe[:, j] for i, j in [(0,1),(1,4),(2,3),(3,4),(2,4),(5,4)]]
            blocks.extend([np.column_stack(ratios), np.sign(raw)*np.log1p(np.abs(raw))])
        if self.pump_id:
            blocks.append(np.column_stack([(X.Pump_ID.to_numpy() == p).astype(float) for p in self.pumps_]))
        return np.column_stack(blocks)


def get_models():
    yield 'dummy_majority', make_pipeline(SensorFeatures(), SimpleImputer(), DummyClassifier(strategy='most_frequent'))
    for engineered in [False, True]:
        tag = 'engineered' if engineered else 'raw'
        feature = SensorFeatures(engineered=engineered)
        for c in [0.01, 1.0]:
            yield f'logistic_{tag}_C{c}', make_pipeline(clone(feature), SimpleImputer(), StandardScaler(),
                LogisticRegression(C=c, solver='liblinear', max_iter=1000, random_state=42))
        for leaf in [7, 31]:
            yield f'histgb_{tag}_leaves{leaf}', make_pipeline(clone(feature), SimpleImputer(),
                HistGradientBoostingClassifier(max_iter=120, max_leaf_nodes=leaf, l2_regularization=10,
                    learning_rate=0.05, early_stopping=True, random_state=42))
        yield f'extratrees_{tag}', make_pipeline(clone(feature), SimpleImputer(),
            ExtraTreesClassifier(n_estimators=160, min_samples_leaf=4, max_features=0.8, n_jobs=2, random_state=42))
    yield 'rf_deep_raw', make_pipeline(SensorFeatures(), SimpleImputer(),
        RandomForestClassifier(n_estimators=160, min_samples_leaf=2, max_features=1.0, n_jobs=2, random_state=42))
    for k in [15, 75]:
        yield f'knn_{k}', make_pipeline(SensorFeatures(), SimpleImputer(), StandardScaler(),
            KNeighborsClassifier(n_neighbors=k, weights='distance', n_jobs=2))
    yield 'rbf_kernel_approx', make_pipeline(SensorFeatures(), SimpleImputer(), StandardScaler(),
        Nystroem(n_components=256, gamma=0.15, random_state=42),
        LogisticRegression(C=1, solver='liblinear', random_state=42))
    yield 'mlp_32_16', make_pipeline(SensorFeatures(), SimpleImputer(), StandardScaler(),
        MLPClassifier(hidden_layer_sizes=(32,16), alpha=0.1, early_stopping=True,
            max_iter=120, random_state=42))
    yield 'histgb_with_pump', make_pipeline(SensorFeatures(engineered=True, pump_id=True), SimpleImputer(),
        HistGradientBoostingClassifier(max_iter=120, max_leaf_nodes=15, l2_regularization=10, random_state=42))


def measure(y, s, threshold):
    report = pump.metrics(y, s, threshold)
    report.update(accuracy=float(accuracy_score(y, s>=threshold)),
                  balanced_accuracy=float(balanced_accuracy_score(y, s>=threshold)),
                  roc_auc=float(roc_auc_score(y, s)))
    return report


def threshold_for_accuracy(y, s):
    # Fit threshold on development OOF only, never validation/test.
    ts = np.unique(np.r_[0.0, np.linspace(0.35,0.65,61),1.0])
    return float(max(ts, key=lambda t:(accuracy_score(y,s>=t), -abs(t-0.5))))


def wilson(correct, n):
    z=1.96
    p=correct/n
    center=(p+z*z/(2*n))/(1+z*z/n)
    margin=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [float(center-margin),float(center+margin)]


def run(args):
    out=Path(args.out)
    out.mkdir(parents=True,exist_ok=True)
    df=pump.load_frame(args.csv,True).drop_duplicates(subset=['Pump_ID']+pump.FEATURES).reset_index(drop=True)
    original=json.loads(Path('artifacts/report.json').read_text(encoding='utf-8'))
    digest=__import__('hashlib').sha256(Path(args.csv).read_bytes()).hexdigest()
    if digest != original['sha256']:
        raise ValueError('Source CSV changed; original split indices cannot be reused')
    splits=json.loads(Path('artifacts/split_indices.json').read_text())
    all_indices=[i for group in splits.values() for i in group]
    if len(set(all_indices)) != len(df) or len(all_indices) != len(df) or set(all_indices) != set(df.index):
        raise ValueError('Split indices must be disjoint and cover the deduplicated source exactly')
    tr,va,te=(df.loc[splits[k]] for k in ['train','validation','test'])
    # Never create target-based features or a row-order pseudo time axis.
    x=tr[['Pump_ID']+pump.FEATURES]
    y=tr[pump.TARGET]
    cv=StratifiedKFold(n_splits=3,shuffle=True,random_state=2026)
    rows=[]
    fitted={}
    for name,model in get_models():
        start=time.perf_counter()
        s=cross_val_predict(model,x,y,cv=cv,method='predict_proba',n_jobs=1)[:,1]
        threshold=threshold_for_accuracy(y,s)
        model.fit(x,y)
        train_scores=pump.score(model,x)
        val_scores=pump.score(model,va)
        row=dict(name=name,threshold=threshold,cv_oof=measure(y,s,threshold),
                 validation=measure(va[pump.TARGET],val_scores,threshold),
                 train_accuracy=float(accuracy_score(y,train_scores>=threshold)),
                 pickle_bytes=len(pickle.dumps(model,protocol=5)),seconds=time.perf_counter()-start)
        rows.append(row)
        fitted[name]=model
        pump.save_json(out/'progress.json',rows)
        print(f'{name}: CV acc={row["cv_oof"]["accuracy"]:.4f} val acc={row["validation"]["accuracy"]:.4f} AUC={row["validation"]["roc_auc"]:.4f}',flush=True)
    # Validation chooses the candidate; OOF chooses each threshold. Freeze here.
    eligible=[r for r in rows if not r['name'].startswith('dummy')]
    best=max(eligible,key=lambda r:(r['validation']['accuracy'], -r['pickle_bytes']))
    model=fitted[best['name']]
    test_s=pump.score(model,te)
    test=measure(te[pump.TARGET],test_s,best['threshold'])
    test['accuracy_95pct_wilson']=wilson(int(np.sum((test_s>=best['threshold'])==te[pump.TARGET])),len(te))
    # Matched-size, same-CV shuffled-label control for the selected configuration.
    shuffled=[]
    for seed in range(args.permutations):
        yp=np.random.default_rng(seed+100).permutation(y.to_numpy())
        sp=cross_val_predict(clone(model),x,yp,cv=cv,method='predict_proba',n_jobs=1)[:,1]
        tp=threshold_for_accuracy(yp,sp)
        shuffled.append(measure(yp,sp,tp))
        print(f'shuffled control {seed+1}/{args.permutations}: accuracy={shuffled[-1]["accuracy"]:.4f}',flush=True)
    numeric=tr[pump.FEATURES]
    mi=mutual_info_classif(numeric,y,random_state=42)
    audit={col:dict(point_biserial_r=float(pointbiserialr(y,numeric[col]).statistic),
                    mutual_information=float(mi[i])) for i,col in enumerate(pump.FEATURES)}
    report=dict(target='Original Maintenance_Flag unchanged',primary_metric='accuracy',goal=0.8,
        split_policy='Reuses original 60/20/20 indices. Original test was seen in previous run; final score is exploratory, not a fresh prospective test.',
        source_sha256=__import__('hashlib').sha256(Path(args.csv).read_bytes()).hexdigest(),
        features='6 sensors; products, squares, log1p, six ratios; optional train-fitted pump one-hot',
        models=rows,selected=best['name'],threshold=best['threshold'],test=test,
        reaches_80pct=test['accuracy']>=0.8,feature_signal_train_only=audit,
        shuffled_label_controls=shuffled,
        caveats=['Permutation controls are diagnostic, not a selection-adjusted significance test.',
                 'Ratios are exploratory; units and pump curve are unverified.',
                 'No relabelling, target-derived features, filtering by prediction correctness, or temporal features from row order.'])
    pump.save_json(out/'report.json',report)
    joblib.dump(dict(model=model,threshold=best['threshold'],columns=['Pump_ID']+pump.FEATURES,
                     research_only=True,report=report),out/'candidate.joblib',compress=3)
    table=['| Model | CV accuracy | Validation accuracy | Validation ROC-AUC | Size (KiB) |',
           '|---|---:|---:|---:|---:|']
    for r in sorted(rows,key=lambda r:r['validation']['accuracy'],reverse=True):
        table.append(f'| {r["name"]} | {r["cv_oof"]["accuracy"]:.2%} | {r["validation"]["accuracy"]:.2%} | {r["validation"]["roc_auc"]:.4f} | {r["pickle_bytes"]/1024:.1f} |')
    note=f'''# ผลทดลองเพิ่มฟีเจอร์และเปลี่ยนโมเดล

เป้าหมาย: accuracy 80% บน label เดิม โดยไม่แก้ข้อมูลต้นฉบับ

โมเดลที่เลือกจาก validation: **{best['name']}**

- Test accuracy: **{test['accuracy']:.2%}**, 95% Wilson interval {test['accuracy_95pct_wilson'][0]:.2%}–{test['accuracy_95pct_wilson'][1]:.2%}
- Balanced accuracy: {test['balanced_accuracy']:.2%}, ROC-AUC: {test['roc_auc']:.4f}, PR-AUC: {test['pr_auc']:.4f}
- Precision: {test['precision']:.2%}, recall: {test['recall']:.2%}, F1: {test['f1']:.4f}
- Confusion matrix [0,1]: {test['confusion_matrix']}

'''+'\n'.join(table)+'''

การแบ่งข้อมูลยึด indices เดิม ไม่มีการย้าย test ไป train เลือก threshold บน 3-fold OOF ใน train และเลือกโมเดลจาก validation เท่านั้น ก่อนประเมินผู้ชนะบน test หนึ่งครั้งในรอบนี้ อย่างไรก็ตาม test นี้เคยใช้รายงานในรอบก่อน จึงเป็นผลสำรวจ ไม่ใช่ชุดทดสอบใหม่ที่ยังไม่เคยเห็น

ฟีเจอร์ทดลอง: products/squares ของเซนเซอร์, log1p, ratios และ Pump_ID แบบ one-hot ที่ fit เฉพาะ train ไม่มี timestamp จึงไม่สร้าง rolling หรือ lag จากลำดับแถว อัตราส่วนยังไม่ใช่ค่าทางฟิสิกส์ที่ยืนยันเพราะไม่ทราบหน่วยและจุดติดตั้งเซนเซอร์

ผลควบคุมสลับ label และสถิติสัญญาณแต่ละฟีเจอร์อยู่ใน report.json การทดสอบนี้ไม่พิสูจน์ว่า label เป็นข้อมูลสุ่ม แต่ช่วยตรวจว่าผลโมเดลต่างจากการเรียนรู้ label สุ่มมากน้อยเพียงใด

ถ้าไม่ถึง 80%: ตรวจวิธีสร้าง Maintenance_Flag กับเจ้าของชุดข้อมูลก่อน แล้วเก็บค่าจริงพร้อม timestamp, operating load และผลตรวจซ่อมที่ยืนยันได้ การสร้าง label ใหม่ตามกฎอุณหภูมิ/การสั่นจะเปลี่ยนโจทย์เป็นเลียนแบบกฎ ไม่ใช่เพิ่มความแม่นยำของโจทย์เดิม ไม่ควรนำมารวมเป็นผล 80% ของชุดนี้

candidate.joblib เป็น research artifact ใช้ SensorFeatures จาก experiments.py และต้องส่ง dataframe ที่มี Pump_ID กับเซนเซอร์ทั้ง 6 ตัว ไม่แทนที่ artifacts/model.joblib หรือเสียบเข้า pump.py replay โดยตรง
'''
    (out/'RESULTS.md').write_text(note,encoding='utf-8')
    print(json.dumps(dict(selected=best['name'],test=test,reaches_80pct=report['reaches_80pct']),indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv',default='data/Large_Industrial_Pump_Maintenance_Dataset.csv')
    parser.add_argument('--out',default='experiments')
    parser.add_argument('--permutations',type=int,default=5)
    args=parser.parse_args()
    with threadpool_limits(limits=2):
        from experiments import run as execute
        execute(args)
