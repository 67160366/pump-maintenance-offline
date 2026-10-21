"""AI4I experiment: original labels, no failure-mode leakage, local inference."""
import argparse
import hashlib
import json
import pickle
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import pump

SENSORS=['Air temperature [K]','Process temperature [K]','Rotational speed [rpm]','Torque [Nm]','Tool wear [min]']
INPUTS=['Type']+SENSORS
TARGET='Machine failure'
MODES=['TWF','HDF','PWF','OSF','RNF']
SOURCE='https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset'


def load(path, training=False):
    df=pd.read_csv(path)
    missing=set(INPUTS+([TARGET] if training else []))-set(df.columns)
    if missing: raise ValueError('Missing columns: '+', '.join(sorted(missing)))
    if not df.Type.isin(['L','M','H']).all(): raise ValueError('Type must be L/M/H')
    for c in SENSORS: df[c]=pd.to_numeric(df[c],errors='raise')
    if not np.isfinite(df[SENSORS].to_numpy()).all(): raise ValueError('Sensor values must be finite and complete')
    if (df[SENSORS]<0).any().any(): raise ValueError('Sensor values cannot be negative')
    if training and (df[TARGET].isna().any() or set(df[TARGET].unique())!={0,1}):
        raise ValueError('Machine failure must have both binary classes')
    return df


class AI4IFeatures(BaseEstimator, TransformerMixin):
    def __init__(self, physics=False): self.physics=physics
    def fit(self,X,y=None): return self
    def transform(self,X):
        raw=X[SENSORS].to_numpy(dtype=float)
        onehot=np.column_stack([(X.Type.to_numpy()==c).astype(float) for c in ['L','M','H']])
        blocks=[raw,onehot]
        if self.physics:
            air,process,rpm,torque,wear=raw.T
            blocks.append(np.column_stack([process-air,torque*rpm*(2*np.pi/60),wear*torque]))
        return np.column_stack(blocks)


def candidates():
    yield 'dummy_majority',make_pipeline(AI4IFeatures(),DummyClassifier(strategy='most_frequent'))
    for physics in [False,True]:
        tag='physics' if physics else 'raw'
        for weight in [None,'balanced']:
            suffix='default' if weight is None else weight
            yield f'logistic_{tag}_{suffix}',make_pipeline(AI4IFeatures(physics),StandardScaler(),
                LogisticRegression(solver='liblinear',class_weight=weight,max_iter=2000,random_state=42))
        for depth in [8,12]:
            yield f'forest_{tag}_{depth}',make_pipeline(AI4IFeatures(physics),
                RandomForestClassifier(n_estimators=100,max_depth=depth,min_samples_leaf=2,
                    class_weight='balanced',n_jobs=2,random_state=42))
        for leaves in [7,15]:
            yield f'histgb_{tag}_{leaves}',make_pipeline(AI4IFeatures(physics),
                HistGradientBoostingClassifier(max_iter=150,max_leaf_nodes=leaves,l2_regularization=1,
                    early_stopping=False,learning_rate=0.05,random_state=42))


def measure(y,s,t):
    r=pump.metrics(y,s,t)
    r.update(accuracy=float(accuracy_score(y,s>=t)),balanced_accuracy=float(balanced_accuracy_score(y,s>=t)),
             roc_auc=float(roc_auc_score(y,s)))
    return r


def threshold(y,s):
    choices=np.unique(np.r_[np.linspace(.01,.8,80),.9,.95,.99])
    return float(max(choices,key=lambda t:(measure(y,s,t)['f1'],-abs(t-.5))))


def experiment(df,indices,name,out):
    tr,va,te=[df.loc[indices[k]] for k in ['train','validation','test']]
    rows=[]
    fitted={}
    for model_name,model in candidates():
        start=time.perf_counter()
        model.fit(tr[INPUTS],tr[TARGET])
        s=pump.score(model,va[INPUTS])
        t=.5 if model_name.startswith('dummy') else threshold(va[TARGET],s)
        rows.append(dict(name=model_name,threshold=t,validation=measure(va[TARGET],s,t),
                         bytes=len(pickle.dumps(model,protocol=5)),train_seconds=time.perf_counter()-start))
        fitted[model_name]=model
        print(name,model_name,'val F1',round(rows[-1]['validation']['f1'],4),flush=True)
    eligible=[r for r in rows if not r['name'].startswith('dummy')]
    best_f1=max(r['validation']['f1'] for r in eligible)
    chosen=min([r for r in eligible if r['validation']['f1']>=best_f1-.01],key=lambda r:(r['bytes'],r['name']))
    model=fitted[chosen['name']]
    start=time.perf_counter()
    scores=pump.score(model,te[INPUTS])
    batch_seconds=time.perf_counter()-start
    test=measure(te[TARGET],scores,chosen['threshold'])
    dummy=measure(te[TARGET],pump.score(fitted['dummy_majority'],te[INPUTS]),.5)
    per_failure={}
    pred=scores>=chosen['threshold']
    for col in MODES:
        if col in te:
            mask=te[col].to_numpy()==1
            per_failure[col]=dict(rows=int(mask.sum()),alert_rate=float(pred[mask].mean()) if mask.any() else None)
    sizes={k:dict(rows=len(ix),failures=int(df.loc[ix,TARGET].sum())) for k,ix in indices.items()}
    report=dict(split=name,sizes=sizes,candidates=rows,selected=chosen['name'],threshold=chosen['threshold'],
                test=test,dummy_test=dummy,per_failure_alert_rate=per_failure,
                meets_accuracy_80=test['accuracy']>=.8,meets_balanced_accuracy_80=test['balanced_accuracy']>=.8,
                meets_f1_80=test['f1']>=.8,batch_inference_seconds=batch_seconds,hardware='PC, not Pi',
                source=SOURCE,excluded_features=['UDI','UID','Product ID']+MODES)
    dest=out/name;dest.mkdir(parents=True,exist_ok=True)
    bundle=dict(model=model,threshold=chosen['threshold'],inputs=INPUTS,report=report,
                sklearn_version=__import__('sklearn').__version__)
    joblib.dump(bundle,dest/'model.joblib',compress=3)
    pump.save_json(dest/'report.json',report)
    pump.save_json(dest/'split_indices.json',indices)
    te[INPUTS].head(20).to_csv(dest/'parity_inputs.csv',index=False)
    pump.save_json(dest/'parity_expected.json',dict(scores=pump.score(model,te[INPUTS].head(20)).tolist(),threshold=chosen['threshold']))
    return report


def train(args):
    df=load(args.csv,True)
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    if 'UDI' in df and not df.UDI.is_monotonic_increasing:
        raise ValueError('Expected original UDI order for ordered split')
    if 'UID' in df and not df.UID.is_monotonic_increasing:
        raise ValueError('Expected original UID order for ordered split')
    n=len(df);a=int(n*.6);b=int(n*.8)
    ordered=dict(train=list(range(a)),validation=list(range(a,b)),test=list(range(b,n)))
    tr,rest=train_test_split(df.index,test_size=.4,stratify=df[TARGET],random_state=42)
    va,te=train_test_split(rest,test_size=.5,stratify=df.loc[rest,TARGET],random_state=42)
    random=dict(train=tr.tolist(),validation=va.tolist(),test=te.tolist())
    # Models are selected independently in each protocol, before its test is read.
    reports=[experiment(df,ordered,'ordered_primary',out),experiment(df,random,'random_secondary',out)]
    audit=dict(rows=len(df),columns=df.columns.tolist(),missing=df.isna().sum().to_dict(),
               target_counts={str(k):int(v) for k,v in df[TARGET].value_counts().items()},
               input_duplicates=int(df.duplicated(INPUTS).sum()),
               source=SOURCE,license='CC BY 4.0',sha256=hashlib.sha256(Path(args.csv).read_bytes()).hexdigest(),
               note='Ordered split uses source row order, not actual timestamps or independent machine identities.')
    pump.save_json(out/'audit.json',audit)
    pump.save_json(out/'comparison.json',reports)
    lines=['# ผลทดลอง AI4I 2020','',f'ข้อมูล {len(df):,} แถว label เดิม: {audit["target_counts"]}',
           '', '| Split | Model | Accuracy | Baseline accuracy | Balanced accuracy | Precision | Recall | F1 | PR-AUC |',
           '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in reports:
        t=r['test']
        lines.append(f'| {r["split"]} | {r["selected"]} | {t["accuracy"]:.2%} | {r["dummy_test"]["accuracy"]:.2%} | {t["balanced_accuracy"]:.2%} | {t["precision"]:.2%} | {t["recall"]:.2%} | {t["f1"]:.4f} | {t["pr_auc"]:.4f} |')
    lines+=['','เลือกโมเดลและ threshold จาก validation โดย maximize F1 ของเครื่องเสีย แล้วเลือกขนาดเล็กที่สุดที่ F1 ห่างตัวดีที่สุดไม่เกิน 0.01 ไม่ใช้ test เลือกโมเดล',
            '', 'Primary: แบ่งตามลำดับแถวเดิม 60/20/20 เพื่อแยกส่วนกระบวนการที่ใกล้กัน ไม่ถือว่าเป็น timestamp จริง Secondary: stratified random 60/20/20 แยกรายงาน ไม่เลือก split ที่ให้คะแนนสูงกว่า',
            '', 'อินพุต: Type และเซนเซอร์ 5 ตัว ฟีเจอร์เสริมคือส่วนต่างอุณหภูมิ กำลัง torque*rpm*2pi/60 และ wear*torque ไม่ใช้ ID หรือ TWF/HDF/PWF/OSF/RNF เป็นอินพุต ไม่เปลี่ยน target',
            '', 'เป็นข้อมูลสังเคราะห์ของกระบวนการผลิต ไม่ใช่ข้อมูลปั๊มจริงหรือ remaining useful life คะแนนไม่ยืนยันผลกับเครื่องจริง ต้องทดสอบ Pi และ LLM จริงแยกต่างหาก',
            '', 'Source: '+SOURCE, 'License: CC BY 4.0. Credit: AI4I 2020 Predictive Maintenance Dataset, UCI Machine Learning Repository, DOI 10.24432/C5HS5C.']
    (out/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps([dict(split=r['split'],selected=r['selected'],test=r['test']) for r in reports],indent=2))


def predict(args):
    bundle=joblib.load(args.model)
    if bundle['sklearn_version']!=__import__('sklearn').__version__: raise ValueError('scikit-learn version mismatch')
    df=load(args.csv)
    for _,row in df.head(args.limit).iterrows():
        start=time.perf_counter()
        s=float(pump.score(bundle['model'],row[INPUTS].to_frame().T)[0])
        state=int(s>=bundle['threshold'])
        elapsed=time.perf_counter()-start
        text=('สถานะ: '+('ควรตรวจบำรุงรักษา' if state else 'ยังไม่พบสัญญาณเครื่องเสียจากโมเดล')+
              f'\nคะแนนโมเดล: {s:.4f} (ยังไม่ใช่โอกาสเสียที่ผ่าน calibration)'+
              '\nค่าที่วัด: '+', '.join(f'{c}={row[c]}' for c in INPUTS)+
              '\nเป็นผลจากข้อมูลสังเคราะห์ AI4I ไม่ระบุสาเหตุยืนยันหรือเวลาที่จะเสีย')
        summary,method,seconds=pump.summarize(args,text)
        print(json.dumps(dict(status=state,score=s,inference_seconds=elapsed,summary=summary,
                              summary_method=method,llm_seconds=seconds),ensure_ascii=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('train');p.add_argument('--csv',default='data/ai4i/ai4i2020.csv');p.add_argument('--out',default='ai4i-artifacts');p.set_defaults(func=train)
    p=sub.add_parser('predict');p.add_argument('--csv',required=True);p.add_argument('--model',default='ai4i-artifacts/ordered_primary/model.joblib');p.add_argument('--limit',type=int,default=10);p.add_argument('--llama-cli');p.add_argument('--gguf');p.set_defaults(func=predict)
    args=parser.parse_args()
    with threadpool_limits(limits=2):
        args.func(args)

if __name__=='__main__':
    from ai4i import main as execute
    execute()
