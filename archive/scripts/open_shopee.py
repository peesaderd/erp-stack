import os
import sys
import json
import time
from playwright.sync_api import sync_playwright

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    profile_dir = os.path.abspath(".firefox_shopee_profile")
    print(f"Using persistent Firefox profile in: {profile_dir}")
    
    os.makedirs(profile_dir, exist_ok=True)
    
    with sync_playwright() as p:
        print("Launching Firefox browser in headed mode...")
        # Launch headed Firefox so the user can interact and log in
        context = p.firefox.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
            
        print("Opening Shopee Login Page...")
        try:
            page.goto("https://shopee.co.th/buyer/login")
        except Exception as e:
            print(f"Error loading Shopee: {e}")
            
        print("\n" + "="*60)
        print("คำแนะนำสำหรับการล็อกอิน Shopee:")
        print("1. หน้าต่างเบราว์เซอร์ Firefox ได้เปิดขึ้นบนหน้าจอของคุณแล้ว")
        print("2. กรุณาทำการล็อกอินเข้าสู่บัญชี Shopee ของคุณให้เรียบร้อย (กรอกรหัส หรือสแกน QR)")
        print("3. เมื่อเข้าสู่ระบบสำเร็จและเห็นหน้าหลักของ Shopee แล้ว")
        print("   ให้กด 'ปิดหน้าต่างเบราว์เซอร์ Firefox' เพื่อบันทึกคุกกี้และจบการทำงาน")
        print("="*60 + "\n")
        
        # Monitor the browser until the user closes the window
        while True:
            try:
                # Query page URL to check if browser is still open
                _ = page.url
            except Exception:
                print("ตรวจพบว่าหน้าต่างเบราว์เซอร์ Firefox ถูกปิดลงแล้ว")
                break
            time.sleep(1)
            
        print("กำลังดึงข้อมูลคุกกี้...")
        try:
            cookies = context.cookies()
            
            # Format and normalize cookies for Playwright compatibility
            clean_cookies = []
            for c in cookies:
                clean_c = {
                    "name": c["name"],
                    "value": c["value"]
                }
                if "domain" in c:
                    clean_c["domain"] = c["domain"]
                if "path" in c:
                    clean_c["path"] = c["path"]
                if "expires" in c:
                    clean_c["expires"] = c["expires"]
                elif "expirationDate" in c:
                    clean_c["expires"] = c["expirationDate"]
                if "httpOnly" in c:
                    clean_c["httpOnly"] = c["httpOnly"]
                if "secure" in c:
                    clean_c["secure"] = c["secure"]
                if "sameSite" in c:
                    val = c["sameSite"]
                    if val is None:
                        clean_c["sameSite"] = "None"
                    elif isinstance(val, str):
                        val_lower = val.lower()
                        if "none" in val_lower or "no_restriction" in val_lower:
                            clean_c["sameSite"] = "None"
                        elif "lax" in val_lower:
                            clean_c["sameSite"] = "Lax"
                        elif "strict" in val_lower:
                            clean_c["sameSite"] = "Strict"
                clean_cookies.append(clean_c)
                
            output_file = "shopee_cookies.json"
            with open(output_file, 'w', encoding='utf-8') as f_out:
                json.dump(clean_cookies, f_out, indent=4, ensure_ascii=False)
                
            print(f"บันทึกคุกกี้จำนวน {len(clean_cookies)} ตัวลงในไฟล์ {output_file} สำเร็จแล้ว!")
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการดึงคุกกี้: {e}")
            
        context.close()
        print("ปิดโปรแกรมเรียบร้อย!")

if __name__ == "__main__":
    main()
