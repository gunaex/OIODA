# Kickoff Spec — PWA (Installable App) via vite-plugin-pwa
> เป้าหมาย: ให้ browser โชว์ปุ่ม "Add to Home Screen"/"Install App" บน iPad Safari, Android Chrome, Windows/macOS Chrome/Edge — ตอบโจทย์ cross-platform ฟรีที่ตั้งใจไว้ตั้งแต่ต้น

## 1. ทำไมตอนนี้ไม่มีปุ่ม Install
Vite React app เดิมยังไม่มี:
- `manifest.json` (Web App Manifest — บอก browser ว่าแอปนี้ชื่ออะไร ไอคอนหน้าตายังไง เปิดแบบ standalone หรือไม่)
- Service Worker (ทำให้ browser เห็นว่า "ติดตั้งได้" ตามเกณฑ์ PWA)

ไม่มี 2 อย่างนี้ = ไม่มีปุ่ม Install ไม่ว่า platform ไหน — เป็นเหตุผลตรงไปตรงมา ไม่ใช่บั๊ก

## 2. วิธีทำ (ใช้ `vite-plugin-pwa` — มาตรฐานสำหรับ Vite project)

### 2.1 ติดตั้ง package
```bash
npm install -D vite-plugin-pwa
```

### 2.2 แก้ `vite.config.js` — เพิ่ม plugin
```js
import { VitePWA } from 'vite-plugin-pwa'

// ใน plugins array เพิ่ม:
VitePWA({
  registerType: 'autoUpdate',
  manifest: {
    name: 'PM Platform',            // ชื่อเต็ม
    short_name: 'PM Platform',      // ชื่อสั้น (โชว์ใต้ไอคอนตอนติดตั้ง)
    description: 'Project Management Platform',
    theme_color: '#1F4E78',         // สีเดียวกับ header theme ที่ใช้อยู่ (Toyota Red หรือ navy ที่ใช้ใน document header ก็ได้ ให้ Claude Code เช็คสีจริงที่ใช้)
    background_color: '#ffffff',
    display: 'standalone',          // เปิดแบบไม่มี browser UI เหมือน native app
    start_url: '/',
    icons: [
      { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
      { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
      { src: 'icon-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' }
    ]
  },
  workbox: {
    // cache static assets พื้นฐาน — ไม่ต้อง cache API response (ข้อมูลเปลี่ยนบ่อย ให้ดึงสดเสมอ)
    globPatterns: ['**/*.{js,css,html}']
  }
})
```

### 2.3 สร้างไอคอน
- ต้องมีไฟล์ `icon-192.png`, `icon-512.png`, `icon-512-maskable.png` ใน `frontend/public/`
- ถ้ายังไม่มีโลโก้จริง ใช้ตัวอักษรย่อ/สีพื้น theme ไปก่อนได้ (placeholder) แล้วเปลี่ยนทีหลังได้ง่าย
- **Maskable icon** สำคัญสำหรับ Android — ต้องมี safe zone (โลโก้ไม่ชิดขอบเกินไป ไม่งั้นถูกตัดตอนแสดงเป็นวงกลม/rounded square)

### 2.4 เพิ่ม meta tags ใน `index.html`
```html
<meta name="theme-color" content="#1F4E78" />
<link rel="apple-touch-icon" href="/icon-192.png" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
```
(iOS Safari ต้องการ meta tag เฉพาะแบบนี้เพิ่มจาก manifest ปกติ ถึงจะรองรับ "Add to Home Screen" ได้ดี)

## 3. ข้อควรระวัง — อย่า cache API response
Service Worker ที่ generate จาก `vite-plugin-pwa` ต้อง cache **เฉพาะ static asset** (JS/CSS/HTML/ไอคอน) เท่านั้น **ห้าม cache `/api/*` requests** เพราะข้อมูล (Task/Document/Gantt) เปลี่ยนบ่อย ถ้า cache ผิดจะเห็นข้อมูลเก่าค้างแม้ backend อัปเดตแล้ว — ตรวจสอบ `workbox.globPatterns`/`runtimeCaching` config ให้แน่ใจว่าไม่ครอบคลุม API path

## 4. Build & Deploy
- `npm run build` ตามปกติ — `vite-plugin-pwa` จะ generate `manifest.webmanifest` + service worker ให้อัตโนมัติตอน build
- Deploy ขึ้น Vercel ใหม่ (push code แล้ว Vercel auto-redeploy ตามปกติ)

## 5. ทดสอบ (สำคัญ — ต้องลองจริงทุก platform)
- [ ] **Android Chrome**: เปิด URL production → เมนู (3 จุด) → ต้องมี "Install app" หรือ "Add to Home Screen"
- [ ] **iPad Safari**: เปิด URL production → ปุ่ม Share → "Add to Home Screen" ต้องขึ้น icon/ชื่อถูกต้อง
- [ ] **Windows/macOS Chrome/Edge**: address bar ต้องมี icon ⊕/install แสดงขึ้นมาให้กดติดตั้ง
- [ ] เปิดแอปที่ติดตั้งแล้ว ต้องไม่มี browser UI (address bar/tab) — เหมือน native app
- [ ] แก้ข้อมูลใน Task แล้ว refresh ในแอปที่ติดตั้งไว้ ต้องเห็นข้อมูลใหม่ทันที (ยืนยันว่าไม่ cache API ผิด)

## Build Order
1. ติดตั้ง `vite-plugin-pwa` + แก้ `vite.config.js`
2. สร้างไอคอน placeholder (3 ขนาดตามข้อ 2.3)
3. เพิ่ม meta tags ใน `index.html`
4. Build local ทดสอบก่อน (`npm run build && npm run preview`) เช็คว่า manifest/service worker generate ถูกต้อง
5. Push + deploy ขึ้น Vercel
6. ทดสอบตามข้อ 5 ทุก platform ที่มีเครื่องทดสอบได้จริง

## Acceptance Criteria
- [ ] ปุ่ม Install/Add to Home Screen ขึ้นจริงอย่างน้อย 2 ใน 3 platform ที่ทดสอบได้ (Android/iPad/Desktop)
- [ ] API data ไม่ถูก cache ผิด (ข้อมูลใหม่ขึ้นทันทีหลัง refresh)
- [ ] แอปที่ติดตั้งแล้วเปิดแบบ standalone ไม่มี browser chrome UI
