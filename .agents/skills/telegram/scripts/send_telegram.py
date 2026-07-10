import os
import sys
import argparse
import urllib.request
import urllib.parse
import json

def send_message(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    req_data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    import ssl
    context = ssl._create_unverified_context()
    
    try:
        with urllib.request.urlopen(req, timeout=15, context=context) as response:
            resp_data = json.loads(response.read().decode("utf-8"))
            if resp_data.get("ok"):
                print("SUCCESS: Telegram notification sent successfully.")
                return True
            else:
                print(f"ERROR: Failed to send Telegram message: {resp_data}")
                return False
    except Exception as e:
        print(f"ERROR: Exception occurred while sending to Telegram: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Send a message to a Telegram chat/channel.")
    parser.add_argument("--message", required=True, help="The message content to send.")
    parser.add_argument("--token", help="Telegram Bot Token.")
    parser.add_argument("--chat-id", help="Telegram Chat ID.")
    args = parser.parse_args()
    
    # Resolve credentials: args -> env -> dotenv file
    token = args.token or os.environ.get("TELEGRAM_NOTIFY_TOKEN")
    chat_id = args.chat_id or os.environ.get("TELEGRAM_NOTIFY_CHAT_ID")
    
    # Try reading from workspace .env file if still not found
    if not token or not chat_id:
        try:
            # Dynamically traverse upwards from current script file to find .env
            curr_dir = os.path.dirname(os.path.abspath(__file__))
            env_path = None
            for _ in range(6): # search up to 6 parent levels
                check_path = os.path.join(curr_dir, ".env")
                if os.path.exists(check_path):
                    env_path = check_path
                    break
                parent = os.path.dirname(curr_dir)
                if parent == curr_dir:
                    break
                curr_dir = parent
                
            if env_path and os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip() and not line.strip().startswith("#"):
                            parts = line.strip().split("=", 1)
                            if len(parts) == 2:
                                key, val = parts[0].strip(), parts[1].strip()
                                val = val.strip("'\"")
                                if key == "TELEGRAM_NOTIFY_TOKEN" and not token:
                                    token = val
                                elif key == "TELEGRAM_NOTIFY_CHAT_ID" and not chat_id:
                                    chat_id = val
        except Exception:
            pass
            
    if not token or not chat_id:
        print("ERROR: Telegram Bot Token and Chat ID are required.")
        print("Please configure them via arguments or environment variables (TELEGRAM_NOTIFY_TOKEN, TELEGRAM_NOTIFY_CHAT_ID).")
        sys.exit(1)
        
    success = send_message(token, chat_id, args.message)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
