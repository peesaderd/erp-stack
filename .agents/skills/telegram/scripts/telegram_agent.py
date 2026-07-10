import os
import sys
import time
import urllib.request
import urllib.parse
import json
import ssl
import socket
import csv
import threading

# Global chat sessions mapping (to keep conversation history)
chat_histories = {}

def safe_print(*args, **kwargs):
    new_args = []
    for arg in args:
        try:
            encoding = sys.stdout.encoding or 'utf-8'
            enc = str(arg).encode(encoding, errors='replace')
            new_args.append(enc.decode(encoding, errors='replace'))
        except Exception:
            new_args.append(str(arg))
    print(*new_args, **kwargs)

def get_workspace_dir():
    # 4 levels up from this script: .agents/skills/telegram/scripts/telegram_agent.py
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        curr_dir = os.path.dirname(curr_dir)
    return curr_dir

# --- Active Transcript Monitor for Approvals ---

def get_active_transcript_path():
    brain_dir = r"C:\Users\ADMIN\.gemini\antigravity\brain"
    if not os.path.exists(brain_dir):
        return None
    
    newest_time = 0
    newest_path = None
    
    try:
        subdirs = os.listdir(brain_dir)
        for subdir in subdirs:
            if subdir == "tempmediaStorage":
                continue
            path = os.path.join(brain_dir, subdir, ".system_generated", "logs", "transcript.jsonl")
            if os.path.exists(path):
                mtime = os.path.getmtime(path)
                if mtime > newest_time:
                    newest_time = mtime
                    newest_path = path
    except Exception as e:
        safe_print(f"Error finding active transcript: {e}")
        
    return newest_path

def transcript_monitor_thread(token, chat_id):
    safe_print("INFO: Active transcript monitor thread started.")
    last_notified_state = None
    last_checked_step_count = 0
    last_step_time = time.time()
    
    while True:
        try:
            path = get_active_transcript_path()
            if not path:
                time.sleep(5)
                continue
                
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            if not lines:
                time.sleep(5)
                continue
                
            step_count = len(lines)
            last_line = json.loads(lines[-1])
            step_type = last_line.get("type")
            has_tool_calls = "tool_calls" in last_line and bool(last_line["tool_calls"])
            
            # If step count changed, reset timers
            if step_count != last_checked_step_count:
                last_checked_step_count = step_count
                last_step_time = time.time()
                # Reset notify flag if we are no longer in a waiting state
                if step_type != "PLANNER_RESPONSE" or not has_tool_calls:
                    last_notified_state = None
            
            # Time elapsed in current step
            elapsed = time.time() - last_step_time
            
            # If the last step is a PLANNER_RESPONSE with tool calls, and we haven't seen a new step in 12 seconds
            if step_type == "PLANNER_RESPONSE" and has_tool_calls:
                if elapsed >= 12 and last_notified_state != "WAITING_APPROVAL":
                    tool_calls = last_line.get("tool_calls", [])
                    tools_desc = []
                    for tc in tool_calls:
                        name = tc.get("name")
                        args = tc.get("args", {})
                        if name == "run_command":
                            cmd = args.get("CommandLine", "")
                            tools_desc.append(f"รันคำสั่ง: `{cmd}`")
                        elif name == "write_to_file":
                            file = args.get("TargetFile", "")
                            tools_desc.append(f"เขียนไฟล์: `{os.path.basename(file)}`")
                        elif name == "replace_file_content" or name == "multi_replace_file_content":
                            file = args.get("TargetFile", "")
                            tools_desc.append(f"แก้ไขไฟล์: `{os.path.basename(file)}`")
                        else:
                            tools_desc.append(f"เรียกใช้เครื่องมือ: `{name}`")
                            
                    tools_str = "\n".join([f"- {desc}" for desc in tools_desc])
                    msg = (
                        "🔔 *บอท Antigravity กำลังรอการอนุมัติ (Approve)*\n\n"
                        f"มีคำขอทำงานค้างอยู่ในหน้าจอคอมพิวเตอร์ของคุณ:\n{tools_str}\n\n"
                        "กรุณาตรวจสอบและกด Approve / Proceed ใน VS Code หรือ Terminal ของคุณครับ"
                    )
                    safe_print(f"DEBUG: Sending approval notification on Telegram...")
                    send_telegram_reply(token, chat_id, msg)
                    last_notified_state = "WAITING_APPROVAL"
                    
        except Exception as e:
            safe_print(f"Error in monitor loop: {e}")
            
        time.sleep(5)

# --- Tool implementations ---

def local_list_workspace_files():
    workspace_dir = get_workspace_dir()
    files_list = []
    for root, dirs, files in os.walk(workspace_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, workspace_dir)
            try:
                stat = os.stat(full_path)
                size = stat.st_size
                mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
                files_list.append({
                    "filename": rel_path.replace(os.sep, '/'),
                    "size_bytes": size,
                    "last_modified": mtime
                })
            except Exception:
                pass
    return {"files": files_list}

def local_read_workspace_file(filename):
    workspace_dir = get_workspace_dir()
    filename = filename.replace('/', os.sep).replace('\\', os.sep)
    target_path = os.path.abspath(os.path.join(workspace_dir, filename))
    
    if not target_path.startswith(os.path.abspath(workspace_dir)):
        return {"error": "Access denied: file is outside the workspace."}
    
    if not os.path.exists(target_path):
        return {"error": f"File {filename} does not exist."}
    
    if os.path.isdir(target_path):
        return {"error": f"{filename} is a directory."}
        
    try:
        lines = []
        with open(target_path, 'r', encoding='utf-8', errors='replace') as f:
            for i, line in enumerate(f):
                if i >= 2000:
                    lines.append("... [Content truncated: exceeded 2000 lines limit] ...")
                    break
                lines.append(line)
        content = "".join(lines)
        if len(content) > 102400:
            content = content[:102400] + "\n... [Content truncated: exceeded 100KB limit] ..."
        return {"content": content}
    except Exception as e:
        return {"error": f"Failed to read file: {e}"}

def local_get_json_file_summary(filename):
    workspace_dir = get_workspace_dir()
    filename = filename.replace('/', os.sep).replace('\\', os.sep)
    target_path = os.path.abspath(os.path.join(workspace_dir, filename))
    
    if not target_path.startswith(os.path.abspath(workspace_dir)):
        return {"error": "Access denied."}
    
    if not os.path.exists(target_path):
        return {"error": f"File {filename} does not exist."}
        
    try:
        with open(target_path, 'r', encoding='utf-8', errors='replace') as f:
            data = json.load(f)
            
        summary = {}
        if isinstance(data, list):
            summary["type"] = "array"
            summary["length"] = len(data)
            if len(data) > 0:
                summary["first_item_preview"] = data[0]
        elif isinstance(data, dict):
            summary["type"] = "object"
            summary["keys"] = list(data.keys())
            summary["preview"] = {k: data[k] for k in list(data.keys())[:3]}
        else:
            summary["type"] = str(type(data))
            summary["value_preview"] = str(data)[:200]
            
        return {"summary": summary}
    except Exception as e:
        return {"error": f"Failed to parse JSON file: {e}"}

def local_get_csv_file_summary(filename):
    workspace_dir = get_workspace_dir()
    filename = filename.replace('/', os.sep).replace('\\', os.sep)
    target_path = os.path.abspath(os.path.join(workspace_dir, filename))
    
    if not target_path.startswith(os.path.abspath(workspace_dir)):
        return {"error": "Access denied."}
    
    if not os.path.exists(target_path):
        return {"error": f"File {filename} does not exist."}
        
    try:
        rows = []
        with open(target_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            for i, row in enumerate(reader):
                if i >= 10:
                    break
                rows.append(row)
        return {
            "headers": headers,
            "first_10_rows": rows
        }
    except Exception as e:
        return {"error": f"Failed to parse CSV file: {e}"}

# --- Gemini Tool Configuration ---

TOOLS = [
    {
        "functionDeclarations": [
            {
                "name": "list_workspace_files",
                "description": "List all files in the workspace (excluding hidden directories starting with a dot, like .git or .firefox_*) with their size and modification time."
            },
            {
                "name": "read_workspace_file",
                "description": "Read the contents of a text, python, json, or csv file in the workspace.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "filename": {
                            "type": "STRING",
                            "description": "The relative path of the file to read (e.g. 'open_shopee.py'). Path traversal using '..' is strictly forbidden."
                        }
                    },
                    "required": ["filename"]
                }
            },
            {
                "name": "get_json_file_summary",
                "description": "Summarize a JSON file by listing its keys, length (if array), and a preview of the first item. Use this for large JSON files instead of reading the entire file.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "filename": {
                            "type": "STRING",
                            "description": "The relative path of the JSON file to summarize (e.g. 'captured_shopee_api.json')."
                        }
                    },
                    "required": ["filename"]
                }
            },
            {
                "name": "get_csv_file_summary",
                "description": "Summarize a CSV file by returning the column headers and the first 10 rows.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "filename": {
                            "type": "STRING",
                            "description": "The relative path of the CSV file to summarize (e.g. 'trending_affiliate_products.csv')."
                        }
                    },
                    "required": ["filename"]
                }
            }
        ]
    }
]

def get_env_credentials():
    token = os.environ.get("TELEGRAM_NOTIFY_TOKEN")
    chat_id = os.environ.get("TELEGRAM_NOTIFY_CHAT_ID")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    
    try:
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        env_path = None
        for _ in range(6):
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
                            elif key == "GEMINI_API_KEY" and not gemini_key:
                                gemini_key = val
    except Exception:
        pass
        
    return token, chat_id, gemini_key

def send_telegram_reply(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    req_data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=15, context=context) as response:
            return True
    except Exception as e:
        safe_print(f"Error sending Markdown reply: {e}. Retrying as plain text...")
        data["parse_mode"] = None
        req_data = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15, context=context) as response2:
                return True
        except Exception as e2:
            safe_print(f"Error sending plain text reply: {e2}")
            return False

def generate_ai_response(gemini_key, user_id, message_text):
    if not gemini_key:
        return "สวัสดีครับ! ยินดีต้อนรับสู่บอท Antigravity บน Telegram\n\n⚠️ ยังไม่ได้ตั้งค่า API Key: กรุณาเพิ่ม GEMINI_API_KEY=\"your-api-key\" ในไฟล์ .env ก่อน เพื่อให้ผมสามารถตอบกลับได้ครับ!"
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
    
    if user_id not in chat_histories:
        chat_histories[user_id] = []
        
    history = chat_histories[user_id]
    
    history.append({
        "role": "user",
        "parts": [{"text": message_text}]
    })
    
    if len(history) > 40:
        history = history[-40:]
        chat_histories[user_id] = history

    context = ssl._create_unverified_context()
    
    system_instruction = {
        "parts": [
            {
                "text": (
                    "คุณคือ Antigravity AI Coding Assistant ที่ทำงานอยู่บน Telegram "
                    "คุณมีหน้าที่หลักในการช่วยเหลือผู้ใช้วิเคราะห์และใช้งานสคริปต์ในโปรเจกต์นี้ (calm-noether) "
                    "ซึ่งเป็นระบบดึงข้อมูลออเดอร์/สินค้าจาก Shopee และ TikTok Shop\n\n"
                    "คุณมีเครื่องมือดังต่อไปนี้เพื่ออ่านไฟล์และวิเคราะห์ผลลัพธ์ในโปรเจกต์:\n"
                    "1. list_workspace_files: ดูรายการไฟล์ในโปรเจกต์\n"
                    "2. read_workspace_file: อ่านโค้ดหรือเนื้อหาในไฟล์ที่เลือก\n"
                    "3. get_json_file_summary: สรุปผลลัพธ์ไฟล์ JSON ขนาดใหญ่ (เช่น ข้อมูลที่ดึงมาจาก API)\n"
                    "4. get_csv_file_summary: สรุปข้อมูลในไฟล์ CSV\n\n"
                    "ทุกครั้งที่ผู้ใช้ถามเกี่ยวกับสคริปต์ โค้ด ข้อมูลที่ดึงได้ หรือผลการทำงาน "
                    "คุณต้องเรียกใช้เครื่องมือเพื่อนำข้อมูลจริงมาตอบเสมอ ห้ามตอบเดาเนื้อหาของโค้ดเด็ดขาด\n\n"
                    "จงตอบกลับด้วยภาษาไทยที่เป็นกันเอง สุภาพ และมีคำอธิบายที่เข้าใจง่าย"
                )
            }
        ]
    }
    
    loop_count = 0
    max_loops = 6
    
    while loop_count < max_loops:
        loop_count += 1
        
        data = {
            "contents": history,
            "tools": TOOLS,
            "systemInstruction": system_instruction
        }
        
        req_data = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30, context=context) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                
                candidates = resp_data.get("candidates", [])
                if not candidates:
                    return "ขออภัยครับ ไม่สามารถดึงคำตอบจาก AI ได้ (No candidates)"
                    
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if not parts:
                    return "ขออภัยครับ ไม่สามารถดึงคำตอบจาก AI ได้ (No parts in response)"
                
                function_call = parts[0].get("functionCall")
                if function_call:
                    func_name = function_call.get("name")
                    func_args = function_call.get("args", {})
                    
                    history.append(content)
                    
                    safe_print(f"DEBUG: Telegram Agent calling tool '{func_name}' with args {func_args}")
                    
                    if func_name == "list_workspace_files":
                        result = local_list_workspace_files()
                    elif func_name == "read_workspace_file":
                        filename = func_args.get("filename")
                        result = local_read_workspace_file(filename)
                    elif func_name == "get_json_file_summary":
                        filename = func_args.get("filename")
                        result = local_get_json_file_summary(filename)
                    elif func_name == "get_csv_file_summary":
                        filename = func_args.get("filename")
                        result = local_get_csv_file_summary(filename)
                    else:
                        result = {"error": f"Unknown function: {func_name}"}
                    
                    history.append({
                        "role": "function",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": func_name,
                                    "response": result
                                }
                            }
                        ]
                    })
                    
                    continue
                
                reply_text = parts[0].get("text", "")
                if reply_text:
                    history.append({
                        "role": "model",
                        "parts": [{"text": reply_text}]
                    })
                    return reply_text
                else:
                    return "ขออภัยครับ ไม่สามารถประมวลผลคำตอบได้"
                    
        except Exception as e:
            safe_print(f"Error in Gemini API call: {e}")
            if len(history) > 0 and history[-1].get("role") == "user":
                history.pop()
            return f"เกิดข้อผิดพลาดในการดึงข้อมูลจาก Gemini API: {e}"
            
    return "ขออภัยครับ ระบบใช้เวลาประมวลผลเครื่องมือมากเกินไป"

def poll_updates(token, allowed_chat_id, gemini_key):
    offset = 0
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    context = ssl._create_unverified_context()
    
    safe_print(f"INFO: Antigravity Telegram Agent is running and listening on Bot Token... (Polling updates)")
    safe_print(f"INFO: Locked to Chat ID / User ID: {allowed_chat_id}")
    
    while True:
        try:
            req_url = f"{url}?offset={offset}&timeout=10"
            req = urllib.request.Request(req_url, method="GET")
            with urllib.request.urlopen(req, timeout=15, context=context) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                if not resp_data.get("ok"):
                    time.sleep(2)
                    continue
                    
                updates = resp_data.get("result", [])
                for update in updates:
                    update_id = update.get("update_id")
                    offset = update_id + 1
                    
                    message = update.get("message")
                    if not message:
                        continue
                        
                    chat = message.get("chat", {})
                    chat_id = str(chat.get("id"))
                    text = message.get("text", "").strip()
                    
                    if not text:
                        continue
                        
                    if allowed_chat_id and chat_id != str(allowed_chat_id):
                        safe_print(f"Ignored message from unauthorized chat_id: {chat_id}")
                        send_telegram_reply(token, chat_id, "🔒 ขออภัยครับ บอทนี้ได้รับการกำหนดสิทธิ์ให้ใช้งานแบบส่วนตัวเท่านั้น")
                        continue
                    
                    safe_print(f"Received message: '{text}' from {chat_id}")
                    
                    reply_text = generate_ai_response(gemini_key, chat_id, text)
                    
                    send_telegram_reply(token, chat_id, reply_text)
                    
        except KeyboardInterrupt:
            safe_print("\nShutting down listener...")
            break
        except Exception as e:
            safe_print(f"Error in polling loop: {e}")
            time.sleep(3)

def main():
    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lock_socket.bind(('127.0.0.1', 47285))
    except socket.error:
        sys.exit(0)
        
    token, chat_id, gemini_key = get_env_credentials()
    if not token or not chat_id:
        safe_print("ERROR: Telegram Token and Chat ID must be configured in .env file.")
        sys.exit(1)
        
    # Start the active transcript monitor thread in the background
    monitor_t = threading.Thread(
        target=transcript_monitor_thread,
        args=(token, chat_id),
        daemon=True
    )
    monitor_t.start()
    
    poll_updates(token, chat_id, gemini_key)

if __name__ == "__main__":
    main()
