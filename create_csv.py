import csv
import os
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    
    # Exact products from TikTok Shop Thailand with active IDs, categories, commissions, and links
    products = [
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
        }
    ]

    output_file = "trending_affiliate_products.csv"
    
    with open(output_file, mode='w', encoding='utf-8-sig', newline='') as f:
        fieldnames = ["Product ID", "Product Name", "Category", "Price (THB)", "Commission Rate", "Product URL", "Google Sheets Link", "AI Video Hook / Concept"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in products:
            writer.writerow(p)
            
    print(f"Successfully updated {output_file} with Sheet-friendly formulas.")

if __name__ == "__main__":
    main()
