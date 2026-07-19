# Kickoff Spec — Slippage Predictor (Rule-based, ไม่ใช้ AI/ML)
> ทำพ่วงไปกับ STEP 2 Frontend (Resource Pool/Heatmap/Dashboard) ได้เลย เพราะแสดงผลบน Dashboard เดียวกัน — ทั้งหมดเป็นแค่ SQL query + arithmetic ธรรมดา ไม่มี ML/AI dependency ใดๆ

## 1. หลักการ (3 สัญญาณ รวมกันเป็น slippage score)

### 1.1 Gantt-based signal
เทียบ % เวลาที่ผ่านไปของ task กับ % progress จริง:
```
elapsed_pct = (today - start_date) / (baseline_end - start_date) * 100
gap = elapsed_pct - progress
ถ้า gap > threshold (default 20) -> flag "at risk"
```
ใช้ `baseline_start`/`baseline_end` ที่มีอยู่แล้วในตาราง `gantt_items` (จาก MVP เดิม) — ไม่ต้องเพิ่ม column ใหม่

### 1.2 Document-based signal (ต่อ phase)
```
docs_remaining = mandatory documents ที่ยังไม่ Confirmed ใน phase นี้
days_left_in_phase = phase's Gantt milestone end_date - today
ratio = docs_remaining / days_left_in_phase
ถ้า days_left_in_phase <= 0 และ docs_remaining > 0 -> "overdue" (สูงสุด)
ถ้า ratio > threshold (default 1 doc/day) -> flag "at risk"
```
Reuse join เดียวกับที่ Phase Closure Report และ RAG logic ใช้อยู่แล้ว (document_templates + documents + gantt milestone)

### 1.3 Historical average delay (ไม่ใช่ ML — แค่ arithmetic average)
```
สำหรับ task/phase ที่ "เสร็จแล้ว" ในอดีต (status=Done, มี actual_end กับ baseline_end)
avg_delay_days = AVERAGE(actual_end - baseline_end) ต่อ phase (หรือต่อ owner ก็ได้ถ้าอยากละเอียดกว่า)
ใช้ avg_delay_days นี้ทำนาย task/phase ที่กำลังทำอยู่ตอนนี้ -> "expected_completion = baseline_end + avg_delay_days"
```
**หมายเหตุ:** ถ้ายังไม่มีข้อมูลในอดีตมากพอ (เช่น < 3 records) ให้ return `null`/ไม่แสดง signal นี้ แทนการเดา — อย่าทำนายจากข้อมูลน้อยเกินไปจนไม่น่าเชื่อถือ

## 2. Data Model — ไม่ต้องเพิ่มตารางใหม่
ทุกอย่างคำนวณแบบ on-the-fly จาก query (ไม่ต้องเก็บ prediction ไว้เป็น state แยก เพราะข้อมูลเปลี่ยนทุกวัน คำนวณสดดีกว่า) ยกเว้น:

### `slippage_snapshots` (optional, เก็บ history ไว้ดู trend ย้อนหลังได้)
| column | type | note |
|---|---|---|
| id | INTEGER PK | |
| snapshot_date | DATE | |
| entity_type | TEXT | `task` \| `phase` |
| entity_id | INTEGER | |
| gap_score | REAL | จากข้อ 1.1/1.2 |
| flag | TEXT | `on_track` \| `at_risk` \| `overdue` |

(ตารางนี้ทำทีหลังก็ได้ถ้าเวลาไม่พอ — MVP แรกให้คำนวณสดพอ ไม่บันทึก history ก็ใช้งานได้)

## 3. API Endpoints
```
GET /api/{slug}/slippage/tasks             list task ที่ flag at_risk/overdue พร้อม gap score
GET /api/{slug}/slippage/phases            list phase ที่ flag at_risk/overdue (จาก document signal)
GET /api/{slug}/slippage/summary           รวมทั้ง 2 อย่างข้างบน สำหรับแสดงใน Project Dashboard
```

## 4. Frontend — ผูกเข้า Dashboard ที่กำลังทำอยู่พอดี
- เพิ่ม section "⚠️ Slippage Warning" ใน **Project Dashboard** (ที่กำลังสร้างใน STEP 2 อยู่แล้ว) — แสดง task/phase ที่ flag at_risk/overdue เรียงตาม gap score มากไปน้อย
- Badge สี: `on_track` = เขียว, `at_risk` = เหลือง, `overdue` = แดง (ใช้ `<StatusBadge>` component เดียวกับที่มีอยู่แล้ว)
- ถ้ามี historical average (ข้อ 1.3) ให้โชว์ "คาดว่าจะเสร็จ: {expected_completion}" ต่อท้าย task นั้น — ถ้าไม่มีข้อมูลพอ (null) ไม่ต้องโชว์บรรทัดนี้เลย

## 5. Build Order
1. Backend: query logic ข้อ 1.1 (Gantt-based) — endpoint `/slippage/tasks`
2. Backend: query logic ข้อ 1.2 (Document-based) — endpoint `/slippage/phases`
3. Backend: historical average ข้อ 1.3 (ถ้ามีข้อมูลพอ — ข้ามได้ถ้า project ยังใหม่ไม่มี Done task เลย)
4. Backend: `/slippage/summary` รวมทั้งหมด
5. Frontend: เพิ่ม section ใน Project Dashboard ตามข้อ 4
6. RBAC: ผูก auth check เหมือน endpoint อื่น (client_viewer อ่านได้อย่างเดียวเหมือน Dashboard อื่นๆ)
7. ทดสอบ: สร้าง task ที่ progress ช้ากว่าแผนจงใจ ดูว่า flag at_risk ขึ้นจริง, ทดสอบ phase ที่เอกสารค้างเยอะใกล้ deadline ดูว่า flag ถูกต้อง

## Acceptance Criteria
- [ ] Task ที่ progress ช้ากว่า elapsed time เกิน threshold ขึ้น flag at_risk/overdue ถูกต้อง
- [ ] Phase ที่เอกสาร mandatory ค้างเยอะใกล้ deadline ขึ้น flag ถูกต้อง
- [ ] Project ใหม่ที่ไม่มีข้อมูลในอดีตเลย ไม่ error และไม่แสดง historical prediction (แสดงแค่ signal 1.1/1.2)
- [ ] ไม่มี ML/AI library หรือ external API call ใดๆ ถูกเพิ่มเข้ามาในโค้ด — เป็น SQL/Python arithmetic ล้วน
