# ผลทดลอง AI4I 2020

ข้อมูล 10,000 แถว label เดิม: {'0': 9661, '1': 339}

| Split | Model | Accuracy | Baseline accuracy | Balanced accuracy | Precision | Recall | F1 | PR-AUC |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| ordered_primary | forest_physics_12 | 99.25% | 98.05% | 85.80% | 87.50% | 71.79% | 0.7887 | 0.7682 |
| random_secondary | histgb_physics_7 | 99.10% | 96.60% | 91.73% | 89.06% | 83.82% | 0.8636 | 0.9031 |

เลือกโมเดลและ threshold จาก validation โดย maximize F1 ของเครื่องเสีย แล้วเลือกขนาดเล็กที่สุดที่ F1 ห่างตัวดีที่สุดไม่เกิน 0.01 ไม่ใช้ test เลือกโมเดล

Primary: แบ่งตามลำดับแถวเดิม 60/20/20 เพื่อแยกส่วนกระบวนการที่ใกล้กัน ไม่ถือว่าเป็น timestamp จริง Secondary: stratified random 60/20/20 แยกรายงาน ไม่เลือก split ที่ให้คะแนนสูงกว่า

อินพุต: Type และเซนเซอร์ 5 ตัว ฟีเจอร์เสริมคือส่วนต่างอุณหภูมิ กำลัง torque*rpm*2pi/60 และ wear*torque ไม่ใช้ ID หรือ TWF/HDF/PWF/OSF/RNF เป็นอินพุต ไม่เปลี่ยน target

เป็นข้อมูลสังเคราะห์ของกระบวนการผลิต ไม่ใช่ข้อมูลปั๊มจริงหรือ remaining useful life คะแนนไม่ยืนยันผลกับเครื่องจริง ต้องทดสอบ Pi และ LLM จริงแยกต่างหาก

Source: https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset
License: CC BY 4.0. Credit: AI4I 2020 Predictive Maintenance Dataset, UCI Machine Learning Repository, DOI 10.24432/C5HS5C.
