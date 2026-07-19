# Kickoff Spec — Report Generator (Excel) + Project Note + Quick Wins + Google Reserved

## ส่วนที่ 1: Report Generator — แก้ Pain Point เรื่องเสียเวลาทำเอกสาร/รายงาน

**Pain point ของ user:** รวมเอกสาร/ทำ report ส่ง user ใช้เวลานานเกินจำเป็น ต้องการให้ export เป็น **Excel เท่านั้น (ไม่เอา Word)**

### 1.1 Report ที่ต้อง generate อัตโนมัติ (ดึงจากข้อมูลที่มีอยู่แล้วในระบบ ไม่ต้องพิมพ์ซ้ำ)

| Report | ที่มาของข้อมูล | Sheet ใน Excel output |
|---|---|---|
| **Daily Report** | Task ที่ update สถานะวันนี้ + Note ที่สร้างวันนี้ | 1 sheet: Task Updates Today |
| **Weekly Report** | Task/Function/Document status เปลี่ยนในช่วง 7 วัน, % completion ต่อ phase | 2 sheets: Progress Summary, Detail Log |
| **Monthly Report** | สรุประดับ phase ทั้งหมด, overdue task, mandatory document ที่ยังไม่ confirm | 3 sheets: Executive Summary, Phase Breakdown, Risk/Overdue |
| **Phase Closure Report** | ทุก `documents` ใน phase นั้น (จาก `document_templates` auto-populate) + สถานะ + signoff ล่าสุด + defect summary (ถ้ามี) | 2 sheets: Document Checklist (M/O พร้อมสถานะ Confirmed/Pending), Signoff Detail |

### 1.2 API Endpoint

```
GET /api/{slug}/reports/daily?date=YYYY-MM-DD          → xlsx download
GET /api/{slug}/reports/weekly?week_start=YYYY-MM-DD   → xlsx download
GET /api/{slug}/reports/monthly?month=YYYY-MM          → xlsx download
GET /api/{slug}/reports/phase-closure?phase_code=50    → xlsx download
```

### 1.3 หลักการสร้าง Excel (สำคัญ — ต้องทำให้ "ใช้แทนของเดิมได้จริง")
- ใช้ `openpyxl` ฝั่ง backend, header สีตัดกับข้อมูล, font Arial/Calibri มาตรฐาน
- Phase Closure Report: คอลัมน์ doc_code, doc_name, mandatory_level (M/O), status, confirmed_date, signed_by — ให้หน้าตาพร้อมส่งลูกค้าได้เลยโดยไม่ต้องแต่งเพิ่ม
- ทุก Report มีปุ่ม "Generate" ในหน้า Dashboard/Project overview — เลือกช่วงวันที่/phase แล้วกดโหลดได้ทันที ไม่ต้องเข้าไปนั่งรวบรวมเองทีละที่แบบเดิม
- เก็บ log ว่า generate report ไหนไปแล้วเมื่อไหร่ (ตาราง `report_generation_log`: id, report_type, params_json, generated_at, generated_by) กันลืมว่าส่งรอบไหนไปแล้ว

### 1.4 Build Order
1. Backend: `report_generation_log` table
2. Backend: query logic รวมข้อมูลแต่ละ report type (reuse query จาก Task/Function/Document module เดิม)
3. Backend: openpyxl builder function ต่อ report type (แยกไฟล์ `reports/daily.py`, `weekly.py`, `monthly.py`, `phase_closure.py`)
4. Frontend: ปุ่ม Generate Report ในหน้า Dashboard พร้อม date/phase picker
5. ทดสอบ: generate ทั้ง 4 แบบ เทียบกับข้อมูลจริงในระบบว่าตรง ไม่ตกหล่น

---

## ส่วนที่ 2: Project Note (Quick Capture)

**Use case:** เจองานด่วนตอน morning brief หรือระหว่างวัน ต้อง note ไว้ก่อนเร็วๆ แล้วค่อยย้ายไปเป็น Task/Issue ทีหลัง

### 2.1 Data Model

```
notes
- id
- content (TEXT, free text สั้นๆ)
- status: Open / PromotedToTask / PromotedToIssue
- linked_task_id (nullable FK)
- linked_issue_id (nullable FK, ไว้รอ Issue module ที่จะทำใน phase ถัดไป)
- created_at
```

### 2.2 API
```
GET    /api/{slug}/notes                     list (filter status=Open ก่อนเป็น default)
POST   /api/{slug}/notes                     สร้าง note ใหม่ (content เดียว ไม่บังคับ field อื่น)
POST   /api/{slug}/notes/{id}/promote-task   สร้าง Task จาก note (prefill title=content) → update note.status=PromotedToTask, linked_task_id
DELETE /api/{slug}/notes/{id}
```
(`promote-issue` เตรียม endpoint ไว้แต่ยังไม่ต้อง implement เต็ม เพราะ Issue board ยังไม่ถูกสร้าง — ทำ stub ที่ return 501 Not Implemented ไปก่อน)

### 2.3 Frontend
- **Quick Note bar** — ลอย (floating widget) มุมล่างขวาทุกหน้าในระบบ พิมพ์แล้ว Enter บันทึกทันที ไม่ต้องเปลี่ยนหน้า
- **Note List page** — list ของ note ที่ status=Open, ปุ่ม "Promote to Task" ต่อรายการ
- Note ที่ promote แล้วยังเห็นใน list แต่ mark ว่า "→ Task #123" (มี link คลิกไปดู task นั้นได้)

---

## ส่วนที่ 3: Quick-win Cross-cutting Features (ทำแทรกได้ ไม่ชนกับ module อื่น)

1. **Global Search** — endpoint เดียว `GET /api/{slug}/search?q=...` ค้นข้าม functions/tasks/documents/notes (SQL LIKE), แสดงผลรวมเป็น list พร้อม type badge
2. **Comment ต่อรายการ** — ตาราง `comments` (id, entity_type, entity_id, content, created_by, created_at) ใช้ร่วมกันได้ทั้ง Task/Document
3. **Activity Log แบบเบา** — ตาราง `activity_log` (id, entity_type, entity_id, field_changed, old_value, new_value, changed_by, changed_at) — insert อัตโนมัติทุกครั้งที่มี PUT/status change บน functions/tasks/documents
4. **Export เฉพาะที่ filter อยู่** — ทุก export endpoint (functions/tasks/documents) รับ query params เดียวกับที่ list endpoint ใช้ filter อยู่แล้ว ส่งต่อไปเป็นเงื่อนไข query ก่อน export
5. **Clone/Duplicate** — `POST /api/{slug}/functions/{id}/clone` และเทียบเท่าใน tasks — copy ทุก field ยกเว้น id/code (generate code ใหม่อัตโนมัติ)
6. **Status Badge สี** — Tailwind class mapping ต่อ status value ใน component กลาง `<StatusBadge status={x}/>` ใช้ร่วมทุกหน้า
7. **My Tasks View** — filter tasks by `owner` param, เพิ่ม tab "My Tasks" ในหน้า Task List (ใช้ dropdown เลือกชื่อตัวเองไปก่อนถ้ายังไม่มี login จริง)
8. **Keyboard Shortcuts** — `react-hotkeys-hook`: `/` = focus search bar, `n` = open quick note bar, `Esc` = close modal ที่เปิดอยู่

---

## ส่วนที่ 4: Google Workspace — เตรียมไว้เฉยๆ (ยังไม่ implement จริง)

ตามที่ตกลง — เก็บโครงไว้ก่อน ไม่ต่อ OAuth ตอนนี้:

- เพิ่ม column nullable: `documents.google_drive_file_id` (TEXT, nullable)
- เพิ่ม column nullable: `gantt_items.google_calendar_event_id` (TEXT, nullable)
- เพิ่ม column nullable: `projects.notification_email` (TEXT, nullable) — เผื่อฟีเจอร์ email แจ้งเตือนในอนาคตใช้ field เดียวกันได้เลย
- **ห้าม implement OAuth flow หรือ API call จริงตอนนี้** แค่เตรียมที่เก็บข้อมูลไว้ ป้องกันต้อง migrate ใหญ่ตอนทำจริงใน phase หลัง

---

## Build Order รวมของเอกสารนี้ (แนะนำลำดับ)
1. Google reserved columns (เร็วสุด แค่ ALTER TABLE เพิ่ม nullable column ทำพร้อมกับงานอื่นได้เลย)
2. Quick-win ทั้ง 8 ข้อ (เบา ไม่ผูกกัน ทำสลับกับงานอื่นได้)
3. Project Note module
4. Report Generator (ใหญ่สุด ควรทำหลังสุดเพราะต้องรอ Phase 2 Document module + phase-model correction เสถียรก่อน)
