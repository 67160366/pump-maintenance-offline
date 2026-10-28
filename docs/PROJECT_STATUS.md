# สถานะและงานถัดไป — 28 ตุลาคม 2026

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
