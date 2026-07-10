import json
import os
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    
    file_path = "compass_captured.json"
    if not os.path.exists(file_path):
        print(f"{file_path} not found!")
        return
        
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"Total API calls intercepted: {len(data)}")
    for idx, item in enumerate(data):
        url = item['url']
        if "insights" in url or "ranking" in url or "rank" in url:
            print(f"\n[{idx}] {item['status']} | {url[:120]}")
            res_data = item['data']
            if isinstance(res_data, dict):
                print(f"  -> Keys: {list(res_data.keys())}")
                # print a snippet
                print(json.dumps(res_data, indent=2, ensure_ascii=False)[:500])
                print("-" * 50)

if __name__ == "__main__":
    main()
