# ผลเตรียมสภาพแวดล้อม Pi

## ข้อสรุป

ชุดหลักพร้อมสำหรับเดโม CSV → ML → template → Dashboard → SQLite → คำตอบพร้อม citation
บน Linux ARM64 จำลอง โดยติดตั้ง Python packages จาก wheels ใน repo และตัด network
ของ container ขณะทดสอบ ไม่เท่ากับการตรวจรับ Pi จริง

เลือก ML เดิม `forest_physics_12` / AI4I ordered_primary / threshold 0.41
เลือก LLM ทางเลือก Qwen2.5-0.5B-Instruct Q4_K_M ให้ตรงกับไฟล์ที่มีบน Pi จากรายงานเดิม
profile นี้ pin source commit + official model revision/hash ใน `deploy/pi-lock.json`
LLM ยังไม่ผ่านเกณฑ์ production ในการจำลอง จึงเปิด template เป็นค่าเริ่มต้น

## สภาพแวดล้อมที่ทดสอบ

- Host Windows x86-64; Docker Desktop Linux/WSL2 + QEMU ARM64
- User space Debian Bookworm, glibc 2.36, Python 3.12.14, `platform.machine()=aarch64`
- รอบ fresh install/final smoke กำหนด 4 CPUs / memory limit 8 GiB
- ไม่ปลอม `/proc/device-tree/model`; ไม่มี Pi, GPIO, sensor หรือปั๊มเชื่อมอยู่
- llama.cpp commit `7df8b876b91208a86a6d792e1140b3deec14535b`
- Cross-compile ด้วย GNU 12.2.0 เป็น Linux aarch64 / `armv8-a` แล้ว execute ผ่าน QEMU
- ไม่ได้ compile จบแบบ native บน Pi ในงานนี้; วิธี build จริงให้ Pi อยู่ใน provisioning script

## ผลที่ตรวจแล้ว

| รายการ | ผล |
| --- | --- |
| ARM64 wheels 11 packages / checksum / offline install | ผ่าน |
| Fresh Linux venv จาก installer ใหม่, `pip check` | ผ่าน ไม่มี broken requirements |
| Model manifest + dependency versions + parity | ผ่าน 20 แถว atol=1e-9 |
| Model bytes | SHA-256 `24043f821f48a5fba59a7aaaffdcd7d53e505bbe2849e7b755207e58e3024714` ไม่เปลี่ยน |
| Template replay | ผ่าน 12 แถว: normal 6 / alert 6 |
| Export / fixed questions 4 intents / citations | ผ่าน |
| ไม่สร้างเวลาวัด/รหัสปั๊มจาก replay | ผ่าน |
| Restart session และ SQLite history | ผ่าน เริ่ม session ใหม่โดยไม่ลบประวัติ |
| Browser จาก PC → ARM64 backend ที่ 800×480 | normal/alert/history/ask/citation ผ่าน ไม่มี console error หรือ external requests |
| ชุดทดสอบเดิม | 31 tests ผ่านทั้ง Windows และ ARM64 |
| Installer integrity test เพิ่ม | ผ่านบน ARM64; Windows ข้ามตาม platform (รวม 32 tests, skipped 1) |
| ไฟล์ wheel ถูกแก้ / requirements ไม่ตรง | ปฏิเสธก่อนสร้าง venv |
| ZIP ชุดส่งต่อใน Linux directory ใหม่ / venv ใหม่ / network none | ผ่าน setup, parity, smoke 12 แถว, launcher และสร้าง service file |
| LLM executable ARM64 | build/run ผ่าน รายงาน GNU 12.2.0 / Linux aarch64 |
| GGUF hash | ตรง official file และตรงรายงาน Pi เดิม |
| Real GGUF transport probes หลังแก้ stdout | ผ่าน `A` และ `summary` ไม่ใช้ mock |
| Full production LLM guards / deadlines | summary 2/2 timeout 30s, question 4/4 timeout 10s ใน QEMU |
| Actual executable-failure fallback | ผ่าน รักษาข้อเท็จจริงไว้เมื่อระบุไฟล์โมเดลที่ไม่มีจริง |
| Physical network disconnected / Pi thermal / Pi display | ยังไม่ได้ทดสอบรอบนี้ |

ชุดทดสอบเดิมมี SciPy OptimizeWarning เรื่อง `iprint` แต่ผ่าน ไม่เปลี่ยน dependency
หรือ metadata ของโมเดลเพื่อหลบ warning

## สิ่งที่พบและแก้เกี่ยวกับ LLM

ใน runtime รุ่นที่ pin ไว้ generated tokens ใช้ logging output channel เช่นเดียวกับ CLI
`--log-disable` จึงทำให้คำสั่งจบ exit 0 แต่ stdout ว่าง พบจริงใน initial probe
นอกจากนี้ completion มีข้อความ ` [end of text]` ที่ไม่ใช่คำตอบของโมเดล

profile ใหม่ใช้ explicit Qwen ChatML, ไม่เปิด conversation/prompt echo, verbosity 0
และ compatibility patch ที่เปลี่ยนเฉพาะ EOG banner ไป debug logging
`deploy/patch_completion.py` ยอมรับเฉพาะ source commit และเนื้อหาเดิม/patch ที่คาดไว้
ไม่ตัด substring จากคำตอบ ไม่ผ่อน guard และไม่เปลี่ยนสถานะ/ตัวเลข ML
adapter ใช้ `exec` เพื่อให้ timeout ฆ่า inference process ตัวจริง

หลังแก้ raw probes บน QEMU ส่ง `A` และ `summary` ถูกต้อง ใช้ประมาณ 27.15s / 37.41s
นี่เป็นผล raw transport เท่านั้น ไม่ใช่ `local_llm_validated` ของ application
production summary/question ยังใช้ timeout 30s/10s เดิม จึงไม่ใช้ raw probe ที่รอนานกว่า
มาประกาศว่า LLM ผ่านเกณฑ์ ต้องทดสอบ application บน Pi จริงต่อ
รอบ application หลัง patch ยืนยันว่า normal/alert ทั้งสองแถวเป็น `template_timeout`
ประมาณ 30.07s/30.10s และคำถามทั้ง 4 แบบเป็น `local_query_llm_timeout` ประมาณ 10.07s
ข้อสรุปนี้บอกขีดจำกัดของการจำลอง ไม่ได้พิสูจน์ว่า Pi จริงจะช้าหรือเร็วเท่ากัน

## ไฟล์และการใช้งาน

- [คำสั่ง clone/install/run และเกณฑ์ตรวจรับ](PI_READY.md)
- `setup_pi.py`: offline-first installer, ใช้ `--no-compile` ลดงานสร้าง bytecode ทั้ง wheel บน Pi
- `start_pi.py`: template default; `--llm` เป็นการเลือกเปิดเองและตรวจ model hash ก่อนเริ่ม
- `deploy/provision-llm.sh`: online provisioning/build ที่ pin แล้ว ไม่มี runtime download
- `deploy/smoke.py`: real model → HTTP → SQLite → cited questions → restart
- `deploy/diagnose_llm.py`: actual GGUF stdout/stderr, application guard, actual executable-failure fallback
- `deploy/make_service.py`: สร้าง unit ตาม user/path จริงเพื่อ review ไม่ติดตั้งหรือ enable เอง
- `prepare_pi.py`: สร้าง ZIP พร้อม hashes/wheels; ไม่รวม imported local device notes, venv, GGUF หรือ SQLite

หลักฐานดิบอยู่ ignored `evidence/`: `arm64-ready-smoke.json`, `arm64-template.json`,
`arm64-fresh-install.log`, `arm64-browser.json`, PNG, `arm64-setup-integrity.log`,
`arm64-llm-diagnostic-initial.json`, `arm64-llm-transport.json`,
`arm64-llm-application.json` และ build logs
ไม่คัดลอกข้อมูลส่วนตัวหรือฐานข้อมูลเหล่านี้เข้าชุด Git

ชุดแก้ไขใช้ branch `codex/pi-ready-environment`; คำสั่ง clone ใน README ระบุ branch นี้
แยกจาก main อ่านผลตรวจชุดส่งต่อและการตรวจไฟล์โมเดลใน `PROJECT_STATUS.md`
การตรวจรับ hardware ยังเป็นงานแยกจากการเผยแพร่ Git
`hardware_acceptance_verified=false` เสมอในหลักฐานรอบนี้

ชุดส่งต่อ `pi-release-ready.zip` ขนาด 76,531,052 bytes ผ่านการคัดลอกไป Linux storage
ใหม่และสร้าง `.venv` ใหม่ใน container ที่ไม่มี network ไม่ใช้ Windows venv หรือ
environment ที่ติดมากับ source ไฟล์ GGUF/local runtime/SQLite/imported device notes
ไม่อยู่ใน ZIP หลักฐานตรวจชุดนี้อยู่ `evidence/package-validation/` และ
`evidence/pi-ready-package-validation.log`; `evidence/pi-ready-package.json` เก็บ SHA-256
รายงานยืนยัน ZIP ส่วนนี้เพิ่มหลังสร้าง snapshot จึงอ่านจาก working tree ปัจจุบัน
