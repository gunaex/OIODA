# Deployment Prep Spec — Fly.io (Backend) + Vercel (Frontend)
> **สำคัญ: ทำแค่เตรียม config ไว้ก่อน ยังไม่ต้อง deploy จริง** — รอจนทดสอบ local ครบทุก feature (Phase 2/3) ผ่านหมดก่อน แล้วค่อยสั่ง deploy จริงในคำสั่งแยกต่างหาก

## เป้าหมาย
เตรียมไฟล์ที่จำเป็นสำหรับ deploy ในอนาคต โดยไม่กระทบการทำงาน local ปัจจุบัน (backend :8000, frontend :5173 ต้องรันได้เหมือนเดิมทุกอย่าง)

---

## 1. Backend → Fly.io

### 1.1 `backend/Dockerfile`
- Python 3.11-slim base image
- ติดตั้ง dependencies จาก `requirements.txt`
- Copy โค้ด backend ทั้งหมด
- Expose port 8000
- CMD รัน uvicorn (`uvicorn app.main:app --host 0.0.0.0 --port 8000`)

### 1.2 `backend/fly.toml`
- app name: ตั้งชื่อ placeholder (เช่น `pmo-platform-backend`) — ผู้ใช้จะเปลี่ยนตอน deploy จริง
- **Mount persistent volume** ที่ path `/app/data/projects` (ตรงกับที่ SQLite per-project files เก็บอยู่ตาม Kickoff Spec เดิม) — ขนาดเริ่มต้น 1-3GB (free tier)
- Health check endpoint: ใช้ `/api/health` (ถ้ายังไม่มี ให้เพิ่ม simple endpoint ที่ return `{"status": "ok"}`)
- Region: `sin` (Singapore) — ใกล้ผู้ใช้ในไทยที่สุด, latency ต่ำสุด

### 1.3 Backend code change ที่ต้องทำ (เล็กน้อย)
- เพิ่ม `GET /api/health` endpoint (ถ้ายังไม่มี)
- แก้ CORS middleware ให้รองรับ origin จาก Vercel (เช่น `https://*.vercel.app` และ custom domain ที่จะตั้งภายหลัง) — **อย่า hardcode URL จริง ใช้ environment variable `ALLOWED_ORIGINS` แทน** จะได้ปรับตอน deploy โดยไม่ต้องแก้โค้ด
- ตรวจสอบว่า path เก็บ SQLite files (`/app/data/projects`) อ่านจาก environment variable ได้ (เช่น `DATA_DIR`) ไม่ hardcode path ตรงๆ ในโค้ด — เพื่อให้ path ตรงกับ volume mount ตอน deploy จริง

---

## 2. Frontend → Vercel

### 2.1 `frontend/vercel.json`
- Build command: `npm run build` (Vite default)
- Output directory: `dist`
- Rewrite rule: proxy `/api/*` requests ไปยัง backend URL บน Fly.io (ผ่าน environment variable `VITE_API_BASE_URL`) — **อย่า hardcode URL ตรงๆ ในโค้ด frontend**

### 2.2 Environment variable ที่ต้องเตรียมไว้ (แต่ยังไม่ต้องใส่ค่าจริง)
```
# backend (.env.example)
DATA_DIR=/app/data/projects
ALLOWED_ORIGINS=http://localhost:5173

# frontend (.env.example)
VITE_API_BASE_URL=http://localhost:8000
```
ตอน deploy จริงค่อยตั้งค่าจริงใน Fly.io secrets / Vercel environment variables settings — **ไม่ commit ค่าจริงลง git**

---

## 3. สิ่งที่ห้ามทำในขั้นนี้
- ห้ามรัน `fly deploy` หรือ `vercel deploy` จริง
- ห้ามสมัคร/ผูก account Fly.io หรือ Vercel ในขั้นนี้ (รอผู้ใช้ทำเองตอนพร้อม)
- ห้ามเปลี่ยน behavior ของ local dev environment (`npm run dev`, `uvicorn` local ต้องรันได้เหมือนเดิมทุกอย่าง)

---

## 4. Local Testing Checklist (ต้องผ่านให้ครบก่อนค่อย deploy จริง)
- [ ] Phase 2 (Document Sign-off) ทำงานถูกต้องครบ flow (Draft→Review→Signoff→Confirmed→version bump)
- [ ] Phase model correction (UR/DR/DN/PU/ST/UT/TR/IP/MA) ใช้งานถูกต้องทุกจุด ไม่มี phase เก่าหลงเหลือ
- [ ] document_templates auto-populate ตอนสร้าง project ใหม่ทำงานถูกต้องตาม project_category
- [ ] Report Generator ทั้ง 4 แบบ (Daily/Weekly/Monthly/Phase Closure) export Excel ได้ถูกต้อง
- [ ] Project Note + Promote to Task ทำงานถูกต้อง
- [ ] Quick-win 8 ข้อ ทำงานได้หมด ไม่มี error ใน console
- [ ] Gantt (หลังแก้ flicker) ยัง smooth เหมือนเดิม ไม่ regression จากการแก้อื่นๆ

## Build Order
1. เพิ่ม `/api/health` endpoint
2. แก้โค้ดให้อ่าน `DATA_DIR` / `ALLOWED_ORIGINS` จาก environment variable แทน hardcode
3. สร้าง `backend/Dockerfile`, `backend/fly.toml`, `.env.example` (backend + frontend)
4. สร้าง `frontend/vercel.json`
5. รัน local ตาม Testing Checklist ข้อ 4 ให้ผ่านหมดก่อน — **ยังไม่ deploy จริงจนกว่าจะสั่งเพิ่มเติม**
