# Pump Maintenance Offline

ระบบทดลอง Machine Learning สำหรับจำแนกสถานะเครื่องจักรและสรุปผลภาษาไทยแบบออฟไลน์ ออกแบบเพื่อนำไปทดสอบบน **Raspberry Pi 4 RAM 8 GB**

```text
CSV → ตรวจอินพุต → ML classifier → สถานะและคะแนน → สรุปภาษาไทย
                                                    ├─ Template (ค่าเริ่มต้น)
                                                    └─ LLM ในเครื่องผ่าน llama.cpp (ทางเลือก)
```

**สถานะ:** เทรนและทดสอบบนคอมพิวเตอร์แล้ว ยังไม่ได้ยืนยันประสิทธิภาพบน Pi, LLM GGUF จริง หรือปั๊มจริง โมเดลจำแนก snapshot ไม่ทำนายเวลาที่จะเสีย

## เริ่มจากอะไรดี

แนะนำเริ่ม **AI4I 2020** เพื่อทดลอง pipeline ที่มีสัญญาณให้เรียนรู้ จากนั้นค่อยศึกษาชุดปั๊มเดิมและการทดลองฟีเจอร์เพิ่มเติม

| ชุดข้อมูล / วิธีประเมิน | Accuracy | Balanced accuracy | Precision เครื่องเสีย | Recall เครื่องเสีย | F1 เครื่องเสีย |
|---|---:|---:|---:|---:|---:|
| AI4I แบ่งตามลำดับแถว — ผลหลัก | 99.25% | 85.80% | 87.50% | 71.79% | 78.87% |
| AI4I แบ่งสุ่ม — ผลรอง | 99.10% | 91.73% | 89.06% | 83.82% | 86.36% |
| ชุดปั๊มเดิม หลังทดลอง 17 แบบ | 50.10% | 50.12% | 49.93% | 54.89% | 52.29% |

AI4I มีเครื่องเสียเพียง 339/10,000 แถว การทายว่าไม่เสียทุกแถวก็ได้ accuracy สูงอยู่แล้ว ต้องอ่าน recall/F1 และ baseline ประกอบ ผลหลักยังไม่ถึง recall/F1 80% อ่าน [ผล AI4I](docs/AI4I_RESULTS.md) และ [ผลทดลองชุดปั๊ม](docs/PUMP_EXPERIMENTS.md)

## ติดตั้งบน Windows

ใช้ **Python 3.11 หรือ 3.12** โดย environment ที่ทดสอบจริงเป็น Python 3.12

```powershell
git clone https://github.com/67160366/pump-maintenance-offline.git
cd pump-maintenance-offline
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m unittest -v
```

หากไม่มี Python Launcher ให้ใช้ `python -m venv .venv` แทน ตรวจว่า Python เป็นรุ่นที่รองรับ

## ลอง AI4I ภายใน 3 ขั้นตอน

รันจาก root ของ repository:

```powershell
# 1. ดาวน์โหลด CSV จาก UCI (ต้องต่ออินเทอร์เน็ต)
.venv\Scripts\python download_data.py ai4i

# 2. เทรนบนคอมพิวเตอร์ พร้อมสร้างรายงานและโมเดล
.venv\Scripts\python ai4i.py train

# 3. ทำนายและแสดงสรุปภาษาไทยโดยไม่ใช้อินเทอร์เน็ต
.venv\Scripts\python ai4i.py predict --csv ai4i-artifacts/ordered_primary/parity_inputs.csv --limit 10
```

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

ทางเลือก LLM ใช้ **Qwen3-0.6B GGUF Q8_0 + llama.cpp** ผ่าน subprocess ในเครื่อง ไม่มีการเรียกบริการภายนอกหรือดาวน์โหลดใน `predict`/`replay` ดาวน์โหลดไฟล์และเตรียม runtime ไว้ล่วงหน้า

LLM รุ่นนี้เลือกข้อความที่ตรวจสอบได้ A/B ข้อเท็จจริงยังสร้างจาก template ใช้ `/no_think`, context 1024, output ไม่เกิน 128 tokens และ fallback เมื่อเกิน 30 วินาทีหรือคำตอบไม่ถูกต้อง จึงยังไม่ใช่แชตวิเคราะห์หรือวินิจฉัยสาเหตุอย่างอิสระ

## โครงสร้าง

| ไฟล์ | หน้าที่ |
|---|---|
| `ai4i.py` | เทรนและทำนาย AI4I พร้อมสรุปไทย |
| `pump.py` | เทรนชุดปั๊ม ตรวจ parity และ replay CSV พร้อมวัดทรัพยากร |
| `experiments.py` | เปรียบเทียบฟีเจอร์/โมเดลชุดปั๊ม 17 แบบ พร้อม shuffled-label controls |
| `download_data.py` | ดาวน์โหลดข้อมูลต้นฉบับจาก UCI/Kaggle ตามคำสั่งผู้ใช้ |
| `test_*.py` | ทดสอบการตรวจข้อมูล ฟีเจอร์ ข้อมูลรั่ว parity และ LLM fallback |
| `docs/` | วิธีใช้งาน ผลทดลอง และรายงานตรวจ target leakage |

ข้อมูล, โมเดล, GGUF, virtual environment และไฟล์ ZIP ไม่รวมใน Git ให้ดาวน์โหลดและเทรนตามขั้นตอน

## ข้อจำกัดและความถูกต้องของผล

- AI4I เป็นข้อมูลสังเคราะห์ของกระบวนการผลิต ไม่ใช่ข้อมูลปั๊มน้ำจริง ผลไม่ยืนยันว่าจะย้ายไปใช้กับปั๊มได้
- คะแนน `predict_proba` ยังไม่ผ่าน probability calibration จึงไม่ใช่โอกาสเสียจริงที่ยืนยันแล้ว
- การใช้ Maintenance_Flag สร้าง Current จะทำให้คำตอบรั่วเข้าอินพุต แม้แยก train/test แล้ว อ่าน [รายงานตรวจสอบ](docs/TARGET_LEAKAGE_REVIEW.md)
- ยังไม่ยืนยัน latency, RAM หรือคุณภาพภาษาไทยของ GGUF บน Pi ต้องวัดบนเครื่องเป้าหมาย
- โหลด `.joblib` เฉพาะไฟล์ที่เชื่อถือได้ เพราะใช้การ deserialize แบบ pickle

## แหล่งข้อมูล

- [AI4I 2020 — UCI](https://archive.ics.uci.edu/dataset/601/ai4i%2B2020%2Bpredictive%2Bmaintenance%2Bdataset): CC BY 4.0. Credit: AI4I 2020 Predictive Maintenance Dataset, UCI Machine Learning Repository, DOI [10.24432/C5HS5C](https://doi.org/10.24432/C5HS5C).
- [Large Industrial Pump Maintenance Dataset — Kaggle](https://www.kaggle.com/datasets/selonamaris/large-industrial-pump-maintenance-dataset): ตรวจเงื่อนไขปัจจุบันกับผู้จัดทำก่อนเผยแพร่ข้อมูลซ้ำ
- [llama.cpp](https://github.com/ggml-org/llama.cpp) และ [Qwen3-0.6B GGUF](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF): ใช้ตามเงื่อนไขของแต่ละโครงการ
