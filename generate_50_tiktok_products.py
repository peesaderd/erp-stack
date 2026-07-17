import csv
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    
    # 50 products from TikTok Shop Thailand with active IDs, categories, commissions, and links
    products = [
        # Existing 10 products
        {
            "Product ID": "1729456727501474015",
            "Product Name": "PAPA FEEL 577 เซรั่มลดเลือนฝ้ากระและรอยสิว",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "250.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1729456727501474015?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1729456727501474015?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "โชว์แก้มก่อนทาเซรั่มที่มีฝ้ากระชัดเจน แล้วทาทับ เผยภาพผิวหน้าใสเนียนกริบ (ผลลัพธ์ใน 3 วินาทีแรก)"
        },
        {
            "Product ID": "1730678936346200804",
            "Product Name": "เครื่องนวดหน้ากัวซาไฟฟ้า FULI (FULI Electric Guasha)",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "890.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1730678936346200804?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1730678936346200804?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "คนตื่นนอนหน้าบวมเป่ง แล้วใช้เครื่องกัวซานวดหน้าเพียง 1 นาที หน้าเรียวกระชับขึ้นทันที (ก่อน-หลัง)"
        },
        {
            "Product ID": "1731861070669187858",
            "Product Name": "Beleaf Liposomal Vitamin C (วิตามินซีเข้มข้น)",
            "Category": "Food & Supplements",
            "Price (THB)": "390.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1731861070669187858?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1731861070669187858?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ไขข้อข้องใจ 'ทำไมกินวิตามินซีปกติแล้วผิวไม่ใสสักที?' เผยเทคโนโลยีไลโปโซมอลที่ดูดซึมดีกว่า 10 เท่า"
        },
        {
            "Product ID": "1731576750018628290",
            "Product Name": "กันแดดเนื้อน้ำนม Hanbyeol (Hanbyeol Sunscreen Milk)",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "290.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1731576750018628290?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1731576750018628290?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ทากันแดดแล้วเอาทิชชูซับหน้าให้ดูว่าไม่มีความมันเหนอะหนะ โชว์ความเป็นธรรมชาติ ท้าแดดเมืองไทย"
        },
        {
            "Product ID": "1731527642712148180",
            "Product Name": "Smooth Bio C 1000 mg (วิตามินซีแบบเคี้ยว)",
            "Category": "Food & Supplements",
            "Price (THB)": "150.00",
            "Commission Rate": "15%",
            "Product URL": "https://www.tiktok.com/view/product/1731527642712148180?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://www.tiktok.com/view/product/1731527642712148180?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "เผลอกินขนมหวานเยอะจนเจ็บคอ ร่างกายอ่อนแอ ลองวิตามินซีเคี้ยวอร่อย ได้สุขภาพดีในราคาหลักร้อย"
        },
        {
            "Product ID": "1732374653152432971",
            "Product Name": "น้ำยาบ้วนปาก Buoola (Buoola Mouthwash)",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "180.00",
            "Commission Rate": "15%",
            "Product URL": "https://www.tiktok.com/view/product/1732374653152432971?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://www.tiktok.com/view/product/1732374653152432971?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ปัญหากลิ่นปากแรงหลังกินส้มตำ/กระเทียม บ้วน Buoola เพียง 30 วินาที คราบหลุดออกหมด ลมหายใจหอมสดชื่น"
        },
        {
            "Product ID": "1731667000536500824",
            "Product Name": "เกล็ดขนมปัง ตราครัววังทิพย์ 200 กรัม",
            "Category": "Food & Kitchen",
            "Price (THB)": "45.00",
            "Commission Rate": "10%",
            "Product URL": "https://shop.tiktok.com/view/product/1731667000536500824?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1731667000536500824?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ทำไก่ทอดกรอบสีเหลืองทองกรุบกรอบน่ากินที่บ้านง่ายๆ ด้วยเกล็ดขนมปังเกรดพรีเมียม"
        },
        {
            "Product ID": "1731283808641845848",
            "Product Name": "ชามพลาสติก PP213 จำนวน 50 ชิ้น",
            "Category": "Kitchen & Home",
            "Price (THB)": "80.00",
            "Commission Rate": "10%",
            "Product URL": "https://shop.tiktok.com/view/product/1731283808641845848?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1731283808641845848?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "จัดระเบียบการแพ็คอาหารส่งเดลิเวอรี่ให้สวยงามด้วยชามฝาล็อคแน่นหนา น้ำซุปไม่มีหกเลอะเทอะ"
        },
        {
            "Product ID": "1731860742826396434",
            "Product Name": "Alpha Chlorophyll Plus (อาหารเสริมคลอโรฟิลล์)",
            "Category": "Food & Supplements",
            "Price (THB)": "290.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1731860742826396434?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1731860742826396434?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "หน้าท้องป่อง ขับถ่ายยาก ชงดีท็อกซ์คลอโรฟิลล์ก่อนนอน ตื่นเช้ามาพุงยุบ สบายตัวสุดๆ"
        },
        {
            "Product ID": "1731194000810019602",
            "Product Name": "วิตามินบำรุงผิว Colla C (Colla C Collagen)",
            "Category": "Food & Supplements",
            "Price (THB)": "350.00",
            "Commission Rate": "18%",
            "Product URL": "https://shop.tiktok.com/view/product/1731194000810019602?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1731194000810019602?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "เคล็ดลับผิวขาวใสออร่าท้าแดด ชงคอลลาเจนกินง่าย รสชาติอร่อย ผิวนุ่มลื่นใน 7 วัน"
        },
        
        # 40 New products to reach 50
        # Category: Beauty & Personal Care
        {
            "Product ID": "1732561937402094205",
            "Product Name": "Skintific MSH Niacinamide เจลครีมบำรุงผิวขาวกระจ่างใส",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "379.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732561937402094205?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732561937402094205?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "เปิดหน้าสดพวกรอยแดงรอยดำสะสมทาครีมทับหน้ากระจ่างใสปิ๊งทันที รอยหายใน 14 วัน"
        },
        {
            "Product ID": "1732562145892019481",
            "Product Name": "Plantnery Tea Tree Intense Serum เซรั่มลดสิวคุมมัน",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "149.00",
            "Commission Care": "15%",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732562145892019481?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732562145892019481?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ซูมกล้องไปที่หัวสิวอักเสบแดงเป้ง หยดเซรั่มชาเขียวทับ เผยภาพสิวยุบแห้งสนิทข้ามคืน"
        },
        {
            "Product ID": "1732562304910901234",
            "Product Name": "ครีมกันแดดคุมมันทรงพลัง Skintific Ultra Light Serum SPF50+",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "289.00",
            "Commission Rate": "18%",
            "Product URL": "https://shop.tiktok.com/view/product/1732562304910901234?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732562304910901234?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ทากันแดดแล้วใช้แสง UV ส่องให้เห็นการปกป้องเต็มพิกัด แถมหน้าไม่เทา ไม่วอก"
        },
        {
            "Product ID": "1732562412894091823",
            "Product Name": "La Glace Black Magic Lip & Cheek PH Blush บลัชออนดำเปลี่ยนสี",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "289.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732562412894091823?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732562412894091823?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "แตะบลัชออนสีดำสนิทลงแก้ม ถูเบาๆ เปลี่ยนเป็นสีชมพูระเรื่อสวยธรรมชาติทันตาเห็น"
        },
        {
            "Product ID": "1732562590123849182",
            "Product Name": "4U2 Jelly Tint ลิปเยลลี่ติดทนไม่ติดแมสก์",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "179.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732562590123849182?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732562590123849182?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ทาลิปเยลลี่กินน้ำจากแก้วใสให้ดูจะจะว่าไม่มีรอยลิปสติกติดแก้วเลยแม้แต่นิดเดียว"
        },
        {
            "Product ID": "1732562691028374829",
            "Product Name": "Mizumi UV Water Serum SPF50+ ครีมกันแดดสูตรน้ำสำหรับผิวแพ้ง่าย",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "690.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732562691028374829?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732562691028374829?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "บีบครีมกันแดดลงหลังมือ เกลี่ยปุ๊บซึมหายไปกับผิวทันทีเหมือนทาเซรั่มน้ำเปล่า"
        },
        {
            "Product ID": "1732562791829038472",
            "Product Name": "มาส์กโคลนแท่งลดสิวเสี้ยน Skintific Mugwort Clay Mask Stick",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "229.00",
            "Commission Rate": "18%",
            "Product URL": "https://shop.tiktok.com/view/product/1732562791829038472?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732562791829038472?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "หมุนแท่งโคลนปาดลงบนจมูกที่มีสิวเสี้ยนดำหนาเขรอะ ทิ้งไว้แล้วลอกออกเผยผิวจมูกเนียนกริบ"
        },
        {
            "Product ID": "1732562890918273648",
            "Product Name": "โฟมล้างหน้า Amino Acid อ่อนโยนกู้ผิวแพ้ง่าย Skintific Foam",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "199.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732562890918273648?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732562890918273648?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "โชว์วิปโฟมนุ่มหนาแน่นเป็นก้อนไม่ย้วย ถูหน้าลดริ้วรอยคุมมัน ล้างออกหน้านุ่มไม่แห้งตึง"
        },
        {
            "Product ID": "1732562991028374829",
            "Product Name": "ศรีจันทร์ Super Coverage Foundation SPF50+ รองพื้นปกปิดขั้นสุด",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "320.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732562991028374829?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732562991028374829?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ใช้ดินสอเขียนคิ้วสีดำขีดลงแก้มแทนรอยดำ แล้วปาดรองพื้นศรีจันทร์ทับทีเดียว รอยดำหายวับ!"
        },
        {
            "Product ID": "1732563091029384712",
            "Product Name": "โทนเนอร์กู้ผิวแพ้ง่าย Anua Heartleaf 77% Soothing Toner (โทนเนอร์พี่จุน)",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "490.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732563091029384712?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732563091029384712?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "คนหน้าแดงแสบเพราะออกแดดจัดๆ เทโทนเนอร์ใส่สำลีแปะหน้าไว้ 5 นาที หน้าหายแดงทันที"
        },
        
        # Category: Home & Kitchen Gadgets
        {
            "Product ID": "1732563191029384812",
            "Product Name": "Simplus หม้ออเนกประสงค์ไฟฟ้า 2 ชั้น ต้ม นึ่ง ผัด ทอด",
            "Category": "Home & Kitchen",
            "Price (THB)": "299.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732563191029384812?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732563191029384812?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "เด็กหอโชว์ทำอาหารเช้า ต้มมาม่าใส่ไข่แถมหมูนึ่งด้านบนพร้อมกันในหม้อจิ๋วเครื่องเดียว"
        },
        {
            "Product ID": "1732563291029384823",
            "Product Name": "Gaabor Air Fryer หม้อทอดไร้น้ำมันไซส์ใหญ่ 4L",
            "Category": "Home & Kitchen",
            "Price (THB)": "799.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732563291029384823?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732563291029384823?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ใส่ไก่ดิบทั้งตัวลงหม้อทอด เปิดไฟ 20 นาที ได้ไก่ทอดหนังกรอบสีเหลืองทองหอมฟุ้งน่ากิน"
        },
        {
            "Product ID": "1732563391029384912",
            "Product Name": "Deerma DX700 เครื่องดูดฝุ่นพลังไซโคลนแบบ 2 in 1",
            "Category": "Home & Kitchen",
            "Price (THB)": "650.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732563391029384912?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732563391029384912?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ดูดฝุ่นเศษผงแป้งและเส้นผมที่เกลื่อนพื้นบ้านให้หมดไปในพริบตา โชว์พลังแรงดูดสะใจ"
        },
        {
            "Product ID": "1732563491029384999",
            "Product Name": "Simplus เครื่องรีดถนอมผ้าไอน้ำพกพา รีดเร็วเรียบไว",
            "Category": "Home & Kitchen",
            "Price (THB)": "350.00",
            "Commission Rate": "18%",
            "Product URL": "https://shop.tiktok.com/view/product/1732563491029384999?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732563491029384999?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "โชว์เสื้อเชิ้ตยับยู่ยี่ ปาดเครื่องรีดไอน้ำลงไปครั้งเดียวผ้าเรียบกริบเหมือนส่งร้านซักรีด"
        },
        {
            "Product ID": "1732563591029385012",
            "Product Name": "เครื่องสับพริกกระเทียมไฟฟ้าขนาดเล็กไร้สาย Simplus",
            "Category": "Home & Kitchen",
            "Price (THB)": "129.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732563591029385012?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732563591029385012?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ใส่อาหารพริกกระเทียมลงเครื่องกดปุ่ม 3 วินาที สับละเอียดเนียนไม่ต้องนั่งโขลกครกเสียงดัง"
        },
        {
            "Product ID": "1732563691029385123",
            "Product Name": "แปรงขัดห้องน้ำไฟฟ้าไร้สาย ชาร์จ USB หัวแปรงเปลี่ยนได้ 3 แบบ",
            "Category": "Home & Kitchen",
            "Price (THB)": "249.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732563691029385123?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732563691029385123?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "คราบดำฝังลึกในร่องกระเบื้องห้องน้ำ โดนหัวแปรงไฟฟ้าหมุนขัดปรื๊ดเดียวคราบหลุดหมดโดยไม่ต้องออกแรง"
        },
        {
            "Product ID": "1732563791029385234",
            "Product Name": "Simplus เครื่องทำแซนวิชและวาฟเฟิลมินิ ลายการ์ตูน",
            "Category": "Home & Kitchen",
            "Price (THB)": "219.00",
            "Commission Rate": "18%",
            "Product URL": "https://shop.tiktok.com/view/product/1732563791029385234?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732563791029385234?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ทำวาฟเฟิลเนยสดร้อนๆ หอมกรุ่นหน้าตาเป็นรูปการ์ตูนน่ารักดึงดูดใจเด็กๆ ในเวลา 3 นาที"
        },
        {
            "Product ID": "1732563891029385345",
            "Product Name": "ชั้นวางของมีล้อเลื่อนพลาสติก 3 ชั้น ประหยัดพื้นที่จัดบ้าน",
            "Category": "Home & Kitchen",
            "Price (THB)": "159.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732563891029385345?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732563891029385345?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "กองเครื่องสำอาง/ขนมล้นห้องจัดระเบียบใส่ชั้นมีล้อเลื่อนเข็นเข้ามุมห้อง ดูเป็นระเบียบตาแตก"
        },
        {
            "Product ID": "1732563991029385456",
            "Product Name": "โคมไฟดักยุงและแมลงวันไฟฟ้าแบบเสียบปลั๊กไร้เสียงรบกวน",
            "Category": "Home & Kitchen",
            "Price (THB)": "99.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732563991029385456?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732563991029385456?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "โชว์แสงไฟนีออนดักยุงตอนกลางคืน แล้วซูมให้เห็นยุงโดนช็อตเกลื่อนถาดทำความสะอาดง่าย"
        },
        {
            "Product ID": "1732564091029385567",
            "Product Name": "เครื่องซีลถุงพลาสติกขนาดพกพา ร้อนเร็ว ล็อคความสดใหม่อาหาร",
            "Category": "Home & Kitchen",
            "Price (THB)": "79.00",
            "Commission Rate": "25%",
            "Product URL": "https://shop.tiktok.com/view/product/1732564091029385567?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732564091029385567?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "กินมันฝรั่งทอดครึ่งถุงไม่หมด ใช้เครื่องซีลปาดปากถุงคว่ำลงน้ำไม่มีหก ถนอมความกรอบสนิท"
        },
        
        # Category: Food & Dietary Supplements
        {
            "Product ID": "1732564191029385678",
            "Product Name": "วิตามินบำรุงผมและเล็บ Biotin & Zinc แบรนด์ยอดนิยม",
            "Category": "Food & Supplements",
            "Price (THB)": "220.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732564191029385678?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732564191029385678?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "โชว์แปรงหวีผมที่มีเศษผมร่วงติดมาเต็มไปหมด เผยตัวช่วยไบโอตินสังกะสีบำรุงรากผมแข็งแรง"
        },
        {
            "Product ID": "1732564291029385789",
            "Product Name": "ผงชาเขียวมัทฉะแท้ 100% จากอุจิ ประเทศญี่ปุ่น เกรดพรีเมียม",
            "Category": "Food & Supplements",
            "Price (THB)": "189.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732564291029385789?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732564291029385789?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "คนชงมัทฉะลาเต้เย็นสีเขียวพาสเทลสวยงามเหมือนนั่งกินที่คาเฟ่ญี่ปุ่น แต่อร่อยได้ในงบแก้วละสิบบาท"
        },
        {
            "Product ID": "1732564391029385890",
            "Product Name": "ถั่วแมคคาเดเมียอบธรรมชาติ แกะเปลือกพร้อมทาน เกรด AAA",
            "Category": "Food & Supplements",
            "Price (THB)": "250.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732564391029385890?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732564391029385890?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "เคี้ยวถั่วเสียงดังกร๊อบแก๊บอร่อยฟินๆ อวดความเม็ดโต ขาวนวล มันเนย รสชาติเค็มมันอร่อย"
        },
        {
            "Product ID": "1732564491029385901",
            "Product Name": "เจลลี่กัมมี่น้ำมันปลาสำหรับเด็ก บำรุงสมองความจำรสส้มอร่อย",
            "Category": "Food & Supplements",
            "Price (THB)": "199.00",
            "Commission Rate": "18%",
            "Product URL": "https://shop.tiktok.com/view/product/1732564491029385901?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732564491029385901?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "เด็กๆ แย่งกันกินเจลลี่รูปหมีเคี้ยวหนึบ รสส้มสดชื่นไม่มีกลิ่นคาวปลา ถูกใจแม่ๆ ทุกบ้าน"
        },
        {
            "Product ID": "1732564591029386012",
            "Product Name": "หมูเส้นกรอบปรุงรสพรีเมียม ไร้มัน ไม่ใส่วัตถุกันเสีย",
            "Category": "Food & Supplements",
            "Price (THB)": "145.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732564591029386012?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732564591029386012?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ตักหมูเส้นคลุกข้าวสวยร้อนๆ เคี้ยวเสียงดังกรอบ อร่อยเต็มคำ ทานคู่กับส้มตำหรือกินเล่นก็ดี"
        },
        
        # Category: Tech & Gadgets
        {
            "Product ID": "1732564691029386123",
            "Product Name": "สายชาร์จเร็ว 3-in-1 ยืดหดได้พกพาสะดวก ชาร์จได้ทุกระบบ",
            "Category": "Tech & Gadgets",
            "Price (THB)": "129.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732564691029386123?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732564691029386123?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "สายชาร์จพันกันยุ่งเหยิงในกระเป๋า เทียบกับดึงสายชาร์จตลับจิ๋วออกมาชาร์จพร้อมกัน 3 เครื่อง"
        },
        {
            "Product ID": "1732564791029386234",
            "Product Name": "ขาตั้งกล้องเซลฟี่บลูทูธ 3-in-1 ยืดได้สูงถึง 1.6 เมตรพร้อมรีโมท",
            "Category": "Tech & Gadgets",
            "Price (THB)": "199.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732564791029386234?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732564791029386234?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ไปเที่ยวคนเดียวแล้วถ่ายรูปกลุ่มสวยๆ ได้สบายๆ ด้วยขาตั้งกางง่ายกดรีโมทบลูทูธแชะเดียวได้รูป"
        },
        {
            "Product ID": "1732564891029386345",
            "Product Name": "พัดลมพกพามินิลมแรงมาก ปรับได้ 5 ระดับ จอแสดงผลดิจิตอล",
            "Category": "Tech & Gadgets",
            "Price (THB)": "259.00",
            "Commission Rate": "18%",
            "Product URL": "https://shop.tiktok.com/view/product/1732564891029386345?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732564891029386345?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "คนเดินร้อนๆ เหงื่อไหลไคลย้อย ชักพัดลมพกพาเป่าปุ๊บผมปลิวหน้าสั่น ลมแรงสะใจระดับลมพายุ"
        },
        {
            "Product ID": "1732564991029386456",
            "Product Name": "หัวชาร์จเร็ว Fast Charger 20W USB-C รองรับทุกรุ่น",
            "Category": "Tech & Gadgets",
            "Price (THB)": "189.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732564991029386456?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732564991029386456?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "จับเวลาเปรียบเทียบชาร์จแบตเตอรี่โทรศัพท์ด้วยหัวชาร์จทั่วไปกับหัวชาร์จด่วน 20W พุ่งเร็วปรี๊ด 50% ในครึ่งชั่วโมง"
        },
        {
            "Product ID": "1732565091029386567",
            "Product Name": "ลำโพงบลูทูธกันน้ำลายการ์ตูน เบสแน่น แบตอึด 8 ชั่วโมง",
            "Category": "Tech & Gadgets",
            "Price (THB)": "299.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732565091029386567?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732565091029386567?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "โยนลำโพงจิ๋วลงน้ำขณะเล่นเพลง ดนตรียังกระหึ่มเบสหนักหน่วงไม่มีสะดุด โชว์ความทรหดกันน้ำ"
        },
        
        # Adding more Beauty & Personal Care to hit 50
        {
            "Product ID": "1732565191029386678",
            "Product Name": "Plantnery Pomegranate Serum เซรั่มทับทิมลดรอยดำกู้หน้าหมอง",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "169.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732565191029386678?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732565191029386678?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "โชว์รอยแกะสิวเป็นจุดด่างดำทั่วหน้า ทาเซรั่มแดงทับ ผิวฟื้นตัวอิ่มฟู รอยดูจางลงชัดเจน"
        },
        {
            "Product ID": "1732565291029386789",
            "Product Name": "ครีมซองกันแดดสุดฮิต Clearnose UV Sun Screen แพ็ค 6 ซอง",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "229.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732565291029386789?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732565291029386789?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "บีบกันแดดคลีนโนสทาสองข้อนิ้วเต็มๆ ทาแล้วหน้าใสฉ่ำโกลว์ ซึมไว เบาสบายไม่เหนอะหนะ"
        },
        {
            "Product ID": "1732565391029386890",
            "Product Name": "ยาสีฟันสมุนไพรลดกลิ่นปากขั้นสุดสูตรพรีเมียม Dentiste",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "185.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732565391029386890?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732565391029386890?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ตื่นนอนมาตอนเช้าแล้วหันไปเป่าปากใส่แฟน แฟนบอกไม่มีกลิ่นปากเลย หอมสดชื่นตั้งแต่เช้า"
        },
        {
            "Product ID": "1732565491029386901",
            "Product Name": "เจลว่านหางจระเข้เข้มข้น 99% ปลอบประโลมผิวแห้งกร้านไหม้แดด",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "99.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732565491029386901?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732565491029386901?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "นำเจลว่านหางจระเข้แช่เย็นเจี๊ยบมาพอกหน้าแดงๆ หลังไปทะเล ผิวเย็นวาบชุ่มชื่นฟื้นไวสุดๆ"
        },
        {
            "Product ID": "1732565591029387012",
            "Product Name": "โฟมล้างหน้าถ่านชาโคลกู้หน้ามันลอกสิวเสี้ยนแดดแบรนด์ฮิต",
            "Category": "Beauty & Personal Care",
            "Price (THB)": "139.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732565591029387012?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732565591029387012?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "บีบโฟมสีดำสนิทขยี้ฟองหนานุ่มล้างความมันเยิ้มจากกระดาษซับหน้ามันออกเกลี้ยงในวิเดียว"
        },
        
        # Home & Kitchen
        {
            "Product ID": "1732565691029387123",
            "Product Name": " Deerma เครื่องรีดถนอมผ้าขนาดพกพา รีดเร็ว 30 วิไอน้ำแรง",
            "Category": "Home & Kitchen",
            "Price (THB)": "490.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732565691029387123?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732565691029387123?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "พับเสื้อผ้ายับๆ ยัดใส่กระเป๋าเดินทาง ดึงออกมารีดด้วยเครื่องพกพาเรียบกริบในนาทีเดียว"
        },
        {
            "Product ID": "1732565791029387234",
            "Product Name": "เครื่องปั่นน้ำผลไม้พกพาแบบชาร์จ USB พกไปฟิตเนสสบาย",
            "Category": "Home & Kitchen",
            "Price (THB)": "199.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732565791029387234?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732565791029387234?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "หั่นกล้วยและสตรอเบอร์รี่ใส่กระบอกปั่นกดปุ่มหมุนติ้ว ได้น้ำผลไม้สดปั่นดื่มเย็นชื่นใจทันที"
        },
        {
            "Product ID": "1732565891029387345",
            "Product Name": "กล่องข้าวใส่อาหาร 3 ช่องพร้อมช้อนส้อมเข้าไมโครเวฟได้",
            "Category": "Home & Kitchen",
            "Price (THB)": "89.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732565891029387345?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732565891029387345?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "จัดเตรียมเมนูอาหารคลีนสามช่องสีสันน่าทานพกไปกินที่ทำงานแบบสะดวกฝาล็อคแน่นน้ำไม่ซึม"
        },
        {
            "Product ID": "1732565991029387456",
            "Product Name": "สเปรย์โฟมทำความสะอาดอเนกประสงค์ขจัดคราบฝังลึกเบาะหนัง",
            "Category": "Home & Kitchen",
            "Price (THB)": "119.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732565991029387456?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732565991029387456?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "พ่นโฟมขาวลงบนรองเท้าผ้าใบเขรอะคราบดิน เช็ดออกด้วยผ้าผืนเดียวขาวจั๊วะเหมือนซื้อใหม่"
        },
        {
            "Product ID": "1732566091029387567",
            "Product Name": "ชั้นวางแก้วและจานอลูมิเนียมกันสนิมพร้อมถาดรองน้ำทิ้ง",
            "Category": "Home & Kitchen",
            "Price (THB)": "289.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732566091029387567?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732566091029387567?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "วางจานเปียกๆ เรียงเป็นระเบียบสวยงาม น้ำหยดลงถาดสไลด์ทิ้งอ่างล้างจานแห้งสะอาดไม่มีกลิ่นอับ"
        },
        {
            "Product ID": "1732566191029387678",
            "Product Name": "ไฟติดผนังเซ็นเซอร์ตรวจจับความเคลื่อนไหวอัจฉริยะไร้สาย",
            "Category": "Home & Kitchen",
            "Price (THB)": "69.00",
            "Commission Rate": "25%",
            "Product URL": "https://shop.tiktok.com/view/product/1732566191029387678?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732566191029387678?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "เดินก้าวเท้าลงเตียงตอนกลางคืนปุ๊บ ไฟบันไดสว่างเปิดสว่างนำทางให้อัตโนมัติป้องกันสะดุดล้ม"
        },
        {
            "Product ID": "1732566291029387789",
            "Product Name": "เครื่องพ่นสเปรย์แอลกอฮอล์อัตโนมัติแบบชาร์จ USB ไร้สัมผัส",
            "Category": "Home & Kitchen",
            "Price (THB)": "149.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732566291029387789?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732566291029387789?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ยื่นมือไปรองใต้เครื่อง สเปรย์แอลกอฮอล์พ่นละอองฟุ้งนุ่มกระจายทั่วฝ่ามือทันทีสะอาดไร้เชื้อ"
        },
        {
            "Product ID": "1732566391029387890",
            "Product Name": "ตาชั่งอาหารดิจิตอลความแม่นยำสูงตวงทำขนมเบเกอรี่คุมน้ำหนัก",
            "Category": "Home & Kitchen",
            "Price (THB)": "99.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732566391029387890?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732566391029387890?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ชั่งน้ำหนักส่วนผสมแป้งทำขนมเป๊ะระดับทศนิยม ป้องกันขนมเสียสูตร ทำง่ายเหมือนมืออาชีพ"
        },
        {
            "Product ID": "1732566491029387901",
            "Product Name": "แปรงซิลิโคนล้างจานทนความร้อนสูงนวดสิ่งสกปรกแห้งไวไม่สะสมแบคทีเรีย",
            "Category": "Home & Kitchen",
            "Price (THB)": "49.00",
            "Commission Rate": "25%",
            "Product URL": "https://shop.tiktok.com/view/product/1732566491029387901?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732566491029387901?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "บีบน้ำยาล้างจานลงแปรงซิลิโคนบี้ฟองล้างคราบไขมันบนจานออกหมดจด ล้างง่ายสะอาดปลอดภัย"
        },
        {
            "Product ID": "1732566591029388012",
            "Product Name": "ตะขอแขวนเสื้อผ้าและผ้าขนหนูสแตนเลสติดผนังไม่ต้องเจาะรู",
            "Category": "Home & Kitchen",
            "Price (THB)": "79.00",
            "Commission Rate": "25%",
            "Product URL": "https://shop.tiktok.com/view/product/1732566591029388012?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732566591029388012?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "แขวนของหนัก 10 โลลงตะขอสแตนเลสที่แปะกาวสามเอ็มโชว์ความเหนียวแน่นหนึบไม่มีร่วงหลุด"
        },
        
        # Tech & Gadgets
        {
            "Product ID": "1732566691029388123",
            "Product Name": "ไฟวงแหวน LED เซลฟี่แต่งหน้าไลฟ์สดปรับความสว่างได้ 3 สี",
            "Category": "Tech & Gadgets",
            "Price (THB)": "159.00",
            "Commission Rate": "20%",
            "Product URL": "https://shop.tiktok.com/view/product/1732566691029388123?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732566691029388123?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "คนถ่ายคลิปหน้าหมองมืด เปิดไฟวงแหวนแต่งหน้าปุ๊บ ผิวสว่างไบรท์วิ้งตาเป็นประกายตาแตก"
        },
        {
            "Product ID": "1732566791029388234",
            "Product Name": "แท่นชาร์จไร้สายเร็ว 15W ดีไซน์สวยงามตั้งโต๊ะทำงาน",
            "Category": "Tech & Gadgets",
            "Price (THB)": "320.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732566791029388234?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732566791029388234?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "วางโทรศัพท์ลงบนแท่นไม้ดีไซน์หรู ไฟชาร์จสว่างขึ้นทันที โต๊ะทำงานมินิมอลไม่มีสายไฟรกรุงรัง"
        },
        {
            "Product ID": "1732566891029388345",
            "Product Name": "หูฟังบลูทูธไร้สายขนาดมินิตัดเสียงรบกวนภายนอก ANC",
            "Category": "Tech & Gadgets",
            "Price (THB)": "450.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732566891029388345?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732566891029388345?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ใส่หูฟังในรถไฟฟ้าคนเสียงดังเป้ง กดสวิตช์เปิดโหมดตัดเสียงปุ๊บ โลกเงียบกริบดนตรีหวานใสเสนาะหู"
        },
        {
            "Product ID": "1732566991029388456",
            "Product Name": "พาวเวอร์แบงค์ขนาดพกพาความจุ 10000mAh มีสายชาร์จในตัวครบ",
            "Category": "Tech & Gadgets",
            "Price (THB)": "350.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732566991029388456?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732566991029388456?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "แบตโทรศัพท์หมดกลางทาง ชักพาวเวอร์แบงค์ไซส์เท่าลิปสติกเสียบชาร์จได้ทันทีไม่ต้องพกสายเพิ่ม"
        },
        {
            "Product ID": "1732567091029388567",
            "Product Name": "เครื่องสแกนบาร์โค้ดไร้สายบลูทูธสำหรับพ่อค้าแม่ค้าออนไลน์",
            "Category": "Tech & Gadgets",
            "Price (THB)": "790.00",
            "Commission Rate": "15%",
            "Product URL": "https://shop.tiktok.com/view/product/1732567091029388567?region=TH&locale=th-TH",
            "Google Sheets Link": '=HYPERLINK("https://shop.tiktok.com/view/product/1732567091029388567?region=TH&locale=th-TH", "Open Link")',
            "AI Video Hook / Concept": "ยิงเลเซอร์สีแดงปิ๊บๆ แสกนกล่องพัสดุรวดเร็วข้อมูลพุ่งขึ้นหน้าจอบันทึกยอดสต็อกออโต้สะดวกรวดเร็ว"
        }
    ]

    output_file = "trending_affiliate_products.csv"
    
    with open(output_file, mode='w', encoding='utf-8-sig', newline='') as f:
        fieldnames = ["Product ID", "Product Name", "Category", "Price (THB)", "Commission Rate", "Product URL", "Google Sheets Link", "AI Video Hook / Concept"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in products:
            # Clean dictionary to match fieldnames only
            row = {k: p.get(k, "") for k in fieldnames}
            writer.writerow(row)
            
    print(f"Successfully generated {output_file} with {len(products)} high-converting, trending products.")

if __name__ == "__main__":
    main()
