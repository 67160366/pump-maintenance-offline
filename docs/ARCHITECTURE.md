# ระบบทำงานอย่างไร

```text
Browser บน Pi (หรือเครื่องใน LAN ที่ไว้ใจได้)
  │ GET /api/state, POST /api/action
  ▼
dashboard.py — HTTP server + คิวประมวลผลทีละแถว + สถานะ replay ร่วมกัน
  │
  ▼
bridge.py — ตัวกลางของระบบ
  ├─ 1. อ่าน snapshot, ตรวจ schema และหน่วยตาม dataset
  ├─ 2. เรียก sklearn model.joblib → score → เทียบ threshold → status
  ├─ 3. จัด facts: readings, model, score, threshold, status, limitations
  │      └─ ส่งผล ML ให้หน้าจอทันทีระหว่างรอสรุป
  └─ 4. สร้างข้อความข้อเท็จจริง → pump.summarize
         ├─ ไม่ตั้งค่า LLM → template
         └─ llama.cpp subprocess + GGUF ในเครื่อง
              ├─ A/B ถูกต้องและสอดคล้อง → local_llm_validated
              └─ เกิน 30s / error / ขัดสถานะ → template พร้อม reason
  │
  ▼
JSON state → dashboard: readings, status, score, summary, method, timings, history
```

## หน้าที่ของตัวกลาง

`InferenceBridge.evaluate(index, progress)` ใน `bridge.py` เป็นจุดเชื่อมระหว่าง ML กับ
LLM แยกจากหน้าเว็บ จึงใช้ inference path เดียวกันกับ `pi_check.py --benchmark` ได้
ไม่มีการใช้ LLM เลือกโมเดลหรือคำนวณคะแนนใหม่

`handoff` ใน JSON เป็น facts ที่ตัวกลางจัดเตรียม: dataset, model, status (0/1/null),
score (0–1/null), threshold, readings, `score_is_calibrated_probability=false`,
`remaining_life_available=false` หน้าเว็บมีส่วนเปิดดู facts นี้ได้

คำสั่ง LLM ปัจจุบันใช้ **ข้อความข้อเท็จจริงที่สร้างจาก facts** เป็น prompt ไม่ได้ส่ง JSON
ให้ LLM วิเคราะห์อิสระ ใช้ grammar ให้ตอบ A หรือ B และตรวจคำตอบซ้ำ สถานะที่ต้องตรวจ
บำรุงรักษารับได้เฉพาะ A ตัวเลขและข้อเท็จจริงในสรุปยังมาจาก template เสมอ

| summary_method | ความหมาย |
| --- | --- |
| pending | ML ตอบแล้ว กำลังรอสรุป |
| template | ไม่ได้ตั้งค่า LLM |
| local_llm_validated | LLM ในเครื่องตอบ A/B และผ่านการตรวจ |
| template_timeout | เกิน 30 วินาที |
| template_rejected_llm | exit code/รูปแบบคำตอบไม่ผ่าน |
| template_inconsistent_llm | คำตอบไม่สอดคล้องกับสถานะเตือน |
| template_llm_unavailable | เริ่ม subprocess ไม่ได้ |
| template_missing_data | ปั๊มมีค่าว่าง จึงไม่ประเมินและไม่เรียก LLM |

AI4I ปฏิเสธ CSV ที่ขาดค่า/ค่าผิด schema ก่อนเริ่ม server ส่วนปั๊มยอมรับค่าว่างรายแถว
แต่แสดงประเมินไม่ได้ คอลัมน์จำเป็นหายทั้งคอลัมน์ทำให้หยุดเริ่ม server

## Dashboard และ API

- `GET /` — หน้าเดียวภาษาไทย, JavaScript/CSS/font จากเครื่อง ไม่มี CDN
- `GET /api/state` — metadata, current event, history สูงสุด 60 แถว, resources, error
- `POST /api/action` — JSON `{"action":"step"}` / `start` / `pause` / `reset`
- `GET /api/export` — snapshot session ล่าสุดสำหรับบันทึก JSON; ไม่ใช่ benchmark peak
- poll ทุก 700 ms; worker หนึ่งตัว ไม่สะสมคิวและไม่เปิด LLM หลาย process พร้อมกัน
- `start` เล่นจนจบ CSV; `pause` หยุดแถวถัดไป, งานปัจจุบันทำจนเสร็จ;
  `reset` ต้องรอแถวปัจจุบันเสร็จแล้ว
- state อยู่ใน RAM และร่วมกันทุก browser; restart server ทำให้เริ่ม session ใหม่

Server ใช้ Python standard library เพื่อเดโมในเครื่อง/วง LAN ที่เชื่อถือได้ ค่าเริ่มต้น
bind `127.0.0.1` ไม่มี auth, multi-user isolation หรือ production reverse proxy
ไม่เปิด port ไปอินเทอร์เน็ต และไม่มี endpoint upload model/รัน shell

## สิ่งที่เดโมแสดงและยังไม่แสดง

แสดงระบบครบจาก CSV ไปโมเดลจริงและข้อความไทย แต่การเลือก snapshot ปกติ/เตือนสลับกัน
เป็นการจัดลำดับเพื่อสาธิต ไม่ใช่ลำดับเวลา และใช้วัด accuracy ใหม่ไม่ได้
กราฟเป็นประวัติคะแนน replay ไม่ใช่แนวโน้มเครื่องจักรหรือการคาดการณ์อนาคต

RAM บนหน้าเว็บเป็นค่าขณะนั้นรวม process ลูก; benchmark เก็บ peak แยกใน `pi_check.py`
อุณหภูมิอ่านจาก Linux thermal sysfs หากรองรับ ค่าอ่านไม่ได้จะแสดงชัดเจน
