# สิ่งที่ clone แล้วได้ทันที

ชุดส่งต่อใช้ branch `codex/pi-ready-environment` ตามคำขอให้เผยแพร่ไฟล์ที่มีอยู่ครบสำหรับนำไปใช้บน Pi
`.gitignore` เดิมกัน models/data/artifacts/wheels ทั้งหมด ตอนนี้เปิดเฉพาะรายการที่ใช้จริง

| ใน Git | หน้าที่ |
| --- | --- |
| `runtime/` | โมเดล AI4I primary พร้อม 12 demo snapshots, parity 20 แถว, report, provenance, requirements, manifest |
| `requirements-pi.txt` | dependency 11 packages ตรง PC/Python 3.12 |
| `wheels/pi4-cp312/*.whl` | Linux aarch64 / CPython 3.12 หรือ universal wheels; ติดตั้ง packages แบบ offline ได้ |
| `ai4i-artifacts/ordered_primary/` | โมเดลหลัก, threshold, รายงาน, indices และ parity |
| `ai4i-artifacts/random_secondary/` | โมเดลผลรอง พร้อมรายงานและ parity; ไม่ใช้แทนผลหลัก |
| `artifacts/` | โมเดลปั๊มเดิมและ reference; ใช้สาธิตเท่านั้น |
| `experiments/` | research candidate และผลเปรียบเทียบ ไม่ใช้แทน deployment bundle |
| `data/ai4i/ai4i2020.csv` | AI4I ต้นฉบับ CC BY 4.0 |
| `data/Large_Industrial_Pump_Maintenance_Dataset.csv` | ข้อมูลปั๊มสาธารณะ MIT พร้อมที่มา/notice |
| source, tests, `web/`, `deploy/`, `docs/` | ตัวกลาง, dashboard, service template, วิธีใช้งานและภาพ PC |

## สิ่งที่ยัง ignore และเหตุผล

- `.venv/`, `__pycache__/`: ต้องสร้าง environment ให้ตรง OS/CPU เป้าหมาย
- `.env*`, `*.pem`, `*.key`: credentials ของเครื่อง ไม่ใช่ส่วนหนึ่งของเดโม
- `models/`, `local/`, `*.gguf`, `*.pkl`: GGUF/llama.cpp เป็น provisioning ทางเลือกตาม
  `deploy/pi-lock.json` ไม่จำเป็นสำหรับเดโมหลัก; `.pkl` จากงานภายนอกไม่ได้ใช้กับระบบนี้
- `*.zip`, `pi-release*/`: archive สร้างซ้ำจากโค้ด/โมเดลที่ติด Git ได้
  ZIP งานภายนอกที่ตรวจ target leakage ไม่ใช่ dependency ของระบบ
- `reviews/`, `evidence/`, logs, JSONL, benchmark output: งานชั่วคราวและผลเฉพาะเครื่อง
  ผลทดสอบที่ต้องการเผยแพร่ให้สรุปลง `docs/PROJECT_STATUS.md`
- ไฟล์ข้อมูลอื่นและโมเดลใหม่: ต้องเลือกเพิ่มพร้อมที่มา/schema ก่อน ไม่เปิด wildcard ทั้งเครื่อง

## เริ่มใช้งาน

ทำตาม `docs/PI_HANDOFF.md` ข้อ 0 ค่าเริ่มต้น `python dashboard.py` และ `python pi_check.py`
ใช้ `runtime/` ตรวจ hash/versions ให้ก่อน ไม่มีการ train/download ระหว่าง inference
โหมด template ไม่ต้องใช้ LLM หากต้องการ LLM ให้เตรียม GGUF/llama.cpp ตามคู่มือข้อ 4

เริ่มตรวจด้วย `python3.12 verify_checkout.py` โดยยังไม่ต้องติดตั้ง packages
สคริปต์ตรวจว่าโมเดลเป็นไฟล์จริง ไม่ใช่ Git LFS pointer พร้อม checksums ใน
`deploy/checkout-assets.json` (5 model files + 2 public datasets), runtime manifest
และ `deploy/wheels-sha256.json` (11 wheels) ถ้าขาดให้แก้ clone ไม่ใช่เทรนบน Pi

`.gitattributes` รักษา bytes ของ `runtime/`, CSV, joblib และ wheels เพื่อให้ hash ตรงกัน
ทั้ง Windows และ Linux ตรวจไฟล์สำคัญที่ควรติด Git ด้วย:

```bash
git ls-files runtime ai4i-artifacts artifacts experiments data wheels
git check-ignore -v runtime/model.joblib
```

คำสั่งหลังอาจแสดงกฎ `!` ซึ่งเป็นการอนุญาตไฟล์ ดู `git ls-files` ยืนยันว่าไฟล์ถูก track จริง
ไฟล์ใหญ่สุดเป็น scipy wheel ประมาณ 34 MB ต่ำกว่า GitHub file limit ไม่ต้องใช้ Git LFS
