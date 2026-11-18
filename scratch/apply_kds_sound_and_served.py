import re

vue_file = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\PosRestodash.vue'
with open(vue_file, 'r', encoding='utf-8') as f:
    content = f.read()

# -------------------------------------------------------------------
# 1. Update Top Alarm Banner to support order_served & order_appended
# -------------------------------------------------------------------
old_alarm_banner = """    <!-- ── TOP ALARM BANNER (When New Order Arrives with Sound) ───────── -->
    <transition name="slide-down">
      <div v-if="activeAlarmBanner && viewMode === 'pos'" class="pos-alarm-banner">
        <div class="alarm-content">
          <div class="alarm-icon-box">🔔</div>
          <div class="alarm-text-box">
            <div class="alarm-title">มีออเดอร์ใหม่เข้ามา! (เสียงกำลังเตือน)</div>
            <div class="alarm-desc">
              {{ activeAlarmBanner.message || `ออเดอร์ #${activeAlarmBanner.orderId?.slice(-6) || ''} • ${activeAlarmBanner.table || 'หน้าร้าน'} • ฿${formatBaht(activeAlarmBanner.total)}` }}
            </div>
          </div>
          <div class="alarm-actions">
            <button @click="acceptOrderAlarm" class="alarm-btn-accept">
              🛎️ รับออเดอร์
            </button>
            <button @click="dismissOrderAlarm" class="alarm-btn-dismiss">
              ✕ ปิดเสียง / รับทราบ
            </button>
          </div>
        </div>
      </div>
    </transition>"""

new_alarm_banner = """    <!-- ── TOP ALARM BANNER (When New Order, Appended Items, or Food Served) ───────── -->
    <transition name="slide-down">
      <div
        v-if="activeAlarmBanner && viewMode === 'pos'"
        class="pos-alarm-banner"
        :class="{
          'is-served-banner': activeAlarmBanner.type === 'order_served',
          'is-appended-banner': activeAlarmBanner.type === 'order_appended'
        }"
      >
        <div class="alarm-content">
          <div class="alarm-icon-box">
            {{ activeAlarmBanner.type === 'order_served' ? '🥗' : (activeAlarmBanner.type === 'order_appended' ? '✨' : '🔔') }}
          </div>
          <div class="alarm-text-box">
            <div class="alarm-title">
              {{ activeAlarmBanner.type === 'order_served' ? 'อาหารเสิร์ฟครบแล้ว (พร้อมคิดเงิน)!' : (activeAlarmBanner.type === 'order_appended' ? 'มีรายการสั่งอาหารเพิ่ม!' : 'มีออเดอร์ใหม่เข้ามา!') }}
            </div>
            <div class="alarm-desc">
              {{ activeAlarmBanner.message || `ออเดอร์ #${activeAlarmBanner.orderId?.slice(-6) || ''} • ${activeAlarmBanner.table || 'หน้าร้าน'} • ฿${formatBaht(activeAlarmBanner.total)}` }}
            </div>
          </div>
          <div class="alarm-actions">
            <!-- If food is served: Quick Checkout button -->
            <button
              v-if="activeAlarmBanner.type === 'order_served'"
              @click="quickCheckoutServedOrder(activeAlarmBanner)"
              class="alarm-btn-checkout"
            >
              💳 คิดเงินโต๊ะนี้ทันที
            </button>
            <!-- If new/appended: Go to KDS -->
            <button
              v-else
              @click="acceptOrderAlarm"
              class="alarm-btn-accept"
            >
              🛎️ ดูหน้าครัว (KDS)
            </button>
            <button @click="dismissOrderAlarm" class="alarm-btn-dismiss">
              ✕ รับทราบ
            </button>
          </div>
        </div>
      </div>
    </transition>"""

if old_alarm_banner in content:
    content = content.replace(old_alarm_banner, new_alarm_banner, 1)
    print("1. Updated Top Alarm Banner")
else:
    print("1. WARNING: old_alarm_banner NOT found")

# -------------------------------------------------------------------
# 2. Update Table Map Modal (Modal 1) to support 'served' status
# -------------------------------------------------------------------
old_table_card = """          <div
            v-for="tb in filteredTables"
            :key="tb.id"
            class="table-card"
            :class="{
              'is-active': selectedTableId === tb.id && orderType !== 'takeaway',
              'is-occupied': tb.status === 'occupied'
            }"
            @click="selectTable(tb.id)"
          >
            <div class="table-card-top">
              <span class="table-number">{{ tb.name }}</span>
              <span class="table-zone-badge">{{ tb.zone || 'Indoor' }}</span>
            </div>
            <div class="table-capacity">👥 {{ tb.capacity || 4 }} ที่นั่ง</div>
            <div class="table-status-label">
              <span v-if="tb.status === 'occupied'" class="status-dot red"></span>
              <span v-else class="status-dot green"></span>
              <span>{{ tb.status === 'occupied' ? 'มีลูกค้า' : 'ว่าง' }}</span>
            </div>
          </div>"""

new_table_card = """          <div
            v-for="tb in filteredTables"
            :key="tb.id"
            class="table-card"
            :class="{
              'is-active': selectedTableId === tb.id && orderType !== 'takeaway',
              'is-occupied': tb.status === 'occupied',
              'is-served': tb.status === 'served'
            }"
            @click="selectTable(tb.id)"
          >
            <div class="table-card-top">
              <span class="table-number">{{ tb.name }}</span>
              <span class="table-zone-badge">{{ tb.zone || 'Indoor' }}</span>
            </div>
            <div class="table-capacity">👥 {{ tb.capacity || 4 }} ที่นั่ง</div>
            <div class="table-status-label">
              <span v-if="tb.status === 'served'" class="status-dot served-green-pulse"></span>
              <span v-else-if="tb.status === 'occupied'" class="status-dot red"></span>
              <span v-else class="status-dot green"></span>
              <span :class="{ 'text-served-bold': tb.status === 'served' }">
                {{ tb.status === 'served' ? '🟢 เสิร์ฟครบแล้ว (พร้อมคิดเงิน)' : (tb.status === 'occupied' ? 'กำลังทาน / รอเสิร์ฟ' : 'ว่าง') }}
              </span>
            </div>
          </div>"""

if old_table_card in content:
    content = content.replace(old_table_card, new_table_card, 1)
    print("2. Updated Table Map Modal cards")
else:
    print("2. WARNING: old_table_card NOT found")

# -------------------------------------------------------------------
# 3. Update KDS Modal Header with Audio Toggle & Test Chime
# -------------------------------------------------------------------
old_kds_header = """        <div class="modal-header">
          <div>
            <div class="modal-title">🍳 หน้าจอห้องครัว (Kitchen Display System)</div>
            <div class="modal-sub">
              ออเดอร์รอปรุง: <b>{{ kitchenOrders.length }} ตั๋ว</b> • คลิกที่ชื่ออาหารเพื่อติ๊ก <b>"เสิร์ฟแล้ว"</b>
            </div>
          </div>
          <button @click="showKitchenModal = false" class="modal-close-btn">✕</button>
        </div>"""

new_kds_header = """        <div class="modal-header kds-header-flex">
          <div>
            <div class="modal-title">🍳 หน้าจอห้องครัว (Kitchen Display System)</div>
            <div class="modal-sub">
              ออเดอร์รอปรุง: <b>{{ kitchenOrders.length }} ตั๋ว</b> • คลิกที่ชื่ออาหารเพื่อติ๊ก <b>"เสิร์ฟแล้ว"</b>
            </div>
          </div>
          <div class="kds-header-controls">
            <button
              @click="toggleKdsSound"
              class="kds-sound-toggle-btn"
              :class="{ 'is-muted': !isKdsSoundEnabled }"
              :title="isKdsSoundEnabled ? 'คลิกเพื่อปิดเสียงเตือนครัว' : 'คลิกเพื่อเปิดเสียงเตือนครัว'"
            >
              {{ isKdsSoundEnabled ? '🔊 เสียงเตือนครัว: เปิด' : '🔇 เสียงเตือนครัว: ปิด' }}
            </button>
            <button
              @click="playKdsChime"
              class="kds-test-sound-btn"
              title="ทดสอบเสียงกระดิ่งครัว"
            >
              🔔 ทดสอบเสียง
            </button>
            <button @click="showKitchenModal = false" class="modal-close-btn">✕</button>
          </div>
        </div>"""

if old_kds_header in content:
    content = content.replace(old_kds_header, new_kds_header, 1)
    print("3. Updated KDS Modal Header")
else:
    print("3. WARNING: old_kds_header NOT found")

# -------------------------------------------------------------------
# 4. Update KDS Ticket Item Rows with '✨ สั่งเพิ่ม (New)' Badge
# -------------------------------------------------------------------
old_kds_item_row = """                <div
                  v-for="(item, itIdx) in order.items"
                  :key="itIdx"
                  class="ticket-item-row"
                  :class="{ 'is-served': item.item_served }"
                  @click="toggleItemServed(order, item, itIdx)"
                  title="คลิกเพื่อติ๊กเสิร์ฟแล้ว"
                >
                  <div class="ticket-item-check-icon">
                    {{ item.item_served ? '✓' : '○' }}
                  </div>
                  <div class="ticket-item-qty">{{ item.quantity }}x</div>
                  <div class="ticket-item-name-box">
                    <span class="item-name" :class="{ 'line-through': item.item_served }">
                      {{ item.name }}
                    </span>
                    <span v-if="item.item_served" class="badge-served-mini">เสิร์ฟแล้ว</span>
                    <div v-if="item.notes" class="ticket-item-notes">📝 {{ item.notes }}</div>
                  </div>
                </div>"""

new_kds_item_row = """                <div
                  v-for="(item, itIdx) in order.items"
                  :key="itIdx"
                  class="ticket-item-row"
                  :class="{
                    'is-served': item.item_served,
                    'is-appended-new': item.is_new_item && !item.item_served
                  }"
                  @click="toggleItemServed(order, item, itIdx)"
                  title="คลิกเพื่อติ๊กเสิร์ฟแล้ว"
                >
                  <div class="ticket-item-check-icon">
                    {{ item.item_served ? '✓' : '○' }}
                  </div>
                  <div class="ticket-item-qty">{{ item.quantity }}x</div>
                  <div class="ticket-item-name-box">
                    <div class="item-name-row">
                      <span class="item-name" :class="{ 'line-through': item.item_served }">
                        {{ item.name }}
                      </span>
                      <span v-if="item.is_new_item && !item.item_served" class="badge-new-item-pill">
                        ✨ สั่งเพิ่ม (New)
                      </span>
                      <span v-if="item.item_served" class="badge-served-mini">เสิร์ฟแล้ว</span>
                    </div>
                    <div v-if="item.notes" class="ticket-item-notes">📝 {{ item.notes }}</div>
                  </div>
                </div>"""

if old_kds_item_row in content:
    content = content.replace(old_kds_item_row, new_kds_item_row, 1)
    print("4. Updated KDS Ticket Item Rows with '✨ สั่งเพิ่ม (New)'")
else:
    print("4. WARNING: old_kds_item_row NOT found")

# -------------------------------------------------------------------
# 5. Add JavaScript methods & watchers for KDS Sound and Cashier Alert
# -------------------------------------------------------------------
old_kds_methods = """async function completeKitchenOrder(orderId) {
  try {
    await updateOrderStatus(orderId, 'served')
    kitchenOrders.value = kitchenOrders.value.filter(o => o.order_id !== orderId)
    showToast(`ปิดตั๋วออเดอร์ #${orderId.slice(-6)} เรียบร้อย 🍳`)
  } catch (err) {
    console.error('Complete kitchen order error:', err)
  }
}"""

new_kds_methods = """// ── KDS Sound & Audio Synthesis ──────────────────────────────────────
const isKdsSoundEnabled = ref(localStorage.getItem('kds_sound_enabled') !== 'false')
const knownKitchenSignatures = ref(new Set())
let hasInitializedKitchen = false

function toggleKdsSound() {
  isKdsSoundEnabled.value = !isKdsSoundEnabled.value
  localStorage.setItem('kds_sound_enabled', isKdsSoundEnabled.value ? 'true' : 'false')
  if (isKdsSoundEnabled.value) {
    playKdsChime()
    showToast('🔊 เปิดเสียงเตือนห้องครัวแล้ว')
  } else {
    showToast('🔇 ปิดเสียงเตือนห้องครัวแล้ว')
  }
}

function playKdsChime() {
  if (!isKdsSoundEnabled.value) return
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext
    if (!AudioCtx) return
    const ctx = new AudioCtx()
    if (ctx.state === 'suspended') {
      ctx.resume()
    }
    const now = ctx.currentTime

    // Note 1: E5 (659.25 Hz)
    const osc1 = ctx.createOscillator()
    const gain1 = ctx.createGain()
    osc1.type = 'sine'
    osc1.frequency.setValueAtTime(659.25, now)
    gain1.gain.setValueAtTime(0.22, now)
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.35)
    osc1.connect(gain1)
    gain1.connect(ctx.destination)
    osc1.start(now)
    osc1.stop(now + 0.36)

    // Note 2: A5 (880 Hz) - pleasant dining bell
    const osc2 = ctx.createOscillator()
    const gain2 = ctx.createGain()
    osc2.type = 'sine'
    osc2.frequency.setValueAtTime(880, now + 0.12)
    gain2.gain.setValueAtTime(0.26, now + 0.12)
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.60)
    osc2.connect(gain2)
    gain2.connect(ctx.destination)
    osc2.start(now + 0.12)
    osc2.stop(now + 0.61)

    // Note 3: C#6 (1108.7 Hz) - chime decay
    const osc3 = ctx.createOscillator()
    const gain3 = ctx.createGain()
    osc3.type = 'sine'
    osc3.frequency.setValueAtTime(1108.73, now + 0.24)
    gain3.gain.setValueAtTime(0.18, now + 0.24)
    gain3.gain.exponentialRampToValueAtTime(0.001, now + 0.75)
    osc3.connect(gain3)
    gain3.connect(ctx.destination)
    osc3.start(now + 0.24)
    osc3.stop(now + 0.76)
  } catch (err) {
    console.warn('Audio chime playback error:', err)
  }
}

// Watch kitchen orders to play chime on incoming orders or re-orders
watch(kitchenOrders, (newOrders) => {
  if (!Array.isArray(newOrders)) return
  if (!hasInitializedKitchen) {
    newOrders.forEach(o => {
      const sig = `${o.order_id}_${o.items?.length || 0}`
      knownKitchenSignatures.value.add(sig)
    })
    hasInitializedKitchen = true
    return
  }

  let hasNewOrAppended = false
  newOrders.forEach(o => {
    const sig = `${o.order_id}_${o.items?.length || 0}`
    if (!knownKitchenSignatures.value.has(sig)) {
      hasNewOrAppended = true
      knownKitchenSignatures.value.add(sig)
    }
  })

  if (hasNewOrAppended) {
    playKdsChime()
    showToast('🍳 มีออเดอร์ใหม่ หรือ รายการสั่งเพิ่มในครัว!')
  }
}, { deep: true })

async function completeKitchenOrder(orderId) {
  try {
    await updateOrderStatus(orderId, 'served')
    const finished = kitchenOrders.value.find(o => o.order_id === orderId)
    const tName = finished?.table_name || (finished?.table_id ? `โต๊ะ ${finished.table_id}` : '')
    kitchenOrders.value = kitchenOrders.value.filter(o => o.order_id !== orderId)
    showToast(`🎉 ออเดอร์ ${tName ? tName + ' ' : ''}#${orderId.slice(-6)} เสิร์ฟครบแล้ว! แจ้งแคชเชียร์เรียบร้อย 🥗`)
    fetchData()
  } catch (err) {
    console.error('Complete kitchen order error:', err)
  }
}

async function quickCheckoutServedOrder(banner) {
  dismissOrderAlarm()
  try {
    const orderId = banner.orderId
    let order = allOrders.value.find(o => o.order_id === orderId)
    if (!order) {
      order = await getOrder(orderId).catch(() => null)
    }
    if (order) {
      openUnpaidOrderCheckout(order)
      showToast(`เปิดบิลคิดเงิน ${banner.table || ''} เรียบร้อย 💳`)
    } else {
      showToast(`เปิดคิดเงินออเดอร์ #${orderId.slice(-6)}`)
    }
  } catch (err) {
    console.error('Quick checkout served order error:', err)
  }
}"""

if old_kds_methods in content:
    content = content.replace(old_kds_methods, new_kds_methods, 1)
    print("5. Added KDS Sound, Chime & Quick Checkout methods")
else:
    print("5. WARNING: old_kds_methods NOT found")

# -------------------------------------------------------------------
# 6. Update pollNotifications to handle event_type
# -------------------------------------------------------------------
old_poll = """async function pollNotifications() {
  try {
    const res = await apiNotif.get('/notifications/pending')
    if (res.data && Array.isArray(res.data) && res.data.length > 0) {
      const unhandled = res.data.filter(n => {
        const nid = String(n.id || '')
        const oid = String(n.data?.order_id || '')
        return !dismissedNotifIds.has(nid) && !dismissedNotifIds.has(oid)
      })

      if (unhandled.length > 0) {
        const top = unhandled[0]
        activeAlarmBanner.value = {
          id: top.id,
          orderId: top.data?.order_id || top.id,
          table: top.data?.table_name || top.table_name || `โต๊ะ ${top.data?.table_id || ''}`,
          total: top.data?.grand_total || top.total || 0,
          message: top.message || `มีออเดอร์ใหม่ #${String(top.data?.order_id || top.id).slice(-6)}`
        }
      } else {
        activeAlarmBanner.value = null
      }
    } else {
      activeAlarmBanner.value = null
    }
  } catch {}
}"""

new_poll = """async function pollNotifications() {
  try {
    const res = await apiNotif.get('/notifications/pending')
    if (res.data && Array.isArray(res.data) && res.data.length > 0) {
      const unhandled = res.data.filter(n => {
        const nid = String(n.id || '')
        const oid = String(n.data?.order_id || '')
        return !dismissedNotifIds.has(nid) && !dismissedNotifIds.has(oid)
      })

      if (unhandled.length > 0) {
        const top = unhandled[0]
        activeAlarmBanner.value = {
          id: top.id,
          type: top.event_type || 'new_order',
          orderId: top.data?.order_id || top.id,
          table: top.data?.table_name || top.table_name || `โต๊ะ ${top.data?.table_id || ''}`,
          total: top.data?.grand_total || top.total || 0,
          message: top.message || `มีออเดอร์ใหม่ #${String(top.data?.order_id || top.id).slice(-6)}`
        }
      } else {
        activeAlarmBanner.value = null
      }
    } else {
      activeAlarmBanner.value = null
    }
  } catch {}
}"""

if old_poll in content:
    content = content.replace(old_poll, new_poll, 1)
    print("6. Updated pollNotifications to preserve event_type")
else:
    print("6. WARNING: old_poll NOT found")

# -------------------------------------------------------------------
# 7. Add Styles inside <style scoped>
# -------------------------------------------------------------------
kds_and_served_styles = """
/* ── KDS Header Controls & Sound Toggle ──────────────────────────────── */
.kds-header-flex {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  gap: 12px !important;
}

.kds-header-controls {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
}

.kds-sound-toggle-btn {
  display: inline-flex !important;
  align-items: center !important;
  gap: 6px !important;
  background: #ECFDF5 !important;
  color: #065F46 !important;
  border: 1.5px solid #A7F3D0 !important;
  padding: 6px 14px !important;
  border-radius: 8px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  cursor: pointer !important;
  transition: all 0.2s ease !important;
  user-select: none !important;
}

.kds-sound-toggle-btn:hover {
  background: #D1FAE5 !important;
  transform: translateY(-1px) !important;
}

.kds-sound-toggle-btn.is-muted {
  background: #F3F4F6 !important;
  color: #6B7280 !important;
  border-color: #E5E7EB !important;
}

.kds-test-sound-btn {
  display: inline-flex !important;
  align-items: center !important;
  gap: 5px !important;
  background: #EFF6FF !important;
  color: #1D4ED8 !important;
  border: 1.5px solid #BFDBFE !important;
  padding: 6px 12px !important;
  border-radius: 8px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  cursor: pointer !important;
  transition: all 0.2s ease !important;
}

.kds-test-sound-btn:hover {
  background: #DBEAFE !important;
  transform: translateY(-1px) !important;
}

/* ── KDS Appended Item Highlight & Badge ─────────────────────────────── */
.item-name-row {
  display: flex !important;
  align-items: center !important;
  flex-wrap: wrap !important;
  gap: 6px !important;
}

.badge-new-item-pill {
  display: inline-flex !important;
  align-items: center !important;
  gap: 3px !important;
  background: linear-gradient(135deg, #F59E0B, #D97706) !important;
  color: #FFFFFF !important;
  font-size: 10.5px !important;
  font-weight: 800 !important;
  padding: 2px 8px !important;
  border-radius: 999px !important;
  box-shadow: 0 2px 6px rgba(217, 119, 6, 0.4) !important;
  letter-spacing: 0.3px !important;
  animation: pulse-gold-glow 2s infinite ease-in-out !important;
}

@keyframes pulse-gold-glow {
  0% { transform: scale(1); box-shadow: 0 2px 6px rgba(217, 119, 6, 0.4); }
  50% { transform: scale(1.06); box-shadow: 0 4px 12px rgba(217, 119, 6, 0.65); }
  100% { transform: scale(1); box-shadow: 0 2px 6px rgba(217, 119, 6, 0.4); }
}

.ticket-item-row.is-appended-new {
  background: #FFFBEB !important;
  border-left: 3.5px solid #F59E0B !important;
}

/* ── Top Alarm Banner Variants (Served & Appended) ───────────────────── */
.pos-alarm-banner.is-served-banner {
  background: linear-gradient(135deg, #059669, #047857) !important;
  border-color: #34D399 !important;
  box-shadow: 0 6px 20px rgba(5, 150, 105, 0.35) !important;
}

.pos-alarm-banner.is-appended-banner {
  background: linear-gradient(135deg, #D97706, #B45309) !important;
  border-color: #FBBF24 !important;
}

.alarm-btn-checkout {
  background: #FFFFFF !important;
  color: #065F46 !important;
  border: none !important;
  padding: 8px 16px !important;
  border-radius: 8px !important;
  font-size: 13.5px !important;
  font-weight: 800 !important;
  cursor: pointer !important;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.15) !important;
  transition: all 0.2s ease !important;
}

.alarm-btn-checkout:hover {
  transform: translateY(-1px) scale(1.02) !important;
  background: #F0FDF4 !important;
}

/* ── Table Map 'Served' State ────────────────────────────────────────── */
.table-card.is-served {
  border: 2px solid #10B981 !important;
  background: #ECFDF5 !important;
  box-shadow: 0 4px 14px rgba(16, 185, 129, 0.2) !important;
}

.status-dot.served-green-pulse {
  background: #10B981 !important;
  box-shadow: 0 0 0 rgba(16, 185, 129, 0.7) !important;
  animation: pulse-green-dot 1.6s infinite !important;
}

.text-served-bold {
  color: #047857 !important;
  font-weight: 800 !important;
}

@keyframes pulse-green-dot {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
  70% { transform: scale(1.15); box-shadow: 0 0 0 7px rgba(16, 185, 129, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}
"""

idx = content.rfind('</style>')
if idx != -1:
    content = content[:idx] + "\n" + kds_and_served_styles + "\n</style>\n"
    print("7. Added KDS and Served styles inside <style scoped>")
else:
    print("7. WARNING: </style> not found")

with open(vue_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated PosRestodash.vue successfully!")
