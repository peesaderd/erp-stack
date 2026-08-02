import os

log_path = r"C:\Users\ADMIN\.gemini\antigravity\brain\2888f6d4-729a-4739-8977-7ae3d5a0d165\.system_generated\tasks\task-188.log"

if os.path.exists(log_path):
    print("Log exists!")
    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
        print(f.read())
else:
    print("Log not found at:", log_path)
