import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=10)

test_script = """
import sys
sys.path.insert(0, '/home/openhands/super-appsheet/src')
try:
    from erp_client import get_erp_client
    c = get_erp_client()
    products = c.list_products()
    print("ERP products count:", len(products))
    if products:
        print("First 3 ERP products:", products[:3])
except Exception as e:
    print("ERP client error:", type(e), e)
"""

stdin, stdout, stderr = client.exec_command(f'python3 -c "{test_script}"')
print("Output:\n", stdout.read().decode('utf-8', errors='ignore'))
print("Error:\n", stderr.read().decode('utf-8', errors='ignore'))

client.close()
