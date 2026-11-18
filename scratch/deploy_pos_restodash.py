"""
Deploy PosRestodash.vue to remote server at 89.167.82.205
Step 1: Upload Vue file + find router
Step 2: Separate script to add route + build
"""
import paramiko
import io

HOST = '89.167.82.205'
USER = 'openhands'
PASS = 'OpenHands@ERP2026'

VUE_CONTENT = r'''<template>
  <div class="pos-restodash" style="display:flex;height:100vh;width:100vw;overflow:hidden;background:#F8F9FA;font-family:'Prompt',sans-serif;">

    <!-- LEFT SIDEBAR: Categories -->
    <aside style="width:220px;min-width:220px;background:#0F141A;display:flex;flex-direction:column;padding:0;overflow:hidden;">
      <!-- Brand -->
      <div style="padding:20px 16px 12px;border-bottom:1px solid #1E2630;">
        <div style="display:flex;align-items:center;gap:10px;">
          <div style="width:38px;height:38px;background:#FF5722;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;">🍜</div>
          <div>
            <div style="color:#fff;font-weight:700;font-size:13px;line-height:1.2;">ก๋วยเตี๋ยวคุณย่า</div>
            <div style="color:#8B9BAE;font-size:11px;">POS System</div>
          </div>
        </div>
      </div>

      <!-- Table Info -->
      <div style="margin:12px 12px 0;background:#1A2130;border-radius:10px;padding:10px 12px;">
        <div style="color:#8B9BAE;font-size:10px;text-transform:uppercase;letter-spacing:0.5px;">โต๊ะที่</div>
        <div style="color:#FF5722;font-size:20px;font-weight:800;">{{ tableLabel || '-' }}</div>
        <div style="color:#8B9BAE;font-size:11px;">{{ orderTypeTh }}</div>
      </div>

      <!-- Clock -->
      <div style="margin:10px 12px 0;text-align:center;">
        <div style="color:#fff;font-size:22px;font-weight:700;font-family:'Inter',monospace;">{{ clockTime }}</div>
        <div style="color:#8B9BAE;font-size:11px;">{{ clockDate }}</div>
      </div>

      <!-- Category Nav -->
      <div style="flex:1;overflow-y:auto;padding:12px 10px;margin-top:4px;">
        <div style="color:#8B9BAE;font-size:10px;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;padding-left:4px;">หมวดหมู่</div>
        <button
          v-for="cat in ['ทั้งหมด', ...categories]"
          :key="cat"
          @click="activeCat = cat"
          :style="{
            width:'100%',
            textAlign:'left',
            padding:'9px 12px',
            borderRadius:'8px',
            border:'none',
            cursor:'pointer',
            marginBottom:'4px',
            fontFamily: `'Prompt',sans-serif`,
            fontSize:'13px',
            fontWeight: activeCat===cat ? '600' : '400',
            background: activeCat===cat ? '#FF5722' : 'transparent',
            color: activeCat===cat ? '#fff' : '#8B9BAE',
            transition:'all 0.15s'
          }"
        >{{ cat }}</button>
      </div>

      <!-- Bottom Nav Links -->
      <div style="border-top:1px solid #1E2630;padding:12px 10px;">
        <router-link to="/pos" style="display:flex;align-items:center;gap:8px;padding:8px 12px;color:#8B9BAE;text-decoration:none;border-radius:8px;font-size:12px;">
          <span style="font-size:16px;">🏠</span> กลับหน้าหลัก
        </router-link>
      </div>
    </aside>

    <!-- CENTER: Menu Grid -->
    <main style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
      <!-- Top Bar -->
      <div style="background:#fff;padding:14px 20px;border-bottom:1px solid #E9ECEF;display:flex;align-items:center;gap:12px;flex-shrink:0;">
        <div style="flex:1;position:relative;">
          <span style="position:absolute;left:12px;top:50%;transform:translateY(-50%);color:#8B9BAE;font-size:16px;">🔍</span>
          <input
            v-model="search"
            placeholder="ค้นหาเมนู..."
            style="width:100%;padding:9px 12px 9px 36px;border:1.5px solid #E9ECEF;border-radius:10px;font-size:13px;font-family:'Prompt',sans-serif;outline:none;box-sizing:border-box;"
          />
        </div>
        <div style="color:#495057;font-size:13px;white-space:nowrap;">
          <span style="font-weight:600;color:#FF5722;">{{ filteredMenu.length }}</span> รายการ
        </div>
      </div>

      <!-- Menu Grid -->
      <div style="flex:1;overflow-y:auto;padding:16px 20px;">
        <div v-if="loading" style="display:flex;align-items:center;justify-content:center;height:200px;color:#8B9BAE;">
          <div>⏳ กำลังโหลดเมนู...</div>
        </div>
        <div v-else style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:14px;">
          <div
            v-for="item in filteredMenu"
            :key="item.id"
            @click="addToCart(item)"
            style="background:#fff;border-radius:14px;overflow:hidden;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,0.07);transition:transform 0.15s,box-shadow 0.15s;"
            @mouseenter="e => { e.currentTarget.style.transform='translateY(-2px)'; e.currentTarget.style.boxShadow='0 6px 20px rgba(255,87,34,0.15)'; }"
            @mouseleave="e => { e.currentTarget.style.transform='translateY(0)'; e.currentTarget.style.boxShadow='0 1px 4px rgba(0,0,0,0.07)'; }"
          >
            <div style="height:110px;background:#F8F9FA;overflow:hidden;position:relative;">
              <img
                v-if="item.image_url"
                :src="item.image_url"
                :alt="item.name"
                style="width:100%;height:100%;object-fit:cover;"
                @error="e => e.target.style.display='none'"
              />
              <div v-else style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:40px;">
                {{ getCatEmoji(item.category) }}
              </div>
              <div
                v-if="getCartQty(item.id) > 0"
                style="position:absolute;top:6px;right:6px;background:#FF5722;color:#fff;width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;"
              >{{ getCartQty(item.id) }}</div>
            </div>
            <div style="padding:10px 10px 12px;">
              <div style="font-size:12px;font-weight:600;color:#1A2130;line-height:1.3;margin-bottom:4px;">{{ item.name }}</div>
              <div style="font-size:13px;font-weight:700;color:#FF5722;">฿{{ Number(item.price).toLocaleString() }}</div>
            </div>
          </div>
        </div>
        <div v-if="!loading && filteredMenu.length === 0" style="display:flex;align-items:center;justify-content:center;height:200px;color:#8B9BAE;">
          ไม่พบเมนูที่ค้นหา
        </div>
      </div>
    </main>

    <!-- RIGHT: Order Panel -->
    <aside style="width:300px;min-width:300px;background:#fff;display:flex;flex-direction:column;border-left:1px solid #E9ECEF;overflow:hidden;">
      <!-- Order Header -->
      <div style="padding:16px;border-bottom:1px solid #E9ECEF;flex-shrink:0;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
          <span style="font-size:15px;font-weight:700;color:#1A2130;">รายการออเดอร์</span>
          <span style="background:#FF5722;color:#fff;border-radius:20px;padding:2px 10px;font-size:12px;font-weight:600;">
            โต๊ะ {{ tableLabel || '-' }}
          </span>
        </div>
        <div style="color:#8B9BAE;font-size:11px;">{{ orderTypeTh }} · {{ cart.length }} รายการ</div>
      </div>

      <!-- Cart Items -->
      <div style="flex:1;overflow-y:auto;padding:12px 14px;">
        <div v-if="cart.length === 0" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:150px;color:#C0CBDA;">
          <div style="font-size:36px;margin-bottom:8px;">🛒</div>
          <div style="font-size:13px;">ยังไม่มีรายการ</div>
        </div>
        <div v-for="(item, idx) in cart" :key="idx" style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #F0F2F5;">
          <div style="width:38px;height:38px;background:#F8F9FA;border-radius:8px;overflow:hidden;flex-shrink:0;">
            <img v-if="item.image_url" :src="item.image_url" style="width:100%;height:100%;object-fit:cover;" @error="e=>e.target.style.display='none'"/>
            <div v-else style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:20px;">{{ getCatEmoji(item.category) }}</div>
          </div>
          <div style="flex:1;min-width:0;">
            <div style="font-size:12px;font-weight:600;color:#1A2130;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ item.name }}</div>
            <div style="font-size:12px;color:#FF5722;font-weight:600;">฿{{ Number(item.price).toLocaleString() }}</div>
          </div>
          <div style="display:flex;align-items:center;gap:4px;">
            <button @click="changeQty(idx,-1)" style="width:24px;height:24px;border:1px solid #E9ECEF;background:#fff;border-radius:6px;cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center;color:#495057;">-</button>
            <span style="font-size:13px;font-weight:600;min-width:16px;text-align:center;">{{ item.qty }}</span>
            <button @click="changeQty(idx,1)" style="width:24px;height:24px;border:1px solid #FF5722;background:#FF5722;border-radius:6px;cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center;color:#fff;">+</button>
          </div>
        </div>
      </div>

      <!-- Summary -->
      <div style="padding:14px;border-top:1px solid #E9ECEF;flex-shrink:0;">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
          <span style="font-size:12px;color:#8B9BAE;">ยอดรวม</span>
          <span style="font-size:12px;color:#495057;font-weight:600;">฿{{ cartTotal.toLocaleString() }}</span>
        </div>
        <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
          <span style="font-size:12px;color:#8B9BAE;">ภาษี (7%)</span>
          <span style="font-size:12px;color:#495057;">฿{{ cartVat.toLocaleString() }}</span>
        </div>
        <div style="display:flex;justify-content:space-between;margin-bottom:14px;padding-top:8px;border-top:1px solid #E9ECEF;">
          <span style="font-size:14px;font-weight:700;color:#1A2130;">ยอดสุทธิ</span>
          <span style="font-size:16px;font-weight:800;color:#FF5722;">฿{{ cartGrand.toLocaleString() }}</span>
        </div>
        <button
          @click="showPay = true"
          :disabled="cart.length === 0"
          style="width:100%;padding:13px;background:#FF5722;color:#fff;border:none;border-radius:12px;font-size:14px;font-weight:700;cursor:pointer;font-family:'Prompt',sans-serif;transition:opacity 0.2s;"
          :style="{ opacity: cart.length === 0 ? '0.5' : '1', cursor: cart.length === 0 ? 'not-allowed' : 'pointer' }"
        >
          💳 ชำระเงิน ฿{{ cartGrand.toLocaleString() }}
        </button>
        <button
          v-if="cart.length > 0"
          @click="cart = []"
          style="width:100%;padding:9px;background:transparent;color:#8B9BAE;border:none;border-radius:8px;font-size:12px;cursor:pointer;margin-top:6px;font-family:'Prompt',sans-serif;"
        >ล้างรายการ</button>
      </div>
    </aside>

    <!-- Payment Modal -->
    <div v-if="showPay" style="position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:1000;" @click.self="showPay=false">
      <div style="background:#fff;border-radius:20px;padding:28px;width:380px;max-width:95vw;box-shadow:0 20px 60px rgba(0,0,0,0.2);">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
          <h3 style="margin:0;font-size:18px;font-weight:700;color:#1A2130;">ชำระเงิน</h3>
          <button @click="showPay=false" style="background:none;border:none;font-size:20px;cursor:pointer;color:#8B9BAE;">✕</button>
        </div>

        <div style="background:#F8F9FA;border-radius:12px;padding:16px;margin-bottom:20px;text-align:center;">
          <div style="font-size:13px;color:#8B9BAE;margin-bottom:4px;">ยอดที่ต้องชำระ</div>
          <div style="font-size:32px;font-weight:800;color:#FF5722;">฿{{ cartGrand.toLocaleString() }}</div>
        </div>

        <div style="margin-bottom:16px;">
          <div style="font-size:12px;color:#8B9BAE;margin-bottom:8px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">วิธีชำระเงิน</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <button
              v-for="m in payMethods"
              :key="m.id"
              @click="payMethod = m.id"
              :style="{
                padding:'10px 8px',
                border: payMethod===m.id ? '2px solid #FF5722' : '1.5px solid #E9ECEF',
                borderRadius:'10px',
                background: payMethod===m.id ? '#FFF3F0' : '#fff',
                cursor:'pointer',
                fontSize:'12px',
                fontWeight: payMethod===m.id ? '700' : '500',
                color: payMethod===m.id ? '#FF5722' : '#495057',
                fontFamily: `'Prompt',sans-serif`,
                transition:'all 0.15s'
              }"
            >{{ m.name }}</button>
          </div>
        </div>

        <div v-if="payMethod === 'cash'" style="margin-bottom:16px;">
          <label style="font-size:12px;color:#8B9BAE;margin-bottom:6px;display:block;font-weight:600;">รับเงินมา (บาท)</label>
          <input
            v-model.number="amountReceived"
            type="number"
            :min="cartGrand"
            style="width:100%;padding:10px 12px;border:1.5px solid #E9ECEF;border-radius:10px;font-size:16px;font-weight:700;text-align:right;box-sizing:border-box;font-family:'Prompt',sans-serif;outline:none;"
          />
          <div v-if="amountReceived >= cartGrand" style="margin-top:8px;display:flex;justify-content:space-between;background:#E8F5E9;border-radius:8px;padding:8px 12px;">
            <span style="font-size:12px;color:#2E7D32;">เงินทอน</span>
            <span style="font-size:14px;font-weight:700;color:#2E7D32;">฿{{ (amountReceived - cartGrand).toLocaleString() }}</span>
          </div>
        </div>

        <button
          @click="confirmPayment"
          :disabled="paying"
          style="width:100%;padding:14px;background:#FF5722;color:#fff;border:none;border-radius:12px;font-size:15px;font-weight:700;cursor:pointer;font-family:'Prompt',sans-serif;"
        >{{ paying ? 'กำลังดำเนินการ...' : '✅ ยืนยันชำระเงิน' }}</button>
      </div>
    </div>

    <!-- Toast -->
    <div
      v-if="toastMsg"
      style="position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1A2130;color:#fff;padding:12px 24px;border-radius:12px;font-size:13px;font-weight:600;z-index:2000;box-shadow:0 8px 24px rgba(0,0,0,0.2);"
    >{{ toastMsg }}</div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getMenu, createOrder, getOrder, processPayment, getPaymentMethods } from '../api/index.js'

const route = useRoute()
const router = useRouter()

const tableLabel = computed(() => route.query.table || route.query.name || '')
const orderType = computed(() => route.query.type || 'dinein')
const orderTypeTh = computed(() => {
  const map = { dinein: 'ทานที่ร้าน', takeaway: 'สั่งกลับบ้าน', delivery: 'เดลิเวอรี่' }
  return map[orderType.value] || 'ทานที่ร้าน'
})

const menu = ref([])
const loading = ref(true)
const cart = ref([])
const search = ref('')
const activeCat = ref('ทั้งหมด')
const showPay = ref(false)
const payMethod = ref('cash')
const amountReceived = ref(0)
const paying = ref(false)
const toastMsg = ref('')
const clockTime = ref('')
const clockDate = ref('')
const payMethods = ref([
  { id: 'cash', name: '💵 เงินสด' },
  { id: 'promptpay', name: '📱 พร้อมเพย์' },
  { id: 'card', name: '💳 บัตรเครดิต' },
  { id: 'other', name: '🏦 อื่นๆ' }
])

let clockTimer = null
function updateClock() {
  const now = new Date()
  clockTime.value = now.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
  const days = ['อาทิตย์','จันทร์','อังคาร','พุธ','พฤหัส','ศุกร์','เสาร์']
  clockDate.value = days[now.getDay()] + ' ' + now.toLocaleDateString('th-TH', { day:'numeric', month:'short' })
}

const categories = computed(() => [...new Set(menu.value.map(i => i.category).filter(Boolean))])

const filteredMenu = computed(() => {
  let items = menu.value
  if (activeCat.value !== 'ทั้งหมด') items = items.filter(i => i.category === activeCat.value)
  if (search.value.trim()) {
    const q = search.value.toLowerCase()
    items = items.filter(i => i.name?.toLowerCase().includes(q))
  }
  return items
})

const cartTotal = computed(() => cart.value.reduce((s, i) => s + i.price * i.qty, 0))
const cartVat = computed(() => Math.round(cartTotal.value * 0.07))
const cartGrand = computed(() => cartTotal.value + cartVat.value)

function getCartQty(id) {
  const f = cart.value.find(i => i.id === id)
  return f ? f.qty : 0
}

function getCatEmoji(cat) {
  if (!cat) return '🍽️'
  const c = cat.toLowerCase()
  if (c.includes('noodle') || c.includes('ก๋วย')) return '🍜'
  if (c.includes('rice') || c.includes('ข้าว')) return '🍚'
  if (c.includes('drink') || c.includes('เครื่อง') || c.includes('น้ำ')) return '🥤'
  if (c.includes('dessert') || c.includes('ของหวาน')) return '🍮'
  return '🍽️'
}

function addToCart(item) {
  const existing = cart.value.find(i => i.id === item.id)
  if (existing) { existing.qty++ } else { cart.value.push({ ...item, qty: 1 }) }
  showToast('เพิ่ม ' + item.name + ' ✓')
}

function changeQty(idx, delta) {
  const item = cart.value[idx]
  if (!item) return
  item.qty += delta
  if (item.qty <= 0) cart.value.splice(idx, 1)
}

async function confirmPayment() {
  if (cart.value.length === 0) return
  paying.value = true
  try {
    const orderPayload = {
      table_number: tableLabel.value || '',
      order_type: orderType.value,
      customer_name: route.query.name || '',
      items: cart.value.map(i => ({ menu_item_id: i.id, quantity: i.qty, unit_price: i.price, notes: '' }))
    }
    const orderRes = await createOrder(orderPayload)
    const orderId = orderRes?.id || orderRes?.order_id
    if (orderId) {
      await processPayment({
        order_id: orderId,
        payment_method: payMethod.value,
        amount: cartGrand.value,
        received_amount: payMethod.value === 'cash' ? amountReceived.value : cartGrand.value
      })
    }
    showToast('ชำระเงินสำเร็จ! ✅')
    cart.value = []
    showPay.value = false
    amountReceived.value = 0
    setTimeout(() => router.push('/pos'), 2000)
  } catch (err) {
    console.error('Payment error:', err)
    showToast('เกิดข้อผิดพลาด กรุณาลองใหม่')
  } finally {
    paying.value = false
  }
}

function showToast(msg) {
  toastMsg.value = msg
  setTimeout(() => { toastMsg.value = '' }, 2500)
}

onMounted(async () => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  try {
    const methods = await getPaymentMethods()
    if (methods && methods.length > 0) payMethods.value = methods.map(m => ({ id: m.id || m.code, name: m.name }))
  } catch (e) {}
  try {
    const data = await getMenu()
    menu.value = Array.isArray(data) ? data : (data?.items || data?.data || [])
  } catch (e) {
    console.error('Menu load error:', e)
  } finally {
    loading.value = false
  }
  if (route.query.order) {
    try {
      const order = await getOrder(route.query.order)
      if (order?.items) {
        cart.value = order.items.map(i => ({
          id: i.menu_item_id, name: i.name || i.menu_item_name,
          price: i.unit_price || i.price, image_url: i.image_url,
          category: i.category, qty: i.quantity
        }))
      }
    } catch (e) {}
  }
})

onUnmounted(() => { if (clockTimer) clearInterval(clockTimer) })
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');
.pos-restodash * { box-sizing: border-box; }
.pos-restodash ::-webkit-scrollbar { width: 4px; }
.pos-restodash ::-webkit-scrollbar-track { background: transparent; }
.pos-restodash ::-webkit-scrollbar-thumb { background: #2A3545; border-radius: 4px; }
.pos-restodash button:focus { outline: none; }
</style>
'''


def run_ssh(ssh, cmd, timeout=120):
    print(f"\n>>> {cmd[:100]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip():
        print("OUT:", out[:800])
    if err.strip() and 'warning' not in err.lower():
        print("ERR:", err[:400])
    return out, err


def main():
    print("=== PosRestodash Deploy Script ===")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {HOST}...")
    ssh.connect(HOST, username=USER, password=PASS, timeout=20)
    print("Connected!\n")

    # 1. Upload Vue file via SFTP
    print("[1] Uploading PosRestodash.vue...")
    sftp = ssh.open_sftp()
    remote_vue = '/home/openhands/super-appsheet/frontend/src/views/PosRestodash.vue'
    sftp.putfo(io.BytesIO(VUE_CONTENT.encode('utf-8')), remote_vue)
    sftp.close()
    print(f"    Done -> {remote_vue}")

    # 2. Find router file
    print("\n[2] Finding router file...")
    out, _ = run_ssh(ssh, "find /home/openhands/super-appsheet/frontend/src -type f \\( -name '*.js' -o -name '*.ts' \\) | xargs grep -l 'createRouter\\|routes' 2>/dev/null | head -5")
    router_files = [l.strip() for l in out.strip().split('\n') if l.strip()]
    print("Found:", router_files)

    if not router_files:
        # Fallback: look for index.js or router.js
        out2, _ = run_ssh(ssh, "find /home/openhands/super-appsheet/frontend/src -type f -name '*.js' | head -20")
        print("All JS files:", out2)
        out3, _ = run_ssh(ssh, "find /home/openhands/super-appsheet/frontend/src -type f -name '*.ts' | head -20")
        print("All TS files:", out3)

    # 3. Show router content and add route
    for rf in router_files[:3]:
        print(f"\n[3] Reading {rf}...")
        content_out, _ = run_ssh(ssh, f"cat '{rf}'")
        print(content_out[:3000])

    # 4. Write a Python script on the remote server to patch the router
    patch_script = r"""
import re, sys

router_files = []
import subprocess
result = subprocess.run(
    ["find", "/home/openhands/super-appsheet/frontend/src", "-type", "f", "-name", "*.js"],
    capture_output=True, text=True
)
all_js = result.stdout.strip().split('\n')

for f in all_js:
    if not f:
        continue
    try:
        with open(f, 'r') as fh:
            c = fh.read()
        if 'createRouter' in c or ('routes' in c and 'path' in c):
            router_files.append(f)
    except:
        pass

print("Router files found:", router_files)

NEW_ROUTE = """  {
    path: '/pos/restodash',
    name: 'PosRestodash',
    component: () => import('./views/PosRestodash.vue')
  },"""

for rf in router_files:
    with open(rf, 'r') as fh:
        content = fh.read()
    
    if 'restodash' in content.lower():
        print(f"Route already exists in {rf}")
        continue
    
    # Find insertion point: after last route entry before closing bracket
    # Pattern: find last occurrence of path: '...' entry and insert after it
    # Try inserting before the closing of routes array
    
    # Strategy 1: find "  }\n]" or "  },\n]" pattern
    patterns = [
        ("  }\n]", "  }\n" + NEW_ROUTE + "\n]"),
        ("  },\n]", "  },\n" + NEW_ROUTE + "\n]"),
        ("  }\r\n]", "  }\r\n" + NEW_ROUTE + "\r\n]"),
    ]
    
    patched = False
    for old, new in patterns:
        if old in content:
            # Replace last occurrence
            idx = content.rfind(old)
            content = content[:idx] + new + content[idx+len(old):]
            patched = True
            print(f"Patched {rf} using pattern '{old.strip()}'")
            break
    
    if not patched:
        # Strategy 2: regex - find last path entry and insert after
        # Look for pattern like path: '/something' followed by content and closing
        m = list(re.finditer(r"path:\s*['\"](?!/pos/restodash)[^'\"]+['\"]", content))
        if m:
            last_match = m[-1]
            # Find the closing brace of this route object
            end_idx = last_match.end()
            depth = 0
            started = False
            for i in range(last_match.start() - 20, len(content)):
                if content[i] == '{':
                    depth += 1
                    started = True
                elif content[i] == '}' and started:
                    depth -= 1
                    if depth == 0:
                        end_idx = i + 1
                        break
            content = content[:end_idx] + ",\n" + NEW_ROUTE + content[end_idx:]
            patched = True
            print(f"Patched {rf} using regex strategy")
    
    if patched:
        with open(rf, 'w') as fh:
            fh.write(content)
        print(f"Saved {rf}")
        # Show verification
        import subprocess
        result = subprocess.run(["grep", "-n", "restodash", rf], capture_output=True, text=True)
        print("Verify:", result.stdout)
    else:
        print(f"Could not patch {rf} automatically!")
        print("Last 500 chars:", content[-500:])
"""

    # Write patch script to remote
    print("\n[4] Writing router patch script to remote...")
    sftp2 = ssh.open_sftp()
    sftp2.putfo(io.BytesIO(patch_script.encode('utf-8')), '/tmp/patch_router.py')
    sftp2.close()

    print("[5] Running router patch...")
    out_patch, err_patch = run_ssh(ssh, "cd /home/openhands/super-appsheet/frontend && python3 /tmp/patch_router.py", timeout=30)

    # 6. Build
    print("\n[6] Building frontend (this takes ~2-3 min)...")
    out_build, err_build = run_ssh(ssh,
        "cd /home/openhands/super-appsheet/frontend && npm run build 2>&1 | tail -40",
        timeout=240
    )
    print("Build result:", out_build[-1000:])

    # 7. Check dist
    print("\n[7] Checking dist...")
    run_ssh(ssh, "ls -la /home/openhands/super-appsheet/frontend/dist/ 2>/dev/null | tail -5")

    ssh.close()
    print("\n=== DONE ===")
    print("URL: https://pos.m2igen.com/pos/restodash?type=dinein&table=5&name=Table5")


if __name__ == '__main__':
    main()
