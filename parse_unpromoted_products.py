import json
import os
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    
    file_path = "captured_add_products.json"
    if not os.path.exists(file_path):
        print(f"{file_path} not found!")
        return
        
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    found_api = False
    for idx, item in enumerate(data):
        url = item['url']
        if "product_selection/list" in url:
            found_api = True
            print(f"\n[{idx}] Found Product Selection List API Call:")
            print(f"URL: {url}")
            res_data = item['data']
            print("\nResponse Data:")
            print(json.dumps(res_data, indent=4, ensure_ascii=False))
            
    if not found_api:
        print("product_selection/list API Call not found in captured responses.")

if __name__ == "__main__":
    main()
