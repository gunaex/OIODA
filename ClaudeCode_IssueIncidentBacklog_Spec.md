# Kickoff Spec — Issue / Incident / Backlog Board
> ปลดล็อก `promote-issue` endpoint ที่เป็น stub (501) ใน Project Note module ให้ใช้งานได้จริง

## 1. แนวคิด
3 board แยกกันแต่ link กันได้ตามวงจรชีวิตจริง:
```
Backlog --(promote)--> Issue --(confirm เกิดจริง)--> Incident
Note --(promote-issue)--> Issue
Issue/Incident --(promote)--> Task (ให้คนไปแก้)
```

## 2. Data Model

### `board_items` (ตารางเดียวใช้ร่วมกัน 3 ประเภท แยกด้วย `item_type`)
| column | type | note |
|---|---|---|
| id | INTEGER PK | |
| item_type | TEXT | `issue` \| `incident` \| `backlog` |
| item_code | TEXT | เช่น ISS-001, INC-001, BLG-001 (prefix ตาม item_type) |
| title | TEXT | |
| description | TEXT | |
| severity | TEXT | Low/Medium/High/Critical (ใช้กับ issue/incident, nullable สำหรับ backlog) |
| status | TEXT | Open/InProgress/Resolved/Closed (issue/incident) หรือ Backlog/Planned/InProgress/Done (backlog) |
| phase | TEXT | อ้างอิง phase enum เดิม (UR/DR/DN/PU/ST/UT/TR/IP/MA), nullable |
| owner | TEXT | |
| linked_note_id | INTEGER FK → notes.id | nullable, ที่มาถ้า promote มาจาก note |
| linked_task_id | INTEGER FK → tasks.id | nullable, ถ้า promote ไป task แล้ว |
| promoted_from_id | INTEGER FK → board_items.id | nullable, self-reference (backlog→issue, issue→incident) |
| sla_due_date | DATE | nullable — คำนวณจาก severity + business-day logic (reuse pattern เดียวกับที่มีอยู่ใน SPARK ถ้ามี hook ไว้แล้ว, ถ้ายังไม่มีใน MVP นี้ให้ทำแบบ calendar day ธรรมดาไปก่อน) |
| created_at | DATETIME | |
| updated_at | DATETIME | |

## 3. API Endpoints

```
GET    /api/{slug}/board-items?type=issue|incident|backlog     list แยกตาม type
POST   /api/{slug}/board-items                                  create (ระบุ item_type ตอนสร้าง)
PUT    /api/{slug}/board-items/{id}
DELETE /api/{slug}/board-items/{id}

POST   /api/{slug}/board-items/{id}/promote                     
  body: { "target_type": "issue" | "incident" | "task" }
  - backlog -> issue: สร้าง issue ใหม่ copy title/description, ตั้ง promoted_from_id ชี้กลับ backlog เดิม, backlog.status = "Promoted"
  - issue -> incident: เช่นเดียวกัน
  - issue/incident -> task: สร้าง task ใหม่ (title=item title), ตั้ง linked_task_id

# แก้ endpoint เดิมที่เป็น stub
POST   /api/{slug}/notes/{id}/promote-issue                     
  - สร้าง board_items (item_type=issue) จาก note.content
  - update note.status = PromotedToIssue, linked_issue_id = ...
  - **ลบ 501 stub ออก แทนที่ด้วย logic จริงตัวนี้**

GET    /api/{slug}/board-items/export?type=issue|incident|backlog   → Excel export (รูปแบบเดียวกับ export อื่นๆ ในระบบ)
```

## 4. Frontend

1. **3 tabs แยกกันในหน้าเดียว**: Issue / Incident / Backlog — ใช้ Kanban view (column ตาม status) หรือ list view สลับได้
2. Card แต่ละใบโชว์: item_code, title, severity badge (สีตาม severity), owner, ปุ่ม "Promote →"
3. ปุ่ม Promote เปิด modal เลือกปลายทาง (Issue→Incident หรือ →Task) ตาม item_type ปัจจุบัน
4. หน้า Note List (มีอยู่แล้ว) — ปุ่ม "Promote to Issue" ต้องใช้งานได้จริงแล้ว (ไม่ error 501 อีกต่อไป)
5. Filter by severity/status/phase/owner

## 5. Build Order
1. Migration: สร้างตาราง `board_items`
2. Backend CRUD + promote logic (ทุก path: backlog→issue, issue→incident, issue/incident→task)
3. แก้ `notes/{id}/promote-issue` จาก stub เป็น logic จริง — ทดสอบว่า note เก่าที่เคย promote ไม่ได้ (เพราะติด 501) ตอนนี้ทำงานได้แล้ว
4. Frontend: 3-tab board + Kanban/List view toggle
5. Export Excel
6. ทดสอบ end-to-end: สร้าง note → promote to issue → promote issue to incident → promote incident to task → เช็คว่า link ย้อนกลับ (linked_note_id, promoted_from_id, linked_task_id) ถูกต้องทุกจุด

## Acceptance Criteria
- [ ] `notes/{id}/promote-issue` ไม่ return 501 อีกต่อไป ทำงานได้จริง
- [ ] Promote path ทุกเส้นทาง (backlog→issue→incident→task) เก็บ trail ย้อนกลับได้ครบ ไม่หลุดหาย
- [ ] Export Excel แยกตาม item_type ได้ถูกต้อง
