# Kickoff Spec — Thai Business-day Engine (Shared Module)
> เป้าหมาย: ทำ logic กลางตัวเดียว ตัดเสาร์-อาทิตย์ + วันหยุดนักขัตฤกษ์ไทยออกจากการคำนวณ deadline ทุกที่ในระบบ (ตรรกะเดียวกับที่เคยทำใน SPARK BI SLA logic) แทนที่ calendar-day fallback ที่ใช้อยู่ตอนนี้ใน Issue/Incident board และ Slippage Predictor

## 1. Data Model

### `thai_holidays` (master.db — global, ใช้ร่วมทุก project)
| column | type | note |
|---|---|---|
| id | INTEGER PK | |
| holiday_date | DATE | |
| name_th | TEXT | ชื่อวันหยุดภาษาไทย |
| name_en | TEXT | nullable |
| year | INTEGER | เผื่อ query filter ตามปีง่ายๆ |
| is_special | BOOLEAN | true ถ้าเป็นวันหยุดพิเศษที่รัฐบาลประกาศเพิ่มปีนั้น (ไม่ fix ทุกปี) |

**Seed ข้อมูลเริ่มต้น:** ใส่วันหยุดนักขัตฤกษ์ไทยมาตรฐานปี 2026 (และ 2027 ล่วงหน้าถ้าประกาศแล้ว) — วันหยุดที่ตรงกับเสาร์-อาทิตย์ให้ใส่ "วันหยุดชดเชย" ด้วยตามประกาศราชกิจจานุเบกษาจริง (ต้องเช็คให้ตรง ไม่ใช่คำนวณเดาเอง)

## 2. Backend — Shared Utility Module
สร้างไฟล์ `backend/app/business_day.py` (ใช้ร่วมกันทุกจุดในระบบ):

```python
def is_business_day(date: date) -> bool:
    # False ถ้าเป็นเสาร์/อาทิตย์ หรืออยู่ใน thai_holidays

def add_business_days(start: date, n: int) -> date:
    # เลื่อนไปข้างหน้า n วันทำการ ข้าม weekend+holiday

def business_days_between(start: date, end: date) -> int:
    # นับจำนวนวันทำการระหว่าง 2 วันที่ (ใช้กับ Slippage Predictor)

def next_business_day(date: date) -> date:
    # ถ้า date ตรงกับวันหยุด เลื่อนไปวันทำการถัดไป
```

ทุกฟังก์ชัน query จากตาราง `thai_holidays` (cache ในหน่วยความจำต่อ request หรือต่อวันก็ได้ ไม่ต้อง query ซ้ำทุกครั้งถ้าไม่จำเป็น)

## 3. จุดที่ต้องเปลี่ยนมาใช้ engine นี้ (แทนของเดิม)

### 3.1 Issue/Incident/Backlog Board — `board_items.sla_due_date`
เปลี่ยนจาก calendar-day fallback เดิม:
```
Critical = 1 วัน, High = 3 วัน, Medium = 7 วัน, Low = 14 วัน (นับรวมเสาร์-อาทิตย์)
```
เป็น business-day:
```
sla_due_date = add_business_days(created_at, N)  # N เดิมตามตาราง severity
```
**Migration:** ของเก่าที่สร้างไปแล้วใน production ไม่ต้อง backfill recalculation ย้อนหลัง (เพราะ sla_due_date เดิมอาจผูกกับ commitment ที่แจ้งไปแล้ว) — ใช้ logic ใหม่กับ item ที่สร้างใหม่นับจากนี้เท่านั้น

### 3.2 Slippage Predictor
- ข้อ 1.1 (Gantt-based): เปลี่ยน `elapsed_pct` ให้นับ business days แทน calendar days (ถ้า task เป็นงานที่ทำเฉพาะวันทำการ — ให้เป็น config ต่อ task ก็ได้ว่านับแบบไหน แต่ default ควรเป็น business-day)
- ข้อ 1.2 (Document-based): `days_left_in_phase` เปลี่ยนเป็น `business_days_between(today, phase_deadline)`

### 3.3 Task due_date (ใหม่ — เสริมจากที่มีอยู่)
เพิ่ม helper endpoint/utility ให้ตอนสร้าง task เลือกได้ว่าจะตั้ง due_date เป็น "N วันทำการจากวันนี้" (ใช้ `add_business_days`) แทนต้องกรอกวันที่ตรงๆ เอง — สะดวกขึ้นเวลาตั้ง deadline

## 4. API Endpoints (สำหรับดูแล/แก้วันหยุด)
```
GET    /api/holidays?year=2026        list วันหยุดปีนั้น
POST   /api/holidays                   เพิ่มวันหยุดพิเศษ (pmo_admin เท่านั้น)
PUT    /api/holidays/{id}
DELETE /api/holidays/{id}
```
(RBAC: เฉพาะ `pmo_admin` แก้ไขได้ — วันหยุดเป็นข้อมูล reference กลาง ไม่ควรให้ role อื่นแก้)

## 5. Frontend
- หน้าเล็กๆ (อยู่ใต้ settings หรือ admin area) ให้ pmo_admin ดู/เพิ่ม/แก้วันหยุดไทยได้ — เผื่อปีถัดไปรัฐบาลประกาศวันหยุดพิเศษเพิ่ม จะได้ไม่ต้องรอ Claude Code แก้โค้ด
- ไม่ต้องมี UI พิเศษอื่นสำหรับผลลัพธ์การคำนวณ — sla_due_date/slippage ที่มีอยู่แล้วแสดงผลปกติ แค่ค่าที่คำนวณเบื้องหลังถูกต้องขึ้น

## Build Order
1. Migration: สร้างตาราง `thai_holidays` ใน master.db
2. Seed วันหยุดไทยปี 2026 (และ 2027 ถ้ามีประกาศแล้ว) — ต้องเช็คจากแหล่งทางการ (ราชกิจจานุเบกษา/ปฏิทินราชการ) ไม่ใช่เดาเอง
3. Backend: สร้าง `business_day.py` utility module
4. Backend: CRUD holidays endpoint
5. แก้ `board_items` SLA calculation ให้ใช้ engine ใหม่ (เฉพาะ item ใหม่ ไม่ backfill ของเก่า)
6. แก้ Slippage Predictor (1.1, 1.2) ให้ใช้ business-day
7. เพิ่ม helper สร้าง task ด้วย "N วันทำการ" (ข้อ 3.3)
8. Frontend: หน้า admin ดู/แก้วันหยุด (pmo_admin only)
9. ทดสอบ: สร้าง Critical issue วันศุกร์ก่อนวันหยุดยาว → sla_due_date ต้องข้ามวันหยุดไปวันทำการถัดไปจริง ไม่ใช่นับรวมวันหยุด

## Acceptance Criteria
- [ ] `add_business_days` ข้ามเสาร์-อาทิตย์และวันหยุดไทยที่ seed ไว้ถูกต้อง (ทดสอบข้ามช่วงสงกรานต์/ปีใหม่)
- [ ] Issue ใหม่ที่สร้างช่วงก่อนวันหยุดยาว sla_due_date เลื่อนออกไปถูกต้อง (ของเก่าไม่เปลี่ยน)
- [ ] Slippage Predictor ใช้ business-day ในการคำนวณ elapsed_pct/days_left แล้ว
- [ ] pmo_admin เพิ่ม/แก้วันหยุดพิเศษได้ผ่าน UI, role อื่นแก้ไม่ได้ (403)
