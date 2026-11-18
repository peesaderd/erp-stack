<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getKitchenOrders, updateOrderStatus, markItemServed } from '../api/index.js'

// State
const orders = ref([])
const loading = ref(false)
const error = ref('')
const activeFilter = ref('preparing') // 'preparing' | 'new_appended' | 'served' | 'all'
const isFullscreen = ref(false)
const isAudioEnabled = ref(true)
const lastKnownOrderCount = ref(0)
const knownOrderIds = ref(new Set())
const knownItemCounts = ref(new Map())
const currentTime = ref('')
let timerInterval = null
let clockInterval = null

// Audio Engine via Web Audio API (No external sound file required, reliable & instant)
function playKitchenChime() {
  if (!isAudioEnabled.value) return
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext
    if (!AudioContext) return
    const ctx = new AudioContext()
    if (ctx.state === 'suspended') {
      ctx.resume()
    }

    const now = ctx.currentTime
    // Tone 1: High crisp ding (880Hz - A5)
    const osc1 = ctx.createOscillator()
    const gain1 = ctx.createGain()
    osc1.type = 'sine'
    osc1.frequency.setValueAtTime(880, now)
    gain1.gain.setValueAtTime(0.4, now)
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.5)
    osc1.connect(gain1)
    gain1.connect(ctx.destination)
    osc1.start(now)
    osc1.stop(now + 0.5)

    // Tone 2: Warm harmonic chime (1318.5Hz - E6)
    const osc2 = ctx.createOscillator()
    const gain2 = ctx.createGain()
    osc2.type = 'sine'
    osc2.frequency.setValueAtTime(1318.5, now + 0.12)
    gain2.gain.setValueAtTime(0.5, now + 0.12)
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.9)
    osc2.connect(gain2)
    gain2.connect(ctx.destination)
    osc2.start(now + 0.12)
    osc2.stop(now + 0.9)
  } catch (e) {
    console.warn('Audio alert error:', e)
  }
}

function testSound() {
  playKitchenChime()
}

function toggleAudio() {
  isAudioEnabled.value = !isAudioEnabled.value
  localStorage.setItem('pos_kds_audio_enabled', isAudioEnabled.value ? 'true' : 'false')
  if (isAudioEnabled.value) {
    testSound()
  }
}

// Fullscreen Toggle
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().then(() => {
      isFullscreen.value = true
    }).catch(() => {})
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen().then(() => {
        isFullscreen.value = false
      }).catch(() => {})
    }
  }
}

// Clock
function updateClock() {
  const d = new Date()
  currentTime.value = d.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

// Elapsed timer helper
function getElapsedMinutes(createdAt) {
  if (!createdAt) return 0
  const diff = Date.now() - new Date(createdAt).getTime()
  return Math.max(0, Math.floor(diff / 60000))
}

function formatElapsed(createdAt) {
  const mins = getElapsedMinutes(createdAt)
  if (mins < 1) return '< 1 นาที'
  if (mins < 60) return `${mins} นาที`
  const hours = Math.floor(mins / 60)
  const remMins = mins % 60
  return `${hours} ชม. ${remMins} น.`
}

function getTimerClass(createdAt) {
  const mins = getElapsedMinutes(createdAt)
  if (mins >= 20) return 'timer-red-pulse'
  if (mins >= 10) return 'timer-yellow'
  return 'timer-green'
}

function formatTime(isoString) {
  if (!isoString) return ''
  const d = new Date(isoString)
  return d.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' })
}

// Load KDS Orders
async function loadKitchenOrders(isPoll = false) {
  if (!isPoll) loading.value = true
  try {
    const data = await getKitchenOrders()
    const incomingOrders = Array.isArray(data) ? data : (data.orders || [])

    // Detect new orders or appended items to trigger sound alert
    let triggerAlert = false

    if (isPoll && isAudioEnabled.value) {
      for (const order of incomingOrders) {
        const oId = order.order_id
        const itemCount = (order.items || []).length

        // Case 1: Brand new order
        if (!knownOrderIds.value.has(oId)) {
          triggerAlert = true
          break
        }

        // Case 2: Existing order got appended items
        const prevCount = knownItemCounts.value.get(oId) || 0
        if (itemCount > prevCount) {
          triggerAlert = true
          break
        }
      }
    }

    if (triggerAlert) {
      playKitchenChime()
    }

    // Update tracking
    const newKnownIds = new Set()
    const newCounts = new Map()
    incomingOrders.forEach(o => {
      newKnownIds.add(o.order_id)
      newCounts.set(o.order_id, (o.items || []).length)
    })
    knownOrderIds.value = newKnownIds
    knownItemCounts.value = newCounts
    lastKnownOrderCount.value = incomingOrders.length

    orders.value = incomingOrders
    error.value = ''
  } catch (err) {
    console.error('KDS load error:', err)
    error.value = 'ไม่สามารถดึงข้อมูลครัวได้ กรุณาตรวจสอบการเชื่อมต่อ'
  } finally {
    if (!isPoll) loading.value = false
  }
}

// Check if an order has newly appended items
function hasNewItems(order) {
  if (!order || !order.items) return false
  return order.items.some(i => i.is_new_item && !i.item_served)
}

function isAllServed(order) {
  if (!order || !order.items || order.items.length === 0) return false
  return order.items.every(i => i.item_served)
}

function getUnservedCount(order) {
  if (!order || !order.items) return 0
  return order.items.filter(i => !i.item_served).length
}

// Actions
async function handleMarkItemServed(order, item, itemIndex) {
  const line = item.line !== undefined ? item.line : itemIndex
  try {
    await markItemServed(order.order_id, line)
    item.item_served = true

    // Check if all served
    if (isAllServed(order) && order.status === 'preparing') {
      await updateOrderStatus(order.order_id, 'served')
      order.status = 'served'
    }
  } catch (err) {
    console.error('Mark item served failed:', err)
    alert('ไม่สามารถอัปเดตรายการนี้ได้: ' + (err.message || ''))
  }
}

async function handleMarkOrderServed(order) {
  try {
    // 1. Mark all items served locally & on server
    if (order.items && order.items.length > 0) {
      for (let idx = 0; idx < order.items.length; idx++) {
        const it = order.items[idx]
        if (!it.item_served) {
          const line = it.line !== undefined ? it.line : idx
          try {
            await markItemServed(order.order_id, line)
          } catch (e) {
            console.warn('Item served err:', e)
          }
          it.item_served = true
        }
      }
    }

    // 2. Mark order status as 'served'
    await updateOrderStatus(order.order_id, 'served')
    order.status = 'served'

    // Refresh after short delay
    setTimeout(() => {
      loadKitchenOrders(true)
    }, 800)
  } catch (err) {
    console.error('Complete order served failed:', err)
    alert('เกิดข้อผิดพลาดในการเสิร์ฟ: ' + (err.message || ''))
  }
}

// Computed Filters
const filteredOrders = computed(() => {
  if (activeFilter.value === 'preparing') {
    return orders.value.filter(o => o.status === 'preparing' || o.status === 'pending')
  }
  if (activeFilter.value === 'new_appended') {
    return orders.value.filter(o => hasNewItems(o))
  }
  if (activeFilter.value === 'served') {
    return orders.value.filter(o => o.status === 'served')
  }
  return orders.value
})

const preparingCount = computed(() => {
  return orders.value.filter(o => o.status === 'preparing' || o.status === 'pending').length
})

const appendedCount = computed(() => {
  return orders.value.filter(o => hasNewItems(o)).length
})

const servedCount = computed(() => {
  return orders.value.filter(o => o.status === 'served').length
})

onMounted(() => {
  const savedAudio = localStorage.getItem('pos_kds_audio_enabled')
  if (savedAudio !== null) {
    isAudioEnabled.value = savedAudio === 'true'
  }

  updateClock()
  clockInterval = setInterval(updateClock, 1000)

  loadKitchenOrders()
  timerInterval = setInterval(() => {
    loadKitchenOrders(true)
  }, 3500)

  document.addEventListener('fullscreenchange', () => {
    isFullscreen.value = !!document.fullscreenElement
  })
})

onUnmounted(() => {
  if (clockInterval) clearInterval(clockInterval)
  if (timerInterval) clearInterval(timerInterval)
})
</script>

<template>
  <div class="kds-standalone-app">

    <!-- ── TOP KDS HEADER BAR ────────────────────────────────────────── -->
    <header class="kds-header">
      <div class="kds-header-left">
        <div class="kds-brand">
          <span class="kds-brand-icon">🍳</span>
          <div class="kds-brand-text">
            <h1 class="kds-title">หน้าจอห้องครัว (KDS)</h1>
            <span class="kds-sub">Kitchen Display System • Bakehouse POS</span>
          </div>
        </div>

        <!-- Live Status Pill -->
        <div class="kds-live-pill">
          <span class="live-dot-pulse"></span>
          <span>ระบบออนไลน์</span>
        </div>
      </div>

      <!-- Center: Filter Tabs -->
      <div class="kds-filter-tabs">
        <button
          @click="activeFilter = 'preparing'"
          class="kds-tab-btn"
          :class="{ 'is-active': activeFilter === 'preparing' }"
        >
          <span>🔥 กำลังปรุง</span>
          <span class="kds-tab-badge badge-orange">{{ preparingCount }}</span>
        </button>

        <button
          v-if="appendedCount > 0"
          @click="activeFilter = 'new_appended'"
          class="kds-tab-btn tab-appended-highlight"
          :class="{ 'is-active': activeFilter === 'new_appended' }"
        >
          <span>✨ สั่งเพิ่มใหม่</span>
          <span class="kds-tab-badge badge-purple">{{ appendedCount }}</span>
        </button>

        <button
          @click="activeFilter = 'served'"
          class="kds-tab-btn"
          :class="{ 'is-active': activeFilter === 'served' }"
        >
          <span>🟢 เสิร์ฟแล้ว</span>
          <span class="kds-tab-badge badge-green">{{ servedCount }}</span>
        </button>

        <button
          @click="activeFilter = 'all'"
          class="kds-tab-btn"
          :class="{ 'is-active': activeFilter === 'all' }"
        >
          <span>📋 ทั้งหมด</span>
          <span class="kds-tab-badge badge-slate">{{ orders.length }}</span>
        </button>
      </div>

      <!-- Right: Audio Controls, Clock, Fullscreen & POS Link -->
      <div class="kds-header-right">
        <!-- Audio Alarm Toggle -->
        <button
          @click="toggleAudio"
          class="kds-action-btn btn-audio-toggle"
          :class="{ 'is-muted': !isAudioEnabled }"
          :title="isAudioEnabled ? 'ปิดเสียงเตือน' : 'เปิดเสียงเตือน'"
        >
          <span>{{ isAudioEnabled ? '🔊 เสียงเตือน: เปิด' : '🔇 เสียงเตือน: ปิด' }}</span>
        </button>

        <!-- Test Chime Button -->
        <button
          @click="testSound"
          class="kds-action-btn btn-sound-test"
          title="ทดสอบเสียงกระดิ่งครัว"
        >
          <span>🔔 ทดสอบเสียง</span>
        </button>

        <!-- Fullscreen Button -->
        <button
          @click="toggleFullscreen"
          class="kds-action-btn btn-fullscreen"
          :title="isFullscreen ? 'ออกจากเต็มจอ' : 'แสดงเต็มหน้าจอ'"
        >
          <span>{{ isFullscreen ? '⛶ ย่อจอ' : '⛶ เต็มจอ' }}</span>
        </button>

        <!-- Realtime Clock -->
        <div class="kds-clock">
          {{ currentTime }}
        </div>

        <!-- POS Link -->
        <a href="/pos/restodash" class="kds-btn-pos" title="ไปที่หน้า POS รับออเดอร์">
          <span>หน้าร้าน POS ↗</span>
        </a>
      </div>
    </header>

    <!-- ── TICKETS MAIN GRID ─────────────────────────────────────────── -->
    <main class="kds-main-grid custom-scrollbar">

      <!-- Empty State -->
      <div v-if="filteredOrders.length === 0" class="kds-empty-state">
        <div class="empty-icon-wrap">
          <span class="empty-icon">🍳</span>
        </div>
        <h2 class="empty-title">ไม่มีออเดอร์ที่ต้องทำในขณะนี้</h2>
        <p class="empty-desc">
          {{ activeFilter === 'preparing' ? 'ทุกออเดอร์ปรุงและเสิร์ฟเรียบร้อยแล้ว เมื่อมีออเดอร์ใหม่เข้ามาจะมีเสียงกระดิ่งเตือนทันที' : 'ไม่พบรายการออเดอร์ในหมวดหมู่นี้' }}
        </p>
        <button @click="loadKitchenOrders()" class="btn-empty-refresh">
          🔄 รีเฟรชข้อมูล
        </button>
      </div>

      <!-- Ticket Cards -->
      <div v-else class="kds-cards-container">
        <div
          v-for="order in filteredOrders"
          :key="order.order_id"
          class="kds-ticket-card"
          :class="{
            'is-appended': hasNewItems(order),
            'is-served': order.status === 'served',
            'is-urgent': getElapsedMinutes(order.created_at) >= 20 && order.status === 'preparing'
          }"
        >

          <!-- Ticket Header: Table Name, Elapsed Timer, Order Info -->
          <div class="ticket-header">
            <div class="ticket-table-row">
              <div class="ticket-table-name">
                <span class="table-icon">{{ order.table_id === 'takeaway' ? '📦' : '🪑' }}</span>
                <span>{{ order.table_name || (order.table_id === 'takeaway' ? 'สั่งกลับบ้าน' : `โต๊ะ ${order.table_id}`) }}</span>
              </div>
              <div class="ticket-timer-badge" :class="getTimerClass(order.created_at)">
                <span>⏱️ {{ formatElapsed(order.created_at) }}</span>
              </div>
            </div>

            <div class="ticket-meta-row">
              <span class="ticket-id">#{{ order.order_id.slice(-6) }}</span>
              <span class="ticket-time">{{ formatTime(order.created_at) }}</span>
              <span class="ticket-channel-pill" :class="order.order_channel || 'shop'">
                {{ (order.order_channel === 'online' || order.source === 'qr') ? '📱 สั่งผ่าน QR' : '🏪 สั่งหน้าร้าน' }}
              </span>
            </div>

            <!-- Appended Items Alert Ribbon -->
            <div v-if="hasNewItems(order)" class="ticket-appended-banner">
              <span class="banner-pulse">●</span>
              <span>✨ มีรายการสั่งเพิ่มใหม่ (New Items)</span>
            </div>
          </div>

          <!-- Ticket Items List -->
          <div class="ticket-items-list custom-scrollbar">
            <div
              v-for="(item, idx) in order.items"
              :key="item.line || idx"
              class="ticket-item-row"
              :class="{
                'item-is-served': item.item_served,
                'item-is-new': item.is_new_item && !item.item_served
              }"
            >
              <div class="item-left-col">
                <span class="item-qty-badge">{{ item.quantity }}x</span>
                <div class="item-details">
                  <div class="item-name-row">
                    <span class="item-name">{{ item.name }}</span>
                    <span v-if="item.is_new_item && !item.item_served" class="item-new-pill">✨ สั่งเพิ่ม</span>
                  </div>
                  <div v-if="item.notes" class="item-notes-pill">
                    <span>⚠️ {{ item.notes }}</span>
                  </div>
                </div>
              </div>

              <!-- Action: Mark individual item served -->
              <div class="item-right-col">
                <button
                  v-if="!item.item_served"
                  @click="handleMarkItemServed(order, item, idx)"
                  class="btn-item-serve"
                  title="กดเมื่อทำจานนี้เสร็จแล้ว"
                >
                  ✓ เสิร์ฟจานนี้
                </button>
                <span v-else class="item-served-check" title="เสิร์ฟแล้ว">
                  ✓ เสิร์ฟแล้ว
                </span>
              </div>
            </div>
          </div>

          <!-- Ticket Footer: Summary & Mark Whole Order Served -->
          <div class="ticket-footer">
            <div class="ticket-footer-summary">
              <span>คงเหลือ {{ getUnservedCount(order) }} จาก {{ order.items ? order.items.length : 0 }} จาน</span>
            </div>

            <button
              v-if="order.status === 'preparing'"
              @click="handleMarkOrderServed(order)"
              class="btn-order-complete-serve"
              title="เสิร์ฟอาหารครบทุกจานแล้ว แจ้งเตือนแคชเชียร์ทันที"
            >
              <span>✅ เสิร์ฟครบแล้ว (แจ้งแคชเชียร์)</span>
            </button>
            <div v-else class="ticket-completed-badge">
              <span>🟢 เสิร์ฟครบเรียบร้อยแล้ว</span>
            </div>
          </div>

        </div>
      </div>
    </main>

  </div>
</template>

<style scoped>
/* ── RESTODASH / BAKEHOUSE CLEAN MODERN THEME ───────────────────────── */
.kds-standalone-app {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  z-index: 99999 !important;
  display: flex !important;
  flex-direction: column !important;
  background: #F8FAFC !important;
  color: #0F172A !important;
  font-family: 'Prompt', sans-serif !important;
  overflow: hidden !important;
  user-select: none !important;
}

/* ── KDS HEADER ───────────────────────────────────────────────────── */
.kds-header {
  height: 68px;
  background: #FFFFFF;
  border-bottom: 1.5px solid #E2E8F0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  gap: 16px;
  flex-shrink: 0;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
}

.kds-header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.kds-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.kds-brand-icon {
  font-size: 28px;
}
.kds-title {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: #0F172A;
  line-height: 1.2;
}
.kds-sub {
  font-size: 11px;
  color: #64748B;
  font-weight: 600;
}

.kds-live-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #ECFDF5;
  border: 1px solid #A7F3D0;
  color: #059669;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 20px;
}
.live-dot-pulse {
  width: 8px;
  height: 8px;
  background: #10B981;
  border-radius: 50%;
  animation: pulse-dot 1.5s infinite;
}
@keyframes pulse-dot {
  0% { transform: scale(0.9); opacity: 0.7; }
  50% { transform: scale(1.3); opacity: 1; }
  100% { transform: scale(0.9); opacity: 0.7; }
}

/* ── FILTER TABS ──────────────────────────────────────────────────── */
.kds-filter-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #F1F5F9;
  border: 1px solid #E2E8F0;
  padding: 4px 6px;
  border-radius: 12px;
}
.kds-tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border: none;
  background: transparent;
  color: #64748B;
  font-family: 'Prompt', sans-serif;
  font-size: 13.5px;
  font-weight: 700;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.kds-tab-btn:hover {
  color: #0F172A;
  background: rgba(255, 255, 255, 0.6);
}
.kds-tab-btn.is-active {
  background: #FFFFFF;
  color: #2563EB;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
  font-weight: 800;
}
.kds-tab-badge {
  font-size: 11px;
  font-weight: 800;
  padding: 2px 7px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
  color: #FFFFFF;
}
.badge-orange {
  background: #F97316;
}
.badge-purple {
  background: #8B5CF6;
  animation: bounce-badge 1s infinite alternate;
}
.badge-green {
  background: #10B981;
}
.badge-slate {
  background: #94A3B8;
}

@keyframes bounce-badge {
  from { transform: scale(1); }
  to { transform: scale(1.15); }
}

/* ── HEADER RIGHT ─────────────────────────────────────────────────── */
.kds-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.kds-action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #CBD5E1;
  background: #FFFFFF;
  color: #334155;
  font-family: 'Prompt', sans-serif;
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s ease;
}
.kds-action-btn:hover {
  background: #F8FAFC;
  border-color: #94A3B8;
}
.btn-audio-toggle {
  background: #ECFDF5;
  border-color: #A7F3D0;
  color: #059669;
}
.btn-audio-toggle.is-muted {
  background: #FEF2F2;
  border-color: #FECACA;
  color: #DC2626;
}
.btn-sound-test {
  background: #FFFBEB;
  border-color: #FDE68A;
  color: #B45309;
}
.kds-clock {
  font-family: 'JetBrains Mono', monospace;
  font-size: 15px;
  font-weight: 800;
  color: #0F172A;
  background: #F1F5F9;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #E2E8F0;
  letter-spacing: 0.5px;
}
.kds-btn-pos {
  display: flex;
  align-items: center;
  padding: 8px 14px;
  border-radius: 8px;
  background: #EFF6FF;
  border: 1px solid #BFDBFE;
  color: #1D4ED8;
  font-size: 12.5px;
  font-weight: 800;
  text-decoration: none;
  transition: all 0.15s;
}
.kds-btn-pos:hover {
  background: #2563EB;
  color: #FFFFFF;
  border-color: #2563EB;
}

/* ── KDS MAIN GRID ────────────────────────────────────────────────── */
.kds-main-grid {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  background: #F8FAFC;
}

.kds-cards-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 18px;
  align-items: start;
}

/* ── TICKET CARD ──────────────────────────────────────────────────── */
.kds-ticket-card {
  background: #FFFFFF;
  border: 1.5px solid #E2E8F0;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05);
  display: flex;
  flex-direction: column;
  transition: all 0.2s ease;
}
.kds-ticket-card:hover {
  border-color: #93C5FD;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.08);
  transform: translateY(-2px);
}

.kds-ticket-card.is-appended {
  border-color: #8B5CF6;
  box-shadow: 0 0 20px rgba(139, 92, 246, 0.15);
}

.kds-ticket-card.is-urgent {
  border-color: #EF4444;
  box-shadow: 0 0 20px rgba(239, 68, 68, 0.2);
  animation: pulse-urgent-card 2s infinite alternate;
}
@keyframes pulse-urgent-card {
  from { border-color: #EF4444; }
  to { border-color: #DC2626; box-shadow: 0 0 26px rgba(239, 68, 68, 0.35); }
}

.kds-ticket-card.is-served {
  border-color: #10B981;
  background: #F0FDF4;
  opacity: 0.9;
}

/* ── TICKET HEADER ────────────────────────────────────────────────── */
.ticket-header {
  background: #F8FAFC;
  border-bottom: 1.5px solid #E2E8F0;
  padding: 12px 16px;
}
.ticket-table-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.ticket-table-name {
  font-size: 19px;
  font-weight: 800;
  color: #0F172A;
  display: flex;
  align-items: center;
  gap: 8px;
}
.table-icon {
  font-size: 22px;
}

.ticket-timer-badge {
  font-family: 'Prompt', monospace;
  font-size: 12.5px;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 20px;
}
.timer-green {
  background: #ECFDF5;
  color: #059669;
  border: 1px solid #A7F3D0;
}
.timer-yellow {
  background: #FEF3C7;
  color: #B45309;
  border: 1px solid #FDE68A;
}
.timer-red-pulse {
  background: #FEE2E2;
  color: #DC2626;
  border: 1px solid #FCA5A5;
  animation: pulse-timer 1s infinite alternate;
}
@keyframes pulse-timer {
  from { transform: scale(1); }
  to { transform: scale(1.05); }
}

.ticket-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #64748B;
}
.ticket-id {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  color: #1E293B;
}
.ticket-channel-pill {
  padding: 2px 7px;
  border-radius: 6px;
  font-weight: 700;
  font-size: 11px;
}
.ticket-channel-pill.shop {
  background: #EFF6FF;
  border: 1px solid #DBEAFE;
  color: #1D4ED8;
}
.ticket-channel-pill.online {
  background: #F5F3FF;
  border: 1px solid #DDD6FE;
  color: #6D28D9;
}

.ticket-appended-banner {
  margin-top: 8px;
  background: linear-gradient(135deg, #7C3AED, #A855F7);
  color: #FFFFFF;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 6px;
  animation: pulse-banner 1.5s infinite alternate;
}
@keyframes pulse-banner {
  from { opacity: 0.9; }
  to { opacity: 1; }
}
.banner-pulse {
  color: #FDE047;
}

/* ── TICKET ITEMS LIST ────────────────────────────────────────────── */
.ticket-items-list {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 380px;
  overflow-y: auto;
  background: #FFFFFF;
}

.ticket-item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
  transition: all 0.15s ease;
}
.ticket-item-row.item-is-new {
  background: #FAF5FF;
  border-color: #E9D5FF;
}
.ticket-item-row.item-is-served {
  background: #F0FDF4;
  border-color: #DCFCE7;
  opacity: 0.65;
}

.item-left-col {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}
.item-qty-badge {
  font-family: 'Prompt', monospace;
  font-size: 15px;
  font-weight: 900;
  color: #1D4ED8;
  background: #EFF6FF;
  border: 1px solid #BFDBFE;
  padding: 3px 8px;
  border-radius: 6px;
  min-width: 32px;
  text-align: center;
}
.item-is-new .item-qty-badge {
  color: #6D28D9;
  background: #F5F3FF;
  border-color: #DDD6FE;
}

.item-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.item-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.item-name {
  font-size: 14.5px;
  font-weight: 700;
  color: #0F172A;
}
.item-is-served .item-name {
  text-decoration: line-through;
  color: #94A3B8;
}

.item-new-pill {
  background: #7C3AED;
  color: #FFFFFF;
  font-size: 10px;
  font-weight: 800;
  padding: 1px 6px;
  border-radius: 4px;
}

.item-notes-pill {
  font-size: 11.5px;
  font-weight: 600;
  color: #B45309;
  background: #FFFBEB;
  border: 1px solid #FDE68A;
  padding: 2px 6px;
  border-radius: 4px;
  display: inline-block;
  max-width: fit-content;
}

.item-right-col {
  flex-shrink: 0;
}
.btn-item-serve {
  padding: 6px 12px;
  background: #ECFDF5;
  border: 1px solid #A7F3D0;
  color: #059669;
  border-radius: 8px;
  font-family: 'Prompt', sans-serif;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-item-serve:hover {
  background: #10B981;
  color: #FFFFFF;
  border-color: #10B981;
  box-shadow: 0 2px 6px rgba(16, 185, 129, 0.3);
}
.item-served-check {
  font-size: 12px;
  font-weight: 800;
  color: #059669;
}

/* ── TICKET FOOTER ────────────────────────────────────────────────── */
.ticket-footer {
  padding: 12px 14px;
  background: #F8FAFC;
  border-top: 1.5px solid #E2E8F0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ticket-footer-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 700;
  color: #64748B;
}

.btn-order-complete-serve {
  width: 100%;
  padding: 11px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, #10B981, #059669);
  color: #FFFFFF;
  font-family: 'Prompt', sans-serif;
  font-size: 13.5px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25);
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.btn-order-complete-serve:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(16, 185, 129, 0.35);
}

.ticket-completed-badge {
  text-align: center;
  padding: 8px;
  background: #ECFDF5;
  border: 1px solid #A7F3D0;
  color: #059669;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 800;
}

/* ── EMPTY STATE ──────────────────────────────────────────────────── */
.kds-empty-state {
  height: 60vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #64748B;
}
.empty-icon-wrap {
  width: 90px;
  height: 90px;
  border-radius: 50%;
  background: #FFFFFF;
  border: 2px solid #E2E8F0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.04);
}
.empty-icon {
  font-size: 42px;
}
.empty-title {
  font-size: 20px;
  font-weight: 800;
  color: #0F172A;
  margin: 0 0 8px;
}
.empty-desc {
  font-size: 13.5px;
  max-width: 400px;
  line-height: 1.5;
  margin: 0 0 20px;
}
.btn-empty-refresh {
  padding: 8px 18px;
  background: #FFFFFF;
  border: 1.5px solid #CBD5E1;
  border-radius: 8px;
  color: #1D4ED8;
  font-family: 'Prompt', sans-serif;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(0,0,0,0.04);
}
.btn-empty-refresh:hover {
  background: #EFF6FF;
  border-color: #93C5FD;
}

/* ── RESPONSIVE STYLES ────────────────────────────────────────────── */
@media (max-width: 900px) {
  .kds-header {
    height: auto;
    padding: 10px 14px;
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }
  .kds-header-left {
    justify-content: space-between;
  }
  .kds-filter-tabs {
    overflow-x: auto;
    width: 100%;
    justify-content: flex-start;
  }
  .kds-header-right {
    justify-content: space-between;
    overflow-x: auto;
  }
  .kds-cards-container {
    grid-template-columns: 1fr !important;
  }
}

/* Custom Scrollbar */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: #F1F5F9;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #CBD5E1;
  border-radius: 3px;
}
</style>
