import re

with open('scratch/PosRestodash.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. ADD HELPER METHODS TO SCRIPT
old_select_table = '''function selectTakeaway() {
  orderType.value = 'takeaway'
  selectedTableId.value = null
  showTableModal.value = false
  showToast('เลือก: 📦 สั่งกลับบ้าน (Takeaway) เรียบร้อย')
}

function selectTable(tableId) {
  selectedTableId.value = tableId
  orderType.value = 'dinein'
  showTableModal.value = false
  showToast(`เลือก: โต๊ะ ${tableId} เรียบร้อย`)
}'''

new_select_table = '''// Helper: get active unpaid order for a table
function getTableActiveOrder(tableId) {
  if (!tableId) return null
  return unpaidOrders.value.find(o => String(o.table_id) === String(tableId)) || null
}

function selectTakeaway() {
  orderType.value = 'takeaway'
  selectedTableId.value = null
  showTableModal.value = false

  const existingOrder = getTableActiveOrder('takeaway')
  if (existingOrder) {
    loadOrderIntoCart(existingOrder)
    showToast(`ดึงบิลสั่งกลับบ้าน (#${existingOrder.order_id.slice(-6)}) ยอด ฿${formatBaht(existingOrder.total || existingOrder.grand_total)} เรียบร้อย 💳`)
    if (typeof window !== 'undefined' && window.innerWidth <= 768) {
      isMobileCartOpen.value = true
    }
  } else {
    showToast('เลือก: 📦 สั่งกลับบ้าน (Takeaway) เรียบร้อย')
  }
}

function selectTable(tableId) {
  selectedTableId.value = tableId
  orderType.value = 'dinein'
  showTableModal.value = false

  const existingOrder = getTableActiveOrder(tableId)
  if (existingOrder) {
    loadOrderIntoCart(existingOrder)
    showToast(`ดึงบิลโต๊ะ ${tableId} (#${existingOrder.order_id.slice(-6)}) ยอด ฿${formatBaht(existingOrder.total || existingOrder.grand_total)} เรียบร้อย 💳`)
    if (typeof window !== 'undefined' && window.innerWidth <= 768) {
      isMobileCartOpen.value = true
    }
  } else {
    showToast(`เลือก: โต๊ะ ${tableId} เรียบร้อย ✨`)
  }
}

// Quick checkout directly for a table (Opens payment modal directly)
function checkoutTableDirect(tableId) {
  const existingOrder = getTableActiveOrder(tableId)
  if (existingOrder) {
    loadOrderIntoCart(existingOrder)
    showTableModal.value = false
    openPaymentModal('Cash')
  } else {
    selectTable(tableId)
  }
}

// Quick direct payment from unpaid orders list (Opens payment modal directly)
function payOrderDirect(ord) {
  loadOrderIntoCart(ord)
  showOrdersModal.value = false
  openPaymentModal('Cash')
}'''

assert old_select_table in content, "old_select_table not found!"
content = content.replace(old_select_table, new_select_table, 1)

# 2. UPDATE CENTER TOPBAR ACTIONS
old_topbar_actions = '''          <div class="topbar-actions">
            <!-- Table Switcher Quick Pill -->
            <button
              @click="showTableModal = true"
              class="quick-pill-btn"
              :class="{ 'is-empty': !selectedTableId && orderType !== 'takeaway' }"
            >
              <span>{{ orderType === 'takeaway' ? '📦 สั่งกลับบ้าน' : (selectedTableId ? `🪑 โต๊ะ ${selectedTableId}` : '⚠️ เลือกโต๊ะ') }}</span>
              <span class="pill-arrow">▾</span>
            </button>

            <!-- Quick Kitchen KDS View -->
            <button @click="showKitchenModal = true" class="quick-kds-btn">
              <span>🍳 จอครัว (KDS)</span>
              <span v-if="kitchenOrders.length" class="kds-badge">{{ kitchenOrders.length }}</span>
            </button>

            <!-- Quick Full Page Settings Button -->
            <button @click="viewMode = 'settings'" class="quick-settings-btn" title="ไปที่หน้าการตั้งค่าระบบ">
              ⚙️ ตั้งค่าระบบ
            </button>
          </div>'''

new_topbar_actions = '''          <div class="topbar-actions">
            <!-- Table Switcher Quick Pill -->
            <button
              @click="showTableModal = true"
              class="quick-pill-btn"
              :class="{ 'is-empty': !selectedTableId && orderType !== 'takeaway' }"
            >
              <span>{{ orderType === 'takeaway' ? '📦 สั่งกลับบ้าน' : (selectedTableId ? `🪑 โต๊ะ ${selectedTableId}` : '⚠️ เลือกโต๊ะ') }}</span>
              <span class="pill-arrow">▾</span>
            </button>

            <!-- Quick Unpaid Orders Pill (Brought directly to Topbar) -->
            <button
              @click="showOrdersModal = true"
              class="quick-unpaid-btn"
              title="บิลค้างชำระ & ประวัติการขาย"
            >
              <span>📋 บิลค้าง</span>
              <span v-if="unpaidOrdersCount > 0" class="unpaid-badge-pill">{{ unpaidOrdersCount }}</span>
            </button>

            <!-- Quick Kitchen KDS View -->
            <button @click="showKitchenModal = true" class="quick-kds-btn">
              <span>🍳 จอครัว</span>
              <span v-if="kitchenOrders.length" class="kds-badge">{{ kitchenOrders.length }}</span>
            </button>

            <!-- Quick Direct Checkout Button when active order exists or cart has items -->
            <button
              v-if="cart.length > 0 || activeCheckoutOrder"
              @click="openPaymentModal('Cash')"
              class="quick-checkout-header-btn"
              title="คิดเงินทันที"
            >
              💳 คิดเงิน
            </button>

            <!-- Quick Full Page Settings Button -->
            <button @click="viewMode = 'settings'" class="quick-settings-btn" title="ไปที่หน้าการตั้งค่าระบบ">
              ⚙️ ตั้งค่าระบบ
            </button>
          </div>'''

assert old_topbar_actions in content, "old_topbar_actions not found!"
content = content.replace(old_topbar_actions, new_topbar_actions, 1)

# 3. UPDATE TABLE CARD IN TABLE MODAL WITH QUICK CHECKOUT
old_table_card_status = '''            <div class="table-status-label">
              <span v-if="tb.status === 'served'" class="status-dot served-green-pulse"></span>
              <span v-else-if="tb.status === 'occupied'" class="status-dot red"></span>
              <span v-else class="status-dot green"></span>
              <span :class="{ 'text-served-bold': tb.status === 'served' }">
                {{ tb.status === 'served' ? '🟢 เสิร์ฟครบแล้ว (พร้อมคิดเงิน)' : (tb.status === 'occupied' ? 'กำลังทาน / รอเสิร์ฟ' : 'ว่าง') }}
              </span>
            </div>
          </div>'''

new_table_card_status = '''            <div class="table-status-label">
              <span v-if="tb.status === 'served'" class="status-dot served-green-pulse"></span>
              <span v-else-if="tb.status === 'occupied'" class="status-dot red"></span>
              <span v-else class="status-dot green"></span>
              <span :class="{ 'text-served-bold': tb.status === 'served' }">
                {{ tb.status === 'served' ? '🟢 เสิร์ฟครบแล้ว' : (tb.status === 'occupied' ? 'กำลังทาน' : 'ว่าง') }}
              </span>
            </div>

            <!-- Direct Table Checkout Action if Unpaid Order Exists -->
            <div v-if="getTableActiveOrder(tb.id)" class="table-card-unpaid-box">
              <div class="table-unpaid-sum">
                ฿{{ formatBaht(getTableActiveOrder(tb.id).total || getTableActiveOrder(tb.id).grand_total) }}
              </div>
              <button
                @click.stop="checkoutTableDirect(tb.id)"
                class="btn-table-checkout-direct"
                title="คิดเงินโต๊ะนี้ทันที"
              >
                💳 คิดเงิน
              </button>
            </div>
          </div>'''

assert old_table_card_status in content, "old_table_card_status not found!"
content = content.replace(old_table_card_status, new_table_card_status, 1)

# 4. UPDATE ORDERS MODAL ACTIONS WITH PAY DIRECT
old_order_actions = '''                  <!-- Load Unpaid Order into Cart for Checkout or Modification -->
                  <button
                    v-if="ord.status !== 'paid' && ord.status !== 'cancelled'"
                    @click="loadOrderIntoCart(ord)"
                    class="btn-sm-checkout"
                    title="ดึงออเดอร์นี้เข้าตะกร้าเพื่อคิดเงินหรือแก้ไข"
                  >
                    💳 ชำระ / ดึงเข้าตะกร้า
                  </button>'''

new_order_actions = '''                  <!-- Direct Checkout and Edit Order Buttons -->
                  <button
                    v-if="ord.status !== 'paid' && ord.status !== 'cancelled'"
                    @click="payOrderDirect(ord)"
                    class="btn-sm-checkout"
                    title="เปิดหน้าต่างคิดเงินทันที"
                  >
                    💳 คิดเงินทันที
                  </button>
                  <button
                    v-if="ord.status !== 'paid' && ord.status !== 'cancelled'"
                    @click="loadOrderIntoCart(ord)"
                    class="btn-sm-edit-order"
                    title="ดึงเข้าตะกร้าเพื่อสั่งอาหารเพิ่ม"
                  >
                    ➕ สั่งเพิ่ม
                  </button>'''

assert old_order_actions in content, "old_order_actions not found!"
content = content.replace(old_order_actions, new_order_actions, 1)

# 5. ADD MOBILE BOTTOM NAVIGATION BAR
# Place before closing </div> of .pos-restodash
bottom_nav_html = '''
    <!-- ── MOBILE BOTTOM NAVIGATION BAR (PWA UX) ───────────────────── -->
    <nav class="pos-mobile-bottom-nav">
      <button
        class="m-nav-tab"
        :class="{ 'is-active': viewMode === 'pos' && !showTableModal && !showOrdersModal && !showKitchenModal }"
        @click="viewMode = 'pos'; showTableModal = false; showOrdersModal = false; showKitchenModal = false"
      >
        <span class="m-nav-icon">🍽️</span>
        <span class="m-nav-label">สั่งอาหาร</span>
      </button>

      <button
        class="m-nav-tab"
        :class="{ 'is-active': showTableModal }"
        @click="showTableModal = true; viewMode = 'pos'"
      >
        <span class="m-nav-icon">🪑</span>
        <span class="m-nav-label">{{ selectedTableId ? `โต๊ะ ${selectedTableId}` : 'เลือกโต๊ะ' }}</span>
      </button>

      <button
        class="m-nav-tab m-nav-unpaid-tab"
        :class="{ 'is-active': showOrdersModal }"
        @click="showOrdersModal = true"
      >
        <div class="m-nav-icon-wrap">
          <span class="m-nav-icon">📋</span>
          <span v-if="unpaidOrdersCount > 0" class="m-nav-badge">{{ unpaidOrdersCount }}</span>
        </div>
        <span class="m-nav-label">บิลค้างชำระ</span>
      </button>

      <button
        class="m-nav-tab"
        :class="{ 'is-active': showKitchenModal }"
        @click="showKitchenModal = true"
      >
        <div class="m-nav-icon-wrap">
          <span class="m-nav-icon">🍳</span>
          <span v-if="kitchenOrders.length > 0" class="m-nav-badge kds-pulse">{{ kitchenOrders.length }}</span>
        </div>
        <span class="m-nav-label">จอครัว KDS</span>
      </button>

      <button
        class="m-nav-tab"
        :class="{ 'is-active': viewMode === 'settings' }"
        @click="viewMode = 'settings'; showTableModal = false; showOrdersModal = false; showKitchenModal = false"
      >
        <span class="m-nav-icon">⚙️</span>
        <span class="m-nav-label">ตั้งค่า</span>
      </button>
    </nav>
'''

# Find end of template
end_template_idx = content.rfind('</template>')
content = content[:end_template_idx] + bottom_nav_html + '\n  ' + content[end_template_idx:]

with open('scratch/PosRestodash.vue', 'w', encoding='utf-8') as f:
    f.write(content)

print("Template & methods patched successfully!")
