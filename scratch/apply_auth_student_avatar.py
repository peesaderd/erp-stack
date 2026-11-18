import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='ignore'), stderr.read().decode('utf-8', errors='ignore')

script = r"""python3 -c "
path = '/home/openhands/erp-stack/modules/auth/main.py'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Update _user_to_dict
t1 = '''def _user_to_dict(user: User) -> dict:
    return {
        \"id\": user.id,
        \"email\": user.email,
        \"name\": user.name,
        \"avatar_url\": user.avatar_url,
        \"member_tier\": user.member_tier,
        \"credits\": user.credits,
        \"is_active\": user.is_active,
        \"created_at\": user.created_at.isoformat() if user.created_at else None,
    }'''

r1 = '''def _user_to_dict(user: User) -> dict:
    soc_url = getattr(user, \"social_avatar_url\", \"\")
    if not soc_url and user.avatar_url and user.avatar_url.startswith(\"http\"):
        soc_url = user.avatar_url
    return {
        \"id\": user.id,
        \"email\": user.email,
        \"name\": user.name,
        \"avatar_url\": user.avatar_url,
        \"member_tier\": user.member_tier,
        \"credits\": user.credits,
        \"is_active\": user.is_active,
        \"created_at\": user.created_at.isoformat() if user.created_at else None,
        \"student_name\": getattr(user, \"student_name\", \"\") or user.name,
        \"student_age\": getattr(user, \"student_age\", \"7\") or \"7\",
        \"student_avatar_url\": getattr(user, \"student_avatar_url\", \"\") or user.avatar_url,
        \"social_avatar_url\": soc_url,
        \"avatar_type\": getattr(user, \"avatar_type\", \"cartoon\") or \"cartoon\",
    }'''

if t1 in c:
    c = c.replace(t1, r1)
    print('Updated _user_to_dict')

# 2. Update ProfileUpdateRequest & update_profile
t2 = '''class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None

@app.put(\"/api/v1/auth/profile\")
async def update_profile(
    body: Optional[ProfileUpdateRequest] = None,
    name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    \"\"\"Update user profile (supports both JSON body and query parameters).\"\"\"
    eff_name = body.name if (body and body.name is not None) else name
    eff_avatar = body.avatar_url if (body and body.avatar_url is not None) else avatar_url
    if eff_name is not None:
        user.name = eff_name
    if eff_avatar is not None:
        user.avatar_url = eff_avatar
    await db.commit()
    await db.refresh(user)
    return {\"ok\": True, \"user\": _user_to_dict(user)}'''

r2 = '''class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    student_name: Optional[str] = None
    student_age: Optional[str] = None
    student_avatar_url: Optional[str] = None
    social_avatar_url: Optional[str] = None
    avatar_type: Optional[str] = None

@app.put(\"/api/v1/auth/profile\")
async def update_profile(
    body: Optional[ProfileUpdateRequest] = None,
    name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    \"\"\"Update user profile (Parent & Student details, Avatar choices).\"\"\"
    if body:
        if body.name is not None: user.name = body.name
        if body.avatar_url is not None: user.avatar_url = body.avatar_url
        if body.student_name is not None: user.student_name = body.student_name
        if body.student_age is not None: user.student_age = body.student_age
        if body.student_avatar_url is not None: user.student_avatar_url = body.student_avatar_url
        if body.social_avatar_url is not None: user.social_avatar_url = body.social_avatar_url
        if body.avatar_type is not None: user.avatar_type = body.avatar_type
    else:
        if name is not None: user.name = name
        if avatar_url is not None: user.avatar_url = avatar_url
    await db.commit()
    await db.refresh(user)
    return {\"ok\": True, \"user\": _user_to_dict(user)}'''

if t2 in c:
    c = c.replace(t2, r2)
    print('Updated update_profile and ProfileUpdateRequest')

# 3. In LINE callback: preserve social_avatar_url
c = c.replace('if avatar_url: user.avatar_url = avatar_url', 'if avatar_url: user.social_avatar_url = avatar_url\n                if not user.avatar_url: user.avatar_url = avatar_url')

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)

print('Finished patching auth main.py')
" """

out, err = run(script)
print("=== PATCH MAIN.PY ===")
print(out, err)

# Restart auth service
run("sudo pkill -f 'modules/auth/venv' && cd /home/openhands/erp-stack/modules/auth && nohup /home/openhands/erp-stack/modules/auth/venv/bin/python3 start.py > /tmp/auth.log 2>&1 &")
import time
time.sleep(3)
health_out, _ = run("curl -s http://127.0.0.1:8101/health")
print("=== HEALTH AFTER RESTART ===")
print(health_out)

ssh.close()
