# Security Hardening Spec — ต้องทำก่อน Deploy จริง
> **สำคัญที่สุด:** ถ้าตอนนี้ระบบยังไม่มี login/authentication เลย (`owner`/`created_by` เป็นแค่ free-text field) ให้ Claude Code ยืนยันก่อนว่าจริงไหม แล้วทำข้อ 1-2 เป็นอันดับแรกสุด ก่อนแตะเรื่องอื่นทั้งหมดในไฟล์นี้

## ระดับความสำคัญ
🔴 = ต้องมีก่อน deploy จริง (ห้าม deploy โดยไม่มี)
🟡 = ควรมี ทำเพิ่มได้หลัง deploy รอบแรกไม่นาน
🟢 = nice-to-have ทำทีหลังก็ได้

---

## 1. 🔴 Authentication จริง (login + password)
- ตาราง `users` (master.db): id, email, password_hash (ใช้ `bcrypt` หรือ `argon2` — **ห้ามเก็บ plain text หรือใช้ MD5/SHA1 เด็ดขาด**), role, active, created_at
- Login endpoint: `POST /api/auth/login` → return JWT access token (อายุสั้น เช่น 30 นาที) + refresh token (อายุยาวกว่า เช่น 7 วัน)
- Middleware: ทุก endpoint (ยกเว้น login) ต้องเช็ค JWT ใน header ก่อนทำงาน
- Frontend: เก็บ token ใน **httpOnly cookie** (ไม่ใช่ localStorage — ป้องกัน XSS ขโมย token ได้)
- Logout endpoint: revoke refresh token

## 2. 🔴 Role-Based Access Control (RBAC)
- Role ที่ต้องมีอย่างน้อย: `pmo_admin`, `dev`, `qa`, `client_viewer`
- `client_viewer`: อ่านได้อย่างเดียว, เห็นเฉพาะ Document ที่ Confirmed แล้ว + Dashboard ระดับสรุป — **ห้ามเห็น internal task/note/activity log**
- Sign-off action (confirm เอกสาร) จำกัดเฉพาะ role ที่กำหนดไว้ต่อ project เท่านั้น
- ทุก endpoint ต้องเช็ค role ก่อนอนุญาต ไม่ใช่แค่ซ่อนปุ่มฝั่ง frontend

## 3. 🔴 HTTPS บังคับ + Security Headers
- Fly.io และ Vercel ให้ TLS ฟรีอัตโนมัติอยู่แล้ว — แค่ต้อง**บังคับ redirect http→https** ไม่ปล่อยให้เข้าทาง http ได้
- เพิ่ม security headers ฝั่ง backend: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` (ยกเว้นหน้า Whiteboard ที่ต้อง allow iframe จาก diagrams.net เฉพาะจุด), `Content-Security-Policy` จำกัด domain ที่โหลด script ได้

## 4. 🔴 Rate Limiting (กัน brute-force)
- ใช้ `slowapi` (FastAPI) จำกัด login endpoint โดยเฉพาะ (เช่น 5 ครั้ง/นาที ต่อ IP) — ป้องกันการเดารหัสผ่านซ้ำๆ
- endpoint อื่นๆ จำกัดหลวมกว่า (เช่น 100 req/นาที) กัน abuse ทั่วไป

## 5. 🟡 Multi-Factor Authentication (MFA/2FA)
- ใช้ TOTP (`pyotp` library) — user scan QR ผูกกับ Google Authenticator/Authy
- บังคับใช้อย่างน้อยกับ role `pmo_admin` ก่อน (role อื่นทำทีหลังได้)
- นี่คือคำตอบตรงๆ สำหรับคำถาม "นอกจาก password" — TOTP-based 2FA คือมาตรฐานที่คุ้มที่สุดต่อความยาก/ประโยชน์

## 6. 🔴 Secrets Management
- ห้าม commit ค่า secret จริงลง git เด็ดขาด (JWT secret key, DB path จริง ฯลฯ)
- ใช้ `fly secrets set` (Fly.io) และ Vercel Environment Variables settings เก็บค่าจริง
- JWT secret key ต้อง random ยาวพอ (อย่างน้อย 32 bytes) generate ครั้งเดียวตอน deploy

## 7. 🔴 Backup อัตโนมัติ
- SQLite ทุกไฟล์ (master.db + per-project db) อยู่บน Fly.io volume เดียว — **ถ้า volume เสีย ข้อมูลหายหมด**
- ตั้ง cron job (ใน container หรือ Fly.io scheduled machine) copy ไฟล์ .db ทั้งหมดไปเก็บที่อื่นทุกวัน (เช่น อัปโหลดไป S3-compatible storage ฟรี tier หรือ Google Drive ผ่าน API ที่เตรียม column ไว้แล้ว)
- เก็บ backup อย่างน้อย 7 วันย้อนหลัง

## 8. 🟡 Audit Log ขยายเพิ่ม
- `activity_log` ที่มีอยู่แล้ว (จาก Quick-win) ให้เพิ่ม log การ login/logout, login ล้มเหลว, การเปลี่ยน role/permission ด้วย — ไม่ใช่แค่ data field change

## 9. 🟡 Dependency Security
- รัน `pip-audit` (Python) และ `npm audit` (Node) ก่อน deploy ครั้งแรก แก้ vulnerability ระดับ High/Critical ที่เจอ
- ถ้าใช้ GitHub เก็บโค้ด เปิด Dependabot alerts ไว้ (ฟรี)

## 10. 🟢 Edge Protection (ทำทีหลังได้)
- ใส่ Cloudflare (free tier) หน้า Fly.io app เพิ่มชั้น DDoS protection — ไม่จำเป็นสำหรับ MVP ทีมเล็ก แต่ทำง่ายและฟรี ถ้ามีเวลา

---

## Build Order (ตามระดับความสำคัญ)
1. 🔴 ข้อ 1: Authentication (JWT + bcrypt)
2. 🔴 ข้อ 2: RBAC — ผูกกับทุก endpoint ที่มีอยู่แล้วทั้งหมด (ต้องไล่แก้ endpoint เดิมทุกตัว ใส่ dependency เช็ค role)
3. 🔴 ข้อ 3: HTTPS enforce + security headers
4. 🔴 ข้อ 4: Rate limiting บน login endpoint
5. 🔴 ข้อ 6: Secrets management — ย้าย secret ทั้งหมดออกจาก code/config
6. 🔴 ข้อ 7: Backup automation
7. 🟡 ข้อ 5, 8, 9 — ทำต่อได้หลัง deploy รอบแรกภายในสัปดาห์แรก
8. 🟢 ข้อ 10 — ทำเมื่อมีเวลา

## Acceptance Criteria (ก่อนอนุญาตให้ deploy จริง)
- [ ] ไม่มี endpoint ไหนเข้าถึงได้โดยไม่มี valid JWT (ทดสอบด้วยการยิง request ไม่มี token ต้องได้ 401 ทุกจุด)
- [ ] `client_viewer` role เข้าไม่ถึง internal task/note/activity log ได้จริง (ทดสอบยิง request ตรงๆ ไม่ใช่แค่เช็ค UI)
- [ ] Login endpoint โดน rate limit จริงเมื่อลองผิดเกิน 5 ครั้ง/นาที
- [ ] ไม่มี secret ใดๆ หลงเหลือใน code/git history (grep หา string ที่น่าจะเป็น secret ก่อน push จริง)
- [ ] Backup script รันได้จริงและกู้คืนไฟล์ .db ได้ถูกต้อง (ทดสอบ restore จริงอย่างน้อย 1 ครั้ง)
