# Kickoff Spec — Relabel Progress Matrix Symbols to Official Convention
> **Display label เปลี่ยน — ห้ามแตะ logic การคำนวณ** วันที่/เงื่อนไขเดิมทั้งหมดถูกต้องอยู่แล้ว (89/89 เคสผ่านแล้ว) เป็นแค่เปลี่ยนคำที่แสดงผลให้ตรงกับเอกสารกลางของบริษัท

## 1. Mapping (เดิม → ใหม่)

| ความหมาย | Label เดิม | Label ใหม่ (ตามกลาง) |
|---|---|---|
| เริ่มตามแผน | `PS` | `SP` |
| จบตามแผน | `PR` | `P` |
| เริ่มจริง | `RS` | `SR` |
| จบจริง | `R` | `R` (ไม่เปลี่ยน) |
| แผน start+finish วันเดียวกัน | `PSR` | `SPP` |
| จริง start+finish วันเดียวกัน | `RSR` | `SRR` |

**สำคัญ:** "จบตามแผน" เปลี่ยนจาก 2 ตัวอักษร (`PR`) เป็น **1 ตัวอักษร** (`P`) เท่านั้น — ระวังจุดนี้เป็นพิเศษเวลาแก้ เพราะไม่ใช่แค่สลับตัวอักษร

## 2. ขอบเขตของการเปลี่ยน (ต้องแยกให้ชัด)

**เปลี่ยน (display/label layer):**
- ตัวแปร symbol ที่ render บนตาราง Progress Matrix (frontend)
- Legend หน้า Progress Matrix
- ถ้ามี symbol พวกที่พาดถึง Excel report ด้วย (เช่น Weekly/Monthly ถ้ามีอ้างอิง Progress Matrix) ให้เปลี่ยนที่นั่นด้วย
- Tooltip/hover text ที่อธิบาย symbol

**ห้ามเปลี่ยน (จะทำให้เกิด regression):**
- ชื่อ field ใน database (`plan_start`, `plan_end`, `actual_start`, `actual_end` ฯลฯ) — ยังคงชื่อเดิมทั้งหมด เพราะเป็น internal naming ไม่เกี่ยวกับสิ่งที่ user เห็น
- Enum/status value ภายใน (`derived`/`override`/`effective`/`has_conflict` ฯลฯ) ของ Actual Dates Override feature
- Business logic การคำนวณ symbol (Business-day engine, cross-check, forecast, recovery suggestion) — เพื่อให้เข้าใจถูกต้องอยู่แล้ว เอาไปแค่ตัวหนังสือที่แสดงข้างนอก

## 3. หา string เดิมให้ครบ (grep ก่อนแก้)
Grep หาทุกที่ที่มี string literal `"PS"`, `"PR"`, `"RS"`, `"PSR"`, `"RSR"` ทั้งใน frontend (และ backend ถ้ามีจุดที่ generate ข้อความอธิบายที่มีคำเหล่านี้อยู่ เช่น legend text, tooltip text ที่ backend ส่งมา) — **ระวัง false positive**: `"RS"` อาจเจอตรงกับคำอื่นที่ไม่เกี่ยวข้อง (เช่นถ้ามี variable ชื่อ `hasResult` หรืออะไรที่มี substring ตรงกัน) ต้อง grep แบบ whole-word/exact-match ไม่ใช่ substring match

## 4. Build Order
1. Grep หา string เดิมทั้งหมดตามข้อ 3 ทำ list ที่จะเปลี่ยนก่อน แล้วรายงานผลกลับมาก่อนแก้จริง (ต้องขอ confirm ก่อนเริ่ม)
2. แก้ label ที่ frontend rendering layer (Progress Matrix grid, popover, legend, tooltip)
3. แก้ backend ถ้ามีจุดที่ generate ข้อความอธิบายมีคำเก่าอยู่ (เช่น recovery suggestion text ที่อาจพูดถึง symbol)
4. แก้ test suite เดิมของ Progress Matrix (89 test เดิม) ที่ assert ค่า string ตรงๆ — เปลี่ยน expected value ให้ตรง label ใหม่ (**อย่าลบ test ทิ้ง แก้แค่ expected string**)
5. รัน Progress Matrix test suite เต็มหมด (89 test) ยืนยันว่ายัง 89/89 ผ่านหลังเปลี่ยน label
6. รัน full regression ทั้งระบบอีกรอบ (เพื่อ symbol เดิมถูกอ้างอิงจากที่อื่นที่ไม่ได้คิดถึง เช่น Reports)
7. ขอสอบถามด้วยตา: เปิด Progress Matrix จริง เช็คว่า legend + symbol บนตารางเปลี่ยนตรง ไม่มี label เก่าหลงเหลืออยู่ไหน

## Acceptance Criteria
- [ ] Symbol ที่แสดงบนตาราง Progress Matrix เป็น SP/P/SR/R/SPP/SRR ตรงทุกจุด ไม่มี PS/PR/RS/PSR/RSR หลงเหลือใน UI
- [ ] Legend อัปเดตตรงกับ label ใหม่
- [ ] Database field names และ business logic ไม่เปลี่ยนแปลงเลย (grep ยืนยันว่า column name เดิมยังอยู่ตรง)
- [ ] Progress Matrix test suite เดิม 89 เคส ยังผ่านครบหลังแค่ expected string
- [ ] Full regression ทั้งระบบผ่านหมด ไม่มี module อื่น broken จากการเปลี่ยน label นี้
- [ ] ถ้ามี symbol หล่นๆ ที่พาดถึง Excel report ด้วย ต้องอัปเดตให้ตรงด้วย
