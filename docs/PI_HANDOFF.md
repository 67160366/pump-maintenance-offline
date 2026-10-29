# ส่งงานให้ agent บน Raspberry Pi 4

หน้าเว็บใช้ภาษาไทยแบบง่ายแล้ว: “ดูรายการถัดไป”, “ดูอัตโนมัติ”, “พักการอ่าน” และ
“เริ่มรอบใหม่” (ไม่ลบประวัติ) รายละเอียดเทคนิคเปิดจาก “ข้อมูลเพิ่มเติมสำหรับผู้ดูแล”
อ่าน [รูปแบบหน้าจอ](PI_SCREEN_DESIGN.md) สำหรับความหมายและผลตรวจ UI ล่าสุด

เส้นทางติดตั้งปัจจุบัน: อ่าน [PI_READY.md](PI_READY.md) ก่อน ใช้ `python3.12 setup_pi.py`
เพื่อตรวจ wheels/install/parity และ `.venv/bin/python start_pi.py` เพื่อเปิด template
LLM profile ปัจจุบันคือ Qwen2.5-0.5B-Instruct Q4_K_M + llama-completion ที่ pin ใน
`deploy/pi-lock.json` ใช้ `bash deploy/provision-llm.sh` แล้ว `start_pi.py --llm`
คำสั่ง Qwen3 ในข้อ 4 ด้านล่างเป็นทางเลือกเดิม ไม่ใช่ profile ที่ทดสอบในงานเตรียมล่าสุด
ผล ARM64 จำลองอ่านแยกจากผล Pi จริงใน [สถานะปัจจุบัน](PROJECT_STATUS.md)

เป้าหมายแรก: **เปิด dashboard + เล่น CSV ด้วยโมเดลจริงและ template โดยตัดอินเทอร์เน็ต**
เป้าหมายถัดมา: ทำแบบเดียวกันโดยมี llama.cpp/GGUF จริง พร้อมหลักฐาน fallback

## 0. ทางหลัก: clone Git แล้วใช้โมเดลที่แนบมา

**ไม่ต้องขอ model ZIP เพิ่มและไม่ต้องเทรนบน Pi** ใน Git มีโมเดล/ข้อมูล/reference
ครบแล้วพร้อม Linux ARM64 wheels ดูรายการใน [GIT_CONTENTS.md](GIT_CONTENTS.md)

ใช้ Raspberry Pi OS 64-bit (`uname -m` เป็น `aarch64`) และ Python **3.12**
Python ที่มากับ OS อาจเป็นคนละรุ่น ให้ตรวจ `python3 --version` ก่อน
หากไม่มี 3.12 ให้เตรียมขณะออนไลน์ด้วย uv ตามข้อ 2 ด้านล่าง

```bash
git clone --branch codex/pi-ready-environment --single-branch https://github.com/67160366/pump-maintenance-offline.git
cd pump-maintenance-offline
python3.12 verify_checkout.py
python3.12 setup_pi.py
.venv/bin/python -m unittest -v
.venv/bin/python deploy/smoke.py
.venv/bin/python start_pi.py
```

ถ้าใช้ uv: `uv venv --python 3.12 --seed .venv` แทนคำสั่งสร้าง venv
เปิด browser บน Pi ที่ `http://127.0.0.1:8080` แหล่งข้อมูลเป็น 12 snapshots ใน
`runtime/demo.csv` (ผล normal 6 / alert 6) ทุกแถวผ่านโมเดลจริง
ค่าเริ่มต้นตรวจ `runtime/manifest.json` และ dependency versions ก่อนโหลดโมเดล
ระบุ `--release runtime` ได้โดยตรงเช่นกัน

หน้าจอใหม่แยกภาพรวม/ประวัติ/ถามข้อมูลสำหรับ 800×480 อ่าน
[PI_SCREEN_DESIGN.md](PI_SCREEN_DESIGN.md) SQLite อยู่ `evidence/telemetry.sqlite3`
การกดเริ่มใหม่หรือเปิด server ใหม่ไม่ลบประวัติ เลือก “ทั้งหมดที่บันทึก” เพื่อดูรอบก่อน
หากเปิด LLM ช่วยอ่านคำถามเพิ่ม `--llm-questions` พร้อม paths ที่มีจริงตามคู่มือหน้าจอ
ตัวเลือกนี้มี timeout 10 วินาทีและ fallback; ต้องหยุด replay ก่อนถาม

หลัง preflight ผ่าน ให้หยุด server ด้วย Ctrl+C, ถอด network จริง แล้วตรวจรอบ offline:

```bash
.venv/bin/python pi_check.py --benchmark --offline-confirmed --output evidence/pi-template-offline.json
.venv/bin/python dashboard.py
```

ใช้ [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md) นำเสนอและข้อ 5 ตรวจรับ
หาก clone ผ่าน LAN จาก notebook ต้องใช้หน้าจอ/คีย์บอร์ด Pi เพื่อถอด network แล้วทดสอบต่อได้
เอกสารข้อ 1–3 ด้านล่างเป็น **ทางเลือกย้ายด้วย ZIP** ไม่จำเป็นต้องทำซ้ำเมื่อใช้ Git แล้ว
สำหรับ systemd แก้ WorkingDirectory/ExecStart เป็นโฟลเดอร์ clone จริง

## 1. เตรียมบน PC ที่มี artifacts

จาก root โปรเจกต์บน Windows:

```powershell
.venv\Scripts\python -m unittest -v
.venv\Scripts\python prepare_pi.py --out pi-release
.venv\Scripts\python pi_check.py --release pi-release --benchmark --output evidence/pc-template.json
.venv\Scripts\python dashboard.py --release pi-release
```

เปิด `http://127.0.0.1:8080` ลองอ่านทีละแถวและเล่นอัตโนมัติ หยุด server ด้วย Ctrl+C
สคริปต์สร้าง **pi-release/** และ **pi-release.zip** (ไม่เขียนทับของเก่า ใช้ชื่อใหม่เมื่อต้องออกใหม่)
ให้จด `archive_sha256` จาก output ส่งพร้อม ZIP ไป Pi ผ่าน USB/scp

ภายในมี source, dashboard, docs, tests, `runtime/model.joblib`, demo snapshots,
parity จาก PC, report, `release.json`, `requirements-pi.txt`, `manifest.json`
ข้อมูลเดโม AI4I คัดจาก test partition สูงสุด 6 แถวปกติ + 6 แถวเตือน สลับกันตาม
ผลโมเดล ไม่แก้ค่าเซนเซอร์ และไม่ใช้เดโมนี้ประเมิน accuracy
มี source attribution และ original row indices ใน `runtime/demo_provenance.json`

**ไม่รวม** Windows venv, full dataset, GGUF, llama.cpp; ARM64 wheels รวมได้ด้วยทางเลือกด้านล่าง
โค้ด โมเดล ข้อมูล และ ARM64 wheels อยู่ใน Git แล้ว ZIP เป็นทางเลือกสำหรับ USB transfer
SHA-256 ตรวจไฟล์เสียระหว่างย้าย ไม่ได้ยืนยันผู้เผยแพร่ ต้องรับ model จากแหล่งที่เชื่อถือได้

### ทางเลือก: ใส่ ARM64 wheels ลง ZIP จาก PC

release ที่เตรียมไว้ในงานรอบนี้มี wheel สำหรับ Linux aarch64 / CPython 3.12 ครบ 11 packages
ดาวน์โหลดได้สำเร็จแล้ว แต่ยังต้องทดสอบติดตั้ง/รันบน Pi จริง ไม่ใช่ Windows wheels
สร้างใหม่บน PC (ใช้ Python 3.12 และเปลี่ยนชื่อ output ถ้ามีแล้ว):

```powershell
.venv\Scripts\python -m pip download --only-binary=:all: --platform manylinux2014_aarch64 --platform manylinux_2_27_aarch64 --platform manylinux_2_28_aarch64 --python-version 312 --implementation cp --abi cp312 -r pi-release/requirements-pi.txt -d wheels/pi4-cp312
.venv\Scripts\python prepare_pi.py --out pi-release-with-wheels --wheels-dir wheels/pi4-cp312
```

ใช้ requirements จาก release ที่เพิ่งสร้างด้วย environment เดียวกัน รุ่น glibc ของ Pi
ต้องรองรับ wheel ด้วย (ชุดนี้มี scipy ที่ต้องการ glibc >=2.27 ใช้ Raspberry Pi OS 64-bit
Bookworm/Trixie เป็นเป้าหมาย) หากเปลี่ยน Python/dependencies ให้ดาวน์โหลดชุดใหม่
เมื่อ ZIP มี `wheels/` อยู่แล้ว ใช้ `pip install --no-index --find-links wheels` แทนคำสั่ง
ติดตั้ง online ด้านล่างได้ หลังจากมี Python/venv พร้อมแล้ว

### ถ้าเป็น PC ที่เพิ่ง clone

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python pi_check.py
.venv\Scripts\python prepare_pi.py --out pi-release --wheels-dir wheels/pi4-cp312
```

การเทรนใหม่อาจให้ runtime pins ต่างจาก release เก่า ให้ใช้ไฟล์ที่สร้างมาพร้อมกันทุกครั้ง
ห้ามสลับ model/parity/threshold จากคนละ release

## 2. เตรียม Pi ขณะยังออนไลน์

ใช้ Raspberry Pi OS **64-bit** และดู `uname -m` ต้องเป็น `aarch64`
ตรวจ RAM ด้วย `free -h` และบันทึก OS ด้วย `cat /etc/os-release`
Raspberry Pi OS Bookworm ขึ้นไปให้ติดตั้ง Python packages ใน venv ตาม
[เอกสาร Raspberry Pi](https://www.raspberrypi.com/documentation/computers/os.html)

ตรวจ ZIP เทียบ hash ที่ได้จาก PC ก่อนแตกไฟล์:

```bash
sha256sum pi-release.zip
mkdir -p ~/pump-demo
unzip pi-release.zip -d ~/pump-demo
cd ~/pump-demo
cat release.json
```

ใช้โฟลเดอร์ปลายทางใหม่/ว่าง ห้ามแตก release ใหม่ทับไฟล์ runtime เก่า
Python major.minor ต้องตรง `release.json` (release จาก PC ปัจจุบันใช้ **3.12**)
อย่าสันนิษฐานว่า `python3` ที่มากับ OS เป็นรุ่นเดียวกัน ตรวจ `python3 --version`
หากมี `python3.12` อยู่แล้ว:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements-pi.txt
```

ถ้าไม่มี Python รุ่นนั้น ใช้ uv จัด Python แยกจาก system Python ระหว่างออนไลน์:

```bash
curl -LsSf https://astral.sh/uv/install.sh -o /tmp/uv-install.sh
sh /tmp/uv-install.sh
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.12
uv venv --python 3.12 --seed .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements-pi.txt
```

อ้างอิง [ติดตั้ง uv](https://docs.astral.sh/uv/getting-started/installation/) และ
[จัดการ Python](https://docs.astral.sh/uv/guides/install-python/)
หาก release ระบุ Python อื่น ให้เปลี่ยนรุ่นในคำสั่งให้ตรงกัน
uv/OS packages เป็นงาน provisioning เท่านั้น runtime ไม่ใช้ uv และไม่ดาวน์โหลด Python

เก็บ wheels ที่ตรงเครื่องเป้าหมายไว้ก่อนตัดเน็ต:

```bash
.venv/bin/python -m pip download --only-binary=:all: -r requirements-pi.txt -d wheels
.venv/bin/python -m pip check
.venv/bin/python pi_check.py --release . --output evidence/pi-preflight.json
.venv/bin/python -m unittest -v
```

ถ้า wheel ไม่มีให้หยุดที่ package นั้น อย่าให้ build หนัก ๆ บน Pi โดยไม่วางแผนหรือเปลี่ยน
version ของโมเดลเอง หากต้องติดตั้งซ้ำออฟไลน์ใช้:

```bash
.venv/bin/python -m pip install --no-index --find-links wheels -r requirements-pi.txt
```

`pi_check` ตรวจ checksum, Python/dependency รุ่นเดียวกัน และ parity score atol=1e-9
ก่อนรันจริง การโหลด sklearn ข้ามรุ่นไม่มีการรับรองตาม
[model persistence](https://scikit-learn.org/stable/model_persistence.html)

## 3. เดโม template บน Pi แบบออฟไลน์

ต่อจอ/คีย์บอร์ดกับ Pi เพื่อให้ถอด Wi-Fi และ LAN ได้โดยยังควบคุมเครื่องได้
ตัด network จริงก่อนใส่ `--offline-confirmed` (เป็นคำยืนยันผู้ทดสอบ ไม่ใช่ตัวตรวจเครือข่าย)

```bash
cd ~/pump-demo
.venv/bin/python pi_check.py --release . --benchmark --offline-confirmed --output evidence/pi-template-offline.json
.venv/bin/python dashboard.py --release . --host 127.0.0.1 --port 8080
```

เปิด browser บน Pi ที่ `http://127.0.0.1:8080` ใช้ [บทเดโม](DEMO_RUNBOOK.md)
คำสั่งไม่เริ่ม train/download และ template ไม่ต้องมี GGUF

กรณีเปิดจาก notebook ในวง LAN ที่ไว้ใจได้ ใช้ `--host 0.0.0.0` แล้วเปิด
`http://IP-ของ-Pi:8080` ไม่มีระบบ login ทุก browser ควบคุม session เดียวกัน
การเปิดผ่าน LAN ใช้สาธิตได้ แต่ **ไม่นับเป็นการทดสอบถอด LAN/Wi-Fi**

## 4. เพิ่ม LLM จริงหลัง template ผ่าน

ขณะออนไลน์ build llama.cpp บน Pi ตาม [เอกสาร build](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md)
และเตรียม [Qwen3-0.6B GGUF Q8_0](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF)
เก็บ GGUF ภายนอก release เช่น `~/pump-models/qwen3-0.6b-q8_0.gguf`
บันทึก commit ของ llama.cpp, ผล `llama-cli --version` และ `sha256sum` ของ GGUF
ชุด flags ปัจจุบันต้องรองรับ grammar, single-turn, no-display-prompt; หากรุ่น runtime
ตอบรูปแบบอื่นจะเห็น fallback ต้องตรวจจริงก่อนปรับ adapter ห้ามรายงานว่า LLM ผ่านเพียงเพราะมีข้อความไทย

ตัด network แล้วรัน (แทน path ให้ตรงไฟล์จริง):

```bash
.venv/bin/python pi_check.py --release . --benchmark --offline-confirmed --llama-cli /home/YOUR_USER/llama.cpp/build/bin/llama-cli --gguf /home/YOUR_USER/pump-models/qwen3-0.6b-q8_0.gguf --output evidence/pi-llm-offline.json
.venv/bin/python dashboard.py --release . --llama-cli /home/YOUR_USER/llama.cpp/build/bin/llama-cli --gguf /home/YOUR_USER/pump-models/qwen3-0.6b-q8_0.gguf
```

LLM เป็นตัวเลือก โหลดโมเดลทุกครั้งที่เรียก subprocess จึงอาจช้าบน Pi
ไม่ใช้ CUDA/GPU และยังไม่ยืนยัน latency/ภาษาไทยบนอุปกรณ์จริง
`local_llm_validated` เท่านั้นแปลว่า LLM สำเร็จ ส่วน `template_*` บอกเหตุ fallback
ปัจจุบัน CLI ตรวจไฟล์ที่หายตอนเริ่มต้น; สาธิต runtime failure ได้โดยเริ่ม server เมื่อไฟล์
executable ถูกต้อง แล้วเปลี่ยนชื่อ executable ชั่วคราวก่อนอ่านแถวถัดไป จากนั้นคืนชื่อ
ใช้สำเนา runtime ที่ใช้เดโมเท่านั้น ไม่ทำกับ executable ที่ใช้ร่วมงานอื่น

## 5. ตรวจรับและเก็บหลักฐาน

| รายการ | หลักฐาน/เกณฑ์ |
| --- | --- |
| อุปกรณ์ | Pi 4, ARM64, RAM 8 GB; บันทึก OS/Python/dependencies |
| ความตรงของโมเดล | `parity.passed=true`, status ตรง reference, threshold ไม่เปลี่ยน |
| ออฟไลน์ | operator ถอด network จริง; ไม่มี runtime download/cloud call |
| ML | ทุกแถว <1 วินาที; เก็บ benchmark ไม่อ้างอิงความเร็ว PC |
| Summary | <=30 วินาที; template ได้, ถ้าอ้าง LLM ต้องเห็น validated จริง |
| หน่วยความจำ | system RAM <6 GiB, เก็บ peak process-tree RSS ประกอบ |
| ความร้อน | บันทึกอุณหภูมิและ `vcgencmd get_throttled` ก่อน/หลัง; ตรวจ cooling หากมี throttle |
| หน้าจอ | ทั้ง normal/alert, input, score, threshold, summary_method และ export อ่านได้ |
| Fallback | มีข้อเท็จจริงครบและสถานะไม่เปลี่ยนเมื่อ LLM ล้มเหลว |

ผลลัพธ์ตั้ง `hardware_acceptance_verified=false` เสมอเพื่อให้คนตรวจหลักฐานก่อน
RSS อาจนับ shared pages ซ้ำและการ sample ทุก 50 ms อาจพลาด peak สั้น ๆ
RAM ระบบรวม browser/โปรแกรมอื่น จึงบันทึกว่าเปิดอะไรระหว่างวัดด้วย

## 6. เปิดอัตโนมัติหลัง reboot (หลัง manual demo ผ่าน)

แก้ `deploy/pump-dashboard.service`: User, WorkingDirectory, ExecStart ให้ตรงเครื่อง
ค่าเริ่มต้นเป็น template บน localhost ถ้าต้องใช้ LLM เพิ่มสอง flags แบบ absolute path

```bash
sudo cp deploy/pump-dashboard.service /etc/systemd/system/pump-dashboard.service
sudo systemctl daemon-reload
sudo systemctl enable --now pump-dashboard
systemctl status pump-dashboard
journalctl -u pump-dashboard -n 50 --no-pager
```

ปิด instance manual ก่อนเปิด service หาก port 8080 ถูกใช้แล้ว
service เปิดเฉพาะ server; browser/kiosk ยังเปิดเอง ทดสอบหลัง reboot และอัปเดตสถานะใน Git

## Prompt พร้อมส่งให้ agent บน Pi

> อ่าน AGENTS.md, docs/PROJECT_STATUS.md และ docs/PI_HANDOFF.md ก่อนทำงาน
> งานคือ clone repository ที่มี runtime/model/ARM64 wheels พร้อมแล้ว หรือรับ PC release
> มาเปิด dashboard ของโมเดล AI4I ordered_primary บน Pi 4 8GB เริ่มจาก PI_HANDOFF ข้อ 0
> ตรวจ hash/runtime/parity ก่อน จากนั้นเดโม template แบบถอด network และเก็บ evidence
> แล้วจึงทดสอบ llama.cpp/GGUF จริงถ้ามีไฟล์พร้อม อย่าเทรนใหม่หรือเปลี่ยน threshold/split
> ถ้าไฟล์ไม่พร้อมบอกว่าอะไรขาด ห้ามอ้างว่าได้ทดสอบ Pi หรือ LLM โดยไม่มีหลักฐาน
> ทำตาม DEMO_RUNBOOK และอัปเดต PROJECT_STATUS ด้วยผลจริงและงานที่เหลือ
