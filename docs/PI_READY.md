# Clone แล้วเตรียม Pi ให้พร้อมใช้งาน

## เลือกอะไร และแต่ละส่วนเชื่อมกันอย่างไร

เป้าหมาย Raspberry Pi 4 / RAM 8 GB / OS 64-bit (`aarch64`) / Python 3.12
เริ่มด้วย template เพื่อให้ใช้เดโมได้ทันทีโดยไม่ต้องโหลด LLM

| ส่วน | สิ่งที่ใช้ | หน้าที่ |
| --- | --- | --- |
| ข้อมูล | `runtime/demo.csv`, 12 snapshots: normal 6 / alert 6 | AI4I สังเคราะห์ ไม่มี sensor/ปั๊มจริง |
| ML | `runtime/model.joblib`, `forest_physics_12`, ordered_primary | Random Forest; threshold เดิม 0.41 เป็นผู้ตัดสินสถานะ |
| ตัวกลาง | `bridge.py` | ตรวจ schema → ML → facts → summary |
| ข้อความเริ่มต้น | template ภาษาไทย | ทำงานได้โดยไม่ต้องมี GGUF |
| LLM ทางเลือก | Qwen2.5-0.5B-Instruct Q4_K_M, 491,400,032 bytes | เลือก A/B และเลือก intent; ไม่คำนวณคะแนนหรือเขียน SQL |
| Runtime LLM | llama.cpp `llama-completion` ผ่าน `deploy/llama-local` | subprocess ในเครื่อง, context 1024, 2 threads, grammar |
| ประวัติ/คำถาม | `data_assistant.py` + SQLite | Python คำนวณคำตอบจากข้อมูลและให้ citations |
| เว็บ | `dashboard.py` + `web/` | HTTP localhost:8080, จอ 800×480, ไม่มี CDN |

```text
CSV → bridge → sklearn → status/score/facts → template หรือ guarded local LLM
                    ↓                          ↓
                 dashboard ← JSON result ← summary/method
                    ↓
                  SQLite ← คำถาม → intent → fixed SQL → คำตอบ + citation
```

เลือก Qwen2.5 0.5B ให้ตรงกับโมเดลที่มีบน Pi เดิมและใช้ทรัพยากรต่ำ
นี่เป็นตัวเลือกเตรียมใช้งาน ไม่ใช่การรับรองความแม่นยำภาษาไทย
LLM ไม่ได้วิเคราะห์/วินิจฉัยปั๊มอย่างอิสระ สรุปตัวเลขมาจาก template เสมอ
โมเดลขนาด 1.5B/3B ที่เคยพบยังไม่ได้เลือกเป็นค่าเริ่มต้นเพราะไม่มีผลตรวจรับรอง

## ทางหลัก: template หลัง clone

เตรียม Python 3.12 และ Git ขณะยังออนไลน์ ตรวจ `uname -m` และ `python3.12 --version`
หาก OS ไม่มี Python 3.12 ใช้วิธี uv ใน [PI_HANDOFF](PI_HANDOFF.md) ก่อน
อย่าสลับ scikit-learn หรือแก้ runtime metadata ให้โหลดผ่าน

```bash
git clone --branch codex/pi-ready-environment --single-branch https://github.com/67160366/pump-maintenance-offline.git
cd pump-maintenance-offline
python3.12 verify_checkout.py
python3.12 setup_pi.py
.venv/bin/python deploy/smoke.py --output evidence/pi-ready-smoke.json
.venv/bin/python start_pi.py
```

`setup_pi.py` ตรวจ ARM64/Python/checksum ของ wheels ทั้ง 11 ไฟล์ แล้วสร้าง `.venv`,
ติดตั้งด้วย `--no-index`, ตรวจ dependency และ hash/runtime/parity ก่อนรายงานว่าพร้อม
ใช้ซ้ำได้ ไม่เทรน ไม่เปลี่ยน threshold ไม่ติดตั้ง service และไม่เรียก sudo
ถ้า `.venv` เป็นของ Windows ให้ย้ายเก็บไว้และสร้าง Linux venv ใหม่
เปิด browser บน Pi ที่ `http://127.0.0.1:8080` แล้วอ่าน normal/alert/ถามข้อมูล

ต้องมี Python พร้อมก่อนตัด network; การ clone และ provisioning LLM ต้องใช้อินเทอร์เน็ต
หลัง provisioning แล้ว runtime ไม่ดาวน์โหลดหรือเรียก cloud

## เพิ่ม LLM จริงแบบเลือกเปิดเอง

ทำขณะออนไลน์ หลัง template ผ่านแล้ว:

```bash
sudo apt-get update
sudo apt-get install -y git cmake build-essential ca-certificates
bash deploy/provision-llm.sh
.venv/bin/python deploy/smoke.py --llm --output evidence/pi-ready-llm-smoke.json
.venv/bin/python start_pi.py --llm
```

หยุด dashboard ตัวเก่าก่อนเปิดตัวใหม่ `--llm` ตรวจ hash GGUF ก่อนเริ่ม;
ถ้าไฟล์ขาดจะหยุดพร้อมข้อความ ไม่แอบดาวน์โหลด
`deploy/pi-lock.json` pin ทั้ง llama.cpp commit และ official GGUF revision/SHA-256
`models/` และ `local/` ไม่เข้า Git; clone ใหม่ต้อง provision เพียงครั้งแรก
ถ้ามี GGUF เดิม hash ตรง ให้ copy ไป `models/` ก่อน สคริปต์จะ reuse โดยไม่ดาวน์โหลดซ้ำ
adapter ใช้ explicit Qwen ChatML และ completion ที่ไม่เปิด conversation/prompt echo;
ไม่ตัดข้อความส่วนเกินจาก stdout เพื่อปลอมให้ guard ผ่าน
`deploy/patch_completion.py` ตรวจ source commit/เนื้อหาเดิมก่อนใช้ patch เพียงจุดเดียว:
ย้ายข้อความ CLI ` [end of text]` ไป debug log โดยไม่แตะ generated tokens
ใช้ verbosity 0 แทน `--log-disable` เพราะ runtime รุ่นนี้ส่งคำตอบผ่านช่อง logging เช่นกัน
timeout ฆ่า inference process โดยตรงด้วย `exec` ไม่มี wrapper ลูกค้าง

summary ต้องเห็น `local_llm_validated`; คำถามต้องเห็น `local_llm_intent_validated`
จึงนับว่า LLM ผ่านจริง หากเป็น `template_*` / `local_query_*` ให้ตรวจ evidence/log
โดยใช้ template ทำงานต่อได้และไม่เปลี่ยนสถานะ ML

## จำลอง Linux ARM64 บน Windows

ต้องเปิด Docker Desktop Linux engine ที่รองรับ ARM64 emulation ก่อน:

```powershell
docker build --platform linux/arm64 -f deploy/Dockerfile.pi -t pump-pi-arm64:local .
docker run --rm --platform linux/arm64 --network none --memory=8g --cpus=4 --mount "type=bind,source=$PWD,target=/app" pump-pi-arm64:local python deploy/smoke.py --output evidence/arm64-ready-smoke.json
docker run --rm --platform linux/arm64 --network none --memory=8g --cpus=4 --mount "type=bind,source=$PWD,target=/app" pump-pi-arm64:local python pi_check.py --benchmark --output evidence/arm64-template.json
```

mount นี้มีไว้บันทึก evidence และอ่าน source ล่าสุด; Python ที่ใช้คือ `/opt/pump-venv`
ภายใน image ไม่ใช่ Windows `.venv` บน host ไม่ใส่ `--offline-confirmed` ให้การจำลอง
`--network none` แยก network ของ container แต่ไม่ได้แปลว่าถอด Wi-Fi/LAN ของ Pi จริง

ทางเลือก build tools + GGUF ใน ARM64 จำลอง (ช้า โดยเฉพาะ compile):

```powershell
docker build --platform linux/arm64 -f deploy/Dockerfile.llm -t pump-pi-llm-tools:local .
docker run --rm --platform linux/arm64 --mount "type=bind,source=$PWD,target=/app" pump-pi-llm-tools:local
docker run --rm --platform linux/arm64 --network none --memory=8g --cpus=4 --mount "type=bind,source=$PWD,target=/app" pump-pi-llm-tools:local python deploy/smoke.py --llm --output evidence/arm64-llm-smoke.json
```

ถ้า compile ผ่าน QEMU ช้า ใช้ `deploy/Dockerfile.cross` และ `deploy/cross-llm.sh`
เพื่อ compile target ARM64/armv8-a ด้วย GCC cross toolchain บน x86 หลัง provision
fetch source commit ที่ pin แล้ว (หยุด native compile ก่อนเพื่อไม่แย่งทรัพยากร)
ผลอยู่ `local/llama.cpp/build-cross` จากนั้นรัน ARM64 container โดยเพิ่ม
`-e LLAMA_LOCAL_BUILD=build-cross` ให้ adapter เลือก binary นั้น
นี่เป็นทางลัดของเครื่องจำลอง Pi จริงยังใช้ `provision-llm.sh` และ build เดิม
ไม่ใช้ binary x86 รันแทน ARM64

ตรวจ raw output/guard/fallback จาก GGUF จริงได้ด้วย
`.venv/bin/python deploy/diagnose_llm.py --output evidence/pi-llm-diagnostic.json`
diagnostic เก็บ stdout/stderr ของ probe และผล actual application; raw probe มี timeout
60s เพื่อวิเคราะห์ แต่ production summary/question ยังคง 30s/10s และต้องผ่านแยกกัน

นี่เป็น ARM64 user space ผ่าน QEMU ไม่จำลอง Pi kernel/GPIO/ความร้อน/กำลังไฟ/ความเร็ว CPU
ห้ามใช้ latency/RAM system ของ Docker เป็นผล Pi จริง
คำสั่งจำลองกำหนด limit 4 CPUs/8 GiB แต่ `psutil` อาจรายงาน RAM ของ Linux VM ทั้งระบบ
`local/llama.cpp/build` เป็น binary สำหรับ architecture ที่ build; ย้ายไป Pi ด้วย Git clone
แล้ว build ใหม่ อย่ายก build ที่สร้าง native x86 ไปใช้บน Pi

## ตรวจรับ Pi และเปิดหลัง reboot

หลังติดตั้งทั้งหมด หยุด server ถอด LAN/Wi-Fi จริง แล้วรัน:

```bash
.venv/bin/python pi_check.py --benchmark --offline-confirmed --output evidence/pi-template-offline.json
.venv/bin/python -m unittest -v
.venv/bin/python start_pi.py
```

ถ้าทดสอบ LLM เพิ่ม `--llama-cli deploy/llama-local --gguf models/qwen2.5-0.5b-instruct-q4_k_m.gguf`
ให้ `pi_check.py` แยกไฟล์ evidence อีกชุด ตรวจจอจริง normal/alert/ถาม/citation/export,
อุณหภูมิ/throttling และ performance ตาม PI_HANDOFF; ยังเก็บ acceptance เป็น false ให้คนตรวจ

หลัง manual demo ผ่าน สร้าง service ที่ใส่ user/path จริงให้อัตโนมัติ:

```bash
.venv/bin/python deploy/make_service.py
# หรือเพิ่ม --llm เมื่อผลตรวจ LLM ผ่านแล้ว
cat evidence/pump-dashboard.service
```

สคริปต์พิมพ์คำสั่งติดตั้งให้ตรวจ ก่อนใช้ต้องหยุด manual server ที่ port 8080
ทดสอบหลัง reboot ด้วย `systemctl status pump-dashboard` และ `journalctl -u pump-dashboard`
service เปิด backend; การเปิด browser/kiosk ยังเป็นอีกขั้น

## แหล่งอ้างอิงและข้อจำกัด

- [Official Qwen2.5 GGUF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF)
- [llama.cpp completion](https://github.com/ggml-org/llama.cpp/tree/master/tools/completion)
- [Docker ARM64 / QEMU emulation](https://docs.docker.com/build/building/multi-platform/)

ไม่มีการต่อ sensor หรือควบคุมปั๊มจริง AI4I ไม่ใช่ปั๊มและ score ไม่ใช่ probability
ที่ calibrate แล้ว การเปิดสาธารณะ/auth/multiuser ไม่อยู่ในชุดนี้
