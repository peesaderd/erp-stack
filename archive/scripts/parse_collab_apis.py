import json
import os
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    
    file_path = "captured_collab.json"
    if not os.path.exists(file_path):
        print(f"{file_path} not found!")
        return
        
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for idx, item in enumerate(data):
        url = item['url']
        # Look for product lists or product queries
        if "product" in url or "promote" in url:
            print(f"\n[{idx}] {url[:100]}")
            res_data = item['data']
            if isinstance(res_data, dict):
                # Search for fields that might contain product info
                for key in ["products", "sku_products", "unpromote_products", "list", "data"]:
                    if key in res_data:
                        print(f"  -> Found key '{key}'")
                    if "data" in res_data and isinstance(res_data["data"], dict) and key in res_data["data"]:
                        print(f"  -> Found key '{key}' inside data")
                # Let's print the full JSON if it's small or has few keys
                print(json.dumps(res_data, indent=2, ensure_ascii=False)[:600])
                print("-" * 50)

if __name__ == "__main__":
    main()
