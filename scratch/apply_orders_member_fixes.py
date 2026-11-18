import re

vue_file = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\PosRestodash.vue'
with open(vue_file, 'r', encoding='utf-8') as f:
    content = f.read()

# -------------------------------------------------------------
# 1. Update Table Template in Orders Modal (Remove items column, add customer/member column)
# -------------------------------------------------------------
old_table_headers = """            <thead>
              <tr>
                <th>เลขที่บิล</th>
                <th>เวลาสั่ง</th>
                <th>โต๊ะ / ประเภท</th>
                <th>รายการอาหาร</th>
                <th>ยอดเงิน</th>
                <th>สถานะ</th>
                <th>การจัดการ</th>
              </tr>
            </thead>"""

new_table_headers = """            <thead>
              <tr>
                <th>เลขที่บิล</th>
                <th>เวลาสั่ง</th>
                <th>โต๊ะ / ประเภท</th>
                <th>ลูกค้า / สมาชิก</th>
                <th>ยอดเงิน</th>
                <th>สถานะ</th>
                <th>การจัดการ</th>
              </tr>
            </thead>"""

if old_table_headers in content:
    content = content.replace(old_table_headers, new_table_headers)
    print("1. Replaced table headers")
else:
    print("1. old_table_headers NOT found!")

old_td_items = """                <td>
                  <div class="order-items-preview" :title="formatItemsTooltip(ord.items)">
                    <b>{{ ord.items?.length || 0 }} รายการ:</b> {{ formatItemsSummary(ord.items) }}
                  </div>
                </td>"""

new_td_customer = """                <td>
                  <!-- Member Linked -->
                  <div v-if="ord.member_name || ord.customer_name" class="customer-info-cell">
                    <div class="customer-name-row">
                      <span class="customer-badge-star">⭐</span>
                      <span class="customer-name-text">{{ ord.member_name || ord.customer_name }}</span>
                      <span class="member-tag-badge">สมาชิก</span>
                    </div>
                    <div class="customer-sub-row">
                      <span v-if="ord.member_phone || ord.customer_phone" class="customer-phone">📞 {{ ord.member_phone || ord.customer_phone }}</span>
                      <button @click="openAttachMemberModal(ord)" class="btn-change-member" title="เปลี่ยนสมาชิกหรือแก้ไข">เปลี่ยน</button>
                    </div>
                  </div>
                  <!-- Guest (Default) with Link Member Button -->
                  <div v-else class="customer-info-cell">
                    <div class="guest-row">
                      <span class="guest-avatar">👤</span>
                      <span class="guest-name">Guest</span>
                      <button
                        @click="openAttachMemberModal(ord)"
                        class="btn-link-member"
                        title="ผูกออเดอร์นี้กับสมาชิกเพื่อสะสมแต้ม"
                      >
                        + ผูกสมาชิก
                      </button>
                    </div>
                  </div>
                </td>"""

if old_td_items in content:
    content = content.replace(old_td_items, new_td_customer)
    print("2. Replaced order items column with Customer/Member column")
else:
    print("2. old_td_items NOT found!")

# -------------------------------------------------------------
# 2. Add Member Linking Modal
# -------------------------------------------------------------
member_modal_html = """
    <!-- =================================================================== -->
    <!-- MODAL: ATTACH MEMBER TO ORDER                                       -->
    <!-- =================================================================== -->
    <div v-if="showAttachMemberModal && orderToAttachMember" class="pos-modal-overlay" @click.self="showAttachMemberModal = false">
      <div class="pos-modal-box attach-member-modal">
        <div class="modal-header">
          <div>
            <div class="modal-title">⭐ ผูกสมาชิกกับออเดอร์ #{{ orderToAttachMember.order_id.slice(-6) }}</div>
            <div class="modal-sub">
              {{ orderToAttachMember.table_name || (orderToAttachMember.table_id === 'takeaway' ? '📦 กลับบ้าน' : `โต๊ะ ${orderToAttachMember.table_id}`) }} •
              ยอดเงิน: ฿{{ formatBaht(orderToAttachMember.total || orderToAttachMember.grand_total) }}
            </div>
          </div>
          <button @click="showAttachMemberModal = false" class="modal-close-btn">✕</button>
        </div>

        <div class="attach-member-body">
          <div class="member-search-bar">
            <span class="search-icon">🔍</span>
            <input
              v-model="memberSearchQuery"
              placeholder="ค้นหาชื่อสมาชิก หรือเบอร์โทรศัพท์..."
              class="member-search-input"
            />
            <button v-if="memberSearchQuery" @click="memberSearchQuery = ''" class="search-clear-btn">✕</button>
          </div>

          <div class="member-selection-list custom-scrollbar">
            <div
              v-for="mem in filteredMembersList"
              :key="mem.id"
              @click="selectMemberForOrder(mem)"
              class="member-select-card"
            >
              <div class="mem-card-left">
                <div class="mem-avatar">👤</div>
                <div>
                  <div class="mem-name">{{ mem.name }}</div>
                  <div class="mem-phone">📞 {{ mem.phone }}</div>
                </div>
              </div>
              <div class="mem-card-right">
                <span class="mem-tier-badge">{{ mem.tier || 'Regular' }}</span>
                <span class="mem-points-pill">{{ mem.points || 0 }} แต้ม</span>
                <button class="btn-choose-member">เลือก</button>
              </div>
            </div>

            <div v-if="filteredMembersList.length === 0" class="member-empty-state">
              <span>ไม่พบข้อมูลสมาชิกตรงตามคำค้น</span>
            </div>
          </div>
        </div>

        <div class="modal-footer attach-member-footer">
          <button @click="removeMemberFromOrder" class="btn-clear-member-link">
            ตั้งเป็น Guest (ยกเลิกผูกสมาชิก)
          </button>
          <button @click="showAttachMemberModal = false" class="btn-cancel">ปิด</button>
        </div>
      </div>
    </div>
"""

# Place member_modal_html right after Orders Modal
orders_modal_end = '<!-- MODAL 6: REPORTS & STATS'
if orders_modal_end in content:
    content = content.replace(orders_modal_end, member_modal_html + '\n    ' + orders_modal_end)
    print("3. Inserted Member Modal template")
else:
    print("3. orders_modal_end NOT found!")

# -------------------------------------------------------------
# 3. Add JS state & logic for Member Linking
# -------------------------------------------------------------
target_state = "const orderSearchQuery = ref('')"
new_state = """const orderSearchQuery = ref('')
const showAttachMemberModal = ref(false)
const orderToAttachMember = ref(null)
const memberSearchQuery = ref('')"""

if target_state in content:
    content = content.replace(target_state, new_state, 1)
    print("4. Added state variables for member linking")
else:
    print("4. target_state NOT found!")

# Add functions and computed for member linking
member_functions = """
const filteredMembersList = computed(() => {
  if (!memberSearchQuery.value.trim()) return membersList.value
  const q = memberSearchQuery.value.toLowerCase().trim()
  return membersList.value.filter(m =>
    (m.name && m.name.toLowerCase().includes(q)) ||
    (m.phone && m.phone.includes(q))
  )
})

function openAttachMemberModal(order) {
  orderToAttachMember.value = order
  memberSearchQuery.value = ''
  showAttachMemberModal.value = true
}

function selectMemberForOrder(mem) {
  if (!orderToAttachMember.value) return
  orderToAttachMember.value.customer_name = mem.name
  orderToAttachMember.value.member_name = mem.name
  orderToAttachMember.value.member_id = mem.id
  orderToAttachMember.value.member_phone = mem.phone

  if (activeCheckoutOrder.value && activeCheckoutOrder.value.order_id === orderToAttachMember.value.order_id) {
    activeCheckoutOrder.value.customer_name = mem.name
    activeCheckoutOrder.value.member_name = mem.name
    activeCheckoutOrder.value.member_id = mem.id
    activeCheckoutOrder.value.member_phone = mem.phone
  }

  showToast(`ผูกสมาชิก "${mem.name}" เข้ากับออเดอร์ #${orderToAttachMember.value.order_id.slice(-6)} เรียบร้อย ⭐`)
  showAttachMemberModal.value = false
}

function removeMemberFromOrder() {
  if (!orderToAttachMember.value) return
  orderToAttachMember.value.customer_name = ''
  orderToAttachMember.value.member_name = ''
  orderToAttachMember.value.member_id = ''
  orderToAttachMember.value.member_phone = ''

  if (activeCheckoutOrder.value && activeCheckoutOrder.value.order_id === orderToAttachMember.value.order_id) {
    activeCheckoutOrder.value.customer_name = ''
    activeCheckoutOrder.value.member_name = ''
    activeCheckoutOrder.value.member_id = ''
    activeCheckoutOrder.value.member_phone = ''
  }

  showToast('ตั้งค่าออเดอร์เป็น Guest แล้ว')
  showAttachMemberModal.value = false
}
"""

target_func_spot = "function openUnpaidOrdersModal() {"
if target_func_spot in content:
    content = content.replace(target_func_spot, member_functions + "\n" + target_func_spot)
    print("5. Added member linking functions")
else:
    print("5. target_func_spot NOT found!")

# -------------------------------------------------------------
# 4. Add Modern, Beautiful CSS for Orders Modal & Customer/Member Cell
# -------------------------------------------------------------
modern_orders_css = """
/* ── MODERN BEAUTIFUL ORDERS MODAL STYLING ──────────────────────────── */
.orders-modal-box {
  width: 980px !important;
  max-width: 96vw !important;
  border-radius: 16px !important;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.22) !important;
  overflow: hidden !important;
  background: #FFFFFF !important;
}

.orders-history-table {
  width: 100% !important;
  border-collapse: separate !important;
  border-spacing: 0 !important;
  font-size: 13px !important;
}

.orders-history-table th {
  padding: 12px 14px !important;
  background: #F1F5F9 !important;
  border-bottom: 2px solid #CBD5E1 !important;
  text-align: left !important;
  font-weight: 800 !important;
  color: #334155 !important;
  font-family: 'Prompt', sans-serif !important;
  white-space: nowrap !important;
}

.orders-history-table td {
  padding: 12px 14px !important;
  border-bottom: 1px solid #F1F5F9 !important;
  vertical-align: middle !important;
  background: #FFFFFF !important;
  transition: background 0.15s !important;
}

.orders-history-table tr:hover td {
  background: #F8FAFC !important;
}

/* Remove ugly yellow background for unpaid rows */
.is-unpaid-row td,
.is-unpaid-row {
  background: #FFFFFF !important;
}

.time-main {
  font-weight: 800 !important;
  color: #0F172A !important;
  font-size: 13px !important;
}
.time-sub {
  font-size: 11px !important;
  color: #94A3B8 !important;
}

.table-pill {
  display: inline-block !important;
  background: #EFF6FF !important;
  color: #1D4ED8 !important;
  border: 1px solid #BFDBFE !important;
  padding: 4px 10px !important;
  border-radius: 8px !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  white-space: nowrap !important;
}

/* Customer / Member Info Cell */
.customer-info-cell {
  display: flex !important;
  flex-direction: column !important;
  gap: 3px !important;
}

.customer-name-row {
  display: flex !important;
  align-items: center !important;
  gap: 6px !important;
}

.customer-badge-star {
  font-size: 14px !important;
  color: #F59E0B !important;
}

.customer-name-text {
  font-weight: 800 !important;
  color: #0F172A !important;
  font-size: 13.5px !important;
}

.member-tag-badge {
  background: #FEF3C7 !important;
  color: #D97706 !important;
  border: 1px solid #FDE68A !important;
  font-size: 10px !important;
  font-weight: 800 !important;
  padding: 1px 6px !important;
  border-radius: 6px !important;
}

.customer-sub-row {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
  font-size: 11.5px !important;
  color: #64748B !important;
}

.btn-change-member {
  background: none !important;
  border: none !important;
  color: #2563EB !important;
  font-size: 11px !important;
  font-weight: 700 !important;
  cursor: pointer !important;
  text-decoration: underline !important;
  padding: 0 !important;
}
.btn-change-member:hover {
  color: #1D4ED8 !important;
}

.guest-row {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
}

.guest-avatar {
  font-size: 14px !important;
  color: #94A3B8 !important;
}

.guest-name {
  font-size: 13px !important;
  font-weight: 600 !important;
  color: #64748B !important;
}

.btn-link-member {
  background: #EFF6FF !important;
  border: 1px solid #BFDBFE !important;
  color: #2563EB !important;
  border-radius: 6px !important;
  padding: 2px 8px !important;
  font-size: 11px !important;
  font-weight: 700 !important;
  cursor: pointer !important;
  transition: all 0.15s !important;
}

.btn-link-member:hover {
  background: #2563EB !important;
  color: #FFFFFF !important;
  border-color: #2563EB !important;
  transform: translateY(-1px) !important;
}

/* Status Pills */
.status-pill {
  display: inline-block !important;
  padding: 4px 10px !important;
  border-radius: 12px !important;
  font-size: 11.5px !important;
  font-weight: 800 !important;
  white-space: nowrap !important;
}

.status-pill.paid {
  background: #ECFDF5 !important;
  color: #047857 !important;
  border: 1px solid #A7F3D0 !important;
}

.status-pill.cancelled {
  background: #FEF2F2 !important;
  color: #B91C1C !important;
  border: 1px solid #FECACA !important;
}

.status-pill.unpaid,
.status-pill:not(.paid):not(.cancelled) {
  background: #FFFBEB !important;
  color: #B45309 !important;
  border: 1px solid #FDE68A !important;
}

/* Action Buttons */
.action-buttons-cell {
  display: flex !important;
  gap: 8px !important;
  align-items: center !important;
}

.btn-sm-checkout {
  border: 1px solid #1D4ED8 !important;
  background: #2563EB !important;
  color: #FFFFFF !important;
  border-radius: 8px !important;
  padding: 6px 12px !important;
  font-size: 12px !important;
  font-weight: 800 !important;
  cursor: pointer !important;
  white-space: nowrap !important;
  box-shadow: 0 2px 5px rgba(37, 99, 235, 0.25) !important;
  transition: all 0.15s !important;
}

.btn-sm-checkout:hover {
  background: #1D4ED8 !important;
  transform: translateY(-1px) !important;
}

.btn-sm-view {
  border: 1px solid #CBD5E1 !important;
  background: #FFFFFF !important;
  color: #334155 !important;
  border-radius: 8px !important;
  padding: 6px 10px !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  cursor: pointer !important;
  white-space: nowrap !important;
  transition: all 0.15s !important;
}

.btn-sm-view:hover {
  background: #F1F5F9 !important;
  border-color: #94A3B8 !important;
}

.btn-sm-void {
  border: 1px solid #FECACA !important;
  background: #FEF2F2 !important;
  color: #DC2626 !important;
  border-radius: 8px !important;
  padding: 6px 10px !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  cursor: pointer !important;
  white-space: nowrap !important;
  transition: all 0.15s !important;
}

.btn-sm-void:hover {
  background: #FEE2E2 !important;
}

/* Member Attach Modal Styles */
.attach-member-modal {
  width: 520px !important;
  max-width: 95vw !important;
  background: #ffffff !important;
  border-radius: 16px !important;
  overflow: hidden !important;
}

.attach-member-body {
  padding: 18px 24px !important;
}

.member-search-bar {
  display: flex !important;
  align-items: center !important;
  background: #F8FAFC !important;
  border: 1.5px solid #CBD5E1 !important;
  border-radius: 10px !important;
  padding: 0 12px !important;
  margin-bottom: 14px !important;
}

.member-search-input {
  flex: 1 !important;
  border: none !important;
  background: transparent !important;
  padding: 10px 0 !important;
  font-size: 13.5px !important;
  font-family: 'Prompt', sans-serif !important;
  outline: none !important;
}

.member-selection-list {
  max-height: 280px !important;
  overflow-y: auto !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 8px !important;
}

.member-select-card {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  padding: 10px 14px !important;
  border: 1.5px solid #E2E8F0 !important;
  border-radius: 10px !important;
  background: #FFFFFF !important;
  cursor: pointer !important;
  transition: all 0.15s !important;
}

.member-select-card:hover {
  border-color: #2563EB !important;
  background: #EFF6FF !important;
  transform: translateY(-1px) !important;
}

.mem-card-left {
  display: flex !important;
  align-items: center !important;
  gap: 10px !important;
}

.mem-avatar {
  width: 36px !important;
  height: 36px !important;
  border-radius: 50% !important;
  background: #EFF6FF !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  font-size: 18px !important;
}

.mem-name {
  font-weight: 800 !important;
  color: #0F172A !important;
  font-size: 14px !important;
}

.mem-phone {
  font-size: 12px !important;
  color: #64748B !important;
}

.mem-card-right {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
}

.mem-tier-badge {
  background: #F1F5F9 !important;
  color: #475569 !important;
  font-size: 11px !important;
  font-weight: 700 !important;
  padding: 2px 7px !important;
  border-radius: 6px !important;
}

.mem-points-pill {
  background: #FEF3C7 !important;
  color: #D97706 !important;
  font-size: 11px !important;
  font-weight: 800 !important;
  padding: 2px 8px !important;
  border-radius: 6px !important;
}

.btn-choose-member {
  background: #2563EB !important;
  color: #FFFFFF !important;
  border: none !important;
  border-radius: 6px !important;
  padding: 4px 10px !important;
  font-size: 11.5px !important;
  font-weight: 700 !important;
  cursor: pointer !important;
}

.member-empty-state {
  padding: 30px !important;
  text-align: center !important;
  color: #94A3B8 !important;
  font-size: 13px !important;
}

.attach-member-footer {
  display: flex !important;
  justify-content: space-between !important;
}

.btn-clear-member-link {
  background: #F1F5F9 !important;
  border: 1px solid #CBD5E1 !important;
  color: #64748B !important;
  padding: 8px 14px !important;
  border-radius: 8px !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  cursor: pointer !important;
}
.btn-clear-member-link:hover {
  background: #E2E8F0 !important;
  color: #0F172A !important;
}
"""

# Insert modern_orders_css right before </style>
idx = content.rfind('</style>')
if idx != -1:
    content = content[:idx] + "\n" + modern_orders_css + "\n</style>\n"
    print("6. Added modern CSS for Orders & Member Linking inside <style>")
else:
    print("6. </style> not found!")

with open(vue_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated PosRestodash.vue successfully!")
