import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_code = '''
import requests
r = requests.get("http://127.0.0.1:8000/api/pos/orders")
data = r.json()
print("Type of data:", type(data))
if isinstance(data, dict):
    print("Keys:", data.keys())
    if "orders" in data:
        print("Orders count:", len(data["orders"]))
        if data["orders"]:
            print("Sample order:", data["orders"][0])
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_order.py', 'w') as f:
    f.write(remote_code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_order.py')
print(stdout.read().decode('utf-8'))
print(stderr.read().decode('utf-8'))
ssh.close()
