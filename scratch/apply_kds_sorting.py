# 1. Update PosRestodash.vue
vue_file = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\PosRestodash.vue'
with open(vue_file, 'r', encoding='utf-8') as f:
    vue_code = f.read()

old_korders_assign = "kitchenOrders.value = Array.isArray(kOrders) ? kOrders : []"
new_korders_assign = """const sortedK = (Array.isArray(kOrders) ? kOrders : []).sort((a, b) => {
      const tA = new Date(a.updated_at || a.created_at || 0).getTime()
      const tB = new Date(b.updated_at || b.created_at || 0).getTime()
      return tB - tA
    })
    kitchenOrders.value = sortedK"""

if old_korders_assign in vue_code:
    vue_code = vue_code.replace(old_korders_assign, new_korders_assign, 1)
    with open(vue_file, 'w', encoding='utf-8') as f:
        f.write(vue_code)
    print("1. Sorted kitchenOrders descending in PosRestodash.vue")
else:
    print("1. WARNING: old_korders_assign not found")

# 2. Update pos_engine.py on remote
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=20)

sftp = ssh.open_sftp()
with sftp.open('/home/openhands/super-appsheet/src/pos_engine.py', 'r') as f:
    engine_code = f.read().decode('utf-8')

old_engine_kitchen = """        return [
            o for o in self._orders.values()
            if (o.get("status") in ("pending", "preparing", "cooking", "paid")
                and o.get("kitchen_status") != "done"
                and o.get("status") not in ("completed", "served", "cancelled"))
        ]"""

new_engine_kitchen = """        k_list = [
            o for o in self._orders.values()
            if (o.get("status") in ("pending", "preparing", "cooking", "paid")
                and o.get("kitchen_status") != "done"
                and o.get("status") not in ("completed", "served", "cancelled"))
        ]
        return sorted(k_list, key=lambda o: o.get("updated_at") or o.get("created_at") or "", reverse=True)"""

if old_engine_kitchen in engine_code:
    engine_code = engine_code.replace(old_engine_kitchen, new_engine_kitchen, 1)
    with sftp.open('/home/openhands/super-appsheet/src/pos_engine.py', 'w') as f:
        f.write(engine_code.encode('utf-8'))
    print("2. Sorted get_kitchen_orders descending in pos_engine.py")
    stdin, stdout, stderr = ssh.exec_command("pm2 restart super-appsheet-api")
    print("Restarted super-appsheet-api")
else:
    print("2. WARNING: old_engine_kitchen not found")

sftp.close()
ssh.close()
