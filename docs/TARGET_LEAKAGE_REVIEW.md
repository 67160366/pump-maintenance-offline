# ตรวจสอบ Industrial_Pump_PdM_RaspberryPi4

## ข้อสรุป

ทำซ้ำ accuracy 87.35%, precision 85.06%, recall 90.52%, F1 87.71%, ROC-AUC 0.9459 ได้จริง แต่ตัวเลขวัดการจำแนกข้อมูลที่มี feature จากคำตอบ จึงไม่ใช่หลักฐานความแม่นยำกับข้อมูลปั๊มดั้งเดิมหรือเซนเซอร์จริง

CSV ต้นฉบับใน ZIP ตรงกับ CSV ที่เราใช้ทุก byte (SHA-256 เท่ากัน) และ label ใน processed CSV ไม่เปลี่ยน สาเหตุคะแนนสูงคือเพิ่ม Current โดยใช้ target ไม่ใช่ Random Forest ดีกว่าโมเดลเดิมอย่างเดียว

## ปัญหาหลัก: target leakage

ใน data_prep_and_train.py ของ ZIP ที่ได้รับตรวจสอบ บรรทัด 316–326 (ไม่ได้เผยแพร่ ZIP หรือ source ของงานภายนอกใน repository นี้):

```python
flag = df_featured['Maintenance_Flag'] if 'Maintenance_Flag' in df_featured.columns else 0
i_fault = flag * (3.0 + 0.8 * vib + 0.03 * (temp - 50.0))
total_current = i_base + i_thermal + i_vib + i_fault + sensor_noise
```

จากนั้นใช้ Current เป็นหนึ่งใน features (บรรทัด 580–584) สูตรนี้ต้องรู้ว่าเครื่องเสียหรือไม่ก่อนสร้างอินพุตที่จะใช้ทำนายเครื่องเสีย การแบ่ง train/test ภายหลังไม่แก้ปัญหานี้ แม้แบ่งก่อนแต่ยังสร้าง test Current จาก test label ก็ยังรั่ว

## ทดลองตัดส่วนที่รั่วออก

ใช้ split 80/20 stratified seed 42 และ RF 100 trees, depth10, min_samples_split6, min_samples_leaf3, class_weight balanced เหมือนต้นฉบับ fit scaler เฉพาะ train ทุกกรณี:

| อินพุต | Accuracy | ROC-AUC |
|---|---:|---:|
| Vibration, Temperature, Current ตาม ZIP (มี target term) | 87.35% | 0.9459 |
| สูตร Current เดิมแต่ลบ i_fault ที่มาจาก label | 51.475% | 0.5118 |
| Vibration, Temperature ดั้งเดิม | 49.85% | 0.4941 |
| เซนเซอร์ดั้งเดิม 6 ตัว | 48.475% | 0.4753 |

สร้าง Current ตามสูตรด้วย RandomState42 แล้วตรงกับ processed CSV ทุกแถว จึงระบุสาเหตุได้จากทั้ง source และการทำซ้ำ คะแนน 48–51% ไม่ใช่การเปรียบเทียบผู้ชนะใหม่ แต่เป็น controlled ablation ด้วยโมเดล/splitเดียวกัน

## ประเด็นรอง

- scaler.fit_transform(X_train) และ transform(X_test) บรรทัด 601–603 ทำถูกต้อง ส่วนนี้ไม่รั่ว
- thresholds.json ถูกคำนวณจากข้อมูลทุกแถวก่อนแบ่งชุด (main บรรทัด 795–799; extract_safety_thresholds บรรทัด 386–387) ต้องคำนวณจาก train/calibration เท่านั้น หากใช้ประเมินระบบแจ้งเตือน end-to-end ประเด็นนี้ไม่ใช่ตัวสร้างคะแนน RF 87.35% เพราะ thresholds ไม่ได้เข้า RF features
- ค่าที่เรียกว่า Current เป็นสูตรจำลอง ไม่ใช่กระแสวัดจริง ไม่มีหลักฐานจาก ZIP ที่ยืนยันสมการและค่าสัมประสิทธิ์กับปั๊มจริง จึงใช้เป็นแบบจำลองสาธิตได้ แต่ไม่ควรเรียก validated physical measurement
- llm_diagnostic.py บรรทัด 96–100: auto mode ใช้ OpenAI เมื่อ Ollama ไม่พร้อมและมี OPENAI_API_KEY จึงไม่รับประกัน local-only หากต้องการออฟไลน์ให้เลือก ollama/edge_expert โดยตรงและปิดทาง external provider
- predict_proba ถูกนำไปแสดงเป็นความเสี่ยงเสีย แต่ยังไม่พบขั้นตอน probability calibration หรือ independent validation ของความเสี่ยงนั้น คะแนนโมเดลจึงยังไม่ใช่ความน่าจะเป็นเสียจริงที่ยืนยันแล้ว

## แบบไหนใช้ได้

1. งาน supervised บนชุดเดิม: ใช้เฉพาะเซนเซอร์จริง หรือฟีเจอร์จากอินพุตที่มีจริง ณ เวลาทำนาย ไม่แตะ Maintenance_Flag
2. งาน simulator: สร้าง fault state แล้วสร้างเซนเซอร์จาก state ได้ หากประกาศชัดว่าคือ synthetic benchmark การประเมินวัดการเรียนรู้ simulator ไม่ใช่ความแม่นยำจาก Kaggle เดิม ต้องทดสอบ simulator/operating regimes ที่ไม่เคยเห็นและข้อมูลจริงเพิ่มเติม
3. งานปั๊มจริง: เก็บกระแสจากเซนเซอร์จริงพร้อมเวลาและผลตรวจซ่อม แล้วฝึกใหม่และประเมินแยกเครื่อง/ช่วงเวลา ไม่ควรแทน Current จำลองด้วยกระแสจริงแล้วถือว่า accuracy 87.35% ยังคงใช้ได้

ไม่ได้แก้ ZIP เดิม ไม่ได้รัน source ใน ZIP และไม่ได้โหลด model.pkl/scaler.pkl ใน ZIP ผล ablation มาจากการเขียนสูตรและเทรนใหม่ด้วย sklearn ใน environment ของโปรเจกต์
