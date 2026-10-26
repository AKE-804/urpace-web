# UR.PACE — อัปโหลด GitHub + เปิด Weekly Race Sync

ไฟล์นี้สำหรับแพ็กเกจ **v0.9.1 GitHub Ready** ที่ปรับ Workflow ให้ **Sync แล้ว Deploy GitHub Pages ในรอบเดียวกัน** เพื่อแก้ปัญหา GitHub Pages ไม่ถูกสร้างใหม่เมื่อ Commit โดย `GITHUB_TOKEN`.

## ขั้นตอน (ไม่ต้องใช้ Terminal)

1. เปิด https://github.com/new แล้วสร้าง Repository ชื่อ `urpace-web` เลือก **Public** หากใช้ GitHub Free และต้องการเผยแพร่ด้วย Pages; อย่าเพิ่ม README/.gitignore/license อัตโนมัติในขั้นนี้
2. แตก ZIP แล้วเข้าโฟลเดอร์ที่แตกออกมา **เลือกทุกไฟล์และโฟลเดอร์ภายใน** (`index.html`, `.github`, `scripts`, `data`, `tests`, `fixtures`, `requirements.txt`, `README_TH.md`, `START_HERE_GITHUB.md`) อย่าอัปโหลด ZIP เป็นไฟล์เดียว
3. ใน Repository ใช้ **uploading an existing file** (ถ้า repo ว่าง) หรือ **Add file → Upload files** แล้วลากไฟล์/โฟลเดอร์ทั้งหมดใส่หน้าอัปโหลด กด **Commit changes** บนสาขา `main`
4. ตรวจว่าในหน้า Code มี `index.html` ที่ ROOT และไฟล์ `.github/workflows/weekly-race-sync.yml` อยู่ในโครงสร้างถูกต้อง
5. เปิด **Settings → Pages → Build and deployment → Source = GitHub Actions** (ไม่ใช้ Deploy from a branch สำหรับแพ็กเกจนี้)
6. เปิด **Settings → Actions → General** แล้วตรวจว่า Actions อนุญาตทำงาน หากมี Workflow permissions ให้เลือก **Read and write permissions**
7. ไป **Actions → UR.PACE Race Sync and Pages Deploy → Run workflow → main → Run workflow**
8. ถ้า Sync และ Deploy ขึ้นสีเขียว ให้เปิด **Settings → Pages → Visit site**; URL ปกติคือ `https://YOUR-USERNAME.github.io/urpace-web/`
9. ตรวจผล Sync ที่ `data/sync_status.json` และ `data/review_queue.json` บน Repository ก่อนประกาศ Public Beta ดู `beta_gate.ready` / `sources_with_events` / `future_events_parsed`; อย่าสับสนว่าการรันผ่านคือดึงได้ 67 เว็บ

หมายเหตุ: ปัจจุบันยังมี **28 งานจาก Snapshot ตั้งต้น** และมี **3 เว็บไซต์ที่เปิดทดลองดึง**; โค้ดและตัวทดสอบพร้อมขึ้น GitHub แต่ต้องทดลอง Live Sync บน Actions เพื่อยืนยันจำนวนงานที่อ่านได้จริง ไม่มีการรับรองว่าครบ 60 งานจากรอบแรก

Workflow นี้ deploy โดยตรงจากในรอบ Sync (หลังจาก `git push`) จึงไม่ต้องอาศัยการ trigger Pages จาก commit ของ `GITHUB_TOKEN`.

การแก้ Source HTML ใน Repository ครั้งต่อไป: เมื่อแก้โค้ดเสร็จ ให้รัน Workflow เองอีกครั้งเพื่อ Deploy เวอร์ชันใหม่ หรือต้องเพิ่ม trigger push แยกภายหลัง

---

