import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = """
import shutil, os

src = '/home/openhands/emma-phonics/api_server.py'
bak = '/home/openhands/emma-phonics/api_server.py.bak_pre_progress_api'
shutil.copyfile(src, bak)
print(f"Backed up {src} to {bak}")

with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add urllib.parse import if missing
if "import urllib.parse" not in content:
    content = content.replace("import unicodedata", "import unicodedata\\nimport urllib.parse")

# 2. Add progress engine logic before Handler
progress_code = '''
# ------------------------------------------------------------ progress engine
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "progress.json")
_PROGRESS_LOCK = threading.Lock()


def _load_progress_store():
    if not os.path.exists(PROGRESS_FILE):
        return {}
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[api] Error loading progress file: {e}")
        return {}


def _save_progress_store(data):
    try:
        os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
        tmp_file = PROGRESS_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, PROGRESS_FILE)
        return True
    except Exception as e:
        print(f"[api] Error saving progress file: {e}")
        return False


def _next_lesson_id(current_lid):
    all_keys = list(LESSONS.keys())
    try:
        idx = all_keys.index(current_lid)
        if idx + 1 < len(all_keys):
            return all_keys[idx + 1]
    except Exception:
        pass
    return None


def handle_progress_save(payload):
    user_id = str(payload.get("user_id") or "guest").strip() or "guest"
    lesson_id = str(payload.get("lesson_id") or payload.get("lesson") or "").strip()
    if not lesson_id:
        return 400, {"ok": False, "error": "missing-lesson_id"}

    subject = str(payload.get("subject") or "Phonics").strip()
    try:
        step = int(payload.get("step", 1))
    except Exception:
        step = 1

    try:
        item_index = int(payload.get("item_index", payload.get("index", 0)))
    except Exception:
        item_index = 0

    done = bool(payload.get("done", False))
    level = payload.get("level")
    if level is None:
        m = re.search(r"L(\\\\d+)", lesson_id, re.IGNORECASE)
        level = int(m.group(1)) if m else 1

    lesson_meta = LESSONS.get(lesson_id, {})
    title = payload.get("title")
    if not title:
        l_title = lesson_meta.get("title", "")
        l_desc = lesson_meta.get("desc", "")
        if l_title and l_desc:
            title = f"Level {level}: {l_title} - {l_desc}"
        elif l_title:
            title = f"Level {level}: {l_title}"
        else:
            title = f"Level {level}: {lesson_id}"

    total_steps = int(payload.get("total_steps") or 5)
    if done:
        percent = 100
    else:
        percent = min(99, max(5, int(round((step / float(total_steps)) * 100))))

    url = payload.get("url")
    if not url:
        url = f"theme_phonicsLesson.html?lesson={lesson_id}&step={step}"

    next_lid = _next_lesson_id(lesson_id)

    record = {
        "user_id": user_id,
        "subject": subject,
        "lesson_id": lesson_id,
        "level": level,
        "step": step,
        "item_index": item_index,
        "total_steps": total_steps,
        "done": done,
        "percent": percent,
        "title": title,
        "url": url,
        "next_lesson_id": next_lid,
        "updated_at": int(time.time()),
        "extra": payload.get("extra", {})
    }

    with _PROGRESS_LOCK:
        store = _load_progress_store()
        if user_id not in store:
            store[user_id] = {
                "latest": record,
                "lessons": {}
            }
        user_store = store[user_id]
        if "lessons" not in user_store:
            user_store["lessons"] = {}

        user_store["lessons"][lesson_id] = record
        user_store["latest"] = record
        _save_progress_store(store)

    return 200, {
        "ok": True,
        "saved": record
    }


def handle_progress_latest(params):
    user_id = str(params.get("user_id") or "guest").strip() or "guest"
    subject = str(params.get("subject") or "").strip().lower()

    with _PROGRESS_LOCK:
        store = _load_progress_store()
        user_store = store.get(user_id)
        if not user_store:
            return 200, {"ok": True, "has_progress": False, "latest": None}

        latest = user_store.get("latest")
        if not latest:
            lessons = user_store.get("lessons", {})
            if lessons:
                latest = max(lessons.values(), key=lambda x: x.get("updated_at", 0))

        if not latest:
            return 200, {"ok": True, "has_progress": False, "latest": None}

        if subject and str(latest.get("subject", "")).lower() != subject:
            matching = [v for v in user_store.get("lessons", {}).values() if str(v.get("subject", "")).lower() == subject]
            if matching:
                latest = max(matching, key=lambda x: x.get("updated_at", 0))
            else:
                return 200, {"ok": True, "has_progress": False, "latest": None}

        return 200, {
            "ok": True,
            "has_progress": True,
            "latest": latest
        }


def handle_progress_get(params):
    user_id = str(params.get("user_id") or "guest").strip() or "guest"
    lesson_id = str(params.get("lesson_id") or params.get("lesson") or "").strip()

    with _PROGRESS_LOCK:
        store = _load_progress_store()
        user_store = store.get(user_id)
        if not user_store:
            return 200, {"ok": True, "user_id": user_id, "lessons": {}, "latest": None}

        if lesson_id:
            lesson_prog = user_store.get("lessons", {}).get(lesson_id)
            return 200, {
                "ok": True,
                "user_id": user_id,
                "lesson_id": lesson_id,
                "found": bool(lesson_prog),
                "progress": lesson_prog
            }

        return 200, {
            "ok": True,
            "user_id": user_id,
            "latest": user_store.get("latest"),
            "lessons": user_store.get("lessons", {})
        }


def handle_progress_clear(payload):
    user_id = str(payload.get("user_id") or "guest").strip() or "guest"
    lesson_id = str(payload.get("lesson_id") or payload.get("lesson") or "").strip()

    with _PROGRESS_LOCK:
        store = _load_progress_store()
        if user_id in store:
            if lesson_id:
                if "lessons" in store[user_id] and lesson_id in store[user_id]["lessons"]:
                    del store[user_id]["lessons"][lesson_id]
                if store[user_id].get("latest", {}).get("lesson_id") == lesson_id:
                    remaining = list(store[user_id].get("lessons", {}).values())
                    store[user_id]["latest"] = max(remaining, key=lambda x: x.get("updated_at", 0)) if remaining else None
            else:
                del store[user_id]
            _save_progress_store(store)

    return 200, {"ok": True, "cleared": True, "user_id": user_id, "lesson_id": lesson_id}
'''

if "def handle_progress_save" not in content:
    content = content.replace("# -------------------------------------------------------------------- server", progress_code + "\\n\\n# -------------------------------------------------------------------- server")

# 3. Update do_GET
old_do_get = '''    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path in ("/health", "/"):
            self._json(200, {"ok": True, "service": "emma-phonics", "lessons": len(LESSONS)})
            return
        if path == "/lessons":
            self._json(*handle_lessons())
            return
        m = re.match(r"^/lesson/(.+)$", path)
        if m:
            self._json(*handle_lesson(m.group(1)))
            return
        m = re.match(r"^/session/([0-9a-f]+)/item$", path)
        if m:
            self._json(*handle_session_item(m.group(1)))
            return
        m = re.match(r"^/session/([0-9a-f]+)/audio-plan$", path)
        if m:
            self._json(*handle_session_audio(m.group(1)))
            return
        self._json(404, {"ok": False, "error": "not-found", "path": path})'''

new_do_get = '''    def do_GET(self):  # noqa: N802
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed_url.query).items()}

        if path in ("/health", "/"):
            self._json(200, {"ok": True, "service": "emma-phonics", "lessons": len(LESSONS)})
            return
        if path == "/lessons":
            self._json(*handle_lessons())
            return
        if path == "/progress/latest":
            self._json(*handle_progress_latest(query))
            return
        if path in ("/progress/get", "/progress", "/progress/all"):
            self._json(*handle_progress_get(query))
            return
        m = re.match(r"^/progress/(.+)$", path)
        if m:
            query["lesson_id"] = m.group(1)
            self._json(*handle_progress_get(query))
            return
        m = re.match(r"^/lesson/(.+)$", path)
        if m:
            self._json(*handle_lesson(m.group(1)))
            return
        m = re.match(r"^/session/([0-9a-f]+)/item$", path)
        if m:
            self._json(*handle_session_item(m.group(1)))
            return
        m = re.match(r"^/session/([0-9a-f]+)/audio-plan$", path)
        if m:
            self._json(*handle_session_audio(m.group(1)))
            return
        self._json(404, {"ok": False, "error": "not-found", "path": path})'''

if old_do_get in content:
    content = content.replace(old_do_get, new_do_get)
    print("Replaced do_GET")
else:
    print("Could not find old_do_get")

# 4. Update do_POST
old_do_post = '''        if path == "/session/open":
            self._json(*handle_session_open(payload))
        elif path == "/session/answer":
            self._json(*handle_session_answer(payload))
        elif path == "/session/advance":
            self._json(*handle_session_advance(payload))
        elif path == "/session/jump":
            self._json(*handle_session_jump(payload))
        elif path == "/check":
            self._json(*handle_check(payload))
        elif path == "/audio-plan":
            self._json(*handle_audio_plan(payload))
        else:
            self._json(404, {"ok": False, "error": "not-found", "path": path})'''

new_do_post = '''        if path == "/session/open":
            self._json(*handle_session_open(payload))
        elif path == "/session/answer":
            self._json(*handle_session_answer(payload))
        elif path == "/session/advance":
            self._json(*handle_session_advance(payload))
        elif path == "/session/jump":
            self._json(*handle_session_jump(payload))
        elif path == "/check":
            self._json(*handle_check(payload))
        elif path == "/audio-plan":
            self._json(*handle_audio_plan(payload))
        elif path == "/progress/save":
            self._json(*handle_progress_save(payload))
        elif path == "/progress/latest":
            self._json(*handle_progress_latest(payload))
        elif path in ("/progress/get", "/progress"):
            self._json(*handle_progress_get(payload))
        elif path == "/progress/clear":
            self._json(*handle_progress_clear(payload))
        else:
            self._json(404, {"ok": False, "error": "not-found", "path": path})'''

if old_do_post in content:
    content = content.replace(old_do_post, new_do_post)
    print("Replaced do_POST")
else:
    print("Could not find old_do_post")

with open(src, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated api_server.py successfully")
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/patch_api_server.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/patch_api_server.py")
print("Patch stdout:\n", stdout.read().decode())
print("Patch stderr:\n", stderr.read().decode())

# Test syntax before restarting
stdin, stdout, stderr = ssh.exec_command("python3 -m py_compile /home/openhands/emma-phonics/api_server.py")
compile_err = stderr.read().decode()
if compile_err:
    print("Compilation error:\n", compile_err)
else:
    print("Compilation successful! Restarting emma-phonics.service...")
    stdin, stdout, stderr = ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S systemctl restart emma-phonics.service")
    print("Restart output:", stdout.read().decode(), stderr.read().decode())

ssh.close()
