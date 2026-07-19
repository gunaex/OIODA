# Kickoff Spec — Resource Management + Dashboard

## หลักการสำคัญ: ต้องเป็น Cross-Project
`resources` (คน) เป็นของ**ทั้งบริษัท** ไม่ใช่ของ project ใด project หนึ่ง — คนเดียวกันอาจถูก allocate เข้าหลาย project พร้อมกัน (Vimut + KLINE) ดังนั้นต้องเก็บใน **master DB** (ตัวเดียวกับที่เก็บ `projects` table) ไม่ใช่ per-project SQLite เหมือน functions/tasks

---

## ส่วนที่ 1: Resource Management

### 1.1 Data Model (อยู่ใน master.db)

```
resources
- id, name, role (SR.Arc/DevSecOps/SEC/DBA/Dev/QA/BA/UX/DevOps — reuse role list จาก KLINE manday breakdown)
- email (nullable), weekly_capacity_hours (default 40), active (bool)

resource_allocations
- id, resource_id FK -> resources.id
- project_slug (TEXT, อ้างอิง projects.slug)
- linked_task_id (nullable INT — เก็บแค่ id เฉย ๆ ไม่ทำ FK ข้าม DB จริง เพราะ task อยู่คนละไฟล์ DB)
- allocation_percent (INT, 0-100 — กี่ % ของเวลาคนนี้ในสัปดาห์นั้น)
- start_date, end_date
- note (nullable)
```

### 1.2 API Endpoints
```
GET/POST/PUT/DELETE /api/resources                          global resource pool
GET/POST/PUT/DELETE /api/{slug}/resource-allocations         allocation ผูกกับ project นี้
GET  /api/resources/utilization?from=YYYY-MM-DD&to=YYYY-MM-DD
     -> รวม allocation_percent ของแต่ละ resource ข้ามทุก project ในช่วงเวลานั้น
     -> return ต่อ resource: [{week, total_percent}] เพื่อทำ heatmap
```

### 1.3 Frontend
- **Resource Pool page** (global, ไม่ผูก project) — เพิ่ม/แก้ resource, role, capacity
- **Allocation view ภายใน project** — table แสดง resource ที่ allocate เข้า project นี้ พร้อม % และช่วงวันที่ ผูกกับ task ได้ (optional)
- **Utilization Heatmap** (global) — ตารางคน x สัปดาห์ สีตาม % รวมข้ามทุก project: เขียว <80%, เหลือง 80-100%, แดง >100% (over-allocated)

---

## ส่วนที่ 2: Dashboard

### 2.1 Project Dashboard (ต่อ project หนึ่ง)
Query รวมจากข้อมูลที่มีอยู่แล้ว ไม่ต้องเก็บ table ใหม่:
- % completion ต่อ phase (จาก `documents` confirmed / total ต่อ phase)
- Overdue tasks count (due_date < today, status != Done)
- Upcoming milestones (จาก `gantt_items` ที่ is_milestone=true, เรียงตามวันที่ใกล้สุด)
- Open issues/incidents แยกตาม severity (จาก `board_items`)
- Resource utilization สรุปเฉพาะ project นี้ (join กับ master.db)
- **RAG Status** (Red/Amber/Green) คำนวณจาก:
  - Red = มี mandatory document เลย due date ไปแล้วยังไม่ Confirmed, หรือมี Critical incident ที่ยัง Open
  - Amber = มี overdue task ที่ไม่ critical, หรือ resource over-allocated
  - Green = ไม่เข้าเงื่อนไขข้างบนเลย

### 2.2 Global Dashboard (ทุก project รวมกัน — หน้าแรกหลัง login)
- List ทุก project พร้อม RAG badge + quick stat (overdue count, open issue count)
- Resource utilization heatmap รวม (จากข้อ 1.3)
- คลิก project ไหนก็เข้า Project Dashboard ของ project นั้น

### 2.3 API Endpoints
```
GET /api/{slug}/dashboard          project-level aggregate (ข้อ 2.1)
GET /api/dashboard/global          cross-project rollup (ข้อ 2.2) — ต้อง loop query ทุก project_slug ใน master.db แล้ว aggregate
```

---

## Build Order
1. Migration master.db: สร้าง `resources`, `resource_allocations`
2. Backend: CRUD resources (global) + allocations (per-project reference)
3. Backend: utilization aggregation query (ข้ามทุก project_slug)
4. Frontend: Resource Pool page + Allocation view + Utilization Heatmap
5. Backend: project dashboard aggregate query + RAG logic
6. Backend: global dashboard rollup (loop ทุก project)
7. Frontend: Project Dashboard page + Global Dashboard (ตั้งเป็นหน้า landing หลัง login)
8. ทดสอบ: สร้าง resource 1 คน allocate เข้า 2 project พร้อมกันรวมกัน >100% ต้องขึ้นแดงใน heatmap, ทดสอบ RAG ทั้ง 3 สี (บังคับ mandatory doc ให้เลย due date ดูว่าขึ้นแดงจริง)

## Acceptance Criteria
- [ ] Resource คนเดียวกัน allocate ข้าม 2 project ถูกรวม % ถูกต้องใน utilization heatmap
- [ ] RAG status คำนวณถูกต้องตามเงื่อนไข 3 สี
- [ ] Global Dashboard โหลดทุก project ได้โดยไม่ error แม้บาง project จะไม่มีข้อมูลบางอย่าง (เช่น project ใหม่ยังไม่มี document เลย)
