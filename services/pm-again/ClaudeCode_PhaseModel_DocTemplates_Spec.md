# Correction Spec — Real Phase Model + Document Template Master
> สำคัญ: แก้ก่อนไปต่อ เพราะ phase enum ที่ใช้อยู่ตอนนี้ (UR/DR/PU-PT/IFT/BCT/UAT/IP) เป็นแค่การเดา — ของจริงจากเอกสารมาตรฐานบริษัทคือชุดนี้:

## 1. Phase Enum ที่ถูกต้อง (แทนของเดิมทั้งหมด)

| phase_code | phase_name | ความหมาย |
|---|---|---|
| 10 | UR | User Requirement |
| 20 | DR | Design Requirement |
| 30 | DN | Design (Program Spec/Object List/CFW Config) |
| 40 | PU | Program Unit (Migration sheet, PT Script/Summary) |
| 50 | ST | System Test (รวม IFT + BCT + Response/Stress/Irregular/Breakdown Test) |
| 60 | UT | User Test |
| 70 | TR | Trial |
| 80 | IP | Implementation |
| 90 | MA | Maintenance |

**Action:** แก้ `phase` column ใน `functions`, `tasks`, `documents`, `gantt_items` (ทุกที่ที่อ้างอิง phase) ให้ใช้ enum ชุดนี้แทน — เขียน migration script แปลงค่าเก่าที่เคย insert ไปแล้วด้วย (ถ้ามี mapping ที่พอเทียบได้ เช่น UAT เดิม → UT, BCT/IFT เดิม → ST)

## 2. ตารางใหม่: `document_templates` (Global reference, ไม่ผูกกับ project ใดโดยเฉพาะ)

Import ไฟล์ `DocumentTemplateMaster_Seed.xlsx` (แนบมาด้วย) เข้าตารางนี้ครั้งเดียวตอน setup ระบบ:

| column | type | note |
|---|---|---|
| id | INTEGER PK | |
| doc_code | INTEGER | เช่น 101, 102 (unique) |
| doc_name | TEXT | เช่น "Business Flow" |
| phase_code | INTEGER | อ้างอิง phase enum ข้อ 1 |
| phase_name | TEXT | |
| doc_set_no | TEXT | |
| doc_set_name | TEXT | |
| mandatory_critical | TEXT | M/O — ใช้กับ project category = Critical |
| mandatory_non_critical | TEXT | M/O |
| mandatory_ma | TEXT | M/O |
| mandatory_rollout | TEXT | M/O |
| defined_by | TEXT | role ผู้ให้ข้อมูล |
| documented_by | TEXT | role ผู้จัดทำเอกสาร |
| approved_by | TEXT | role ผู้อนุมัติ |

## 3. เพิ่ม `project_category` ในตาราง `projects`

| column | type | note |
|---|---|---|
| project_category | TEXT | `critical` \| `non_critical` \| `ma` \| `rollout` — เลือกตอนสร้าง project |

## 4. Auto-populate เอกสารตอนสร้าง Project ใหม่

เมื่อสร้าง project ใหม่และเลือก `project_category`:
- Query `document_templates` ทุกแถวที่ column `mandatory_{category}` = `'M'`
- Insert เข้า `documents` (ตารางที่มีอยู่แล้วจาก Phase 2) หนึ่งแถวต่อ doc_code ที่เป็น Mandatory โดย status เริ่มที่ `Draft`, `doc_code`/`phase`/`title` ดึงมาจาก template
- เอกสารที่เป็น Optional (`'O'`) **ไม่ auto-insert** แต่โชว์เป็น "Suggested (Optional)" ในหน้า Document List ให้ user กด "Add" เองถ้าต้องการ

## 5. ผลลัพธ์ที่ต้องการ
- สร้าง project ใหม่ → เอกสารที่ต้อง confirm ทั้งหมดโผล่มาอัตโนมัติตาม category ของ project นั้น ไม่ต้องมานั่งไล่เช็คทีละ phase เอง (ตรง pain point เรื่องเสียเวลาทำเอกสาร)
- Phase enum ตรงกับของจริงที่ทีมใช้ ทำให้ report/Phase Closure ที่จะทำต่อ (ดูอีกไฟล์) อ้างอิงถูกต้อง

## Build Order
1. Migration: เพิ่ม `project_category` ใน projects, สร้างตาราง `document_templates`
2. Import seed data จาก `DocumentTemplateMaster_Seed.xlsx`
3. แก้ phase enum ทุกจุดที่ใช้ (functions/tasks/documents/gantt_items) + migration script แปลงค่าเก่า
4. Backend: auto-populate logic ตอนสร้าง project (ข้อ 4)
5. Frontend: เพิ่ม dropdown Project Category ตอนสร้าง project, ปรับหน้า Document List ให้โชว์ Suggested (Optional) docs แยกจาก Mandatory ที่ auto-insert แล้ว
