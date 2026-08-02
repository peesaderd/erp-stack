import os
import csv
import sys
from google import genai
from google.genai import types

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    # Load API Key from environment or .env file in home directory
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Check if .env file exists in project root or home directory
        env_paths = [os.path.abspath(".env"), os.path.expanduser("~/.env")]
        for p in env_paths:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("GEMINI_API_KEY="):
                            api_key = line.split("=", 1)[1].strip()
                            break
            if api_key:
                break
                
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables or ~/.env file.")
        print("Please configure your API key first using the recommended commands.")
        sys.exit(1)
        
    # Initialize Google GenAI client
    client = genai.Client(api_key=api_key)
    
    input_file = "trending_affiliate_products.csv"
    output_file = "trending_products_with_scripts.csv"
    
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found!")
        sys.exit(1)
        
    print(f"Reading products from {input_file}...")
    with open(input_file, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
        
    # Check if we already have script columns, if not add them
    new_fields = ["Video Hook Script (TH)", "Video Body Script (TH)", "Video Call To Action (TH)"]
    for field in new_fields:
        if field not in fieldnames:
            fieldnames.append(field)
            
    print(f"Generating scripts for {len(rows)} products using Gemini API...")
    
    for idx, row in enumerate(rows):
        name = row.get("Product Name")
        category = row.get("Category")
        price = row.get("Price (THB)")
        hook_concept = row.get("AI Video Hook / Concept")
        
        print(f"[{idx+1}/{len(rows)}] Generating for: {name[:50]}...")
        
        prompt = f"""
คุณเป็นผู้เชี่ยวชาญการทำวิดีโอสั้นและนักการตลาดดิจิทัลบน TikTok Shop (Affiliate) ประเทศไทย
กรุณาสร้างบทพูด (Script) วิดีโอสั้นภาษาไทยเพื่อนำเสนอสินค้าชิ้นนี้ให้ขายดีและดึงดูดใจผู้ชมมากที่สุด

ข้อมูลสินค้า:
- ชื่อสินค้า: {name}
- หมวดหมู่: {category}
- ราคา: {price} บาท
- คอนเซปต์/จุดเด่นของวิดีโอ: {hook_concept}

กรุณาเขียนบทวิดีโอแบ่งออกเป็น 3 ส่วนชัดเจนในรูปแบบ JSON:
1. "hook": บทพูดเปิดตัว 3 วินาทีแรกที่ดึงความสนใจทันที (ห้ามเกริ่นยาว ต้องเข้าเรื่องดึงดูดใจ)
2. "body": บทพูดอธิบายจุดเด่นของสินค้า ปัญหาที่ช่วยแก้ และความคุ้มค่า (ประมาณ 10-15 วินาที)
3. "c2a": บทพูดปิดท้ายกระตุ้นการสั่งซื้อ (Call to Action) เช่น การชี้เป้าหรือสั่งซื้อที่ตะกร้าเหลือง (ประมาณ 3-5 วินาที)

ให้ตอบกลับเฉพาะ JSON ในรูปแบบต่อไปนี้เท่านั้น ห้ามมีคำอธิบายอื่นนอกเหนือจาก JSON:
{{
  "hook": "บทพูดตรงนี้...",
  "body": "บทพูดตรงนี้...",
  "c2a": "บทพูดตรงนี้..."
}}
"""
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            res_text = response.text.strip()
            res_json = json.loads(res_text)
            
            row["Video Hook Script (TH)"] = res_json.get("hook", "")
            row["Video Body Script (TH)"] = res_json.get("body", "")
            row["Video Call To Action (TH)"] = res_json.get("c2a", "")
            
        except Exception as e:
            print(f"  -> Error generating script for {name}: {e}")
            row["Video Hook Script (TH)"] = f"Error: {e}"
            row["Video Body Script (TH)"] = ""
            row["Video Call To Action (TH)"] = ""
            
    print(f"Writing updated products and scripts to {output_file}...")
    with open(output_file, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            
    print("Done! AI script generation completed successfully.")

if __name__ == "__main__":
    main()
