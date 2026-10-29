# Pump Maintenance Offline

ระบบทดลอง Machine Learning สำหรับจำแนกสถานะเครื่องจักรและสรุปผลภาษาไทยแบบออฟไลน์ ออกแบบเพื่อนำไปทดสอบบน **Raspberry Pi 4 RAM 8 GB**

```text
CSV → ตรวจอินพุต → ML classifier → สถานะและคะแนน → สรุปภาษาไทย
                                                    ├─ Template (ค่าเริ่มต้น)
                                                    └─ LLM ในเครื่องผ่าน llama.cpp (ทางเลือก)
```

**สถานะ:** โมเดลและ dashboard ผ่านการทดสอบ PC และ Linux ARM64 จำลองแล้ว มีรายงานการทดลองโมเดลบน Pi จากรอบก่อน แต่ยังไม่ผ่านการตรวจรับ Pi แบบถอดเครือข่ายหรือปั๊มจริง โมเดลจำแนก snapshot ไม่ทำนายเวลาที่จะเสีย

เริ่มที่ [ศูนย์รวมเอกสาร](docs/README.md) และ [คู่มือ clone ลง Pi / จำลอง ARM64](docs/PI_READY.md)
คำสั่งติดตั้งหลักเมื่อมี Python 3.12 บน Pi แล้วคือ `python3.12 setup_pi.py`
จากนั้น `.venv/bin/python start_pi.py` ใช้ template ได้ทันทีโดยไม่ต้องมี LLM

## Clone ลง Pi แล้วเปิดใช้ — ไม่ต้องเทรน

ชุดส่งต่อนี้อยู่บน branch **`codex/pi-ready-environment`** ให้ clone branch นี้โดยตรง
เพื่อให้ได้ installer และหน้าเว็บล่าสุด (ไม่ต้อง merge ก่อนนำไปลอง)
ต้องใช้ Raspberry Pi OS **64-bit / ARM64**, Python **3.12** และ Git
บน Pi ไม่ต้องติดตั้ง Docker, Node.js หรือ npm

```bash
git clone --branch codex/pi-ready-environment --single-branch https://github.com/67160366/pump-maintenance-offline.git
cd pump-maintenance-offline
python3.12 verify_checkout.py
python3.12 setup_pi.py
.venv/bin/python deploy/smoke.py
.venv/bin/python start_pi.py
```

เปิด browser บน Pi ที่ **http://127.0.0.1:8080** กด “ดูรายการถัดไป” หรือ “ดูอัตโนมัติ”
มีข้อมูลตัวอย่าง 12 รายการและโมเดลที่เทรนแล้วพร้อมใช้ คำถามใช้ข้อมูลในเครื่องพร้อม
บันทึกอ้างอิงเป็นค่าเริ่มต้น จึงใช้งานได้โดยไม่ต้องมี LLM

**โมเดล ML อยู่ใน Git เป็นไฟล์จริง ไม่ใช่ลิงก์ให้ไปเทรนเอง:**

| ไฟล์ | บทบาท |
| --- | --- |
| `runtime/model.joblib` | โมเดลหลักที่ dashboard โหลดอัตโนมัติ ขนาด 484,534 bytes |
| `ai4i-artifacts/ordered_primary/model.joblib` | ต้นฉบับโมเดลหลัก พร้อมรายงานและ parity |
| `ai4i-artifacts/random_secondary/model.joblib` | โมเดลเปรียบเทียบชุดรอง |
| `artifacts/model.joblib` | โมเดลชุดปั๊มเดิม ใช้สาธิตข้อจำกัด |
| `experiments/candidate.joblib` | โมเดลจากการทดลอง ไม่ใช้แทนโมเดลหลัก |

ยังมี `runtime/demo.csv`, threshold, parity, checksums, ข้อมูลสาธารณะและ ARM64 wheels
ครบ 11 packages `verify_checkout.py` ตรวจ bytes/hash ของโมเดลทั้ง 5 ไฟล์ ข้อมูล และ
wheels ด้วย Python มาตรฐานก่อนติดตั้ง `setup_pi.py` ตรวจซ้ำก่อนสร้าง environment
แล้วติดตั้งจาก wheels ใน repo ด้วย `--no-index` และตรวจโหลดโมเดล/ผล parity จริง

ถ้าแจ้งว่าโมเดลหาย ให้หยุดและตรวจ branch/clone ไม่ต้องสั่ง train และห้ามแก้ threshold
หรือ metadata ให้ผ่าน หากไม่มี Python 3.12 ให้เตรียมตาม [คู่มือ Pi](docs/PI_HANDOFF.md)
ขณะยังออนไลน์ก่อน การ clone ต้องใช้อินเทอร์เน็ต; เดโมหลักหลังติดตั้งแล้วไม่ใช้

**LLM เป็นอีกส่วนหนึ่ง:** GGUF และ llama.cpp ไม่รวมใน Git ตามขอบเขตโปรเจกต์
ถ้าจะเปิดตัวเลือกนี้ ให้เตรียมขณะออนไลน์ด้วย `bash deploy/provision-llm.sh`
สคริปต์มีรุ่น/hash ของ Qwen2.5 0.5B ที่แน่นอนและ reuse ไฟล์เดิมได้ ไม่มีการเทรน LLM
ผล LLM บน Pi จริงยังต้องตรวจแยก รายละเอียดอยู่ใน [PI_READY](docs/PI_READY.md)

## นำไปเดโมบน Pi 4 / agent เริ่มตรงนี้

มีหน้า dashboard ออฟไลน์แล้ว: อ่าน CSV ทีละแถว/เล่นอัตโนมัติ แสดงเซนเซอร์ ผลโมเดล
ตัวกลาง Python, สรุปไทย, สถานะ LLM/fallback, ประวัติ และทรัพยากรเครื่อง
หน้าเว็บเรียกโมเดลจริงผ่าน `bridge.py` ไม่ต้องมี Node.js หรือบริการ cloud

**หน้าจอ Pi 800×480:** แบ่งภาพรวม / ประวัติ / ถามข้อมูล กดรายการเพื่อดูรายละเอียด
บันทึกผลลง SQLite ในเครื่อง และถามสรุป/รายการเตือน/อุณหภูมิสูงสุดพร้อมหลักฐานได้
ดู [แบบหน้าจอและการใช้ LLM กับข้อมูล](docs/PI_SCREEN_DESIGN.md)
บน PC เปิด `/preview` เพื่อทดลองหน้าจอจริงขนาด 800×480 ส่วนบน Pi เปิด `/` เต็มจอ

- **Agent:** อ่าน [AGENTS.md](AGENTS.md) และ [สถานะ/งานถัดไป](docs/PROJECT_STATUS.md)
- **ย้ายไป Pi:** [ขั้นตอน PC → ZIP → Pi → offline acceptance](docs/PI_HANDOFF.md)
- **นำเสนอ:** [บทเดโม 5–7 นาที](docs/DEMO_RUNBOOK.md)
- **ตัวกลาง/หน้าระบบ:** [สถาปัตยกรรมและ API](docs/ARCHITECTURE.md)

**Clone แล้วมีโมเดลและข้อมูลเดโมพร้อมใช้** ไม่ต้องเทรนใหม่ โดยค่าเริ่มต้นใช้ `runtime/`
มีโมเดล AI4I primary/secondary, โมเดลปั๊มเดิม, research candidate, ข้อมูลต้นฉบับพร้อม
ที่มา และ wheels Linux ARM64/Python 3.12 อยู่ใน Git แล้ว ดู [รายการไฟล์](docs/GIT_CONTENTS.md)

บน Pi ที่มี Python 3.12 แล้ว:

```bash
git clone --branch codex/pi-ready-environment --single-branch https://github.com/67160366/pump-maintenance-offline.git
cd pump-maintenance-offline
python3.12 setup_pi.py
.venv/bin/python start_pi.py
```

เปิด `http://127.0.0.1:8080` หาก Pi ยังไม่มี Python 3.12 ดู [วิธีเตรียม Python](docs/PI_HANDOFF.md)
Windows ใช้ `.venv\Scripts\python -m pip install -r requirements-pi.txt` จาก PyPI
เพราะ wheels ที่แนบเป็น Linux ARM64 เท่านั้น

ทางเลือกสร้าง ZIP สำหรับ USB transfer:

```powershell
.venv\Scripts\python prepare_pi.py --out pi-release
.venv\Scripts\python pi_check.py --release pi-release
.venv\Scripts\python dashboard.py --release pi-release
```

เปิด `http://127.0.0.1:8080` และส่ง `pi-release.zip` พร้อม SHA-256 ไป Pi
ZIP ไม่รวม GGUF, llama.cpp หรือ Python environment; ARM64 wheels ใส่เพิ่มด้วย `--wheels-dir` ได้

## เริ่มจากอะไรดี

แนะนำเริ่ม **AI4I 2020** เพื่อทดลอง pipeline ที่มีสัญญาณให้เรียนรู้ จากนั้นค่อยศึกษาชุดปั๊มเดิมและการทดลองฟีเจอร์เพิ่มเติม

| ชุดข้อมูล / วิธีประเมิน | Accuracy | Balanced accuracy | Precision เครื่องเสีย | Recall เครื่องเสีย | F1 เครื่องเสีย |
|---|---:|---:|---:|---:|---:|
| AI4I แบ่งตามลำดับแถว — ผลหลัก | 99.25% | 85.80% | 87.50% | 71.79% | 78.87% |
| AI4I แบ่งสุ่ม — ผลรอง | 99.10% | 91.73% | 89.06% | 83.82% | 86.36% |
| ชุดปั๊มเดิม หลังทดลอง 17 แบบ | 50.10% | 50.12% | 49.93% | 54.89% | 52.29% |

AI4I มีเครื่องเสียเพียง 339/10,000 แถว การทายว่าไม่เสียทุกแถวก็ได้ accuracy สูงอยู่แล้ว ต้องอ่าน recall/F1 และ baseline ประกอบ ผลหลักยังไม่ถึง recall/F1 80% อ่าน [ผล AI4I](docs/AI4I_RESULTS.md) และ [ผลทดลองชุดปั๊ม](docs/PUMP_EXPERIMENTS.md)

## ติดตั้งบน Windows

ใช้ **Python 3.12** ให้ตรง runtime ที่แนบมา โดย environment ที่ทดสอบจริงเป็น Python 3.12

```powershell
git clone --branch codex/pi-ready-environment --single-branch https://github.com/67160366/pump-maintenance-offline.git
cd pump-maintenance-offline
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-pi.txt
.venv\Scripts\python -m unittest -v
```

หากไม่มี Python Launcher ให้ใช้ `python -m venv .venv` แทน ตรวจว่า Python เป็นรุ่นที่รองรับ

## ลอง AI4I ด้วยโมเดลที่แนบมา

รันจาก root ของ repository:

```powershell
# ทำนายและแสดงสรุปภาษาไทยโดยไม่ใช้อินเทอร์เน็ต
.venv\Scripts\python ai4i.py predict --csv ai4i-artifacts/ordered_primary/parity_inputs.csv --limit 10
```

ข้อมูลและโมเดลมีแล้ว หากต้องการเทรนใหม่ ใช้ `ai4i.py train --out ai4i-retrained`
แยกจาก bundle ที่แนบมา อย่าเขียนทับโมเดล deployment จนกว่าจะตรวจ parity/manifest ใหม่

ผลลัพธ์อยู่ใน `ai4i-artifacts/` แยก `ordered_primary/` และ `random_secondary/` แต่ละชุดมี `model.joblib`, `report.json`, indices และข้อมูลสำหรับตรวจผลซ้ำ ใช้ผลหลักเป็นค่าเริ่มต้น ไม่เลือก split ที่คะแนนสูงกว่ามาแทนผลหลัก

อ่านคำสั่งทั้งหมดและวิธีใช้งาน Pi ใน **[คู่มือใช้งาน](docs/USAGE.md)**

## โมเดลเรียนรู้จากอะไร

- **AI4I:** Type, อุณหภูมิอากาศ/กระบวนการ (K), RPM, Torque (Nm), Tool wear (min)
- **ฟีเจอร์เสริม AI4I:** ส่วนต่างอุณหภูมิ, `Torque × RPM × 2π/60`, `Tool wear × Torque`
- ไม่ใช้ UDI, Product ID หรือคอลัมน์สาเหตุเสีย TWF/HDF/PWF/OSF/RNF เป็นอินพุต
- เปรียบเทียบ Dummy, Logistic Regression, Random Forest และ HistGradientBoosting เลือก threshold จาก validation โดย F1 และเลือกโมเดลเล็กที่สุดที่ F1 ห่างตัวดีที่สุดไม่เกิน 0.01
- แบ่งตามลำดับแถว 60/20/20 เป็นผลหลัก และ stratified random 60/20/20 เป็นผลรอง ลำดับแถวไม่ใช่ timestamp จริงหรือหลักฐานว่าเป็นคนละเครื่อง
- ชุดปั๊มเดิมใช้เซนเซอร์ 6 ตัว ไม่ใช้ Maintenance_Flag สร้างฟีเจอร์ การทดลองเดิมยังไม่ชนะ baseline อย่างน่าเชื่อถือ

## LLM ออฟไลน์

ใช้ได้โดยไม่ต้องมี LLM: โปรแกรมแสดงสถานะ ตัวเลข และข้อความไทยจาก template โดยตรง

ชุดเตรียม Pi ปัจจุบันเลือก **Qwen2.5-0.5B-Instruct GGUF Q4_K_M + llama.cpp** ให้ตรงกับโมเดลเดิมบน Pi มี commit/revision/hash ใน `deploy/pi-lock.json` เตรียมด้วย `bash deploy/provision-llm.sh` ขณะออนไลน์ แล้วเปิดด้วย `.venv/bin/python start_pi.py --llm` ดูผลทดสอบและข้อจำกัดใน [PI_READY](docs/PI_READY.md)

LLM เลือกข้อความที่ตรวจสอบได้ A/B ข้อเท็จจริงยังสร้างจาก template ใช้ context 1024, output ไม่เกิน 128 tokens และ fallback เมื่อเกิน 30 วินาทีหรือคำตอบไม่ถูกต้อง adapter สำหรับ Qwen2.5 ใช้ explicit ChatML และตัด `/no_think` ที่ไม่ใช่คำสั่งของรุ่นนี้ จึงยังไม่ใช่แชตวิเคราะห์หรือวินิจฉัยสาเหตุอย่างอิสระ

## โครงสร้าง

| ไฟล์ | หน้าที่ |
|---|---|
| `ai4i.py` | เทรนและทำนาย AI4I พร้อมสรุปไทย |
| `pump.py` | เทรนชุดปั๊ม ตรวจ parity และ replay CSV พร้อมวัดทรัพยากร |
| `experiments.py` | เปรียบเทียบฟีเจอร์/โมเดลชุดปั๊ม 17 แบบ พร้อม shuffled-label controls |
| `download_data.py` | ดาวน์โหลดข้อมูลต้นฉบับจาก UCI/Kaggle ตามคำสั่งผู้ใช้ |
| `bridge.py` | ตัวกลาง schema → ML → facts → guarded summary |
| `dashboard.py`, `web/` | หน้าเดโมออฟไลน์และ replay API |
| `prepare_pi.py`, `pi_check.py` | แพ็กย้ายเครื่อง ตรวจ parity/runtime และ benchmark |
| `test_*.py` | ทดสอบการตรวจข้อมูล ฟีเจอร์ ข้อมูลรั่ว parity และ LLM fallback |
| `docs/` | วิธีใช้งาน ผลทดลอง และรายงานตรวจ target leakage |

ข้อมูลสาธารณะ โมเดลที่อนุมัติ และ ARM64 wheels รวมใน Git แล้ว ส่วน GGUF, llama.cpp,
virtual environment, credentials, log และ ZIP ที่สร้างซ้ำได้ยังถูก ignore ดู [รายละเอียด](docs/GIT_CONTENTS.md)

## ข้อจำกัดและความถูกต้องของผล

- AI4I เป็นข้อมูลสังเคราะห์ของกระบวนการผลิต ไม่ใช่ข้อมูลปั๊มน้ำจริง ผลไม่ยืนยันว่าจะย้ายไปใช้กับปั๊มได้
- คะแนน `predict_proba` ยังไม่ผ่าน probability calibration จึงไม่ใช่โอกาสเสียจริงที่ยืนยันแล้ว
- การใช้ Maintenance_Flag สร้าง Current จะทำให้คำตอบรั่วเข้าอินพุต แม้แยก train/test แล้ว อ่าน [รายงานตรวจสอบ](docs/TARGET_LEAKAGE_REVIEW.md)
- ยังไม่ยืนยัน latency, RAM หรือคุณภาพภาษาไทยของ GGUF บน Pi ต้องวัดบนเครื่องเป้าหมาย
- โหลด `.joblib` เฉพาะไฟล์ที่เชื่อถือได้ เพราะใช้การ deserialize แบบ pickle

## แหล่งข้อมูล

- [AI4I 2020 — UCI](https://archive.ics.uci.edu/dataset/601/ai4i%2B2020%2Bpredictive%2Bmaintenance%2Bdataset): CC BY 4.0. Credit: AI4I 2020 Predictive Maintenance Dataset, UCI Machine Learning Repository, DOI [10.24432/C5HS5C](https://doi.org/10.24432/C5HS5C).
- [Large Industrial Pump Maintenance Dataset — Kaggle](https://www.kaggle.com/datasets/selonamaris/large-industrial-pump-maintenance-dataset): ตรวจเงื่อนไขปัจจุบันกับผู้จัดทำก่อนเผยแพร่ข้อมูลซ้ำ
- [llama.cpp](https://github.com/ggml-org/llama.cpp) และ [Qwen2.5-0.5B-Instruct GGUF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF): ใช้ตามเงื่อนไขของแต่ละโครงการ
