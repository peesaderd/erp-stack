# Image Prompt Structure — Triptych 16:9 (3 Panels)

> คำอธิบายโครงสร้าง prompt รูปจากเจ้าของงาน (2026-08-19)
> ใช้เป็นหลักอ้างอิงถาวร ห้ามเบี่ยงเบน

## สรุปโครงสร้าง (ทีละ Panel)

### Panel 1 = Cover Page Design
- หน้าปกสินค้า ออกแบบโฆษณาขายของ
- เน้นสินค้าเด่นเต็ม panel (cover page design)
- มี brand/logo/ข้อความโฆษณาได้

### Panel 2 = Model + Product
- ใช้ตัวแปร: **สัญชาติ** (Thai) + **เพศ** (gender) + **อายุ** (เลือกอายุน้อยที่สุดที่ target อนุญาต) + **room setting** (ฉากห้อง)
- Model จะถือ/จับ/วาง/ทำอะไรกับ product ก็ว่าไป
- **ขึ้นอยู่กับ Recipe / UGC style** (holding, unbox, review, comparison, talking_head...)
- Model ตัวกลางระหว่างสินค้ากับผู้ชม

### Panel 3 = Result / End Scene
- Model มาจาก **Panel 2** (คนเดียวกัน)
- แสดงผลลัพธ์ (result) / ฉากจบ (end scene)

## ความสัมพันธ์ที่สำคัญ
- Panel 2 มี Model ตัวจริงอยู่กับสินค้า (ตาม UGC recipe)
- Panel 3 ใช้ **Model คนเดียวกับ Panel 2** เพื่อความต่อเนื่อง แล้วปิดด้วยผลลัพธ์
- ทั้ง 3 panel = 16:9 triptych แบ่ง 3 ช่องเท่ากัน

## กฎการเขียน (จากเจ้าของงาน)
- ใช้ตัวแปรสัญชาติ/เพศ/อายุ/room setting จริง ไม่ hardcode ตายตัว
- อายุ = เลือกอายุน้อยที่สุดที่ target อนุญาต (model ดูอ่อนเยาว์เท่าที่กลุ่มเป้าหมายรองรับ)
- Action กับสินค้า มาจาก Recipe/UGC ไม่ใช่บังคับเอง
- Panel 3 must reuse model จาก Panel 2 เสมอ

## History / ที่มาของโครงสร้างนี้
- 2026-08-19: เจ้าของงานชี้แจงโครงสร้างที่ถูกต้อง (Panel1=cover design, Panel2=model+product ตาม recipe, Panel3=result จาก model เดียวกับ panel2)
- ข้อกำหนดก่อนหน้า (ยังมีผล): reference-driven ไม่ hardcode จำนวนสินค้า, full-frame no border
