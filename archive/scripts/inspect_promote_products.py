import json
import os
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    
    file_path = "captured_affiliate_orders.json"
    if not os.path.exists(file_path):
        print(f"{file_path} not found!")
        return
        
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for idx, item in enumerate(data):
        url = item['url']
        if "promote_products/list" in url:
            print(f"\n[{idx}] promote_products/list:")
            print(json.dumps(item['data'], indent=2, ensure_ascii=False)[:1000])
            print("="*60)
            
        if "promote_products/count" in url:
            print(f"\n[{idx}] promote_products/count:")
            print(json.dumps(item['data'], indent=2, ensure_ascii=False))
            print("="*60)

if __name__ == "__main__":
    main()
