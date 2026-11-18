import re

vue_file = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\PosRestodash.vue'
with open(vue_file, 'r', encoding='utf-8') as f:
    content = f.read()

# -------------------------------------------------------------
# 1. Update Sidebar Bottom button: System menu button -> Settings page direct
# -------------------------------------------------------------
old_sidebar_btn = '''        <!-- Bottom Controls: System Menu + Move Collapse Button Down Here -->
        <div class="sidebar-bottom">
          <button @click="showSystemMenu = true" class="system-menu-btn">
            <span>☰</span>
            <span>เมนูระบบ & จัดการ</span>
          </button>
          <!-- Collapse Button Relocated to Bottom so it does NOT overlap with Logo -->
          <button @click="isSidebarCollapsed = true" class="sidebar-collapse-bottom-btn" title="ย่อเก็บแถบเมนูด้านซ้าย">
            <span>◀ ซ่อนแถบเมนู</span>
          </button>
        </div>'''

new_sidebar_btn = '''        <!-- Bottom Controls: Settings Page Direct + Collapse Button -->
        <div class="sidebar-bottom">
          <button @click="viewMode = 'settings'" class="system-menu-btn" title="เปิดหน้าต่างการตั้งค่าร้านค้า & ระบบ">
            <span>⚙️</span>
            <span>การตั้งค่าร้านค้า & ระบบ</span>
          </button>
          <!-- Collapse Button Relocated to Bottom so it does NOT overlap with Logo -->
          <button @click="isSidebarCollapsed = true" class="sidebar-collapse-bottom-btn" title="ย่อเก็บแถบเมนูด้านซ้าย">
            <span>◀ ซ่อนแถบเมนู</span>
          </button>
        </div>'''

if old_sidebar_btn in content:
    content = content.replace(old_sidebar_btn, new_sidebar_btn)
    print("1. Replaced sidebar bottom button with Settings direct")
else:
    print("1. old_sidebar_btn NOT found!")

# -------------------------------------------------------------
# 2. Add activeCheckoutOrder banner in Cart Header
# -------------------------------------------------------------
old_cart_order_type = '''          <!-- Order Type Switcher in Cart -->
          <div class="order-type-switch">'''

new_cart_order_type = '''          <!-- Active Checkout Order Banner (When checking out an existing unpaid order) -->
          <div v-if="activeCheckoutOrder" class="active-order-banner">
            <div class="active-order-left">
              <span class="active-order-pulse">●</span>
              <span class="active-order-title">ชำระบิล #{{ activeCheckoutOrder.order_id.slice(-6) }}</span>
              <span class="active-order-sub">({{ activeCheckoutOrder.table_name || (activeCheckoutOrder.table_id === 'takeaway' ? 'กลับบ้าน' : `โต๊ะ ${activeCheckoutOrder.table_id}`) }})</span>
            </div>
            <button @click="clearActiveCheckoutOrder" class="active-order-clear-btn" title="ยกเลิกการดึงออเดอร์นี้ แล้วเริ่มบิลใหม่">✕ บิลใหม่</button>
          </div>

          <!-- Order Type Switcher in Cart -->
          <div class="order-type-switch">'''

if old_cart_order_type in content:
    content = content.replace(old_cart_order_type, new_cart_order_type, 1)
    print("2. Added activeCheckoutOrder banner in Cart")
else:
    print("2. old_cart_order_type NOT found!")

# -------------------------------------------------------------
# 3. Replace Payment Modal with Top-Right Hero Badge & 2-Column Summary
# -------------------------------------------------------------
payment_modal_regex = re.compile(
    r'<!-- =+\s*-->\s*<!-- MODAL 2: PAYMENT & CHECKOUT\s*-->\s*<!-- =+\s*-->\s*<div v-if="showPaymentModal".*?<!-- =+\s*-->\s*<!-- MODAL 3: FULL THERMAL RECEIPT',
    re.DOTALL
)

new_payment_modal = '''<!-- =================================================================== -->
    <!-- MODAL 2: PAYMENT & CHECKOUT (Wide 2-Column with Top-Right Total Due)  -->
    <!-- =================================================================== -->
    <div v-if="showPaymentModal" class="pos-modal-overlay" @click.self="showPaymentModal = false">
      <div class="pos-modal-box payment-modal payment-modal-wide">
        <!-- Modal Header with Top-Right Outstanding Balance Hero Badge -->
        <div class="modal-header payment-modal-header">
          <div class="payment-header-left">
            <div class="modal-title">💳 ชำระเงิน / เช็คบิล</div>
            <div class="modal-sub">
              {{ orderType === 'takeaway' ? '📦 สั่งกลับบ้าน' : `🪑 โต๊ะ ${selectedTableId}` }}
              <template v-if="activeCheckoutOrder">
                • ออเดอร์ <b class="text-blue">#{{ activeCheckoutOrder.order_id.slice(-6) }}</b>
              </template>
              • {{ cart.length }} รายการ ({{ cartTotalQty }} จาน)
            </div>
          </div>

          <!-- YOD KHANG JAI TOP RIGHT (Hero Badge - Never Disappears) -->
          <div class="header-outstanding-balance-box">
            <div class="due-tag">ยอดค้างจ่าย (Total Due)</div>
            <div class="due-amount-hero">฿{{ formatBaht(cartGrandTotal) }}</div>
          </div>

          <button @click="showPaymentModal = false" class="modal-close-btn" title="ปิดหน้าต่าง">✕</button>
        </div>

        <!-- 2-Column POS Payment Body -->
        <div class="payment-modal-body-grid">
          <!-- LEFT COLUMN: Order Items & Financial Summary (Never Disappears!) -->
          <div class="payment-order-summary-panel">
            <div class="summary-panel-title">
              <span>🧾 รายการอาหารในบิล</span>
              <span class="summary-items-count">{{ cart.length }} รายการ</span>
            </div>

            <div class="payment-summary-items-list custom-scrollbar">
              <div v-for="(it, idx) in cart" :key="idx" class="payment-summary-item-row">
                <div class="summary-item-name-col">
                  <div class="summary-item-name">{{ it.name }}</div>
                  <div v-if="it.notes" class="summary-item-notes">📝 {{ it.notes }}</div>
                </div>
                <div class="summary-item-qty-col">x{{ it.quantity }}</div>
                <div class="summary-item-price-col">฿{{ formatBaht((it.price || 0) * it.quantity) }}</div>
              </div>
            </div>

            <!-- Financial Breakdown (Always visible) -->
            <div class="payment-summary-financials">
              <div class="financial-row">
                <span>รวมค่าอาหาร (Subtotal)</span>
                <span>฿{{ formatBaht(cartSubtotal) }}</span>
              </div>
              <div class="financial-row">
                <span>ภาษีมูลค่าเพิ่ม VAT ({{ shopSettings.vat || 7 }}%)</span>
                <span>฿{{ formatBaht(cartVat) }}</span>
              </div>
              <div class="financial-row total-highlight-row">
                <span class="total-label">ยอดสุทธิที่ต้องชำระ</span>
                <span class="total-val">฿{{ formatBaht(cartGrandTotal) }}</span>
              </div>
            </div>
          </div>

          <!-- RIGHT COLUMN: Payment Methods & Cash Tender Calculator -->
          <div class="payment-tender-panel">
            <!-- Payment Method Tabs -->
            <div class="payment-tabs-row">
              <button
                @click="selectedPaymentMethod = 'PromptPay'"
                class="pay-tab-btn"
                :class="{ 'is-active': selectedPaymentMethod === 'PromptPay' }"
              >
                📱 สแกน QR
              </button>
              <button
                @click="selectedPaymentMethod = 'Cash'"
                class="pay-tab-btn"
                :class="{ 'is-active': selectedPaymentMethod === 'Cash' }"
              >
                💵 เงินสด (Cash)
              </button>
              <button
                @click="selectedPaymentMethod = 'Credit'"
                class="pay-tab-btn"
                :class="{ 'is-active': selectedPaymentMethod === 'Credit' }"
              >
                💳 บัตรเครดิต
              </button>
            </div>

            <!-- TAB 1: PromptPay QR View -->
            <div v-if="selectedPaymentMethod === 'PromptPay'" class="qr-payment-view">
              <div class="qr-box">
                <img
                  :src="qrCodeUrl"
                  alt="PromptPay QR"
                  class="qr-image"
                  @error="onQrError"
                />
              </div>
              <div class="qr-guide">
                <div class="qr-guide-title">สแกนจ่ายผ่านแอปธนาคารใดก็ได้</div>
                <div class="qr-guide-sub">ยอดเงิน: <b>฿{{ formatBaht(cartGrandTotal) }}</b></div>
              </div>
            </div>

            <!-- TAB 2: Cash Tender View -->
            <div v-if="selectedPaymentMethod === 'Cash'" class="cash-payment-view">
              <div class="cash-input-row">
                <label class="cash-label">รับเงินมา (บาท):</label>
                <div class="cash-input-wrapper">
                  <span class="currency-prefix">฿</span>
                  <input
                    v-model.number="cashReceived"
                    type="number"
                    class="cash-input"
                    placeholder="0.00"
                    min="0"
                  />
                  <button v-if="cashReceived" @click="cashReceived = 0" class="btn-clear-cash" title="ล้างตัวเลข">✕</button>
                </div>
              </div>

              <!-- Quick Cash Buttons Row 1: Direct Set -->
              <div class="quick-cash-label">เลือกจำนวนเงินด่วน:</div>
              <div class="quick-cash-row">
                <button @click="cashReceived = cartGrandTotal" class="quick-cash-btn exact-btn">
                  พอดี (฿{{ formatBaht(cartGrandTotal) }})
                </button>
                <button
                  v-for="amt in getSmartCashOptions(cartGrandTotal)"
                  :key="amt"
                  @click="cashReceived = amt"
                  class="quick-cash-btn"
                >
                  ฿{{ formatBaht(amt) }}
                </button>
              </div>

              <!-- Quick Cash Buttons Row 2: Cumulative Add (+20, +50, +100, +500) -->
              <div class="quick-cash-label">หรือกดเพิ่มตามธนบัตร:</div>
              <div class="cash-add-row">
                <button @click="addCash(20)" class="cash-add-pill">+฿20</button>
                <button @click="addCash(50)" class="cash-add-pill">+฿50</button>
                <button @click="addCash(100)" class="cash-add-pill">+฿100</button>
                <button @click="addCash(500)" class="cash-add-pill">+฿500</button>
                <button @click="addCash(1000)" class="cash-add-pill">+฿1,000</button>
              </div>

              <!-- Change Breakdown Display Box -->
              <div
                class="change-display-box"
                :class="{
                  'has-change': cashChange >= 0,
                  'is-short': cashChange < 0
                }"
              >
                <div class="change-line">
                  <span class="change-title">
                    {{ cashChange >= 0 ? '💰 เงินทอน (Change):' : '⚠️ ยังขาดอีก (Shortage):' }}
                  </span>
                  <span class="change-amount">
                    ฿{{ formatBaht(Math.abs(cashChange)) }}
                  </span>
                </div>
                <div class="change-sub-detail">
                  <span>ยอดค้าง: ฿{{ formatBaht(cartGrandTotal) }}</span>
                  <span>•</span>
                  <span>รับมา: ฿{{ formatBaht(cashReceived || 0) }}</span>
                </div>
              </div>
            </div>

            <!-- TAB 3: Credit Card View -->
            <div v-if="selectedPaymentMethod === 'Credit'" class="credit-payment-view">
              <div class="credit-icon">💳</div>
              <div class="credit-title">แตะหรือเสียบบัตรที่เครื่อง EDC</div>
              <div class="credit-sub">ยอดเงิน: <b>฿{{ formatBaht(cartGrandTotal) }}</b></div>
            </div>
          </div>
        </div>

        <!-- Confirm Button Footer -->
        <div class="modal-footer payment-modal-footer">
          <button @click="showPaymentModal = false" class="btn-cancel">ยกเลิก</button>
          <button
            :disabled="isSubmitting || (selectedPaymentMethod === 'Cash' && cashChange < 0)"
            @click="submitPayment"
            class="btn-confirm-pay"
          >
            {{ isSubmitting ? 'กำลังบันทึก...' : `ยืนยันการชำระเงิน • ฿${formatBaht(cartGrandTotal)}` }}
          </button>
        </div>
      </div>
    </div>

    <!-- =================================================================== -->
    <!-- MODAL 3: FULL THERMAL RECEIPT'''

match = payment_modal_regex.search(content)
if match:
    content = content[:match.start()] + new_payment_modal + content[match.end() - len('<!-- =================================================================== -->\n    <!-- MODAL 3: FULL THERMAL RECEIPT'):]
    print("3. Replaced Payment Modal template successfully")
else:
    print("3. Payment modal regex did not match!")

# -------------------------------------------------------------
# 4. Update JS logic: activeCheckoutOrder, submitPayment, loadOrderIntoCart
# -------------------------------------------------------------
target_refs = "const lastCompletedOrder = ref(null)"
new_refs = """const lastCompletedOrder = ref(null)
const activeCheckoutOrder = ref(null)"""

if target_refs in content:
    content = content.replace(target_refs, new_refs)
    print("4. Added activeCheckoutOrder ref")
else:
    print("4. target_refs NOT found!")

# Update loadOrderIntoCart
old_load = """function loadOrderIntoCart(order) {
  if (!order || !order.items) return

  // Restore cart
  cart.value = order.items.map(it => ({
    id: it.item_id || it.id,
    item_id: it.item_id || it.id,
    name: it.name,
    price: it.price,
    quantity: it.quantity,
    notes: it.notes || ''
  }))

  // Restore table
  if (order.table_id === 'takeaway') {
    orderType.value = 'takeaway'
    selectedTableId.value = null
  } else {
    orderType.value = 'dinein'
    selectedTableId.value = order.table_id
  }

  showOrdersModal.value = false
  showToast(`ดึงออเดอร์ #${order.order_id.slice(-6)} เข้าตะกร้าแล้ว สามารถคิดเงินหรือเพิ่มจานได้ทันที ✅`)
}"""

new_load = """function loadOrderIntoCart(order) {
  if (!order || !order.items) return

  // Track as active unpaid checkout order
  activeCheckoutOrder.value = order

  // Restore cart
  cart.value = order.items.map(it => ({
    id: it.item_id || it.id,
    item_id: it.item_id || it.id,
    name: it.name,
    price: it.price,
    quantity: it.quantity,
    notes: it.notes || ''
  }))

  // Restore table
  if (order.table_id === 'takeaway') {
    orderType.value = 'takeaway'
    selectedTableId.value = null
  } else {
    orderType.value = 'dinein'
    selectedTableId.value = order.table_id
  }

  showOrdersModal.value = false
  showToast(`ดึงออเดอร์ #${order.order_id.slice(-6)} เข้าตะกร้าแล้ว สามารถคิดเงินหรือเพิ่มจานได้ทันที ✅`)
}

function clearActiveCheckoutOrder() {
  activeCheckoutOrder.value = null
  cart.value = []
  showToast('ยกเลิกการดึงบิลเดิมแล้ว พร้อมเริ่มบิลใหม่ 🔄')
}

function addCash(amount) {
  cashReceived.value = (Number(cashReceived.value) || 0) + Number(amount)
}

function getSmartCashOptions(total) {
  const t = Math.ceil(Number(total) || 0)
  const options = []
  const round100 = Math.ceil(t / 100) * 100
  if (round100 > t) options.push(round100)
  const round500 = Math.ceil(t / 500) * 500
  if (round500 > t && !options.includes(round500)) options.push(round500)
  const round1000 = Math.ceil(t / 1000) * 1000
  if (round1000 > t && !options.includes(round1000)) options.push(round1000)
  if (options.length === 0) {
    options.push(t + 100, t + 500)
  }
  return options.slice(0, 3)
}"""

if old_load in content:
    content = content.replace(old_load, new_load)
    print("5. Replaced loadOrderIntoCart & added helpers")
else:
    print("5. old_load NOT found!")

# Update submitPayment
old_submit = """async function submitPayment() {
  if (cart.value.length === 0) return
  isSubmitting.value = true
  try {
    const tableIdParam = orderType.value === 'takeaway' ? 'takeaway' : String(selectedTableId.value || '1')
    const itemsPayload = cart.value.map(i => ({
      item_id: i.id || i.item_id,
      quantity: i.quantity,
      notes: i.notes || ''
    }))

    const newOrder = await createOrder(tableIdParam, itemsPayload)

    await processPayment(
      newOrder.order_id,
      selectedPaymentMethod.value,
      selectedPaymentMethod.value === 'Cash' ? cashReceived.value : cartGrandTotal.value
    )

    lastCompletedOrder.value = {
      order_id: newOrder.order_id,
      table_id: tableIdParam,
      table_name: orderType.value === 'takeaway' ? 'สั่งกลับบ้าน' : `โต๊ะ ${selectedTableId.value}`,
      items: JSON.parse(JSON.stringify(cart.value)),
      subtotal: cartSubtotal.value,
      vat: cartVat.value,
      total: cartGrandTotal.value,
      payment_method: selectedPaymentMethod.value,
      cash_received: selectedPaymentMethod.value === 'Cash' ? cashReceived.value : null,
      change: selectedPaymentMethod.value === 'Cash' ? cashChange.value : 0,
      created_at: new Date().toISOString()
    }

    showPaymentModal.value = false
    showReceiptModal.value = true
    cart.value = []

    showToast(`ชำระเงินสำเร็จ! ออกใบเสร็จ #${newOrder.order_id.slice(-6)} ✅`)
    fetchData()
  } catch (err) {
    console.error('Payment submit error:', err)
    showToast(`เกิดข้อผิดพลาด: ${err.response?.data?.detail || err.message}`)
  } finally {
    isSubmitting.value = false
  }
}"""

new_submit = """async function submitPayment() {
  if (cart.value.length === 0) return
  isSubmitting.value = true
  try {
    const tableIdParam = orderType.value === 'takeaway' ? 'takeaway' : String(selectedTableId.value || '1')
    const itemsPayload = cart.value.map(i => ({
      item_id: i.id || i.item_id,
      quantity: i.quantity,
      notes: i.notes || ''
    }))

    let finalOrderId = null

    if (activeCheckoutOrder.value && activeCheckoutOrder.value.order_id) {
      // 1. Paying an EXISTING unpaid order!
      finalOrderId = activeCheckoutOrder.value.order_id
      try {
        await updateOrderItems(finalOrderId, itemsPayload)
      } catch (err) {
        console.warn('Could not update order items, continuing with payment:', err)
      }
      // Process payment directly on existing order (NO createOrder -> NO New Order Notification!)
      await processPayment(
        finalOrderId,
        selectedPaymentMethod.value,
        selectedPaymentMethod.value === 'Cash' ? cashReceived.value : cartGrandTotal.value
      )
    } else {
      // 2. Creating and paying a fresh new walk-in order
      const newOrder = await createOrder(tableIdParam, itemsPayload)
      finalOrderId = newOrder.order_id
      await processPayment(
        finalOrderId,
        selectedPaymentMethod.value,
        selectedPaymentMethod.value === 'Cash' ? cashReceived.value : cartGrandTotal.value
      )
    }

    lastCompletedOrder.value = {
      order_id: finalOrderId,
      table_id: tableIdParam,
      table_name: orderType.value === 'takeaway' ? 'สั่งกลับบ้าน' : `โต๊ะ ${selectedTableId.value}`,
      items: JSON.parse(JSON.stringify(cart.value)),
      subtotal: cartSubtotal.value,
      vat: cartVat.value,
      total: cartGrandTotal.value,
      payment_method: selectedPaymentMethod.value,
      cash_received: selectedPaymentMethod.value === 'Cash' ? cashReceived.value : null,
      change: selectedPaymentMethod.value === 'Cash' ? cashChange.value : 0,
      created_at: new Date().toISOString()
    }

    showPaymentModal.value = false
    showReceiptModal.value = true
    cart.value = []
    activeCheckoutOrder.value = null

    showToast(`ชำระเงินสำเร็จ! ออกใบเสร็จ #${finalOrderId.slice(-6)} ✅`)
    fetchData()
  } catch (err) {
    console.error('Payment submit error:', err)
    showToast(`เกิดข้อผิดพลาด: ${err.response?.data?.detail || err.message}`)
  } finally {
    isSubmitting.value = false
  }
}"""

if old_submit in content:
    content = content.replace(old_submit, new_submit)
    print("6. Replaced submitPayment logic")
else:
    print("6. old_submit NOT found!")

# Update clearCart to also reset activeCheckoutOrder
old_clear_cart = """function clearCart() {
  cart.value = []
}"""

new_clear_cart = """function clearCart() {
  cart.value = []
  activeCheckoutOrder.value = null
}"""

if old_clear_cart in content:
    content = content.replace(old_clear_cart, new_clear_cart)
    print("7. Updated clearCart")

# -------------------------------------------------------------
# 5. Add New CSS Styles for Wide 2-Column Payment Modal & Top-Right Balance Badge
# -------------------------------------------------------------
extra_css = """
/* ── ACTIVE CHECKOUT ORDER BANNER IN CART ───────────────────────────── */
.active-order-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(135deg, #EFF6FF, #DBEAFE);
  border: 1px solid #93C5FD;
  border-radius: 10px;
  padding: 8px 12px;
  margin-bottom: 10px;
}
.active-order-left {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #1E40AF;
}
.active-order-pulse {
  color: #2563EB;
  font-size: 10px;
  animation: pulse 1.5s infinite;
}
.active-order-title {
  font-weight: 800;
}
.active-order-sub {
  color: #3B82F6;
  font-size: 12px;
}
.active-order-clear-btn {
  background: #FFFFFF;
  border: 1px solid #BFDBFE;
  color: #EF4444;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 6px;
  cursor: pointer;
}
.active-order-clear-btn:hover {
  background: #FEE2E2;
}

/* ── WIDE PAYMENT MODAL & TOP-RIGHT OUTSTANDING BALANCE HERO ───────── */
.payment-modal.payment-modal-wide {
  width: 860px !important;
  max-width: 95vw !important;
}
.payment-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid #E2E8F0;
  gap: 16px;
}
.payment-header-left {
  flex: 1;
}

/* TOP RIGHT HERO BADGE: YOD KHANG JAI */
.header-outstanding-balance-box {
  background: linear-gradient(135deg, #0F172A, #1E293B);
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 8px 18px;
  text-align: right;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.2);
}
.header-outstanding-balance-box .due-tag {
  font-size: 11px;
  font-weight: 700;
  color: #94A3B8;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.header-outstanding-balance-box .due-amount-hero {
  font-size: 24px;
  font-weight: 900;
  color: #38BDF8;
  line-height: 1.1;
  font-family: 'Prompt', monospace;
}

/* 2-Column POS Body Grid */
.payment-modal-body-grid {
  display: grid;
  grid-template-columns: 360px 1fr;
  min-height: 420px;
}
@media (max-width: 768px) {
  .payment-modal-body-grid {
    grid-template-columns: 1fr;
  }
}

/* Left Column: Order Summary (Items & Total) */
.payment-order-summary-panel {
  background: #F8FAFC;
  border-right: 1px solid #E2E8F0;
  padding: 20px;
  display: flex;
  flex-direction: column;
}
.summary-panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 800;
  color: #0F172A;
  padding-bottom: 12px;
  border-bottom: 1px solid #E2E8F0;
  margin-bottom: 12px;
}
.summary-items-count {
  font-size: 12px;
  font-weight: 600;
  color: #64748B;
  background: #E2E8F0;
  padding: 2px 8px;
  border-radius: 12px;
}
.payment-summary-items-list {
  flex: 1;
  max-height: 250px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 4px;
}
.payment-summary-item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px dashed #E2E8F0;
  font-size: 13px;
}
.summary-item-name-col {
  flex: 1;
}
.summary-item-name {
  font-weight: 700;
  color: #1E293B;
}
.summary-item-notes {
  font-size: 11px;
  color: #94A3B8;
}
.summary-item-qty-col {
  font-weight: 800;
  color: #64748B;
  margin: 0 12px;
}
.summary-item-price-col {
  font-weight: 800;
  color: #0F172A;
}

.payment-summary-financials {
  margin-top: auto;
  padding-top: 14px;
  border-top: 2px solid #E2E8F0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.total-highlight-row {
  background: #EFF6FF;
  padding: 8px 12px;
  border-radius: 8px;
  margin-top: 6px;
  border: 1px solid #BFDBFE;
}
.total-highlight-row .total-label {
  font-size: 14px;
  font-weight: 800;
  color: #1E40AF;
}
.total-highlight-row .total-val {
  font-size: 18px;
  font-weight: 900;
  color: #1D4ED8;
}

/* Right Column: Tender & Cash Controls */
.payment-tender-panel {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
}

.cash-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}
.currency-prefix {
  position: absolute;
  left: 14px;
  font-size: 22px;
  font-weight: 900;
  color: #64748B;
}
.cash-input-wrapper .cash-input {
  width: 100%;
  padding: 12px 40px 12px 36px;
  font-size: 24px;
  font-weight: 900;
  border: 2px solid #CBD5E1;
  border-radius: 12px;
  color: #0F172A;
  font-family: 'Prompt', monospace;
}
.cash-input-wrapper .cash-input:focus {
  border-color: #2563EB;
  outline: none;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}
.btn-clear-cash {
  position: absolute;
  right: 12px;
  background: #E2E8F0;
  border: none;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  font-size: 12px;
  font-weight: 800;
  color: #64748B;
  cursor: pointer;
}

.quick-cash-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748B;
  margin: 12px 0 6px;
}
.quick-cash-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.quick-cash-btn.exact-btn {
  background: #EFF6FF;
  border-color: #93C5FD;
  color: #1D4ED8;
}
.quick-cash-btn.exact-btn:hover {
  background: #DBEAFE;
}

.cash-add-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.cash-add-pill {
  padding: 7px 14px;
  background: #F1F5F9;
  border: 1px solid #CBD5E1;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 800;
  color: #334155;
  cursor: pointer;
  transition: all 0.15s;
}
.cash-add-pill:hover {
  background: #E2E8F0;
  border-color: #94A3B8;
  transform: translateY(-1px);
}

.change-display-box {
  margin-top: 16px;
  padding: 14px 18px;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.change-display-box.has-change {
  background: #F0FDF4;
  border: 1.5px solid #86EFAC;
}
.change-display-box.is-short {
  background: #FFFBEB;
  border: 1.5px solid #FCD34D;
}
.change-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.change-title {
  font-size: 14px;
  font-weight: 800;
  color: #0F172A;
}
.change-amount {
  font-size: 22px;
  font-weight: 900;
  font-family: 'Prompt', monospace;
}
.has-change .change-amount {
  color: #16A34A;
}
.is-short .change-amount {
  color: #D97706;
}
.change-sub-detail {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #64748B;
  font-weight: 600;
}
"""

content = content + "\n" + extra_css

with open(vue_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated PosRestodash.vue with all features and styles successfully!")
