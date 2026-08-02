import json
import os

def main():
    if not os.path.exists("captured_orders_api.json"):
        print("captured_orders_api.json not found!")
        return
        
    with open("captured_orders_api.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"Total API calls intercepted: {len(data)}")
    for idx, item in enumerate(data):
        print(f"[{idx}] {item['status']} | {item['url']}")
        # Print a small slice of data to see if there's any error
        json_str = json.dumps(item['data'])
        if "error" in json_str.lower() or "fail" in json_str.lower() or "code" in json_str.lower():
            print(f"  -> Data keys: {list(item['data'].keys())}")
            if "message" in item['data']:
                print(f"  -> Message: {item['data']['message']}")
            if "code" in item['data']:
                print(f"  -> Code: {item['data']['code']}")
            if "err_msg" in item['data']:
                print(f"  -> Err Msg: {item['data']['err_msg']}")

if __name__ == "__main__":
    main()
