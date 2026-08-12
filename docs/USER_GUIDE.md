# 🎯 Conductor Again — คู่มือการใช้งาน

> **Version 0.1.0 MVP** | สิงหาคม 2026

---

## 📋 สารบัญ

1. [เริ่มต้นใช้งาน](#1-เริ่มต้นใช้งาน)
2. [Dashboard — หน้าหลัก](#2-dashboard--หน้าหลัก)
3. [Vision — วิสัยทัศน์โครงการ](#3-vision--วิสัยทัศน์โครงการ)
4. [Requirements — ข้อกำหนด](#4-requirements--ข้อกำหนด)
5. [Skills — คลังความสามารถ](#5-skills--คลังความสามารถ)
6. [AI Resources — ทรัพยากร AI](#6-ai-resources--ทรัพยากร-ai)
7. [Deliberation — การปรึกษาหลายมุมมอง](#7-deliberation--การปรึกษาหลายมุมมอง)
8. [Intake — ระบบย่อยความต้องการ](#8-intake--ระบบย่อยความต้องการ)
9. [Golden Flow — ครบวงจรในคลิกเดียว](#9-golden-flow--ครบวงจรในคลิกเดียว)
10. [การเพิ่ม DeepSeek API Key](#10-การเพิ่ม-deepseek-api-key)
11. [การรันเทส](#11-การรันเทส)
12. [การ Deploy](#12-การ-deploy)

---

## 1. เริ่มต้นใช้งาน

### 1.1 เริ่มต้น Server

```powershell
# Terminal 1 — Backend
cd backend
.\venv\Scripts\Activate.ps1
python -m app.seed              # สร้าง admin user
python -m seed_ai               # ลงทะเบียน AI providers
python -m seed_skills           # สร้าง Skills
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

เปิดเบราว์เซอร์ไปที่: **http://localhost:5174**

### 1.2 ล็อกอินครั้งแรก

| ฟิลด์ | ค่า |
|---|---|
| **Email** | `admin@conductoragain.local` |
| **Password** | `ChangeMe123!` |

> ⚠️ เปลี่ยนรหัสผ่านทันทีหลังล็อกอินครั้งแรก!

---

## 2. Dashboard — หน้าหลัก

![Dashboard](dashboard.png)

### สิ่งที่เห็น:

| ส่วน | รายละเอียด |
|---|---|
| **Stat Cards** | Vision Revisions, Requirements, Skills, AI Resources — แสดงจำนวนจริงจากระบบ |
| **Business Vision** | แสดง Vision ล่าสุด พร้อมปุ่มเพิ่ม Revision ใหม่ |
| **Golden Flow** | ปุ่มเดียวจบ — Vision → Requirements → Functions → Risk (ดูหัวข้อ 9) |
| **Requirements Preview** | แสดง 5 requirements ล่าสุด |

### วิธีการใช้:

1. **เพิ่ม Vision** — กดปุ่ม "Add Vision" หรือ "New Revision" ใส่ข้อความ อธิบายวิสัยทัศน์โครงการ
2. **Run Golden Flow** — กดปุ่ม "Run Golden Flow" ระบบจะ:
   - บันทึก Vision revision ใหม่
   - แตก Requirement ออกมา 5 ข้อ
   - แตกเป็น Functions พร้อมวิเคราะห์
   - ประเมิน Risk

---

## 3. Vision — วิสัยทัศน์โครงการ

### การทำงาน:

- ทุกครั้งที่เพิ่ม Vision = สร้าง Revision ใหม่ (แก้ไขของเก่าไม่ได้ — immutable)
- **Timeline View** — แสดงประวัติทุกรอบเรียงตามเวลา
- **Compare Mode** — เลือก 2 revision เพื่อเปรียบเทียบ side-by-side
- Revision ล่าสุดจะแสดงเต็ม ส่วน revision เก่าแสดงย่อ (กดเพื่อขยาย)

### ตัวอย่าง:

```
Revision 2 (LATEST)
Build a Production BOM management system for a food manufacturing factory...

Revision 1
Build a Production BOM system...
```

---

## 4. Requirements — ข้อกำหนด

### วิธีการใช้:

1. **สร้าง Requirement** — กด "New Requirement" ใส่ Code, Title, Description
2. **ค้นหา** — พิมพ์ในช่อง Search เพื่อกรองตาม code, title, description
3. **กรองตามสถานะ** — dropdown เลือก All / Draft / Clarifying / Approved / Change Proposed / Superseded
4. **เรียงลำดับ** — By Code / By Status / By Date

### สถานะ Requirement:

| สถานะ | ความหมาย |
|---|---|
| `draft` | ฉบับร่าง ยังไม่ได้รับการอนุมัติ |
| `clarifying` | กำลังขอข้อมูลเพิ่มเติม |
| `approved` | ผ่าน baseline แล้ว |
| `change_proposed` | มีการเสนอเปลี่ยนแปลง |
| `superseded` | ถูกแทนที่ด้วยเวอร์ชันใหม่ |

---

## 5. Skills — คลังความสามารถ

### 9 Skills ที่มาพร้อมระบบ:

| Skill | หน้าที่ |
|---|---|
| **Vision Intake** | วิเคราะห์วิสัยทัศน์ ดึง objectives, constraints, assumptions |
| **Domain Clarifier** | ตั้งคำถามเพื่อ clarify requirement ที่คลุมเครือ |
| **Requirement Completeness** | ตรวจสอบ requirement ว่าครบถ้วนหรือไม่ |
| **Scope Decomposer** | แตก scope ใหญ่เป็น workstream ย่อย |
| **Defect Triage** | วิเคราะห์ defect: severity, impact, fix priority |
| **Impact Analysis** | วิเคราะห์ผลกระทบของการเปลี่ยนแปลง |
| **Decision Brief** | สรุปหลักฐาน ตัวเลือก ความเสี่ยง แนะนำการตัดสินใจ |
| **Independent Critique** | Blind peer review — วิจารณ์โดยไม่เห็นตัวตน |
| **Decision Judge** | ประเมินผู้สมัครแบบ blind เทียบกับ rubric |

### การจัดการ Version:

1. เลือก Skill → กดเพื่อขยาย
2. กด "New Version" → ใส่ System Instructions, Prompt Template
3. กด "Publish" เพื่อเปิดใช้งาน
4. กด "Revoke" เพื่อยกเลิก

### AUTO Router:

กดปุ่ม ▶ "Test AUTO router" บน Skill ใดก็ได้ ระบบจะ:
1. ประเมินทุก AI Resource ที่มี
2. ให้คะแนน 8 มิติ
3. เลือกตัวที่ดีที่สุด (Primary) + เตรียม Fallback

---

## 6. AI Resources — ทรัพยากร AI

### Provider ที่ลงทะเบียนไว้:

| Provider | Status |
|---|---|
| 🥇 **DeepSeek** | พร้อมใช้งาน (2 โมเดล) |
| OpenAI | รอใส่ API key |
| Google Gemini | รอใส่ API key |
| Anthropic | รอใส่ API key |
| Cloudflare Workers AI | รอใส่ API key |
| Local Runtime | รอตั้งค่า |

### 5 Sub-tabs:

| Tab | เนื้อหา |
|---|---|
| **Overview** | สรุป: Providers, Accounts, Models, Available/Degraded/Offline |
| **Providers** | รายชื่อ provider ที่ลงทะเบียน |
| **Accounts** | บัญชี API, สถานะ health, จำนวน request |
| **Models** | โมเดลที่ติดตั้ง: capabilities, context limit, pricing |
| **Resources** | Resource ที่ route ได้: entitlements, concurrency, test |

### การเพิ่ม Provider ใหม่:

1. ไปที่ AI Resources tab
2. กด "Add Account"
3. เลือก Provider → ใส่ชื่อบัญชี → API Base URL → API Key
4. ระบบจะ auto-register default models + สร้าง runtime
5. กดปุ่ม refresh เพื่อ Health Check

---

## 7. Deliberation — การปรึกษาหลายมุมมอง

### แนวคิดหลัก:

> ใช้ AI หลายเจ้าคิดแยกกันก่อน → วิจารณ์แบบ blind → แก้ไข → ตัดสิน โดยรักษาความเห็นต่างไว้

### ขั้นตอน:

1. **สร้าง Case** — กำหนดคำถาม, trigger, criteria, skill
2. **ระบบสร้าง Panel** — เลือก AI resources แบบ diverse (คนละ provider)
3. **Independent Round** — สมาชิกส่งคำตอบโดยไม่เห็นของคนอื่น
4. **Blind Critique** — วิจารณ์แบบไม่ระบุตัวตน (Candidate A, B, C...)
5. **Revision** — แก้ไขโดยต้องอ้างเหตุผล (new evidence, valid critique)
6. **Dissent** — บันทึกความเห็นต่างไว้ (ไม่ลบทิ้ง)
7. **Decision** — ตัดสินผล: Agreement / Majority + Dissent / Unresolved

### การตรวจจับ Conformity:

- ถ้าสมาชิกเปลี่ยนความเห็นโดยไม่มีเหตุผล → แจ้งเตือน Conformity Alert
- Diversity snapshot บันทึก metrics ทุกรอบ

---

## 8. Intake — ระบบย่อยความต้องการ

### วิธีใช้:

1. **วางข้อความ** ใน textarea (list, paragraph, markdown)
2. กด **"Decompose & Analyze"**
3. ระบบจะ:
   - แตกเป็น **Function List** (F-001, F-002...)
   - วิเคราะห์ **Complexity** (trivial → very_complex)
   - คำนวณ **Effort** (function points → person-days)
   - ตรวจจับ **Similarity** ระหว่าง functions
   - พยากรณ์ **Risk** พร้อม mitigation
   - กำหนด **Target Module** (CONDUCTOR / PM_AGAIN / QA_AGAIN / DEV)

### ตัวอย่าง:

```
Input:
1. User login with email/password and OAuth2 SSO
2. BOM comparison tool — diff two versions
3. Real-time inventory integration with ERP

Output:
F-001 [moderate] 3.2d → DEV | User login...
F-002 [simple] 2.1d → DEV | BOM comparison...
F-003 [complex] 5.6d → DEV | Real-time inventory...
Risk: MEDIUM (0.28) | Buffer: 10 days
```

### Analysis Views:

| Tab | แสดง |
|---|---|
| **Functions** | รายการ function, complexity, effort, target module |
| **Similarity** | คู่ที่คล้ายกัน: duplicate/high/medium/low |
| **Risk Forecast** | Risk items, severity, mitigation |

---

## 9. Golden Flow — ครบวงจรในคลิกเดียว

### วิธีใช้:

1. ไปที่ **Dashboard**
2. ตรวจสอบว่ามี Vision แล้ว (ถ้ายังไม่มี ให้ Add Vision ก่อน)
3. กดปุ่ม **"Run Golden Flow"**
4. ระบบจะทำทุกอย่างอัตโนมัติ:

```
Vision Revision #N
  → 5 Requirements extracted
  → 5 Functions decomposed
  → 13.6 person-days estimated
  → Risk: LOW (0.12)
  → All functions within manageable complexity ✅
```

### ผลลัพธ์ที่ได้:

| Step | Output |
|---|---|
| `vision_saved` | Vision revision ใหม่ |
| `requirements_extracted` | Requirements ใน DB |
| `functions_decomposed` | Function items ใน Intake |
| `risk_forecast` | Risk assessment |
| `deliberation_ready` | คำแนะนำว่าต้อง deliberation หรือไม่ |

---

## 10. การเพิ่ม DeepSeek API Key

### ขั้นตอน:

1. ไปที่ **AI Resources** tab
2. กด **"Add Account"**
3. กรอกข้อมูล:
   - **Provider**: DeepSeek
   - **Account Name**: DeepSeek Company Account
   - **API Base URL**: `https://api.deepseek.com`
   - **API Key**: `sk-xxxxxxxxxxxxxxxx` (จาก https://platform.deepseek.com)
4. กด **"Add Account"**
5. ระบบจะ auto-register 2 models: `deepseek-chat` (V3) และ `deepseek-reasoner` (R1)
6. กดปุ่ม 🔄 Health Check เพื่อทดสอบการเชื่อมต่อ

### Models ที่ลงทะเบียน:

| Model | Context | Capabilities |
|---|---|---|
| **deepseek-chat** (V3) | 64K | Structured Output, Tool Calling, Code, Multilingual, Thai |
| **deepseek-reasoner** (R1) | 64K | Code Reasoning, Multilingual |

---

## 11. การรันเทส

### Smoke Test (20 tests — ทดสอบทุก endpoint):

```powershell
cd backend
python test_smoke.py
```

### Pytest Suite (63 tests — isolated test DB):

```powershell
cd backend
pip install pytest
$env:PYTHONPATH = "."
python -m pytest tests/ -v
```

---

## 12. การ Deploy

### Backend → Fly.io:

```bash
cd backend
fly launch
fly secrets set JWT_SECRET_KEY=... ALLOWED_ORIGINS=...
fly deploy
```

### Frontend → Cloudflare Pages:

```bash
cd frontend
npm run build
# Upload dist/ to Cloudflare Pages
# Set VITE_API_BASE_URL=https://api.conductoragain.kanphong.com
```

### Environment Variables ที่ต้องตั้งค่า:

| Variable | Required | Description |
|---|---|---|
| `JWT_SECRET_KEY` | ✅ | 32-char random string |
| `ALLOWED_ORIGINS` | ✅ | Frontend URL(s) |
| `COOKIE_SECURE` | ✅ | `true` in production |
| `DATA_DIR` | ✅ | `/app/data` on Fly.io |
| `R2_ACCESS_KEY_ID` | ❌ | For R2 storage |
| `R2_SECRET_ACCESS_KEY` | ❌ | For R2 storage |
| `R2_BUCKET_NAME` | ❌ | Default: `conductor-again-dev` |
| `TURNSTILE_SECRET_KEY` | ❌ | For bot protection |

---

## 📞 การขอความช่วยเหลือ

| ปัญหา | วิธีแก้ |
|---|---|
| ลืมรหัสผ่าน | รัน `python -m app.seed` ใหม่ |
| Database พัง | ลบ `backend/data/` แล้วรัน seed scripts ใหม่ |
| Backend ไม่เริ่ม | ตรวจสอบ port 8000 ไม่ถูกใช้งานอยู่ |
| Frontend build fail | `rm -rf node_modules && npm install` |

---

> **Conductor Again — Project Control Plane + Skill & AI Capability Distributor**  
> เวอร์ชัน 0.1.0 MVP | สิงหาคม 2026
