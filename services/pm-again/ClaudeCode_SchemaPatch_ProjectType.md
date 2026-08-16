# Schema Patch — Function List: Support "Simple" + "Estimate/SI" Project Types
> ส่งต่อให้ Claude Code เพิ่มเติมจาก Kickoff Spec เดิม (ไม่ต้อง rebuild ใหม่ทั้งหมด แค่ extend ตาราง `functions` + `projects`)

## เหตุผล
พบ 2 รูปแบบ project จริงที่ต้องรองรับ:
- **Simple** (สไตล์ Vimut) — function list เรียบง่าย: name, module, phase, owner, status
- **Estimate/SI** (สไตล์ CFW) — ต้องมี priority, complexity, PD breakdown ต่อ role, pricing, performance target (ใช้ตอนทำ proposal เสนอราคาลูกค้า)

แนวทาง: **ตารางเดียว ใช้ร่วมกัน** — core fields บังคับทุก project, extension fields เป็น nullable สำหรับ project type `estimate` เท่านั้น ไม่แยก DB/schema ต่อ type

---

## 1. แก้ตาราง `projects`
เพิ่ม column:

| column | type | note |
|---|---|---|
| project_type | TEXT | `simple` \| `estimate` — กำหนดตอนสร้าง project, ใช้ควบคุมว่า Frontend จะโชว์ field ไหนบ้าง |

---

## 2. แก้ตาราง `functions` — เพิ่ม column ใหม่ทั้งหมด (nullable)

### Core fields (มีอยู่แล้วจาก spec เดิม — ไม่เปลี่ยน)
`id, function_code, name, description, type, phase, owner, status, created_at, updated_at`

### Extension fields ใหม่ (nullable — ใช้เมื่อ project_type = estimate)

| column | type | note |
|---|---|---|
| module | TEXT | กลุ่ม function (เช่น "Recipe & BOM") — **แนะนำใช้แม้ project แบบ simple ก็ได้** เพราะช่วยจัดกลุ่มเสมอ |
| priority | TEXT | Must / Should / Could / Won't (MoSCoW) |
| scope_class | TEXT | เช่น Core, Core/Overlap, Extended |
| complexity | TEXT | Low / Medium / High |
| pd_ba | REAL | Business Analyst person-days |
| pd_ux | REAL | UX person-days |
| pd_fe | REAL | Frontend person-days |
| pd_be | REAL | Backend person-days |
| pd_int_data | REAL | Integration/Data person-days |
| pd_qa | REAL | QA person-days |
| pd_devops | REAL | DevOps person-days |
| pd_total | REAL | รวมทุก role — **คำนวณอัตโนมัติจากผลรวม pd_* ฝั่ง backend ก่อน save ไม่ต้องให้ user กรอกเอง** |
| performance_class | TEXT | เช่น Batch/Async, Transactional, Calculation/CRUD |
| target_option_a | TEXT | performance target ระดับ A |
| target_option_b | TEXT | performance target ระดับ B |
| target_option_c | TEXT | performance target ระดับ C |
| performance_note | TEXT | acceptance note |
| price_thb | REAL | ราคาต่อ function (บาท) |
| commercial_note | TEXT | หมายเหตุการคิดราคา |

---

## 3. Frontend — Conditional Field Display

- ตอนสร้าง "New Project": เพิ่ม dropdown เลือก **Project Type** (`Simple` / `Estimate-SI`)
- หน้า Function List:
  - `project_type = simple` → โชว์เฉพาะ core fields + module
  - `project_type = estimate` → โชว์ core fields + extension fields ทั้งหมด (จัดเป็น section แยก: "Estimate & Pricing" collapsible)
- Field ที่ไม่ได้ใช้ตาม type จะเก็บเป็น `NULL` ในฐานข้อมูล ไม่ error, ไม่บังคับกรอก

---

## 4. Import/Export Template — ต้องมี 2 แบบ

- `GET /api/{slug}/functions/import-template?type=simple` → เฉพาะ core columns
- `GET /api/{slug}/functions/import-template?type=estimate` → core + extension columns ทั้งหมด (ตรงกับไฟล์ CFW ที่แนบมา)
- Import endpoint ต้อง detect จาก column header ว่าเป็น template แบบไหน (หรือส่ง `type` มาพร้อม request) แล้ว validate ตามชุด column ของ type นั้น

---

## 5. Build Task เพิ่มเติมสำหรับ Claude Code

1. Migrate `projects` table: เพิ่ม `project_type` column
2. Migrate `functions` table: เพิ่ม extension columns ทั้งหมด (nullable)
3. Backend: auto-calculate `pd_total` = sum(pd_ba, pd_ux, pd_fe, pd_be, pd_int_data, pd_qa, pd_devops) ก่อน insert/update
4. Frontend: เพิ่ม Project Type selector ตอนสร้าง project + conditional rendering ใน Function List page
5. แก้ import/export endpoint ให้รองรับ 2 template type ตามข้อ 4

---

## หมายเหตุ
ไฟล์ตัวอย่าง `CFW_FunctionList_ImportReady.xlsx` (แนบแยก) คือข้อมูลจริงจาก project ใหม่ — ใช้ทดสอบ import ทันทีที่ทำ Estimate-type schema เสร็จ header ตรงกับ column list ในข้อ 2 แล้ว
