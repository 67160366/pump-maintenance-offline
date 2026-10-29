# สถานะและงานถัดไป

## สถานะล่าสุดของชุดเตรียม Pi

หน้าเว็บปรับภาษาไทยให้อ่านง่ายแล้ว ปุ่มและผลประเมินใช้คำทั่วไป คำตอบจากบันทึกและ
ข้อความแนะนำเมื่อยังไม่มีข้อมูลปรับตามด้วย รายละเอียดเทคนิคเปิดเพิ่มได้เฉพาะเมื่อสนใจ
Browser 800×480/390×844 ผ่านดู normal/alert, อัตโนมัติ 12 แถว, ประวัติ/แบ่งหน้า,
ดาวน์โหลดผล, คำถาม/อ้างอิง/ไม่มีข้อมูล และหน้าอธิบายระบบ ไม่มี console error
API/UI tests ที่เกี่ยวข้องผ่าน 16 tests; ไม่เปลี่ยนโมเดล threshold schema หรือ LLM prompt
รายละเอียด: [รูปแบบหน้าจอ](PI_SCREEN_DESIGN.md)
ชุดย้ายไป Pi ที่รวมหน้าเว็บภาษาไทยล่าสุดคือ `pi-release-thai-ui.zip` พร้อม ARM64 wheels
และ parity 20 แถวผ่าน ส่วน `pi-release-ready.zip` เป็น snapshot ชุดฐานก่อนปรับคำบน UI

เริ่มที่ [ศูนย์รวมเอกสาร](README.md) และ [PI_READY](PI_READY.md)
มี installer แบบ offline-first, launcher, pinned LLM provisioning, wheel checksums,
ARM64 Docker/QEMU และสคริปต์ smoke ผ่าน HTTP/SQLite พร้อมแล้วใน working branch
ชุดส่งต่อใช้ branch `codex/pi-ready-environment` และคำสั่ง clone ใน README ระบุ branch นี้
`verify_checkout.py` ตรวจโมเดลจริงทั้ง 5 ไฟล์, ข้อมูลสาธารณะ, runtime manifest และ
wheels 11 ไฟล์ก่อนติดตั้ง ถ้าขาด/เสียหาย/เป็น LFS pointer จะหยุดโดยไม่เทรนบน Pi

ก่อนส่ง Git ตรวจ bytes จาก staged Git tree โดยตรง: โมเดลหลัก 484,534 bytes,
โมเดลทั้ง 5 ไฟล์และ wheels ทั้ง 11 ไฟล์ hash ตรง ไม่มี telemetry/venv/GGUF/credentials
ในชุดส่ง ทดสอบไฟล์ที่ export จาก Git tree ไปโฟลเดอร์ใหม่ด้วย model parity 20 แถว
และ HTTP/SQLite smoke 12 แถวผ่าน Windows tests รวม 35 tests ผ่าน (ข้าม ARM64 installer
1 test ตาม platform) ผล ARM64/QEMU ด้านล่างเป็นหลักฐานรอบก่อน ไม่ใช้แทน Pi จริง

- Linux ARM64 จำลอง / Python 3.12.14: install wheels ทั้ง 11 packages โดยไม่ใช้ index,
  `pip check` และ model parity 20 แถว atol=1e-9 ผ่าน
- Template ผ่าน replay 12 แถว (normal 6 / alert 6), export, คำถาม 4 intents พร้อม citation,
  ไม่แต่งเวลาวัด และ restart แล้วประวัติ SQLite ยังคงอยู่ ใน container `--network none`
- ชุดทดสอบเดิม 31 tests ผ่านทั้ง Windows และ ARM64 จำลอง มี SciPy `iprint` warning เดิม
- Browser บน PC เชื่อม ARM64 backend: 800×480, normal/alert/history/ask/citation ผ่าน,
  ไม่มี horizontal overflow, ไม่มี console error หรือ external request
- ML ยังคง `forest_physics_12` / ordered_primary / threshold เดิม; ไม่เทรนหรือปรับคะแนน
- Qwen2.5 0.5B Q4_K_M เป็น LLM profile สำหรับเตรียมใช้งาน ไม่ใช่หลักฐาน Pi acceptance
- Build executable ARM64 และ real GGUF raw probes ผ่าน `A` / `summary` หลังแก้ stdout
  แต่ application บน QEMU timeout summary 2/2 และ question 4/4 ตาม deadline 30s/10s
  actual executable-failure fallback ผ่าน ยังต้องยืนยัน performance บน Pi ไม่ประกาศ LLM acceptance
- รายละเอียดการจำลอง ข้อจำกัด และ compatibility patch: [ผลเตรียม Pi](PI_ENVIRONMENT_RESULTS.md)
- ZIP `pi-release-ready.zip` ผ่าน fresh Linux directory/venv + offline setup + smoke 12 แถว
  + launcher + generate service file แล้ว ไม่รวม venv/GGUF/SQLite/บันทึกเครื่องส่วนตัว

หลักฐานส่วนตัว `evidence/arm64-ready-smoke.json`, `arm64-template.json`,
`arm64-browser.json` และ PNG อยู่ ignored; ผลจำลองไม่ใช้แทน timing/thermal ของ Pi
`hardware_acceptance_verified=false` และไม่ได้ทดสอบเซนเซอร์/ปั๊มจริง

## ผล Pi จริงจากรายงานรอบก่อน

รายงานที่ผู้ใช้นำมาให้อ่านระบุ Pi 4 ARM64/Python 3.12.16, parity 20 แถวผ่าน,
benchmark 2 snapshots (normal/alert), ML <1s/แถว, summary <30s, peak system RAM
1,819,664,384 bytes, อุณหภูมิ 46.251°C และ `throttled=0x0` ตอนตรวจ
แต่ LLM ถูก guard ปฏิเสธทั้ง summary และ question routing จึงใช้ fallback
ยังไม่ถอด network จริง ไม่ตรวจ browser บน Pi และยังไม่ผ่าน hardware acceptance
ข้อมูลนี้เป็นรายงานประวัติ ไม่ใช่ผลตรวจอุปกรณ์สดในเครื่อง Windows รอบนี้

## งานต่อก่อนตรวจรับ

1. ยืนยัน LLM profile ใหม่บน Pi ด้วย GGUF จริง ต้องเห็น validated methods และ fallback
2. ถอด Wi-Fi/LAN จริงแล้วเก็บ benchmark/thermal พร้อมตรวจจอ Pi normal/alert/คำถาม/export
3. หลัง manual demo ผ่าน ค่อยสร้าง unit ด้วย `deploy/make_service.py` และตรวจหลัง reboot
4. ใช้ branch `codex/pi-ready-environment` ตาม README เพื่อให้ได้ชุดส่งต่อและ installer ล่าสุด
5. ปั๊มจริงต้องกำหนด sensor/schema/หน่วยและข้อมูล label ก่อน ไม่ย้าย AI4I ไปใช้โดยเปลี่ยนชื่อคอลัมน์

## ประวัติการเตรียมบน PC (เก็บไว้แยกจากสถานะล่าสุด)

ข้อความด้านล่างเป็นสถานะและหลักฐานในรอบก่อนเริ่มทดลอง Pi/ARM64 จึงมีข้อความ
“รอทดสอบ” ที่ไม่ใช่สถานะล่าสุด อ่านส่วนบนสำหรับผลที่มีเพิ่มแล้ว

## ขอบเขตปัจจุบัน

ต้นแบบจำแนกสถานะจาก snapshot CSV บนเครื่องเดียว มีภาษาไทยและหน้า dashboard
เตรียมสำหรับ Raspberry Pi 4 RAM 8 GB ยังไม่มีผลตรวจรับจาก Pi หรือปั๊มจริง

| ส่วน | สถานะ |
| --- | --- |
| เทรน/ประเมินบน PC, artifacts และค่า parity | มีแล้ว |
| AI4I ผลหลัก | Accuracy 99.25%, recall 71.79%, F1 78.87%; synthetic |
| ปั๊มเดิม 17 แบบ | Accuracy 50.10%; ยังไม่ชนะ baseline อย่างน่าเชื่อถือ |
| ตัวกลางระหว่างโมเดลกับข้อความ | `bridge.py` เรียกโมเดลจริง ส่ง facts และตรวจสรุป |
| หน้า dashboard ออฟไลน์ | ปรับสำหรับ 800×480: ภาพรวม / ประวัติ / ถามข้อมูล; รายละเอียดเปิดเมื่อแตะ |
| ประวัติ/ถามข้อมูล | SQLite ในเครื่อง, คำตอบจากข้อมูลพร้อม citations; LLM intent router เป็นทางเลือก |
| แพ็กย้ายเครื่อง | `prepare_pi.py`; model, demo, parity, source, version pins, SHA-256 |
| Git พร้อมใช้ | รวม runtime, โมเดลทั้ง 4 แบบ, public CSV 2 ชุด, reports/parity และ ARM64 wheels; ไม่ต้องเทรนหลัง clone |
| ตรวจเครื่อง/ผลซ้ำ/benchmark | `pi_check.py`; ใช้ได้ทั้ง PC และ Pi |
| Pi / ARM64 runtime / thermal | **รอทดสอบบนเครื่องเป้าหมาย** |
| llama.cpp + GGUF จริง | **รอทดสอบ**; fallback tests ใช้ mock |
| ต่อเซนเซอร์ปั๊มจริง | **ยังไม่ได้ทำ**; ต้องทราบชนิดเซนเซอร์ หน่วย และการเชื่อมต่อก่อน |

## หลักฐานที่ตรวจแล้วบน PC ในรอบเตรียม Pi

- Windows AMD64 / Python 3.12.14; automated tests ผ่าน **22 tests**
- release ใช้ `forest_physics_12` / ordered_primary; parity 20 แถวผ่าน atol=1e-9
- benchmark template 12 snapshots (ผล normal 6 / alert 6), ML สูงสุดประมาณ 32.5 ms/แถว
  และ peak process-tree RSS ประมาณ 146 MiB ในรอบที่วัดนี้ เป็นผล PC เท่านั้น
- ทดสอบผ่าน browser จริง: อ่านทีละแถว normal/alert, start, pause; API export ให้ผลจริง
- ดาวน์โหลด wheel Linux aarch64 / CPython 3.12 ครบ 11 packages แล้ว
  ยังไม่ได้ติดตั้งบน ARM64 จึงไม่นับว่า Pi ผ่าน
- ภาพหน้าจอ PC: [หน้าประเมิน](images/dashboard-pc.png), [สรุป/ประวัติ](images/dashboard-summary-pc.png)
- ผลดิบอยู่ `evidence/pc-template.json` (ignored); เอกสารนี้ไม่แทนผลทดสอบ Pi
- ชุดทดสอบเดิมอาจมี OptimizeWarning เรื่อง `iprint` จาก SciPy/LogisticRegression;
  tests ผ่าน แต่ยังต้องทดสอบ dependencies ทั้งชุดบน Pi

## ให้ agent ถัดไปทำอะไร

1. อ่าน `AGENTS.md` และ `docs/PI_HANDOFF.md` ระบุว่ากำลังทำงานบน PC หรือ Pi
2. บน Pi clone Git แล้วเริ่มที่ PI_HANDOFF ข้อ 0; มี model/data/wheels พร้อม หรือใช้ ZIP เป็นทางเลือก
3. สร้าง environment ให้ตรง `runtime/release.json` / `requirements-pi.txt` แล้วตรวจ parity ก่อนเปิด dashboard
4. ทำเดโม template ออฟไลน์ให้ผ่านก่อน แล้วค่อยเตรียม llama.cpp/GGUF และทดสอบซ้ำ
5. เก็บ JSON หลักฐานบน Pi พร้อม OS, CPU architecture, Python, runtime/GGUF hash,
   ผล network-disconnected run และ `vcgencmd get_throttled`
6. อัปเดตตารางนี้ด้วยผลที่วัดจริงและสิ่งที่ยังไม่ผ่าน

หากไม่มี ARM64 wheel ของ dependency รุ่นใน release ให้หยุดและบันทึก package/version
อย่าแก้ version metadata ของ model ให้โหลดผ่าน ทางแก้คือเตรียม runtime ที่รองรับ หรือ
สร้าง environment/เทรนและออก release ใหม่บน PC แล้วตรวจ parity ใหม่ทั้งหมด

## หลังจบ milestone Pi

- หากต้องการต่อปั๊มจริง ให้เลือกเซนเซอร์/ADC/โปรโตคอลและกำหนด schema พร้อมหน่วยก่อน
- เพิ่ม adapter ที่ส่ง snapshot เข้าตัวกลาง โดยคงการตรวจข้อมูลและระบุแหล่งข้อมูลว่า live จริง
- AI4I ไม่สามารถเปลี่ยนชื่อคอลัมน์แล้วใช้กับเซนเซอร์ปั๊มได้ทันที ต้องมีข้อมูลปั๊มและ label
  จากผลตรวจซ่อมเพื่อประเมิน/เทรนใหม่
- ระบบนี้เป็นการสาธิต ไม่มีการสั่งเปิดปิดปั๊มหรือควบคุมอุปกรณ์

## การเปลี่ยนหน้าระบบ 28 ตุลาคม

อ่าน [PI_SCREEN_DESIGN.md](PI_SCREEN_DESIGN.md) สำหรับหน้าจอ 800×480 และคำถามจากประวัติ
GGUF จริงยังรอทดสอบ การมีช่องถามไม่ใช่หลักฐานว่า LLM ทำงานแล้ว
AI4I ไม่มีรหัสเครื่อง/เวลาวัดจริง จึงไม่ตอบระบุเครื่องของวันนี้

- Tests รอบนี้ผ่าน 31 tests; parity โมเดลเดิม 20 แถวผ่าน ไม่เปลี่ยน model/threshold
- ตรวจ browser viewport จริง 800×480: body สูง 480, ไม่มี horizontal overflow,
  เนื้อหาจบที่ y=424 และ navigation อยู่ y=424–480; ช่องถามจบ y=414 ไม่ทับ navigation
- Browser → API → SQLite → คำตอบ → กด citation เปิด snapshot ต้นทาง ผ่านด้วยโมเดลจริง
- ตรวจรายการเตือน 6/12, อุณหภูมิสูงสุด และการปฏิเสธคำถามวันนี้เมื่อไม่มีเวลาวัดจริง
- ภาพจาก PC viewport 800×480:
  [ภาพรวม](images/pi-overview-800x480.png), [ประวัติ](images/pi-history-800x480.png),
  [ถามข้อมูล](images/pi-ask-800x480.png), [รายละเอียด](images/pi-detail-800x480.png)
- ยังไม่ใช่หลักฐานการรันบน Pi/GGUF จริง
