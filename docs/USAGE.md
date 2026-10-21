# คู่มือใช้งาน

คำสั่งทั้งหมดรันจาก root ของ repository ตัวอย่าง Windows ใช้ `.venv\Scripts\python` ส่วน Pi/Linux ใช้ `.venv/bin/python` ไม่คัดลอก Windows virtual environment ไป Pi

## 1. เลือกชุดข้อมูลและติดตั้ง

ติดตั้ง Python 3.11/3.12, Git และใช้ Raspberry Pi OS 64-bit สำหรับ Pi สร้าง environment:

```bash
git clone https://github.com/67160366/pump-maintenance-offline.git
cd pump-maintenance-offline
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest -v
```

บน Windows ใช้ `py -3.12 -m venv .venv` และ `.venv\Scripts\python` แทน สคริปต์ `download_data.py` ต้องใช้อินเทอร์เน็ต ส่วน inference ไม่ต้องใช้

```bash
.venv/bin/python download_data.py ai4i
# ทางเลือก: ชุดปั๊มเดิม
.venv/bin/python download_data.py pump
```

helper ไม่เขียนทับ CSV ที่มีอยู่ ถ้า endpoint เข้าถึงไม่ได้ ให้ดาวน์โหลดจากแหล่งข้อมูลใน README แล้ววาง AI4I ที่ `data/ai4i/ai4i2020.csv` และปั๊มที่ `data/Large_Industrial_Pump_Maintenance_Dataset.csv` ระวังชื่อและตัวพิมพ์บน Linux

## 2. เทรน AI4I บนคอมพิวเตอร์

```bash
.venv/bin/python ai4i.py train
```

ผลอยู่ใน `ai4i-artifacts/RESULTS.md`, `audit.json`, `comparison.json` และโฟลเดอร์โมเดลสองแบบ:

- `ordered_primary/`: ผลหลัก แบ่งตามลำดับแถว 60/20/20
- `random_secondary/`: ผลรอง stratified random 60/20/20

แต่ละโฟลเดอร์มี `model.joblib`, `report.json`, `split_indices.json`, `parity_inputs.csv`, `parity_expected.json` ไม่สลับ bundle ระหว่าง `ai4i.py` และ `pump.py`

ไฟล์ CSV สำหรับ inference ต้องมี `Type`, `Air temperature [K]`, `Process temperature [K]`, `Rotational speed [rpm]`, `Torque [Nm]`, `Tool wear [min]` ชื่อต้องตรง Type เป็น L/M/H อุณหภูมิเป็น Kelvin ไม่ใช่ Celsius สลับลำดับคอลัมน์ได้ ค่าว่าง/ค่าผิดรูปแบบจะถูกปฏิเสธ ไม่ต้องใส่ target หรือ failure-mode labels

```bash
.venv/bin/python ai4i.py predict \
  --csv ai4i-artifacts/ordered_primary/parity_inputs.csv \
  --model ai4i-artifacts/ordered_primary/model.joblib \
  --limit 10
```

บน PowerShell เขียนคำสั่งเป็นบรรทัดเดียวแทน `\` แต่ละแถวส่งออก JSON ที่มี `status` (0/1), `score`, เวลา inference, ข้อความไทย และวิธีสร้างข้อความ ค่าเริ่มต้นใช้ template ไม่มี API key

## 3. เทรนและทดลองชุดปั๊มเดิม

```bash
.venv/bin/python pump.py train --csv data/Large_Industrial_Pump_Maintenance_Dataset.csv
.venv/bin/python pump.py verify
.venv/bin/python pump.py replay --csv artifacts/parity_inputs.csv --output benchmark-pc.json
```

ต้องมี `Pump_ID`, `Temperature`, `Vibration`, `Pressure`, `Flow_Rate`, `RPM`, `Operational_Hours` และ `Maintenance_Flag` เฉพาะตอน train หน่วยของชุดนี้ยังไม่ยืนยัน

train สร้าง `artifacts/` พร้อมรายงานข้อมูลและโมเดล โดย split 60/20/20 เลือก threshold/weight จาก validation และทำ Leave-One-Pump-Out หากมีหลายปั๊ม `--skip-lopo` ใช้เมื่อต้องการ smoke test เท่านั้น

ค่าว่างตอน train ใช้ imputer ที่ fit เฉพาะ train แต่ตอน replay แถวที่เซนเซอร์ไม่ครบจะแสดงสถานะประเมินไม่ได้ คอลัมน์จำเป็นหายทั้งคอลัมน์จะหยุดพร้อมแจ้ง error ไม่ทำนายต่อเงียบ ๆ

ทดลองเพิ่มฟีเจอร์/โมเดล 17 แบบหลัง train เสร็จ:

```bash
.venv/bin/python experiments.py --permutations 5
```

ผลอยู่ใน `experiments/RESULTS.md` และ `report.json` สคริปต์ตรวจ hash ของ CSV และยึด indices เดิม Test เคยใช้ในรอบก่อนจึงต้องตีความเป็น exploratory research ไม่ใช่ชุดทดสอบใหม่ `experiments/candidate.joblib` เป็น bundle งานวิจัย ไม่ใช้กับ `pump.py replay`

## 4. ย้ายไป Pi และเตรียมออฟไลน์

คัดลอก source และโฟลเดอร์ artifact ของโมเดลที่ต้องการไป Pi สร้าง venv ใหม่ด้วย Python รุ่นเดียวกับ PC และติดตั้ง dependency รุ่นเดียวกัน `requirements.txt` pin dependencies หลัก ส่วน `pip freeze > environment-local.txt` ใช้บันทึก environment ของแต่ละเครื่องเพิ่มเติม

ขณะ Pi ยังมีอินเทอร์เน็ต เตรียม wheels สำหรับ ARM64 บน Pi เอง:

```bash
.venv/bin/python -m pip download -r requirements.txt -d wheels
.venv/bin/python -m pip install --no-index --find-links wheels -r requirements.txt
```

อย่านำ Windows wheels มาใช้บน Pi หากติดตั้งไม่ได้ให้ตรวจ Python version และ ARM64 wheel ที่รองรับก่อน

### ใช้ LLM ในเครื่อง (ทางเลือก)

ติดตั้ง/build [llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md) และดาวน์โหลด [Qwen3-0.6B GGUF Q8_0](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF) เก็บเป็น `models/qwen3-0.6b-q8_0.gguf` จด llama.cpp version และ SHA-256 ของ GGUF เพื่อทำซ้ำ

```bash
.venv/bin/python ai4i.py predict \
  --csv ai4i-artifacts/ordered_primary/parity_inputs.csv \
  --llama-cli /absolute/path/llama-cli \
  --gguf models/qwen3-0.6b-q8_0.gguf \
  --limit 5
```

สำหรับชุดปั๊ม:

```bash
.venv/bin/python pump.py replay \
  --csv artifacts/parity_inputs.csv \
  --llama-cli /absolute/path/llama-cli \
  --gguf models/qwen3-0.6b-q8_0.gguf \
  --output benchmark-pi.json
```

LLM เลือกข้อความ A/B ผ่าน grammar โดยตัวเลขและสถานะมาจาก template ทุกครั้ง โหมดนี้ยังไม่ได้ทดสอบกับ GGUF จริง ถ้า llama.cpp รุ่นที่ใช้ไม่รองรับ flags หรือคืนข้อความผิดรูปแบบ จะ fallback ตรวจ `summary_method` เพื่อแยก `local_llm_validated` จาก template อย่าใช้การเห็นข้อความไทยเป็นหลักฐานว่า LLM ทำงานแล้ว

AI4I สรุปทุกแถวที่เลือก ส่วน pump replay สรุปครั้งแรกหรือเมื่อสถานะของแต่ละปั๊มเปลี่ยน เพิ่ม `--summary-every-row` ได้ใน pump replay

## 5. ตรวจผลบน Pi

1. ตัด Wi-Fi/LAN จริงและรัน inference ตรวจว่าไม่มีการดาวน์โหลดหรือเรียกบริการภายนอก
2. ชุดปั๊มใช้ `python pump.py verify` ตรวจคะแนนและสถานะเทียบ reference อัตโนมัติ
3. AI4I เทียบ `predict_proba` กับ `parity_expected.json` จาก PC โดย tolerance 1e-9 และเทียบ status ตาม threshold ใช้สคริปต์ตัวอย่างด้านล่าง
4. `pump.py replay` บันทึกเวลา inference/LLM, peak process-tree RSS, system memory used และอุณหภูมิถ้าอ่านได้ เป้าหมาย classifier <1 วินาที/แถว, summary <=30 วินาที, RAM ระบบ <6 GiB เป็นเกณฑ์ที่ต้องวัด ไม่ใช่ benchmark Pi ที่ยืนยันแล้ว
5. AI4I บันทึกเวลารายแถว แต่ยังไม่มีตัวเก็บ RAM/อุณหภูมิใน CLI นี้ ต้องวัดเพิ่มบน Pi `hardware_acceptance_verified` ของ pump replay เป็น false เสมอจนมีหลักฐานตรวจรับแยก
6. ตรวจ `vcgencmd get_throttled` และดูสัดส่วน fallback ของ LLM รวมทั้งความตรงของข้อความกับตัวเลขจริง

ตรวจ parity AI4I จาก root ของโปรเจกต์ (บันทึกเป็นสคริปต์หรือรันใน Python):

```python
import json
import joblib
import numpy as np
import ai4i
import pump

root = 'ai4i-artifacts/ordered_primary/'
bundle = joblib.load(root + 'model.joblib')
frame = ai4i.load(root + 'parity_inputs.csv')
with open(root + 'parity_expected.json', encoding='utf-8') as file:
    expected = json.load(file)
scores = pump.score(bundle['model'], frame[ai4i.INPUTS])
np.testing.assert_allclose(scores, expected['scores'], rtol=0, atol=1e-9)
np.testing.assert_array_equal(
    scores >= bundle['threshold'],
    np.array(expected['scores']) >= expected['threshold'],
)
print('PASS')
```

RSS ที่สุ่มวัดทุก 50 ms อาจพลาด peak สั้น ๆ และนับ shared pages ซ้ำได้ ส่วน RAM ระบบรวมโปรแกรมอื่นด้วย จึงควรบันทึกสภาพแวดล้อมการทดสอบประกอบ

## 6. ปัญหาที่พบบ่อย

- **FileNotFoundError:** ยังไม่ดาวน์โหลด CSV/เทรน หรือไม่ได้รันจาก root
- **Missing columns / Type must be L/M/H:** ตรวจชื่อคอลัมน์และ CSV ใช้ schema AI4I และ pump สลับกันไม่ได้
- **scikit-learn version mismatch:** ติดตั้งรุ่นที่ใช้ตอน train หรือ train ใหม่ ห้ามแก้ version metadata เพื่อฝืนโหลด
- **ไม่มี LLM หรือ timeout:** template ยังทำงานได้ ตรวจไฟล์ GGUF และ executable path และเวลารวมโหลดโมเดลซึ่งนับอยู่ใน timeout 30 วินาที
- **คะแนนปั๊มใกล้ 50%:** เป็นผลที่พบกับ label เดิม ไม่ควรแก้ด้วยการสร้าง Current จาก Maintenance_Flag
