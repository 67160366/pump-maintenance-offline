# ผลทดลองเพิ่มฟีเจอร์และเปลี่ยนโมเดล

เป้าหมาย: accuracy 80% บน label เดิม โดยไม่แก้ข้อมูลต้นฉบับ

โมเดลที่เลือกจาก validation: **mlp_32_16**

- Test accuracy: **50.10%**, 95% Wilson interval 48.55%–51.65%
- Balanced accuracy: 50.12%, ROC-AUC: 0.4969, PR-AUC: 0.4913
- Precision: 49.93%, recall: 54.89%, F1: 0.5229
- Confusion matrix [0,1]: [[910, 1097], [899, 1094]]

| Model | CV accuracy | Validation accuracy | Validation ROC-AUC | Size (KiB) |
|---|---:|---:|---:|---:|
| mlp_32_16 | 50.72% | 51.25% | 0.5069 | 26.4 |
| histgb_engineered_leaves31 | 50.42% | 50.55% | 0.5070 | 147.7 |
| logistic_raw_C0.01 | 50.22% | 50.40% | 0.5063 | 1.6 |
| logistic_raw_C1.0 | 50.22% | 50.35% | 0.5064 | 1.6 |
| histgb_engineered_leaves7 | 50.37% | 50.32% | 0.5077 | 90.3 |
| logistic_engineered_C0.01 | 50.18% | 50.18% | 0.5038 | 2.9 |
| dummy_majority | 50.16% | 50.15% | 0.5000 | 0.9 |
| histgb_raw_leaves7 | 50.28% | 50.15% | 0.4909 | 23.5 |
| extratrees_engineered | 50.16% | 50.15% | 0.4937 | 55730.2 |
| rf_deep_raw | 50.16% | 50.15% | 0.5030 | 45053.5 |
| knn_15 | 50.16% | 50.15% | 0.4948 | 815.9 |
| histgb_with_pump | 50.25% | 50.15% | 0.5100 | 106.2 |
| knn_75 | 50.24% | 50.05% | 0.4985 | 815.9 |
| rbf_kernel_approx | 51.11% | 49.73% | 0.4981 | 528.9 |
| extratrees_raw | 50.30% | 49.53% | 0.4963 | 52788.5 |
| histgb_raw_leaves31 | 50.27% | 49.45% | 0.4972 | 49.7 |
| logistic_engineered_C1.0 | 50.35% | 49.38% | 0.4975 | 2.9 |

การแบ่งข้อมูลยึด indices เดิม ไม่มีการย้าย test ไป train เลือก threshold บน 3-fold OOF ใน train และเลือกโมเดลจาก validation เท่านั้น ก่อนประเมินผู้ชนะบน test หนึ่งครั้งในรอบนี้ อย่างไรก็ตาม test นี้เคยใช้รายงานในรอบก่อน จึงเป็นผลสำรวจ ไม่ใช่ชุดทดสอบใหม่ที่ยังไม่เคยเห็น

ฟีเจอร์ทดลอง: products/squares ของเซนเซอร์, log1p, ratios และ Pump_ID แบบ one-hot ที่ fit เฉพาะ train ไม่มี timestamp จึงไม่สร้าง rolling หรือ lag จากลำดับแถว อัตราส่วนยังไม่ใช่ค่าทางฟิสิกส์ที่ยืนยันเพราะไม่ทราบหน่วยและจุดติดตั้งเซนเซอร์

ผลควบคุมสลับ label และสถิติสัญญาณแต่ละฟีเจอร์อยู่ใน report.json การทดสอบนี้ไม่พิสูจน์ว่า label เป็นข้อมูลสุ่ม แต่ช่วยตรวจว่าผลโมเดลต่างจากการเรียนรู้ label สุ่มมากน้อยเพียงใด

ถ้าไม่ถึง 80%: ตรวจวิธีสร้าง Maintenance_Flag กับเจ้าของชุดข้อมูลก่อน แล้วเก็บค่าจริงพร้อม timestamp, operating load และผลตรวจซ่อมที่ยืนยันได้ การสร้าง label ใหม่ตามกฎอุณหภูมิ/การสั่นจะเปลี่ยนโจทย์เป็นเลียนแบบกฎ ไม่ใช่เพิ่มความแม่นยำของโจทย์เดิม ไม่ควรนำมารวมเป็นผล 80% ของชุดนี้

candidate.joblib เป็น research artifact ใช้ SensorFeatures จาก experiments.py และต้องส่ง dataframe ที่มี Pump_ID กับเซนเซอร์ทั้ง 6 ตัว ไม่แทนที่ artifacts/model.joblib หรือเสียบเข้า pump.py replay โดยตรง
