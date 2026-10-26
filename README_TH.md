# UR.PACE — Race Data Sync / Public Beta Package v0.9.1

> **GitHub Ready v0.9.1:** สำหรับการขึ้นเว็บจริง ใช้คำแนะนำใน `START_HERE_GITHUB.md` เป็นหลัก Workflow นี้ตั้ง **Settings → Pages → Source = GitHub Actions** ไม่ใช่ Deploy from a branch เพราะ Deploy อยู่ใน Workflow เดียวกับ Race Sync


> **สถานะ: โค้ดสำหรับการนำเข้าข้อมูลสดพร้อมนำไปทดลองบน GitHub Actions แต่ยังไม่ได้เปิดใช้งานบนโฮสต์ และยังไม่ได้ยืนยันผลการดึง HTML จากเว็บไซต์จริงของแต่ละแหล่ง**

นี่เป็นโปรเจกต์ **UR.PACE v0.8 เดิม** ผนวกหลังบ้าน Race Sync จาก v0.6 เข้าด้วยกัน โดยไม่แก้ Training Engine และไม่เปลี่ยน Database Keys / Event IDs เพียงเพราะเปลี่ยนชื่อแบรนด์

## ระบบทำงานอย่างไร

1. Workflow `.github/workflows/weekly-race-sync.yml` ทำงานทุกวันจันทร์ **09:15 น. เวลาไทย** (GitHub Actions อาจเริ่มช้ากว่าที่กำหนด)
2. Python อ่านแหล่งจาก `data/sources.json` ตรวจ `robots.txt` และดึง HTML สาธารณะเฉพาะแหล่งที่ `enabled: true`
3. Parser ตรวจชื่อ/วัน/ลิงก์จากโครงสร้างที่รู้จัก ไม่สมมติราคา ระยะทาง หรือวันแข่งขันที่ไม่มีหลักฐาน
4. Dedup เทียบลิงก์ + ชื่อ + วัน + จังหวัด; รายการที่ใกล้เคียงแต่ไม่แน่ใจส่งไป `data/review_queue.json`
5. เพิ่ม/อัปเดต canonical events และฝังข้อมูลลง `index.html` โดยรักษา Generator / หน้าตาเดิม
6. GitHub Action commit ข้อมูลใหม่; GitHub Pages จะเผยแพร่เวอร์ชันใหม่ถ้าตั้งให้ deploy จาก branch หลัก

**หลัง Deploy** นักวิ่งเข้าหน้า UR.PACE ได้ตามปกติ ไม่ต้องเปิดเว็บค้างไว้เพื่อให้ข้อมูลอัปเดต

## ความครอบคลุมและข้อจำกัด

- Source Registry **67 รายการ** (ไม่ใช่ 67 เว็บไซต์ที่ซิงก์สำเร็จแล้ว)
- เปิด **3 Pilot adapters** เป็นค่าเริ่มต้น: RUNLAH, Jog & Joy, PatRunning. แหล่งอื่นอยู่ใน Registry แต่ยังไม่ควรยิงดึงด้วย parser ทั่วไปก่อนตรวจโครงสร้าง / เงื่อนไขการใช้งาน
- RUNLAH ส่วน Calendar บางหน้าแสดงรายการผ่าน JavaScript; parser ปัจจุบันจะนำเข้าเฉพาะข้อมูลที่มองเห็นใน HTML ที่ตอบกลับโดยตรงเท่านั้น
- Jog & Joy เหมาะกับการค้นพบงานทั่วประเทศ; บางรายการมีเพียงหน้าปฏิทินต้นทาง ไม่มี URL สมัครโดยตรง จึง **ไม่สร้างลิงก์สมัครปลอม**
- เว็บไซต์ที่ไม่อนุญาตการดึงข้อมูล, บังคับ Login หรือเปิดข้อมูลผ่าน API เฉพาะ จะถูกข้ามและแจ้งสถานะ ไม่หลบเลี่ยงการป้องกัน
- ไม่มีการคัดลอกภาพ/โปสเตอร์จากผู้จัดอัตโนมัติ; เก็บเฉพาะข้อมูลข้อเท็จจริงที่จำเป็นพร้อมลิงก์ต้นทาง
- กิจกรรม We Run Thailand/parkrunthailand เก็บอยู่ใน Registry แต่ **ยังไม่มี API/Parser สำหรับ recurrence** จึงไม่สร้างวันที่จัดประจำเองโดยเดา
- **การอัปเดตขึ้นอยู่กับการ deploy ออนไลน์**; การเปิด `index.html` ด้วย `file://` เป็น Snapshot ณ ครั้งที่แพ็ก/ซิงก์ล่าสุด ไม่ดึงข้อมูลใหม่อัตโนมัติ

## ติดตั้งครั้งเดียวผ่าน GitHub

อ่านขั้นตอนที่ตรวจปรับแล้วใน `START_HERE_GITHUB.md`. **สำคัญ:** ตั้ง Pages Source เป็น **GitHub Actions** และรัน `UR.PACE Race Sync and Pages Deploy` จากแท็บ Actions; workflow จะ Sync, Commit และ Deploy เป็นรอบเดียวกัน

## Quality Gate ก่อนเปิด Public Beta

`sync_status.json > beta_gate.ready` จะเป็น `true` ได้ก็ต่อเมื่อ **ในการรันออนไลน์จริงครั้งนั้น**:

- มีงานอนาคตในฐานข้อมูลอย่างน้อย **60 งาน** (เกณฑ์ผลิตภัณฑ์ตั้งต้น ปรับได้)
- มีอย่างน้อย **2 แหล่ง** ที่ได้รายการงานอนาคตจาก HTML จริง
- มี `last_success` จากการดึงข้อมูลจริง (ไม่รวม fixture/offline)

ตัวเลขนี้ **ไม่ใช่คำรับประกันว่าข้อมูลครบทุกงานวิ่งไทย** การปล่อย Beta ต้องตรวจความถูกต้องของลิงก์สมัคร/วันที่/ระยะจริงด้วย รวมทั้งห้ามระบุว่า source ไหนดึงสำเร็จถ้ายังไม่ได้ทดสอบ live

## โครงสร้างหลัก

| Path | ใช้ทำอะไร |
|---|---|
| `index.html` | UR.PACE front-end (single HTML; มี Training Generator เดิม) |
| `scripts/sync_races.py` | Sync, Parser, Dedup, Embed snapshot |
| `data/sources.json` | 67 แหล่ง / เปิด 3 pilot |
| `data/race_store.json` | Canonical Race DB พร้อม Provenance |
| `data/site_payload.json` | `races`/`categories` สำหรับ Front-end |
| `data/sync_status.json` | สถานะล่าสุดและ Beta Gate |
| `data/review_queue.json` | รายการที่อาจซ้ำหรือวันไม่ตรง |
| `tests/test_sync.py` | Automated parsing/dedup/embedding tests |
| `fixtures/` | HTML **จำลองเพื่อการทดสอบเท่านั้น** |

## คำสั่งทดสอบ

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
# ตรวจว่าไฟล์ HTML ยังคง build ได้โดยไม่เรียกเว็บจริง
python scripts/sync_races.py --offline
# สั่งทดสอบ 3 แหล่งบนโฮสต์ที่ออนไลน์ (และตรวจเงื่อนไขแหล่งข้อมูลแล้ว)
python scripts/sync_races.py --only source-001,source-002,source-003
```

⚠️ **ไม่ควรใช้ `--fixture-dir` ทับฐานข้อมูลจริง** เพราะข้อมูล Fixture เป็นข้อมูลจำลอง; ชุดทดสอบ Unittest จะใช้โฟลเดอร์ชั่วคราวแทน

## การเพิ่มแหล่งอื่นแบบปลอดภัย

เพิ่มทีละกลุ่มจาก Source Registry: ThaiRun, PatRunning, RunThaiHub, ผู้จัดทางการ, Trail, Tri-League และ We Run Thailand โดยตรวจเงื่อนไขการดึงข้อมูลและพัฒนาตัวอ่านเฉพาะไซต์ก่อนตั้ง `enabled: true` จากนั้นรันทดสอบและตรวจงานซ้ำทุกครั้ง
