# Kickoff Spec — Phase 2: Document Repository + Sign-off Workflow
> ทำต่อจาก MVP (Function List / Gantt / Task / Import-Export) — ให้แก้ Gantt flicker (ดู `ClaudeCode_Fix_GanttFlicker.md`) ก่อน แล้วค่อยเริ่ม module นี้

## เป้าหมาย
เก็บเอกสารตาม Document Matrix (UR/DR/PU-PT/IFT/BCT/UAT/IP) พร้อม workflow อนุมัติ Draft → Review → Confirmed และ export ได้

## 1. Data Model

### `documents`
| column | type | note |
|---|---|---|
| id | INTEGER PK | |
| doc_code | TEXT | เช่น URS-001 |
| title | TEXT | |
| phase | TEXT | UR/DR/PU-PT/IFT/BCT/UAT/IP |
| doc_type | TEXT | เช่น "URS", "Sign-off Sheet", "Test Result Report" — free text, ไม่ fix list เพราะแต่ละ project ต่างกัน |
| status | TEXT | Draft / InReview / Confirmed / Rejected |
| version | INTEGER | เพิ่มทีละ 1 ทุกครั้งที่แก้หลัง Confirmed |
| owner | TEXT | คนรับผิดชอบเอกสาร |
| file_path | TEXT | path ไฟล์แนบ (ถ้ามี upload จริง) |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### `document_signoffs`
| column | type | note |
|---|---|---|
| id | INTEGER PK | |
| document_id | INTEGER FK → documents.id | |
| signed_by | TEXT | ชื่อผู้อนุมัติ |
| signed_role | TEXT | เช่น "Client PM", "Internal PMO" |
| signed_at | DATETIME | |
| status | TEXT | Approved / Rejected |
| comment | TEXT | nullable |

**Rule:** เอกสารสถานะ `Confirmed` ต้องมี record ใน `document_signoffs` อย่างน้อย 1 แถวที่ status=`Approved` — ห้าม set status=`Confirmed` ตรงๆ โดยไม่ผ่าน sign-off record

## 2. API Endpoints

```
GET    /api/{slug}/documents                  list (filter by phase/status)
POST   /api/{slug}/documents                  create (status เริ่มที่ Draft เสมอ)
PUT    /api/{slug}/documents/{id}              update (ถ้า status=Confirmed → auto bump version +1, reset status เป็น Draft ต้อง sign-off ใหม่)
DELETE /api/{slug}/documents/{id}
POST   /api/{slug}/documents/{id}/submit-review   Draft → InReview
POST   /api/{slug}/documents/{id}/signoff          บันทึก signoff record; ถ้า status=Approved → document status = Confirmed, ถ้า Rejected → document status = Rejected
GET    /api/{slug}/documents/{id}/signoffs        ดู history การ sign-off ทั้งหมดของเอกสารนั้น
GET    /api/{slug}/documents/export                export list เป็น Excel (รวม signoff ล่าสุดต่อเอกสาร)
POST   /api/{slug}/documents/upload/{id}          upload ไฟล์แนบ (เก็บใน /data/projects/{slug}/documents/)
```

## 3. Frontend Pages

1. **Document List** — table filter by phase/status, badge สี (Draft=เทา, InReview=เหลือง, Confirmed=เขียว, Rejected=แดง)
2. **Document Detail** — เห็น version history + signoff history (timeline), ปุ่ม Submit for Review / Sign-off (Approve/Reject พร้อม comment), upload ไฟล์แนบ
3. เชื่อมกับ Function List เดิม — เพิ่ม tab/filter "Documents" ใน phase view เดียวกัน เพื่อเห็นภาพรวมว่า phase นี้เอกสารอะไร confirm แล้วบ้าง

## 4. Build Order
1. Migrate DB: เพิ่ม `documents`, `document_signoffs` tables
2. Backend CRUD + submit-review + signoff endpoints (มี business rule ข้อ 1 ผูกไว้ในนี้)
3. Backend: version bump logic เมื่อแก้เอกสารที่ Confirmed แล้ว
4. Frontend: Document List page
5. Frontend: Document Detail page (version + signoff timeline)
6. Excel export (รวม signoff ล่าสุด)
7. ทดสอบ: สร้างเอกสาร → submit review → signoff approve → confirm → แก้อีกครั้ง → version ต้องเพิ่มและ status กลับเป็น Draft

## Acceptance Criteria
- [ ] สร้างเอกสารได้ status เริ่มที่ Draft เสมอ
- [ ] Confirmed ได้ก็ต่อเมื่อผ่าน signoff Approved เท่านั้น (บังคับผ่าน backend ไม่ใช่แค่ frontend)
- [ ] แก้เอกสารที่ Confirmed แล้ว → version +1, status กลับ Draft อัตโนมัติ
- [ ] Export Excel ได้ พร้อมคอลัมน์ signoff ล่าสุด (ชื่อผู้อนุมัติ, วันที่, status)
