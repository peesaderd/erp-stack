import re

vue_file = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\PosRestodash.vue'
with open(vue_file, 'r', encoding='utf-8') as f:
    content = f.read()

# -------------------------------------------------------------
# 1. Add Mobile Cart Overlay Backdrop & Close Button in Cart Header
# -------------------------------------------------------------
old_cart_aside = '<aside class="pos-cart-right">'
new_cart_aside = """<!-- Mobile Cart Overlay Backdrop -->
      <div
        v-if="isMobileCartOpen"
        @click="isMobileCartOpen = false"
        class="mobile-cart-backdrop"
      ></div>

      <aside class="pos-cart-right" :class="{ 'is-mobile-open': isMobileCartOpen }">"""

if old_cart_aside in content:
    content = content.replace(old_cart_aside, new_cart_aside, 1)
    print("1. Added mobile cart aside & backdrop")
else:
    print("1. old_cart_aside NOT found!")

# Add close button inside cart header for mobile
old_cart_title = '<span class="cart-title-text">🧾 รายการสั่งอาหาร</span>'
new_cart_title = """<span class="cart-title-text">🧾 รายการสั่งอาหาร</span>
              <button @click="isMobileCartOpen = false" class="mobile-cart-close-btn" title="ปิดตะกร้า (Mobile)">✕ ปิด</button>"""

if old_cart_title in content:
    content = content.replace(old_cart_title, new_cart_title, 1)
    print("2. Added mobile cart close button in header")
else:
    print("2. old_cart_title NOT found!")

# Add mobile floating cart trigger button at bottom of main
old_main_close = '</main>'
new_main_close = """  <!-- Floating Cart Trigger Button for Mobile -->
        <button
          v-if="viewMode === 'pos' && cart.length > 0"
          @click="isMobileCartOpen = true"
          class="mobile-floating-cart-btn"
        >
          <span class="m-cart-icon">🛒</span>
          <span class="m-cart-text">ดูตะกร้า ({{ cartTotalQty }})</span>
          <span class="m-cart-total">฿{{ formatBaht(cartGrandTotal) }}</span>
        </button>
      </main>"""

if old_main_close in content:
    content = content.replace(old_main_close, new_main_close, 1)
    print("3. Added mobile floating cart trigger button")
else:
    print("3. old_main_close NOT found!")

# -------------------------------------------------------------
# 2. Update Orders Modal Filter Bar: Add Order Type (Shop / Online) + Enhanced Date Picker
# -------------------------------------------------------------
old_orders_filter_bar = """        <!-- Filter Bar: Search, Status Tabs, Date Filter -->
        <div class="orders-filter-bar">
          <div class="orders-search-wrap">
            <span class="search-icon">🔍</span>
            <input
              v-model="orderSearchQuery"
              placeholder="ค้นหา (เลขบิล เช่น 0208, ชื่อโต๊ะ, ลูกค้า)..."
              class="orders-search-input"
            />
            <button v-if="orderSearchQuery" @click="orderSearchQuery = ''" class="search-clear-btn">✕</button>
          </div>

          <div class="orders-tabs-toggle">
            <button
              @click="orderStatusFilter = 'unpaid'"
              class="order-tab-btn"
              :class="{ 'is-active': orderStatusFilter === 'unpaid' }"
            >
              ⏳ ค้างชำระ ({{ unpaidOrdersCount }})
            </button>
            <button
              @click="orderStatusFilter = 'all'"
              class="order-tab-btn"
              :class="{ 'is-active': orderStatusFilter === 'all' }"
            >
              📋 ทั้งหมด ({{ allOrders.length }})
            </button>
          </div>

          <div class="orders-date-wrap">
            <span class="date-label">วันที่:</span>
            <input v-model="orderDateFilter" type="date" class="orders-date-input" />
            <button v-if="orderDateFilter" @click="orderDateFilter = ''" class="btn-clear-date" title="ดูทุกวัน">✕ ทุกวัน</button>
          </div>
        </div>"""

new_orders_filter_bar = """        <!-- Filter Bar: Search, Status Tabs, Channel Tabs (Shop/Online), Date Filter -->
        <div class="orders-filter-bar">
          <!-- Search Box -->
          <div class="orders-search-wrap">
            <span class="search-icon">🔍</span>
            <input
              v-model="orderSearchQuery"
              placeholder="ค้นหา (เลขบิล เช่น 0208, ชื่อโต๊ะ, ลูกค้า)..."
              class="orders-search-input"
            />
            <button v-if="orderSearchQuery" @click="orderSearchQuery = ''" class="search-clear-btn">✕</button>
          </div>

          <!-- Status Filter Tabs -->
          <div class="orders-tabs-toggle">
            <button
              @click="orderStatusFilter = 'unpaid'"
              class="order-tab-btn"
              :class="{ 'is-active': orderStatusFilter === 'unpaid' }"
            >
              ⏳ ค้างชำระ ({{ unpaidOrdersCount }})
            </button>
            <button
              @click="orderStatusFilter = 'all'"
              class="order-tab-btn"
              :class="{ 'is-active': orderStatusFilter === 'all' }"
            >
              📋 ทั้งหมด ({{ allOrders.length }})
            </button>
          </div>

          <!-- Channel Filter: Shop vs Online (Requirement) -->
          <div class="orders-channel-toggle">
            <button
              @click="orderChannelFilter = 'all'"
              class="channel-filter-btn"
              :class="{ 'is-active': orderChannelFilter === 'all' }"
            >
              ทุกช่องทาง
            </button>
            <button
              @click="orderChannelFilter = 'shop'"
              class="channel-filter-btn"
              :class="{ 'is-active': orderChannelFilter === 'shop' }"
            >
              🏪 หน้าร้าน (Shop)
            </button>
            <button
              @click="orderChannelFilter = 'online'"
              class="channel-filter-btn"
              :class="{ 'is-active': orderChannelFilter === 'online' }"
            >
              📱 ออนไลน์ (Online)
            </button>
          </div>

          <!-- Enhanced Interactive Date Filter with Quick 'วันนี้' Button -->
          <div class="orders-date-wrap">
            <span class="date-label">📅 วันที่:</span>
            <div class="date-input-container">
              <input
                ref="orderDatePicker"
                v-model="orderDateFilter"
                type="date"
                class="orders-date-input"
                @click="openDatePicker"
              />
            </div>
            <button
              @click="setTodayDate"
              class="btn-date-quick"
              :class="{ 'is-active': isDateToday }"
              title="เลือกดูออเดอร์ของวันนี้"
            >
              วันนี้
            </button>
            <button
              v-if="orderDateFilter"
              @click="orderDateFilter = ''"
              class="btn-clear-date"
              title="ดูทุกวัน"
            >
              ✕ ทุกวัน
            </button>
          </div>
        </div>"""

if old_orders_filter_bar in content:
    content = content.replace(old_orders_filter_bar, new_orders_filter_bar, 1)
    print("4. Replaced orders filter bar with channel toggle & enhanced date picker")
else:
    print("4. old_orders_filter_bar NOT found!")

# -------------------------------------------------------------
# 3. Update Table Column: Display Channel Badge (Shop vs Online)
# -------------------------------------------------------------
old_table_pill = """                <td>
                  <span class="table-pill">
                    {{ ord.table_name || (ord.table_id === 'takeaway' ? '📦 กลับบ้าน' : `โต๊ะ ${ord.table_id}`) }}
                  </span>
                </td>"""

new_table_pill = """                <td>
                  <div class="order-channel-table-cell">
                    <span
                      class="channel-badge-pill"
                      :class="getOrderChannel(ord)"
                    >
                      {{ getOrderChannel(ord) === 'online' ? '📱 ออนไลน์' : '🏪 หน้าร้าน' }}
                    </span>
                    <span class="table-pill">
                      {{ ord.table_name || (ord.table_id === 'takeaway' ? '📦 กลับบ้าน' : `โต๊ะ ${ord.table_id}`) }}
                    </span>
                  </div>
                </td>"""

if old_table_pill in content:
    content = content.replace(old_table_pill, new_table_pill, 1)
    print("5. Replaced table pill with Channel badge + Table pill")
else:
    print("5. old_table_pill NOT found!")

# -------------------------------------------------------------
# 4. In Member Linking Modal: Add Quick Add Member Form
# -------------------------------------------------------------
old_member_search = """        <div class="attach-member-body">
          <div class="member-search-bar">"""

new_member_search = """        <div class="attach-member-body">
          <!-- Quick Add Member Form (Requirement: Name and Phone) -->
          <div v-if="showQuickAddMember" class="quick-add-member-form">
            <div class="quick-add-header">
              <span class="quick-add-title">➕ สมัครสมาชิกใหม่ทันที</span>
              <button @click="showQuickAddMember = false" class="btn-close-quick-add">✕</button>
            </div>
            <div class="quick-add-inputs-grid">
              <div class="quick-field">
                <label>ชื่อสมาชิก *</label>
                <input
                  v-model="newMemberName"
                  placeholder="เช่น คุณสมชาย ใจดี"
                  class="quick-input"
                  autofocus
                />
              </div>
              <div class="quick-field">
                <label>เบอร์โทรศัพท์ *</label>
                <input
                  v-model="newMemberPhone"
                  type="tel"
                  placeholder="เช่น 0812345678"
                  class="quick-input"
                />
              </div>
            </div>
            <div class="quick-add-btn-row">
              <button @click="showQuickAddMember = false" class="btn-cancel-quick">ยกเลิก</button>
              <button
                @click="submitQuickAddMember"
                :disabled="!newMemberName.trim() || !newMemberPhone.trim() || isSubmittingMember"
                class="btn-save-quick-member"
              >
                {{ isSubmittingMember ? 'กำลังบันทึก...' : '✓ บันทึก & ผูกสมาชิกทันที' }}
              </button>
            </div>
          </div>

          <div v-else class="quick-add-trigger-row">
            <button @click="showQuickAddMember = true" class="btn-trigger-add-member">
              ➕ สมัครสมาชิกใหม่ด่วน (ใส่แค่ชื่อกับเบอร์โทร)
            </button>
          </div>

          <div class="member-search-bar">"""

if old_member_search in content:
    content = content.replace(old_member_search, new_member_search, 1)
    print("6. Added Quick Add Member form to Member Linking Modal")
else:
    print("6. old_member_search NOT found!")

# -------------------------------------------------------------
# 5. Add Script Logic for Mobile Cart, Order Channels, Quick Add Member, and Date Picker
# -------------------------------------------------------------
target_state_anchor = "const memberSearchQuery = ref('')"
new_state_vars = """const memberSearchQuery = ref('')
const showQuickAddMember = ref(false)
const newMemberName = ref('')
const newMemberPhone = ref('')
const isSubmittingMember = ref(false)
const orderChannelFilter = ref('all')
const isMobileCartOpen = ref(false)
const orderDatePicker = ref(null)"""

if target_state_anchor in content:
    content = content.replace(target_state_anchor, new_state_vars, 1)
    print("7. Added state variables for channel filter, quick member add, mobile cart")
else:
    print("7. target_state_anchor NOT found!")

# Helper functions to add
script_helpers = """
// Order Channel Detection (Shop vs Online)
function getOrderChannel(ord) {
  if (!ord) return 'shop'
  if (
    ord.channel === 'online' ||
    ord.order_channel === 'online' ||
    ord.source === 'online' ||
    ord.source === 'public' ||
    ord.source === 'qr' ||
    ord.line_user_id ||
    (ord.table_id && String(ord.table_id).toLowerCase().includes('qr')) ||
    (ord.table_name && String(ord.table_name).toLowerCase().includes('qr')) ||
    (ord.order_type === 'online')
  ) {
    return 'online'
  }
  return 'shop'
}

// Date Picker Helpers
function openDatePicker(e) {
  try {
    if (e && e.target && typeof e.target.showPicker === 'function') {
      e.target.showPicker()
    }
  } catch (err) {
    console.debug('openDatePicker showPicker error:', err)
  }
}

function setTodayDate() {
  const today = new Date().toISOString().slice(0, 10)
  orderDateFilter.value = today
}

const isDateToday = computed(() => {
  if (!orderDateFilter.value) return false
  const today = new Date().toISOString().slice(0, 10)
  return orderDateFilter.value === today
})

// Quick Add Member & Auto-Select
async function submitQuickAddMember() {
  if (!newMemberName.value.trim() || !newMemberPhone.value.trim()) return
  isSubmittingMember.value = true
  try {
    const name = newMemberName.value.trim()
    const phone = newMemberPhone.value.trim()

    let created = null
    try {
      created = await updateMember({ name, phone, points: 50, tier: 'Regular' })
    } catch (err) {
      console.warn('API updateMember failed, using local member:', err)
    }

    const newMemberObj = {
      id: (created && created.id) ? created.id : `MEM-${Date.now()}`,
      name: name,
      phone: phone,
      points: (created && created.points) ? created.points : 50,
      tier: (created && created.tier) ? created.tier : 'Regular'
    }

    membersList.value.unshift(newMemberObj)
    selectMemberForOrder(newMemberObj)
    showToast(`สมัครสมาชิกใหม่ "${name}" และผูกเข้ากับออเดอร์แล้ว ⭐`)

    newMemberName.value = ''
    newMemberPhone.value = ''
    showQuickAddMember.value = false
  } catch (err) {
    showToast(`เกิดข้อผิดพลาด: ${err.message}`)
  } finally {
    isSubmittingMember.value = false
  }
}
"""

func_insert_spot = "function openAttachMemberModal(order) {"
if func_insert_spot in content:
    content = content.replace(func_insert_spot, script_helpers + "\n" + func_insert_spot, 1)
    print("8. Added script helper functions")
else:
    print("8. func_insert_spot NOT found!")

# Update sortedFilteredOrders to include orderChannelFilter
old_sorted_filter = """  // Filter by status tab
  if (orderStatusFilter.value === 'unpaid') {
    list = list.filter(o => o.status !== 'paid' && o.status !== 'cancelled')
  }"""

new_sorted_filter = """  // Filter by status tab
  if (orderStatusFilter.value === 'unpaid') {
    list = list.filter(o => o.status !== 'paid' && o.status !== 'cancelled')
  }

  // Filter by channel: shop vs online
  if (orderChannelFilter.value !== 'all') {
    list = list.filter(o => getOrderChannel(o) === orderChannelFilter.value)
  }"""

if old_sorted_filter in content:
    content = content.replace(old_sorted_filter, new_sorted_filter, 1)
    print("9. Updated sortedFilteredOrders with orderChannelFilter")
else:
    print("9. old_sorted_filter NOT found!")

# -------------------------------------------------------------
# 6. Add Responsive & Channel Styling inside <style>
# -------------------------------------------------------------
responsive_and_channel_css = """
/* ── ORDER CHANNEL (SHOP / ONLINE) BADGES & TOGGLES ─────────────────── */
.orders-channel-toggle {
  display: flex !important;
  background: #E2E8F0 !important;
  padding: 3px !important;
  border-radius: 8px !important;
  gap: 3px !important;
}

.channel-filter-btn {
  padding: 5px 12px !important;
  border-radius: 6px !important;
  border: none !important;
  background: transparent !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  font-family: 'Prompt', sans-serif !important;
  color: #64748B !important;
  cursor: pointer !important;
  transition: all 0.15s !important;
  white-space: nowrap !important;
}

.channel-filter-btn.is-active {
  background: #ffffff !important;
  color: #0F172A !important;
  box-shadow: 0 2px 4px rgba(0,0,0,0.08) !important;
}

.order-channel-table-cell {
  display: flex !important;
  flex-direction: column !important;
  gap: 4px !important;
}

.channel-badge-pill {
  display: inline-block !important;
  padding: 2px 8px !important;
  border-radius: 6px !important;
  font-size: 10.5px !important;
  font-weight: 800 !important;
  width: fit-content !important;
}

.channel-badge-pill.shop {
  background: #EFF6FF !important;
  color: #1D4ED8 !important;
  border: 1px solid #BFDBFE !important;
}

.channel-badge-pill.online {
  background: #FAF5FF !important;
  color: #7E22CE !important;
  border: 1px solid #E9D5FF !important;
}

/* ── QUICK ADD MEMBER SECTION IN MODAL ──────────────────────────────── */
.quick-add-trigger-row {
  margin-bottom: 12px !important;
}

.btn-trigger-add-member {
  width: 100% !important;
  background: linear-gradient(135deg, #EFF6FF, #DBEAFE) !important;
  border: 1.5px dashed #3B82F6 !important;
  color: #1D4ED8 !important;
  padding: 10px 14px !important;
  border-radius: 10px !important;
  font-size: 13px !important;
  font-weight: 800 !important;
  font-family: 'Prompt', sans-serif !important;
  cursor: pointer !important;
  transition: all 0.15s !important;
}
.btn-trigger-add-member:hover {
  background: #BFDBFE !important;
  border-style: solid !important;
}

.quick-add-member-form {
  background: #F8FAFC !important;
  border: 1.5px solid #93C5FD !important;
  border-radius: 12px !important;
  padding: 14px 16px !important;
  margin-bottom: 14px !important;
}

.quick-add-header {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  margin-bottom: 10px !important;
}

.quick-add-title {
  font-size: 13.5px !important;
  font-weight: 800 !important;
  color: #1E40AF !important;
}

.btn-close-quick-add {
  background: transparent !important;
  border: none !important;
  font-size: 14px !important;
  color: #64748B !important;
  cursor: pointer !important;
}

.quick-add-inputs-grid {
  display: grid !important;
  grid-template-columns: 1fr 1fr !important;
  gap: 10px !important;
  margin-bottom: 12px !important;
}

.quick-field {
  display: flex !important;
  flex-direction: column !important;
  gap: 4px !important;
}

.quick-field label {
  font-size: 11px !important;
  font-weight: 700 !important;
  color: #475569 !important;
}

.quick-input {
  border: 1.5px solid #CBD5E1 !important;
  border-radius: 8px !important;
  padding: 8px 10px !important;
  font-size: 13px !important;
  font-family: 'Prompt', sans-serif !important;
  background: #ffffff !important;
  outline: none !important;
}
.quick-input:focus {
  border-color: #2563EB !important;
}

.quick-add-btn-row {
  display: flex !important;
  justify-content: flex-end !important;
  gap: 8px !important;
}

.btn-cancel-quick {
  background: #FFFFFF !important;
  border: 1px solid #CBD5E1 !important;
  color: #64748B !important;
  border-radius: 6px !important;
  padding: 6px 12px !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  cursor: pointer !important;
}

.btn-save-quick-member {
  background: #2563EB !important;
  border: none !important;
  color: #ffffff !important;
  border-radius: 6px !important;
  padding: 6px 14px !important;
  font-size: 12px !important;
  font-weight: 800 !important;
  cursor: pointer !important;
}
.btn-save-quick-member:disabled {
  opacity: 0.5 !important;
  cursor: not-allowed !important;
}

/* ── DATE PICKER CLICKABLE STYLES ───────────────────────────────────── */
.orders-date-wrap {
  display: flex !important;
  align-items: center !important;
  gap: 6px !important;
  flex-wrap: nowrap !important;
}

.date-label {
  font-size: 12px !important;
  font-weight: 700 !important;
  color: #475569 !important;
  white-space: nowrap !important;
}

.date-input-container {
  position: relative !important;
  display: flex !important;
  align-items: center !important;
}

.orders-date-input {
  border: 1.5px solid #CBD5E1 !important;
  border-radius: 8px !important;
  padding: 6px 10px !important;
  font-size: 13px !important;
  font-family: 'Prompt', sans-serif !important;
  background: #ffffff !important;
  cursor: pointer !important;
  color: #0F172A !important;
  min-height: 34px !important;
  outline: none !important;
}
.orders-date-input:focus {
  border-color: #2563EB !important;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15) !important;
}

.btn-date-quick {
  background: #EFF6FF !important;
  border: 1px solid #BFDBFE !important;
  color: #1D4ED8 !important;
  border-radius: 6px !important;
  padding: 6px 10px !important;
  font-size: 12px !important;
  font-weight: 800 !important;
  cursor: pointer !important;
  white-space: nowrap !important;
  transition: all 0.15s !important;
}
.btn-date-quick:hover {
  background: #DBEAFE !important;
}
.btn-date-quick.is-active {
  background: #2563EB !important;
  color: #ffffff !important;
  border-color: #2563EB !important;
}

/* ── MOBILE RESPONSIVE STYLES (max-width: 768px) ────────────────────── */
@media (max-width: 768px) {
  /* Center Main on Mobile */
  .pos-center-main {
    width: 100vw !important;
    height: 100vh !important;
  }

  .center-topbar {
    flex-wrap: wrap !important;
    padding: 8px 12px !important;
    gap: 8px !important;
  }
  .search-box-wrapper {
    width: 100% !important;
    max-width: 100% !important;
    order: 2 !important;
  }
  .topbar-actions {
    width: 100% !important;
    justify-content: space-between !important;
    order: 1 !important;
  }

  /* Food Grid: 2 columns on mobile */
  .menu-grid {
    grid-template-columns: repeat(2, 1fr) !important;
    gap: 8px !important;
    padding: 8px !important;
  }

  /* Right Cart as Mobile Slide-over Drawer */
  .pos-cart-right {
    display: none !important;
  }
  .pos-cart-right.is-mobile-open {
    display: flex !important;
    position: fixed !important;
    top: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    width: 90vw !important;
    max-width: 380px !important;
    z-index: 100020 !important;
    box-shadow: -8px 0 30px rgba(0,0,0,0.3) !important;
    background: #ffffff !important;
    animation: slide-in-right 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
  }

  .mobile-cart-backdrop {
    position: fixed !important;
    inset: 0 !important;
    background: rgba(15, 23, 42, 0.6) !important;
    backdrop-filter: blur(2px) !important;
    z-index: 100015 !important;
  }

  .mobile-cart-close-btn {
    display: inline-block !important;
    border: none !important;
    background: #F1F5F9 !important;
    color: #475569 !important;
    padding: 4px 8px !important;
    border-radius: 6px !important;
    font-size: 12px !important;
    font-weight: 800 !important;
    cursor: pointer !important;
    margin-left: 6px !important;
  }

  /* Floating Cart Button on Mobile */
  .mobile-floating-cart-btn {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    position: fixed !important;
    bottom: 16px !important;
    right: 16px !important;
    left: 16px !important;
    background: #2563EB !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 14px !important;
    padding: 12px 18px !important;
    font-size: 15px !important;
    font-weight: 800 !important;
    font-family: 'Prompt', sans-serif !important;
    box-shadow: 0 8px 24px rgba(37, 99, 235, 0.45) !important;
    z-index: 9999 !important;
    cursor: pointer !important;
  }
  .m-cart-total {
    background: rgba(255, 255, 255, 0.2) !important;
    padding: 2px 10px !important;
    border-radius: 20px !important;
    font-size: 14px !important;
  }

  /* Left Sidebar Overlay on Mobile */
  .pos-sidebar-left {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    bottom: 0 !important;
    width: 270px !important;
    z-index: 100010 !important;
    box-shadow: 8px 0 30px rgba(0,0,0,0.3) !important;
  }

  /* Modals on Mobile */
  .pos-modal-box,
  .orders-modal-box,
  .payment-modal,
  .attach-member-modal {
    width: 95vw !important;
    max-width: 95vw !important;
    max-height: 92vh !important;
    margin: 8px !important;
  }

  .orders-filter-bar {
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 8px !important;
    padding: 10px 14px !important;
  }

  .orders-search-wrap,
  .orders-tabs-toggle,
  .orders-channel-toggle,
  .orders-date-wrap {
    width: 100% !important;
  }

  .orders-tabs-toggle,
  .orders-channel-toggle {
    display: grid !important;
    grid-template-columns: 1fr 1fr !important;
  }
  .orders-channel-toggle {
    grid-template-columns: 1fr 1fr 1fr !important;
  }

  .orders-history-table {
    min-width: 680px !important;
  }

  .quick-add-inputs-grid {
    grid-template-columns: 1fr !important;
  }
}

@keyframes slide-in-right {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}
"""

idx = content.rfind('</style>')
if idx != -1:
    content = content[:idx] + "\n" + responsive_and_channel_css + "\n</style>\n"
    print("10. Added responsive & channel styles inside <style>")
else:
    print("10. </style> not found!")

with open(vue_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated PosRestodash.vue with Channel Filter, Quick Add Member, Date Picker & Mobile Responsiveness successfully!")
