# Kickoff Spec — Whiteboard / Diagram Module (Embedded drawio)
> ใช้ diagrams.net (drawio) แบบ **public embed (`embed.diagrams.net`) เป็นค่าเริ่มต้น** — เร็วสุด ไม่ต้อง host เอง เหมือนแนวทางที่เลือก Fly.io ก่อน Turso ไว้ก่อน (เก็บ self-host ไว้เป็น upgrade path ทีหลังตอนเริ่มมี diagram ที่ sensitive จริงๆ เช่น infra detail ของ client)

## 1. สถาปัตยกรรมโดยสรุป
- **drawio** เป็น open-source (Apache 2.0) — ใช้ public instance ที่ diagrams.net เปิดให้ embed ฟรี (`https://embed.diagrams.net`) ไม่ต้องตั้ง container เอง
- Frontend ของเราฝัง drawio ผ่าน `<iframe>` แล้วคุยกันด้วย **postMessage API** (มาตรฐานที่ drawio ให้มาสำหรับ embed mode โดยเฉพาะ — ไม่ต้องเขียน parser เอง)
- **สำคัญ:** save/load ทุกอย่างต้องผ่าน postMessage กลับเข้า backend เราเองเท่านั้น — **ปิด/ไม่ใช้ฟีเจอร์ "save to Google Drive/OneDrive/GitHub" ที่ตัว UI ของ diagrams.net มีมาให้** (ตั้ง param `saveAndExit=0` และไม่ผูก storage integration ใดๆ ของ drawio เอง) เพื่อให้ diagrams.net ทำหน้าที่แค่เสิร์ฟ editor UI เหมือนโหลด library จาก CDN ไม่แตะข้อมูลจริงของเราเลย
- Diagram content เก็บเป็น **XML string** (drawio format มาตรฐาน) ในฐานข้อมูลของเรา ไม่ใช่ไฟล์แยก

## 2. Data Model

### `whiteboards`
| column | type | note |
|---|---|---|
| id | INTEGER PK | |
| title | TEXT | |
| xml_content | TEXT | drawio XML (อาจยาว เก็บเป็น TEXT ไม่จำกัดความยาว) |
| linked_entity_type | TEXT | nullable — `project` \| `phase` \| `function` \| `document` \| `task` (ผูกกับของอื่นในระบบได้ ไม่บังคับ) |
| linked_entity_id | INTEGER | nullable |
| created_by | TEXT | |
| created_at | DATETIME | |
| updated_at | DATETIME | |

## 3. Infra ที่ต้องเพิ่ม (ไม่มี — นี่คือข้อดีของ public embed)
- ไม่ต้องเพิ่ม container หรือ service ใหม่ใดๆ ใน MVP นี้ — iframe ชี้ตรงไป `https://embed.diagrams.net` ได้เลย
- ไม่มี dev setup เพิ่มเติม รันเหมือนเดิมทุกอย่าง

## 4. API Endpoints

```
GET    /api/{slug}/whiteboards                    list (filter by linked_entity_type/id)
POST   /api/{slug}/whiteboards                     create (xml_content เริ่มต้นเป็น blank diagram)
GET    /api/{slug}/whiteboards/{id}
PUT    /api/{slug}/whiteboards/{id}                 save xml_content ใหม่ (เรียกตอน user กด save ใน editor)
DELETE /api/{slug}/whiteboards/{id}
```

## 5. Frontend — Whiteboard Editor Page
1. โหลด iframe ชี้ไป `https://embed.diagrams.net` พร้อม param `?embed=1&ui=min&spin=1&proto=json&saveAndExit=0` (ปิด save-and-exit เพื่อไม่ให้ชวนไปผูก Google Drive/OneDrive/GitHub storage ของ drawio เอง)
2. ตอน iframe โหลดเสร็จ ส่ง postMessage `load` พร้อม `xml_content` เดิม (ถ้ามี) เข้าไปแสดงใน editor
3. Listen event `save`/`autosave` จาก iframe (drawio ส่ง postMessage กลับมาเมื่อ user กด save) → เรียก `PUT /api/{slug}/whiteboards/{id}` บันทึก XML ใหม่ (บันทึกเข้า backend เราเองเท่านั้น)
4. Export: **ใช้ปุ่ม export ในตัว drawio เอง** (PNG/SVG/PDF) ไม่ต้องเขียนเพิ่ม — drawio รองรับอยู่แล้วครบ
5. เพิ่ม entry point เปิด Whiteboard จากหน้า Project/Phase/Function/Document (ปุ่ม "Open Whiteboard" ถ้ามี linked whiteboard, หรือ "Create Whiteboard" ถ้ายังไม่มี)

## 6. Upgrade Path — Self-host ทีหลัง (ยังไม่ทำตอนนี้)
พอเริ่มมี diagram ที่ sensitive จริง (infra detail ของ client เช่น Vimut/KLINE) ค่อยสลับมา self-host:
- รัน container image `jgraph/drawio` แยก ไม่ expose ตรงสู่ internet
- แก้แค่ iframe `src` จาก `https://embed.diagrams.net` เป็น URL container ตัวเอง — postMessage logic ทั้งหมดเหมือนเดิมทุกบรรทัด ไม่ต้องเขียนใหม่

## 7. Build Order
1. Migration: สร้างตาราง `whiteboards`
2. Backend CRUD endpoints
3. Frontend: Whiteboard Editor page + iframe (public embed) /postMessage integration ตามข้อ 5
4. เพิ่ม entry point เชื่อมจาก Project/Phase/Function/Document
5. ทดสอบ: สร้าง diagram → save → ปิดหน้าเปิดใหม่ → XML โหลดกลับมาถูกต้อง → export PNG ได้
6. (ทำทีหลัง เมื่อจำเป็น) สลับมาใช้ self-hosted container ตามข้อ 6

## Acceptance Criteria
- [ ] เปิด/สร้าง whiteboard ผูกกับ entity ใดๆ ในระบบได้ (หรือแบบ standalone ไม่ผูกก็ได้)
- [ ] Save แล้ว XML เก็บถูกต้อง, เปิดใหม่ได้ diagram เดิม
- [ ] Export เป็น PNG/SVG ได้จากปุ่มในตัว editor
- [ ] ข้อมูล diagram ไม่หลุดออกไปนอกระบบเรา (ถ้าเลือก self-host)
