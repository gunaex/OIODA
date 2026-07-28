# Kickoff Spec — Test Execution Tracking (TP / TR / THG / ROK) สำหรับ PU / ST Phase

> ตอนนี้ข้อมูลเสริมบน Progress Matrix — เดิมมีแค่ PS/PR/RS/R (progress ตัวเดียว) เอาข้อมูลจาก Program Test/Unit Test ใน PU และ ST (IFT เดิมรวมอยู่ใน ST แล้ว) ต้องมี**ผลการทดสอบ** ด้วย ไม่ใช่แค่ "เสร็จหรือยัง"

## 1. Symbol ใหม่ (จาก legend กริดของบริษัท)

| Symbol | สี | ความหมาย |
|---|---|---|
| **TP** | เหลืองอ่อน | Test Plan — วันที่วางแผนจะทดสอบเสร็จ |
| **TR** | เหลือง/ส้ม | Test เสร็จ ผลลัพธ์ **OK** (ผ่านรอบแรก) |
| **THG** | แดง | Test เสร็จ ผลลัพธ์ **NG** (ไม่ผ่าน) |
| **ROK** | เขียว | Re-test เสร็จ ผลลัพธ์ **OK** (แก้ไขจาก NG แล้วผ่าน) |

**ความสัมพันธ์:** TP คือแผน (คล้าย PR ของเดิม), TR/THG/ROK คือผลจริง (คล้าย R ของเดิม) แต่แยกสีตามผลลัพธ์ในแต่ละสีเดียว — และ ROK ผูกกับ THG ต้องหน้าเสมอ (retest เกิดจาก NG เท่านั้น)

## 2. Data Model (per-project db)

### `test_executions`
| column | type | note |
|---|---|---|
| id | INTEGER PK | |
| linked_entity_type | TEXT | `task` \| `function` \| `board_item` |
| linked_entity_id | INTEGER | |
| plan_finish_date | DATE | nullable — วันที่วางแผนสอบเสร็จ (TP) |
| actual_finish_date | DATE | nullable — วันที่สอบเสร็จจริง |
| result | TEXT | `OK` \| `NG` \| null (ยังไม่ตรวจสอบ) |
| is_retest | BOOLEAN | default false |
| retest_of_id | INTEGER FK -> test_executions.id | nullable — ผูกกับรอบที่ NG ก่อนหน้า (บังคับ: ตั้งได้เฉพาะเมื่อ retest_of_id ที่ชี้ไปมี result='NG') |
| created_by | TEXT | |
| created_at / updated_at | DATETIME | |

**หนึ่ง entity มีได้หลาย `test_executions`** (รอบแรก + retest 1 หรือมากกว่า) — ไม่ใช่ 1:1

## 3. Symbol Computation Logic

ต่อ `test_executions` แต่ละแถว:
```
ถ้า plan_finish_date มีค่า -> วันนั้นได้ "TP"
ถ้า actual_finish_date มีค่า:
    ถ้า is_retest == false:
        result == "OK"  -> "TR"
        result == "NG"  -> "THG"
    ถ้า is_retest == true:
        result == "OK"  -> "ROK"
        result == "NG"  -> "THG"   (retest ไม่ผ่านอีก ยังคงเป็น THG ไม่มี symbol พิเศษ ตาม legend ที่มีให้)
```
ถ้า `plan_finish_date` และ `actual_finish_date` ตกวันเดียวกัน — แสดงทั้งคู่ได้เต็มเซลล์เดียว (เหมือนหลักการ PSR/RSR ที่มีอยู่แล้ว)

## 4. API
```
GET    /api/{slug}/test-executions?entity_type=&entity_id=
POST   /api/{slug}/test-executions
PUT    /api/{slug}/test-executions/{id}
DELETE /api/{slug}/test-executions/{id}
POST   /api/{slug}/test-executions/{id}/retest      # shortcut: สร้าง retest ใหม่ผูกกับตัวก่อนที่ (ต้อง result เดิม='NG' เท่านั้นถึงสร้างได้ ไม่งั้น 400)
```

## 5. Frontend

### 5.1 Progress Matrix — เพิ่มแถวเสริม
ต่อ item ที่มี `test_executions` ผูกอยู่ (อย่างน้อย 1 แถว) — แสดง**แถวเสริมที่ 2** ใต้แถวหลักของ item ทั้งบนตาราง Matrix เดิม (แถวหลักยังเป็น PS/PR/RS/R ตามปกติ, แถวย่อยเป็น TP/TR/THG/ROK) — ถ้ามีหลายรอบ retest ให้แสดงเรียงต่อกันหลายแถวย่อยต่อกัน (รอบแรก, retest 1, retest 2, ...)

Legend เพิ่ม 4 symbol ใหม่ครอมสีตามข้อ 1

### 5.2 จุดที่กรอกข้อมูล — popover เดิมที่คลิกที่ item
ขยาย popover เดิม (มี Plan dates / Actual dates อยู่แล้ว) เพิ่ม section ที่ 3: **"Test Execution"**
- แสดง list ของ test_executions ที่มีอยู่ (ถ้ามี) พร้อมสถานะ
- ปุ่ม "+ Add Test Result" — กรอก plan_finish_date, แล้วถ้าจบสอบเสร็จกรอก actual_finish_date + เลือกผล OK/NG
- ถ้ารอบล่าสุด result = NG — เปิดปุ่ม "+ Create Retest" (เรียก `/retest` endpoint) ที่จะให้สร้าง test_execution ใหม่ผือเชื่อม (ผัดลืมผูก `retest_of_id`)

### 5.3 คำเฉพาะทาง (ไม่บังคับตัว validation)
Test Execution ออกแบบมาสำหรับ item ใน phase **PU** หรือ **ST** (การเดิมเรียก IFT ถึงรวมอยู่ใน ST แล้ว) — ไม่ hard-block phase อื่น (เพื่อความยืดหยุ่น) แต่ถ้า item ที่ phase ไม่ใช่ PU/ST แล้วมีคนกดเพิ่ม Test Execution ให้แค่โชว์ hint เบาๆ ว่า: "โดยปกติ Test Execution ใช้กับงาน PU/ST — ตรวจสอบว่าถูก phase ไหม"

## 6. เชื่อมกับ Issue/Incident (Board) — เมื่อ NG ต้องมีบักเดี๋ยว

### 6.1 หลักการ
`THG` (NG) ไม่ใช่แค่สถานะ — มันคือ**บันทึกที่ต้องมีบักเด็ก** ตรงกับ Issue/Incident board ที่มีอยู่แล้ว ถ้ายังไม่เชื่อมัน จะเกิดข้อมูล 2 ที่ไม่รู้ว่าอันไหนคือความจริง (เหมือนกันปัญหา `pd_total` vs FP model ที่เจอมาก่อน) — เชื่อมโยง **link ไม่ merge** เพื่อแต่ละ entity แต่ละถูกจับเก็บ

### 6.2 Data Model — เพิ่ม column
ใน `test_executions`:
| column | type | note |
|---|---|---|
| linked_board_item_id | INTEGER FK -> board_items.id | nullable |

### 6.3 Flow

**เมื่อบันทึกผล NG:** เปิดปุ่ม **"Create Issue from this NG result"** (ต่อหน้าถัดจาก "+ Create Retest" ที่มีอยู่แล้ว — ทำได้ทั้งคู่พร้อมกัน ไม่ exclusive) เรียก logic คล้ายกับ "Promote to Issue" ที่มีอยู่แล้วใน Note System:
- สร้าง `board_items` (`item_type='issue'`), prefill title = "{entity title} — Test NG", description = อ้างอิงรายละเอียด test (plan/actual date), severity = default `High` (เพราะเป็น NG จาก test จริง ไม่ใช่แค่ observation)
- ตั้ง `test_executions.linked_board_item_id` ที่เกลี่ยวไปที่ issue ที่สร้าง
- ถ้ามี `linked_board_item_id` อยู่แล้ว (ไม่ต้องสร้างซ้ำ) — ปุ่มเปลี่ยนเป็น "View Linked Issue"

**เมื่อจะสร้าง Retest:** ถ้า test_execution รอบ NG นั้นมี `linked_board_item_id` — แสดง**สถานะของ issue นั้น**เป็น hint (เช่น "Linked issue ISS-014: Open" หรือ "Resolved") **ไม่บังคับ**ว่าต้องเป็น Resolved ก่อนถึงจะสร้าง retest ได้ (soft hint เท่านั้น เพื่อทีมไม่ลืมเช็ค board ก่อนตรวจซ้ำ)

### 6.4 Reverse — ฝั่ง Board Item
ตรงหน้า Board Item detail: เพิ่ม panel **"Linked Test Execution"** (รูปแบบเดียวกับ "Linked Notes" panel ที่ทำไว้ใน Note System) แสดง test_execution ที่ link มาจากตรงนี้ พร้อมสถานะ (NG/retest pending/ROK)

### 6.5 Cross-check / Recovery Suggestion เพิ่มเติม (reuse engine เดิม)
เพิ่มเพื่อต่อยอด Recovery Suggestion (Progress Matrix §6.4 เดิม):
- **"มี test NG ที่ยังไม่ถูก Issue"** — เตะทำสร้าง issue เพื่อ track การแก้ (data quality nudge)
- **"มี test NG ที่ถูก Issue ไว้แล้ว แต่ยังไม่มี Retest หลังจากผ่าน N business days"** — เตะทำติดตาม (ใช้ Thai Business-day Engine เดิม, ถูกกับ Recovery Suggestion pattern เดิมที่ต้องมี data_points เสมอ ตามข้อที่ตั้งไว้แล้ว)

## 7. Build Order (ต่อยอดจากเดิม)
1. Migration: สร้างตาราง `test_executions`
2. Backend: CRUD + retest shortcut + symbol computation logic (`test_execution_symbol.py` — แยกไฟล์ให้ชัด หรือขยายจาก `progress_matrix.py` เดิม)
3. Backend: ต่อเข้า `GET /progress-matrix` — เพิ่ม field `test_rows: [...]` ต่อ item ที่มี test_executions
4. Frontend: แถวเสริมใน Progress Matrix grid + legend ใหม่
5. Frontend: ขยาย popover เดิม section Test Execution + ปุ่ม retest
6. RBAC: ตาม convention เดิม (read ทุกคน role, write require_internal)
7. Backend: เพิ่ม `linked_board_item_id` + endpoint "create issue from NG" (§6.3)
8. Frontend: ปุ่ม Create Issue / View Linked Issue ในส่วน Test Execution ของ popover
9. Frontend: "Linked Test Execution" panel ที่ Board Item detail (§6.4)
10. Backend: เพิ่ม 2 เงื่อนไขใหม่ใน Recovery Suggestion engine (§6.5) — ต้องมี data_points ทุก suggestion ตามข้อเดิม
11. ทดสอบ: สร้าง test รอบแรก NG — THG ขึ้นถูกวัน — กด Create Issue — เช็ค link ทั้ง 2 ทิศทาง — สร้าง retest — ROK ขึ้นถูกวัน — เช็คว่าแถวเสริมทั้ง 2 รอบแสดงแยกกันบนตาราง

## Acceptance Criteria
- [ ] TP/TR/THG/ROK คำนวณและแสดงถูกต้องตรงวันที่จริง
- [ ] Retest สร้างได้เฉพาะกรณีรอบก่อนที่ result='NG' เท่านั้น (400 ถ้าพยายามสร้างจากรอบที่ OK)
- [ ] Item ที่มีหลายรอบ test แสดงถูกต้องเป็นหลายแถวย่อยเรียงกัน ไม่ทับกัน
- [ ] Progress Matrix เดิม (PS/PR/RS/R) ไม่ได้รับผลกระทบ — ตรวจสอบ regression
- [ ] Legend อัปเดตครบ 4 symbol ใหม่พร้อมสีที่ตรงกับข้อกำหนด
- [ ] "Create Issue from NG" สร้าง board_item ถูกต้อง พร้อม link 2 ทิศทาง (test_execution↔board_item)
- [ ] Board Item detail แสดง Linked Test Execution panel ถูกต้อง
- [ ] Recovery Suggestion 2 เงื่อนไขใหม่ทำงานถูกต้อง มี data_points ทุกครั้ง (ตามข้อเดิมที่บังคับไว้กับ test)
