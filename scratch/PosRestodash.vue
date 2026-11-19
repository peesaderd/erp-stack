<template>
  <div class="pos-restodash" :class="{ 'settings-mode': viewMode === 'settings', 'sidebar-is-collapsed': isSidebarCollapsed }">

    <!-- ── TOP ALARM BANNER (When New Order, Appended Items, or Food Served) ───────── -->
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
    </transition>

    <!-- =================================================================== -->
    <!-- VIEW MODE 1: FULL-PAGE SETTINGS (หน้าการตั้งค่าระบบเต็มจอ)           -->
    <!-- =================================================================== -->
    <div v-if="viewMode === 'settings'" class="settings-fullpage">
      <!-- Settings Header Bar -->
      <header class="settings-topbar">
        <div class="settings-topbar-left">
          <button @click="viewMode = 'pos'" class="btn-back-to-pos">
            <span class="btn-back-icon">←</span>
            <span>กลับหน้าร้าน POS</span>
          </button>
          <div class="settings-title-group">
            <h1 class="settings-main-title">⚙️ ตั้งค่าร้านค้าและระบบ</h1>
            <span class="settings-sub-title">จัดการข้อมูลร้าน สต็อก สมาชิก พนักงาน เครื่องพิมพ์ และระบบกะ</span>
          </div>
        </div>

        <div class="settings-topbar-right">
          <div v-if="settingsSuccessMsg" class="settings-alert-success">
            ✓ {{ settingsSuccessMsg }}
          </div>
          <div v-if="settingsErrorMsg" class="settings-alert-error">
            ✕ {{ settingsErrorMsg }}
          </div>
          <div class="store-badge">
            <span class="store-icon">🍲</span>
            <span class="store-name">{{ shopSettings.name || 'ก๋วยเตี๋ยวคุณย่า' }}</span>
          </div>
        </div>
      </header>

      <!-- Settings Layout: Left Nav + Right Content Area -->
      <div class="settings-body-layout" :class="{ 'is-mobile-detail': mobileSettingsView === 'detail' }">
        <!-- Settings Left Sub-Navigation (List Menu on Mobile) -->
        <aside class="settings-nav-sidebar" :class="{ 'mobile-hidden': mobileSettingsView === 'detail' }">
          <div class="settings-mobile-menu-header">
            <h2 class="settings-mobile-title">⚙️ ตั้งค่าระบบ</h2>
            <p class="settings-mobile-sub">เลือกหัวข้อการตั้งค่าที่ต้องการจัดการ</p>
          </div>
          <button
            v-for="tab in settingsTabs"
            :key="tab.id"
            @click="selectSettingsTab(tab.id)"
            class="settings-nav-item"
            :class="{ 'is-active': activeSettingsTab === tab.id }"
          >
            <span class="nav-item-icon">{{ tab.icon }}</span>
            <div class="nav-item-text">
              <div class="nav-item-title">{{ tab.title }}</div>
              <div class="nav-item-desc">{{ tab.desc }}</div>
            </div>
            <span class="nav-item-arrow">›</span>
          </button>
        </aside>

        <!-- Settings Main Content Panel (Detail View on Mobile) -->
        <main class="settings-content-panel custom-scrollbar" :class="{ 'mobile-hidden': mobileSettingsView === 'menu' }">
          <!-- Mobile Back Navigation Button -->
          <div class="settings-mobile-back-bar">
            <button @click="mobileSettingsView = 'menu'" class="btn-settings-back">
              ← ย้อนกลับไปเมนูตั้งค่า
            </button>
            <span class="current-tab-badge">{{ currentSettingsTabTitle }}</span>
          </div>

          <!-- 1. ร้านค้า (Shop Information) -->
          <section v-if="activeSettingsTab === 'shop'" class="settings-card">
            <div class="card-header-row">
              <div>
                <h2 class="card-title">🏪 ข้อมูลร้านค้า & ภาษี</h2>
                <p class="card-subtitle">ข้อมูลนี้จะนำไปแสดงบนหัวใบเสร็จรับเงิน และหน้าจอสั่งอาหาร</p>
              </div>
              <button @click="saveShopSettings" :disabled="isSavingSettings" class="btn-primary-save">
                {{ isSavingSettings ? 'กำลังบันทึก...' : '💾 บันทึกข้อมูลร้าน' }}
              </button>
            </div>

            <div class="form-grid-2">
              <div class="form-group">
                <label>ชื่อร้านอาหาร *</label>
                <input v-model="shopSettings.name" class="form-input" placeholder="เช่น ก๋วยเตี๋ยวคุณย่า" />
              </div>
              <div class="form-group">
                <label>เลขประจำตัวผู้เสียภาษี (Tax ID)</label>
                <input v-model="shopSettings.tax_id" class="form-input" placeholder="เช่น 0-1055-67012-34-5" />
              </div>
              <div class="form-group span-2">
                <label>ที่อยู่ร้านค้า (แสดงบนใบเสร็จ)</label>
                <input v-model="shopSettings.address" class="form-input" placeholder="เลขที่ ถนน แขวง/ตำบล เขต/อำเภอ จังหวัด" />
              </div>
              <div class="form-group">
                <label>เบอร์โทรศัพท์ติดต่อ</label>
                <input v-model="shopSettings.phone" class="form-input" placeholder="02-xxx-xxxx หรือ 08x-xxx-xxxx" />
              </div>
              <div class="form-group">
                <label>อีเมลร้านค้า</label>
                <input v-model="shopSettings.email" class="form-input" placeholder="contact@restaurant.com" />
              </div>
              <div class="form-group">
                <label>ภาษีมูลค่าเพิ่ม VAT (%)</label>
                <input v-model.number="shopSettings.vat" type="number" class="form-input" placeholder="7" />
              </div>
              <div class="form-group">
                <label>Service Charge (%)</label>
                <input v-model.number="shopSettings.service_charge" type="number" class="form-input" placeholder="0" />
              </div>
              <div class="form-group">
                <label>เวลาเปิดร้าน</label>
                <input v-model="shopSettings.open_time" type="time" class="form-input" />
              </div>
              <div class="form-group">
                <label>เวลาปิดร้าน</label>
                <input v-model="shopSettings.close_time" type="time" class="form-input" />
              </div>
            </div>
          </section>

          <!-- 2. สต็อกวัตถุดิบ (Inventory) -->
          <section v-if="activeSettingsTab === 'inventory'" class="settings-card">
            <div class="card-header-row">
              <div>
                <h2 class="card-title">📦 จัดการคลังสต็อกวัตถุดิบ</h2>
                <p class="card-subtitle">ตรวจสอบจำนวนคงเหลือ จุดสั่งซื้อขั้นต่ำ และต้นทุนวัตถุดิบ</p>
              </div>
              <button @click="openAddInventoryModal" class="btn-primary-add">
                + เพิ่มวัตถุดิบใหม่
              </button>
            </div>

            <div class="table-responsive">
              <table class="settings-table">
                <thead>
                  <tr>
                    <th>ชื่อวัตถุดิบ</th>
                    <th>หมวดหมู่</th>
                    <th>หน่วยนับ</th>
                    <th>คงเหลือ</th>
                    <th>ขั้นต่ำเตือน</th>
                    <th>ต้นทุน/หน่วย</th>
                    <th>สถานะ</th>
                    <th>จัดการ</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="inv in inventoryList" :key="inv.id">
                    <td class="font-bold">{{ inv.name }}</td>
                    <td><span class="badge-sub">{{ inv.category || 'ทั่วไป' }}</span></td>
                    <td>{{ inv.unit || 'ชิ้น' }}</td>
                    <td :class="{ 'text-red': inv.stock <= inv.min_stock, 'font-bold': true }">
                      {{ inv.stock }}
                    </td>
                    <td>{{ inv.min_stock }}</td>
                    <td>฿{{ formatBaht(inv.cost || 0) }}</td>
                    <td>
                      <span v-if="inv.stock <= inv.min_stock" class="badge-alert">ใกล้หมด</span>
                      <span v-else class="badge-success">ปกติ</span>
                    </td>
                    <td>
                      <button @click="removeInventoryItem(inv.id)" class="btn-sm-del">🗑️</button>
                    </td>
                  </tr>
                  <tr v-if="inventoryList.length === 0">
                    <td colspan="8" class="text-center text-muted py-6">ยังไม่มีข้อมูลวัตถุดิบในระบบ</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- 3. สมาชิก & แต้ม CRM (Members) -->
          <section v-if="activeSettingsTab === 'members'" class="settings-card">
            <div class="card-header-row">
              <div>
                <h2 class="card-title">👥 ระบบสมาชิก & ลูกค้าสัมพันธ์ (CRM)</h2>
                <p class="card-subtitle">ข้อมูลสมาชิกร้าน เบอร์โทร และแต้มสะสมสำหรับแลกส่วนลด</p>
              </div>
              <button @click="openAddMemberModal" class="btn-primary-add">
                + เพิ่มสมาชิกใหม่
              </button>
            </div>

            <div class="table-responsive">
              <table class="settings-table">
                <thead>
                  <tr>
                    <th>ชื่อสมาชิก</th>
                    <th>เบอร์โทรศัพท์</th>
                    <th>อีเมล</th>
                    <th>ระดับ (Tier)</th>
                    <th>แต้มสะสม</th>
                    <th>จัดการ</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="mem in membersList" :key="mem.id">
                    <td class="font-bold">{{ mem.name }}</td>
                    <td class="font-mono">{{ mem.phone }}</td>
                    <td>{{ mem.email || '-' }}</td>
                    <td><span class="badge-tier">{{ mem.tier || 'Regular' }}</span></td>
                    <td class="font-bold text-blue">{{ mem.points || 0 }} แต้ม</td>
                    <td>
                      <button @click="removeMemberItem(mem.id)" class="btn-sm-del">🗑️</button>
                    </td>
                  </tr>
                  <tr v-if="membersList.length === 0">
                    <td colspan="6" class="text-center text-muted py-6">ยังไม่มีข้อมูลสมาชิกในระบบ</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- 4. พนักงาน & สิทธิ์ PIN (Staff) -->
          <section v-if="activeSettingsTab === 'staff'" class="settings-card">
            <div class="card-header-row">
              <div>
                <h2 class="card-title">🪪 พนักงาน & สิทธิ์การเข้าถึง</h2>
                <p class="card-subtitle">จัดการรายชื่อพนักงาน แคชเชียร์ และรหัส PIN ความปลอดภัย</p>
              </div>
              <button @click="openAddStaffModal" class="btn-primary-add">
                + เพิ่มพนักงาน
              </button>
            </div>

            <div class="table-responsive">
              <table class="settings-table">
                <thead>
                  <tr>
                    <th>ชื่อพนักงาน</th>
                    <th>ตำแหน่ง / บทบาท</th>
                    <th>เบอร์โทรศัพท์</th>
                    <th>รหัส PIN</th>
                    <th>จัดการ</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="st in staffList" :key="st.id">
                    <td class="font-bold">{{ st.name }}</td>
                    <td><span class="badge-role">{{ st.role || 'พนักงานเสิร์ฟ' }}</span></td>
                    <td>{{ st.phone || '-' }}</td>
                    <td class="font-mono text-muted">••••</td>
                    <td>
                      <button @click="removeStaffItem(st.id)" class="btn-sm-del">🗑️ ลบ</button>
                    </td>
                  </tr>
                  <tr v-if="staffList.length === 0">
                    <td colspan="5" class="text-center text-muted py-6">ยังไม่มีข้อมูลพนักงาน</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- 5. แต้มสะสม & รางวัล (Rewards) -->
          <section v-if="activeSettingsTab === 'rewards'" class="settings-card">
            <div class="card-header-row">
              <div>
                <h2 class="card-title">🎁 แต้มสะสม & ของรางวัล</h2>
                <p class="card-subtitle">กำหนดเงื่อนไขการใช้แต้มแลกส่วนลดค่าอาหาร</p>
              </div>
              <button @click="openAddRewardModal" class="btn-primary-add">
                + เพิ่มรางวัล
              </button>
            </div>

            <div class="table-responsive">
              <table class="settings-table">
                <thead>
                  <tr>
                    <th>ชื่อของรางวัล</th>
                    <th>แต้มที่ต้องใช้</th>
                    <th>ประเภทส่วนลด</th>
                    <th>มูลค่าส่วนลด</th>
                    <th>รายละเอียด</th>
                    <th>จัดการ</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="rw in rewardsList" :key="rw.id">
                    <td class="font-bold">{{ rw.name }}</td>
                    <td class="font-bold text-purple">{{ rw.points_required }} แต้ม</td>
                    <td>{{ rw.discount_type === 'percent' ? 'เปอร์เซ็นต์ (%)' : 'บาท (Fixed)' }}</td>
                    <td class="font-bold text-green">
                      {{ rw.discount_type === 'percent' ? `${rw.discount_value}%` : `฿${formatBaht(rw.discount_value)}` }}
                    </td>
                    <td>{{ rw.description || '-' }}</td>
                    <td>
                      <button @click="removeRewardItem(rw.id)" class="btn-sm-del">🗑️ ลบ</button>
                    </td>
                  </tr>
                  <tr v-if="rewardsList.length === 0">
                    <td colspan="6" class="text-center text-muted py-6">ยังไม่มีรายการของรางวัล</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- 6. เครื่องพิมพ์ใบเสร็จ (Printers) -->
          <section v-if="activeSettingsTab === 'printer'" class="settings-card">
            <div class="card-header-row">
              <div>
                <h2 class="card-title">🖨️ เครื่องพิมพ์ใบเสร็จ & การพิมพ์</h2>
                <p class="card-subtitle">ตั้งค่ากระดาษความร้อน Thermal Printer และระบบพิมพ์อัตโนมัติ</p>
              </div>
              <button @click="saveShopSettings" class="btn-primary-save">
                💾 บันทึกการตั้งค่าพิมพ์
              </button>
            </div>

            <div class="form-grid-2">
              <div class="form-group">
                <label>ประเภทเครื่องพิมพ์</label>
                <select v-model="shopSettings.printer_type" class="form-input">
                  <option value="thermal">Thermal Printer (กระดาษความร้อน 80mm)</option>
                  <option value="thermal58">Thermal Printer (กระดาษความร้อน 58mm)</option>
                  <option value="network">Network IP Printer (LAN / Wi-Fi)</option>
                  <option value="browser">พิมพ์ผ่านหน้าต่างบราวเซอร์ (Standard Dialog)</option>
                </select>
              </div>
              <div class="form-group">
                <label>พอร์ต / ที่อยู่ IP เครื่องพิมพ์</label>
                <input v-model="shopSettings.printer_port" class="form-input" placeholder="/dev/usb/lp0 หรือ 192.168.1.200:9100" />
              </div>
              <div class="form-group span-2">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="shopSettings.auto_print" />
                  <span>พิมพ์ใบเสร็จอัตโนมัติทันทีเมื่อชำระเงินสำเร็จ (Auto Print on Payment)</span>
                </label>
              </div>
            </div>
          </section>

          <!-- 7. QR Code สั่งอาหาร (Table QR Codes with 2 Print Templates) -->
          <section v-if="activeSettingsTab === 'qr'" class="settings-card">
            <div class="card-header-row">
              <div>
                <h2 class="card-title">📱 QR Code ประจำโต๊ะอาหาร</h2>
                <p class="card-subtitle">สแกนเพื่อเปิดเมนูสั่งอาหารผ่านมือถือลูกค้า เลือกพิมพ์ได้ 2 รูปแบบ</p>
              </div>

              <!-- Template Mode Selector -->
              <div class="qr-template-selector">
                <span class="selector-label">รูปแบบป้ายพิมพ์:</span>
                <button
                  @click="qrPrintTemplate = 'clean'"
                  class="btn-template-toggle"
                  :class="{ 'is-active': qrPrintTemplate === 'clean' }"
                >
                  🏷️ แบบ QR อย่างเดียว
                </button>
                <button
                  @click="qrPrintTemplate = 'with_menu'"
                  class="btn-template-toggle"
                  :class="{ 'is-active': qrPrintTemplate === 'with_menu' }"
                >
                  🍲 แบบ QR + รูปเมนูแนะนำ
                </button>
              </div>
            </div>

            <div class="qr-tables-grid">
              <div v-for="tb in tables" :key="tb.id" class="table-qr-card">
                <div class="qr-card-header">
                  <span class="qr-table-num">{{ tb.name }}</span>
                  <span class="qr-zone-pill">{{ tb.zone || 'Indoor' }}</span>
                </div>
                <div class="qr-preview-box">
                  <img
                    :src="getTableQrUrl(tb.id)"
                    alt="Table QR"
                    class="qr-img"
                  />
                </div>
                <div class="qr-url-text">pos.m2igen.com/customer/{{ tb.id }}</div>

                <!-- Template Preview Hint -->
                <div class="qr-template-hint">
                  {{ qrPrintTemplate === 'with_menu' ? '✨ ป้ายพร้อมภาพเมนูแนะนำ' : '🏷️ ป้ายสไตล์มินิมอล' }}
                </div>

                <button @click="openTableQrPrintModal(tb)" class="btn-qr-print">
                  🖨️ พิมพ์ป้ายโต๊ะนี้
                </button>
              </div>
            </div>
          </section>

          <!-- 8. จัดการกะ (Shift Management) -->
          <section v-if="activeSettingsTab === 'shift'" class="settings-card">
            <div class="card-header-row">
              <div>
                <h2 class="card-title">🕒 จัดการรอบกะการขาย (Shift Management)</h2>
                <p class="card-subtitle">เปิดกะ นับเงินสดตั้งต้น (Float) และสรุปยอดส่งกะประจำวัน</p>
              </div>
            </div>

            <div class="shift-dashboard-box">
              <div class="shift-kpi-grid">
                <div class="shift-kpi-card">
                  <div class="kpi-label">สถานะกะปัจจุบัน</div>
                  <div class="kpi-val text-green">🟢 กำลังเปิดกะขาย</div>
                </div>
                <div class="shift-kpi-card">
                  <div class="kpi-label">เงินทอนตั้งต้น (Float)</div>
                  <div class="kpi-val text-blue">฿1,000.00</div>
                </div>
                <div class="shift-kpi-card">
                  <div class="kpi-label">ยอดขายเงินสดในกะ</div>
                  <div class="kpi-val text-purple">฿{{ formatBaht(reportStats.totalSales) }}</div>
                </div>
                <div class="shift-kpi-card">
                  <div class="kpi-label">จำนวนบิลทั้งหมด</div>
                  <div class="kpi-val">{{ reportStats.totalBills }} บิล</div>
                </div>
              </div>

              <div class="shift-actions-row">
                <button @click="closeCurrentShift" class="btn-shift-close">
                  🔒 ปิดกะ & สรุปยอดขาย
                </button>
              </div>
            </div>
          </section>

</main>
      </div>
    </div>

    <!-- =================================================================== -->
    <!-- VIEW MODE 2: MAIN POS INTERFACE                                     -->
    <!-- =================================================================== -->
    <template v-else>

      <!-- ── LEFT SIDEBAR (Completely Hides When Collapsed) ─────────────── -->
      <aside v-if="!isSidebarCollapsed" class="pos-sidebar-left">
        <!-- Brand & Store Title -->
        <div class="brand-box">
          <div class="brand-avatar">🍲</div>
          <div class="brand-info">
            <div class="brand-title">{{ shopSettings.name || 'ก๋วยเตี๋ยวคุณย่า' }}</div>
            <div class="brand-sub">Smart POS System</div>
          </div>
        </div>

        <!-- Selected Table / Mode Display (Must Pick Table or Takeaway) -->
        <div
          class="table-chip-box"
          :class="{ 'is-empty': !selectedTableId && orderType !== 'takeaway' }"
          @click="showTableModal = true"
        >
          <div class="table-chip-label">
            <span>{{ currentTableDisplayTitle }}</span>
            <span class="table-chip-change">{{ (selectedTableId || orderType === 'takeaway') ? 'เปลี่ยน ▾' : 'เลือกโต๊ะ ▾' }}</span>
          </div>
          <div class="table-chip-num">
            {{ currentTableDisplayName }}
          </div>
          <div class="table-chip-type">
            {{ currentTableSubText }}
          </div>
        </div>

        <!-- Live Clock & Date -->
        <div class="clock-box">
          <div class="clock-time">{{ clockTime }}</div>
          <div class="clock-date">{{ clockDate }}</div>
        </div>

        <!-- Food Categories List (Clean Sidebar View) -->
        <div class="category-nav-box custom-scrollbar">
          <div class="category-nav-header">หมวดหมู่อาหาร</div>
          <button
            v-for="cat in categoryList"
            :key="cat.name"
            @click="activeCat = cat.name"
            class="category-btn"
            :class="{ 'is-active': activeCat === cat.name }"
          >
            <span class="cat-label">
              <span class="cat-icon">{{ cat.icon }}</span>
              <span>{{ cat.name }}</span>
            </span>
            <span class="cat-count-pill">{{ cat.count }}</span>
          </button>
        </div>

        <!-- Bottom Controls: Settings Page Direct + Collapse Button -->
        <div class="sidebar-bottom">
          <button @click="viewMode = 'settings'" class="system-menu-btn" title="เปิดหน้าต่างการตั้งค่าร้านค้า & ระบบ">
            <span>⚙️</span>
            <span>การตั้งค่าร้านค้า & ระบบ</span>
          </button>
          <!-- Collapse Button Relocated to Bottom so it does NOT overlap with Logo -->
          <button @click="isSidebarCollapsed = true" class="sidebar-collapse-bottom-btn" title="ย่อเก็บแถบเมนูด้านซ้าย">
            <span>◀ ซ่อนแถบเมนู</span>
          </button>
        </div>
      </aside>

      <!-- Floating Expand Button on Main Screen (Visible When Sidebar Collapsed) -->
      <button
        v-if="isSidebarCollapsed"
        @click="isSidebarCollapsed = false"
        class="floating-sidebar-expand-btn"
        title="แสดงแถบเมนูด้านซ้าย (Show Sidebar)"
      >
        <span class="expand-icon">☰</span>
        <span class="expand-text">เปิดเมนู ▶</span>
      </button>

      <!-- ── CENTER: Menu Grid & Horizontal Category Slider ────────────────── -->
      <main class="pos-center-main">
        <!-- Top Search & Quick Actions Bar -->
        <header class="center-topbar">
          <div class="search-box-wrapper">
            <span class="search-icon">🔍</span>
            <input
              v-model="search"
              placeholder="ค้นหาเมนูอาหาร (ชื่อจาน, รหัส, หมวดหมู่)..."
              class="search-input"
            />
            <button v-if="search" @click="search = ''" class="search-clear-btn">✕</button>
          </div>

          <div class="topbar-actions">
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
          </div>
        </header>

        <!-- ── HORIZONTAL CATEGORY SLIDE BAR (Above Thumbnails) ─────────── -->
        <nav class="category-slide-bar custom-scrollbar">
          <button
            v-for="cat in categoryList"
            :key="cat.name"
            @click="activeCat = cat.name"
            class="slide-cat-tab"
            :class="{ 'is-active': activeCat === cat.name }"
          >
            <span class="slide-cat-icon">{{ cat.icon }}</span>
            <span class="slide-cat-name">{{ cat.name }}</span>
            <span class="slide-cat-count">{{ cat.count }}</span>
          </button>
        </nav>

        <!-- Food Items Grid Area (With Real Photos from /images/menu/) -->
        <div class="food-scroll-container custom-scrollbar">
          <div v-if="loading" class="state-container">
            <div class="spinner"></div>
            <div class="state-text">กำลังโหลดเมนูอาหาร...</div>
          </div>

          <div v-else-if="filteredMenu.length === 0" class="state-container">
            <div class="empty-icon">🍽️</div>
            <div class="empty-title">ไม่พบเมนูที่ค้นหา</div>
            <div class="empty-sub">ลองเปลี่ยนคำค้นหา หรือเลือกหมวดหมู่อื่น</div>
            <button @click="search = ''; activeCat = 'ทั้งหมด'" class="reset-filter-btn">
              ดูเมนูทั้งหมด
            </button>
          </div>

          <div v-else class="food-grid">
            <div
              v-for="item in filteredMenu"
              :key="item.id"
              class="food-card"
              @click="handleFoodCardClick(item)"
            >
              <!-- Food Image Thumbnail Wrap (Real Photos Enabled) -->
              <div class="food-thumb-wrap">
                <img
                  v-if="item.image || item.image_url"
                  :src="item.image || item.image_url"
                  :alt="item.name"
                  class="food-img"
                  loading="lazy"
                  @error="onImgError"
                />
                <div class="food-img-fallback" :style="{ display: (item.image || item.image_url) ? 'none' : 'flex' }">
                  {{ getCatEmoji(item.category) }}
                </div>
                <span class="food-badge-cat">{{ item.category || 'ทั่วไป' }}</span>
              </div>

              <div class="food-info">
                <div class="food-name" :title="item.name">{{ item.name }}</div>
                <div class="food-meta">
                  <span class="food-price">฿{{ formatBaht(item.price) }}</span>
                  <button class="food-add-btn" title="เพิ่มลงตะกร้า">+</button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Floating Cart Bar for Mobile (Bottom Sticky Bar with Direct Checkout) -->
        <div
          v-if="viewMode === 'pos' && cart.length > 0"
          class="mobile-floating-cart-bar"
        >
          <!-- Left: View Cart Items -->
          <div @click="isMobileCartOpen = true" class="m-cart-summary-btn" role="button">
            <span class="m-cart-icon">🛒</span>
            <div class="m-cart-info">
              <span class="m-cart-text">ตะกร้า ({{ cartTotalQty }} จาน)</span>
              <span class="m-cart-total">฿{{ formatBaht(cartGrandTotal) }}</span>
            </div>
            <span class="m-cart-arrow">▲ ดูตะกร้า</span>
          </div>

          <!-- Right: DIRECT CHECKOUT BUTTON (NO DRAWER NEEDED!) -->
          <button
            type="button"
            @click.stop="openPaymentModal('Cash')"
            class="m-cart-direct-pay-btn"
            title="คิดเงินทันทีโดยไม่ต้องเปิดตะกร้า"
          >
            <span>💳 คิดเงิน</span>
          </button>
        </div>
      </main>

      <!-- ── RIGHT SIDEBAR: Order Summary / Cart ───────────────────────── -->
      <!-- Mobile Cart Backdrop -->
      <div
        v-if="isMobileCartOpen"
        @click="isMobileCartOpen = false"
        class="mobile-cart-backdrop"
      ></div>

      <aside class="pos-sidebar-right" :class="{ 'is-mobile-open': isMobileCartOpen }">
        <!-- Cart Header -->
        <div class="cart-header">
          <div class="cart-title-row">
            <div class="cart-title">
              <span>🧾 รายการสั่งอาหาร</span>
              <span class="cart-badge">{{ cartTotalQty }}</span>
              <button @click="isMobileCartOpen = false" class="mobile-cart-close-btn" title="ปิดตะกร้า">✕ ปิด</button>
            </div>

            <!-- Cart Header Actions: Unpaid Orders Button & Clear Cart -->
            <div class="cart-title-actions">
              <button
                @click="openUnpaidOrdersModal"
                class="btn-cart-unpaid"
                title="ดูรายการออเดอร์ค้างชำระ / ประวัติบิล"
              >
                <span>📋 ค้างชำระ</span>
                <span v-if="unpaidOrdersCount > 0" class="unpaid-badge-pill">{{ unpaidOrdersCount }}</span>
              </button>

              <button
                v-if="cart.length > 0"
                @click="clearCart"
                class="clear-cart-btn"
                title="ล้างรายการทั้งหมด"
              >
                ล้าง
              </button>
            </div>
          </div>

          <!-- Active Checkout Order Banner (When checking out an existing unpaid order) -->
          <div v-if="activeCheckoutOrder" class="active-order-banner">
            <div class="active-order-left">
              <span class="active-order-pulse">●</span>
              <span class="active-order-title">ชำระบิล #{{ activeCheckoutOrder.order_id.slice(-6) }}</span>
              <span class="active-order-sub">({{ activeCheckoutOrder.table_name || (activeCheckoutOrder.table_id === 'takeaway' ? 'กลับบ้าน' : `โต๊ะ ${activeCheckoutOrder.table_id}`) }})</span>
            </div>
            <button @click="clearActiveCheckoutOrder" class="active-order-clear-btn" title="ยกเลิกการดึงออเดอร์นี้ แล้วเริ่มบิลใหม่">✕ บิลใหม่</button>
          </div>

          <!-- Order Type Switcher in Cart -->
          <div class="order-type-switch">
            <button
              class="type-btn"
              :class="{ 'is-active': orderType !== 'takeaway' }"
              @click="setOrderType('dinein')"
            >
              🍽️ ทานที่ร้าน ({{ selectedTableId ? `โต๊ะ ${selectedTableId}` : 'เลือกโต๊ะ' }})
            </button>
            <button
              class="type-btn"
              :class="{ 'is-active': orderType === 'takeaway' }"
              @click="setOrderType('takeaway')"
            >
              📦 สั่งกลับบ้าน
            </button>
          </div>
        </div>

        <!-- Cart Items List -->
        <div class="cart-items-container custom-scrollbar">
          <div v-if="cart.length === 0" class="cart-empty-state">
            <div class="cart-empty-icon">🛒</div>
            <div class="cart-empty-text">ยังไม่มีรายการอาหาร</div>
            <div class="cart-empty-sub">
              {{ (!selectedTableId && orderType !== 'takeaway') ? 'กรุณาเลือกโต๊ะ หรือสั่งกลับบ้านก่อน' : 'แตะที่เมนูอาหารเพื่อสั่ง' }}
            </div>
          </div>

          <div v-else class="cart-item-list">
            <div
              v-for="(item, idx) in cart"
              :key="idx"
              class="cart-item-row"
            >
              <div class="cart-item-details">
                <div class="cart-item-name">{{ item.name }}</div>
                <div class="cart-item-sub">฿{{ formatBaht(item.price) }} / จาน</div>
                <!-- Note Trigger Button -->
                <button
                  type="button"
                  @click="openItemNoteModal(item, idx)"
                  class="cart-item-note-btn"
                  :class="{ 'has-note': !!item.notes }"
                >
                  <span v-if="item.notes" class="note-btn-content">
                    <span class="note-icon">📝</span>
                    <span class="note-text-snippet">{{ item.notes }}</span>
                    <span class="note-edit-tag">แก้ไข</span>
                  </span>
                  <span v-else class="note-btn-content">
                    <span class="note-icon">➕</span>
                    <span>เพิ่มโน้ต / รายละเอียด</span>
                  </span>
                </button>
              </div>

              <div class="cart-item-control">
                <div class="qty-control-box">
                  <button @click="decreaseQty(idx)" class="qty-btn minus">-</button>
                  <span class="qty-num">{{ item.quantity }}</span>
                  <button @click="increaseQty(idx)" class="qty-btn plus">+</button>
                </div>
                <div class="cart-item-line-total">
                  ฿{{ formatBaht(item.price * item.quantity) }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Cart Financial Summary -->
        <div class="cart-footer">
          <div class="financial-row">
            <span>รวมค่าอาหาร (Subtotal)</span>
            <span>฿{{ formatBaht(cartSubtotal) }}</span>
          </div>
          <div class="financial-row vat-row">
            <span>ภาษีมูลค่าเพิ่ม VAT (7%)</span>
            <span>฿{{ formatBaht(cartVat) }}</span>
          </div>
          <div class="financial-row total-row">
            <span>ยอดสุทธิ (Total)</span>
            <span class="grand-total-amount">฿{{ formatBaht(cartGrandTotal) }}</span>
          </div>

          <!-- Checkout Buttons -->
          <div class="checkout-actions-grid">
            <button
              :disabled="cart.length === 0 || isSubmitting"
              @click="openPaymentModal('PromptPay')"
              class="btn-pay-qr"
            >
              <span>📱 สแกน QR</span>
            </button>
            <button
              :disabled="cart.length === 0 || isSubmitting"
              @click="openPaymentModal('Cash')"
              class="btn-pay-cash"
            >
              <span>💵 เงินสด</span>
            </button>
          </div>

          <!-- Hold / Send to Kitchen Button -->
          <button
            :disabled="cart.length === 0 || isSubmitting"
            @click="sendOrderToKitchenOnly"
            class="btn-send-kitchen"
          >
            <span>🍳 ส่งเข้าครัว (ยังไม่ชำระเงิน)</span>
          </button>
        </div>
      </aside>

    </template>

    <!-- =================================================================== -->
    <!-- MODAL 0: ITEM NOTES & SPECIAL REQUESTS POPUP                        -->
    <!-- =================================================================== -->
    <div v-if="showNoteModal" class="pos-modal-overlay note-modal-overlay" @click.self="showNoteModal = false">
      <div class="pos-modal-box note-modal-box">
        <div class="modal-header">
          <div>
            <div class="modal-title">📝 ระบุโน้ต / รายละเอียดพิเศษ</div>
            <div class="modal-sub">{{ editingItem?.name }} (฿{{ formatBaht(editingItem?.price) }})</div>
          </div>
          <button @click="showNoteModal = false" class="modal-close-btn" title="ปิด">✕</button>
        </div>

        <div class="modal-body note-modal-body">
          <!-- Quick Preset Chips -->
          <div class="quick-notes-label">ตัวเลือกด่วนยอดนิยม (แตะเพื่อเพิ่ม):</div>
          <div class="quick-notes-chips custom-scrollbar">
            <button
              v-for="chip in quickNoteChips"
              :key="chip"
              type="button"
              @click="toggleQuickNote(chip)"
              class="quick-note-chip"
              :class="{ 'is-selected': isChipSelected(chip) }"
            >
              {{ chip }}
            </button>
          </div>

          <!-- Note Input Field -->
          <div class="note-input-group">
            <label class="note-field-label">ข้อความหมายเหตุ:</label>
            <textarea
              v-model="itemNoteText"
              class="note-textarea custom-scrollbar"
              rows="3"
              placeholder="เช่น ไม่ใส่ผัก, เผ็ดน้อย, หวาน 50%, แยกน้ำ..."
            ></textarea>
          </div>
        </div>

        <div class="modal-footer note-modal-footer">
          <button type="button" @click="clearCurrentNote" class="btn-clear-note">
            🗑️ ลบโน้ต
          </button>
          <button type="button" @click="saveItemNote" class="btn-save-note">
            ✓ บันทึกโน้ต
          </button>
        </div>
      </div>
    </div>

    <!-- =================================================================== -->
    <!-- MODAL 1: SELECT TABLE OR TAKEAWAY FIRST                             -->
    <!-- =================================================================== -->
    <div v-if="showTableModal" class="pos-modal-overlay" @click.self="showTableModal = false">
      <div class="pos-modal-box table-select-modal">
        <div class="modal-header">
          <div>
            <div class="modal-title">🪑 เลือกโต๊ะ หรือ เลือกสั่งกลับบ้าน</div>
            <div class="modal-sub">กรุณาเลือกโต๊ะ หรือเลือกประเภทสั่งกลับบ้าน เพื่อเริ่มต้นรับออเดอร์</div>
          </div>
          <button @click="showTableModal = false" class="modal-close-btn">✕</button>
        </div>

        <!-- Takeaway Big Card -->
        <div
          class="takeaway-option-card"
          :class="{ 'is-selected': orderType === 'takeaway' }"
          @click="selectTakeaway"
        >
          <div class="takeaway-icon">📦</div>
          <div class="takeaway-info">
            <div class="takeaway-title">สั่งกลับบ้าน (Takeaway)</div>
            <div class="takeaway-desc">สำหรับลูกค้ารับหน้าร้าน หรือสั่งใส่กล่องกลับบ้าน</div>
          </div>
          <div v-if="getTableActiveOrder('takeaway')" class="table-card-unpaid-box">
            <div class="table-unpaid-sum">
              ฿{{ formatBaht(getOrderDisplayTotal(getTableActiveOrder('takeaway'))) }}
            </div>
            <button
              @click.stop="checkoutTableDirect('takeaway')"
              class="btn-table-checkout-direct"
              title="คิดเงินสั่งกลับบ้านทันที"
            >
              💳 คิดเงิน
            </button>
          </div>
          <button v-else class="takeaway-select-btn">
            {{ orderType === 'takeaway' ? '✓ เลือกอยู่' : 'เลือกกลับบ้าน' }}
          </button>
        </div>

        <div class="table-modal-divider">
          <span>หรือ เลือกโต๊ะนั่งทานในร้าน (Dine-in)</span>
        </div>

        <!-- Zone Filters -->
        <div class="zone-filter-row">
          <button
            v-for="z in zoneOptions"
            :key="z"
            @click="selectedZone = z"
            class="zone-btn"
            :class="{ 'is-active': selectedZone === z }"
          >
            {{ z }}
          </button>
        </div>

        <!-- Table Grid -->
        <div class="tables-grid custom-scrollbar">
          <div
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
                {{ tb.status === 'served' ? '🟢 เสิร์ฟครบแล้ว' : (tb.status === 'occupied' ? 'กำลังทาน' : 'ว่าง') }}
              </span>
            </div>

            <!-- Direct Table Checkout Action if Unpaid Order Exists -->
            <div v-if="getTableActiveOrder(tb.id)" class="table-card-unpaid-box">
              <div class="table-unpaid-sum">
                ฿{{ formatBaht(getOrderDisplayTotal(getTableActiveOrder(tb.id))) }}
              </div>
              <button
                @click.stop="checkoutTableDirect(tb.id)"
                class="btn-table-checkout-direct"
                title="คิดเงินโต๊ะนี้ทันที"
              >
                💳 คิดเงิน
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- =================================================================== -->
    <!-- MODAL 2: PAYMENT & CHECKOUT (Wide 2-Column with Top-Right Total Due)  -->
    <!-- =================================================================== -->
    <div v-if="showPaymentModal" class="pos-modal-overlay" @click.self="showPaymentModal = false">
      <div class="pos-modal-box payment-modal payment-modal-wide">
        <!-- Modal Header with Single-Row Mobile Layout & Top-Right Balance Hero on Desktop -->
        <div class="modal-header payment-modal-header">
          <!-- Desktop Left Header Block -->
          <div class="payment-header-left desktop-only-header-block">
            <div class="modal-title">💳 ชำระเงิน / เช็คบิล</div>
            <div class="modal-sub">
              {{ orderType === 'takeaway' ? '📦 สั่งกลับบ้าน' : `🪑 โต๊ะ ${selectedTableId}` }}
              <template v-if="activeCheckoutOrder">
                • ออเดอร์ <b class="text-blue">#{{ activeCheckoutOrder.order_id.slice(-6) }}</b>
              </template>
              • {{ cart.length }} รายการ ({{ cartTotalQty }} จาน)
            </div>
          </div>

          <!-- Mobile Single-Row Header Block (Clean, uncompressed single row) -->
          <div class="payment-header-mobile-single-row mobile-only-header-block">
            <span class="m-header-title">💳 ชำระเงิน</span>
            <span class="m-header-sep">•</span>
            <span class="m-header-target-chip">{{ orderType === 'takeaway' ? '📦 กลับบ้าน' : `🪑 โต๊ะ ${selectedTableId}` }}</span>
            <span class="m-header-sep">•</span>
            <span class="m-header-total-chip">฿{{ formatBaht(cartGrandTotal) }}</span>
          </div>

          <!-- YOD KHANG JAI TOP RIGHT (Hero Badge - Desktop Only) -->
          <div class="header-outstanding-balance-box desktop-only-hero">
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
            :disabled="isSubmitting || (selectedPaymentMethod === 'Cash' && cashChange < -0.50)"
            @click="submitPayment"
            class="btn-confirm-pay"
          >
            {{ isSubmitting ? 'กำลังบันทึก...' : `ยืนยันการชำระเงิน • ฿${formatBaht(cartGrandTotal)}` }}
          </button>
        </div>
      </div>
    </div>

    <!-- =================================================================== -->
    <!-- MODAL 3: FULL THERMAL RECEIPT<!-- =================================================================== -->
    <!-- MODAL 3: FULL THERMAL RECEIPT & ORDER EDIT / VOID MODAL             -->
    <!-- =================================================================== -->
    <div v-if="showReceiptModal && lastCompletedOrder" class="pos-modal-overlay" @click.self="showReceiptModal = false">
      <div class="pos-modal-box receipt-modal-box">
        <div class="modal-header no-print">
          <div>
            <div class="modal-title">🧾 ใบเสร็จรับเงิน / ใบกำกับภาษีอย่างย่อ</div>
            <div class="modal-sub">ชำระเงินสำเร็จเรียบร้อยแล้ว</div>
          </div>
          <button @click="showReceiptModal = false" class="modal-close-btn">✕</button>
        </div>

        <!-- Thermal Receipt Body (Printable 80mm format) -->
        <div id="printable-receipt" class="thermal-receipt">
          <div class="receipt-header">
            <div class="receipt-store-logo">🍲</div>
            <div class="receipt-store-name">{{ shopSettings.name || 'ก๋วยเตี๋ยวคุณย่า' }}</div>
            <div class="receipt-store-sub">Smart POS System</div>
            <div class="receipt-store-tax">เลขประจำตัวผู้เสียภาษี: {{ shopSettings.tax_id || '0-1055-67012-34-5' }}</div>
            <div class="receipt-store-addr">{{ shopSettings.address || 'กรุงเทพมหานคร' }}</div>
            <div class="receipt-store-phone">โทร: {{ shopSettings.phone || '02-123-4567' }}</div>
          </div>

          <div class="receipt-divider-dashed"></div>

          <div class="receipt-meta-grid">
            <div><b>เลขที่บิล:</b> {{ lastCompletedOrder.order_id || 'ORD-NEW' }}</div>
            <div><b>วันที่:</b> {{ formatDateTime(lastCompletedOrder.created_at) }}</div>
            <div><b>โต๊ะ:</b> {{ lastCompletedOrder.table_name || (orderType === 'takeaway' ? 'สั่งกลับบ้าน' : `โต๊ะ ${selectedTableId}`) }}</div>
            <div><b>พนักงาน:</b> แคชเชียร์</div>
          </div>

          <div class="receipt-divider-dashed"></div>

          <!-- Itemized Lines -->
          <table class="receipt-items-table">
            <thead>
              <tr>
                <th class="col-item">รายการ</th>
                <th class="col-qty">จน.</th>
                <th class="col-price">ราคา</th>
                <th class="col-total">รวม</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(it, iIdx) in lastCompletedOrder.items" :key="iIdx">
                <td class="col-item">{{ it.name }}</td>
                <td class="col-qty">{{ it.quantity }}</td>
                <td class="col-price">{{ formatBaht(it.price) }}</td>
                <td class="col-total">{{ formatBaht(it.price * it.quantity) }}</td>
              </tr>
            </tbody>
          </table>

          <div class="receipt-divider-dashed"></div>

          <!-- Total Breakdown -->
          <div class="receipt-summary-box">
            <div class="receipt-sum-row">
              <span>รวมเป็นเงิน:</span>
              <span>฿{{ formatBaht(lastCompletedOrder.subtotal || lastCompletedOrder.total * 100 / 107) }}</span>
            </div>
            <div class="receipt-sum-row">
              <span>ภาษีมูลค่าเพิ่ม 7%:</span>
              <span>฿{{ formatBaht(lastCompletedOrder.vat || lastCompletedOrder.total * 7 / 107) }}</span>
            </div>
            <div class="receipt-sum-row receipt-grand-total">
              <span>ยอดสุทธิ:</span>
              <span>฿{{ formatBaht(lastCompletedOrder.total) }}</span>
            </div>
            <div class="receipt-sum-row">
              <span>ชำระโดย:</span>
              <span>{{ lastCompletedOrder.payment_method || 'เงินสด' }}</span>
            </div>
            <div v-if="lastCompletedOrder.cash_received" class="receipt-sum-row">
              <span>รับเงินมา:</span>
              <span>฿{{ formatBaht(lastCompletedOrder.cash_received) }}</span>
            </div>
            <div v-if="lastCompletedOrder.change !== undefined" class="receipt-sum-row">
              <span>เงินทอน:</span>
              <span>฿{{ formatBaht(lastCompletedOrder.change) }}</span>
            </div>
          </div>

          <div class="receipt-divider-dashed"></div>

          <div class="receipt-footer">
            <div class="thank-you-text">🙏 ขอบพระคุณที่ใช้บริการ 🙏</div>
            <div class="wifi-info">Wi-Fi: Grandmother-Noodle • Password: 88888888</div>
          </div>
        </div>

        <!-- Receipt Action Buttons (Print, Void/Edit, Next Order) -->
        <div class="receipt-actions-footer no-print">
          <button @click="printReceipt" class="btn-print-receipt">
            🖨️ พิมพ์ใบเสร็จ
          </button>
          <button @click="voidAndReopenOrder" class="btn-void-order" title="ยกเลิกบิลนี้เพื่อนำรายการอาหารกลับไปแก้ไขในตะกร้า">
            🚫 ยกเลิกบิล / เปิดแก้ไข
          </button>
          <button @click="startNextOrder" class="btn-next-order">
            ✨ เปิดบิลถัดไป / โต๊ะใหม่
          </button>
        </div>
      </div>
    </div>

    <!-- =================================================================== -->
    <!-- MODAL 4: KITCHEN DISPLAY (KDS) WITH ITEM-SERVED & AUTO-COMPLETE     -->
    <!-- =================================================================== -->
    <div v-if="showKitchenModal" class="pos-modal-overlay" @click.self="showKitchenModal = false">
      <div class="pos-modal-box kds-modal-box">
        <div class="modal-header kds-header-flex">
          <div class="kds-header-top-row">
            <div class="kds-title-sub-wrap">
              <div class="modal-title">🍳 หน้าจอห้องครัว (KDS)</div>
              <div class="modal-sub">
                รอปรุง: <b>{{ kitchenOrders.length }} ตั๋ว</b> • คลิกที่ชื่ออาหารเพื่อติ๊กเสิร์ฟ
              </div>
            </div>
            <button @click="showKitchenModal = false" class="modal-close-btn kds-mobile-close-btn">✕</button>
          </div>
          <div class="kds-header-controls">
            <!-- Open Standalone Screen in new window/tab -->
            <a
              href="/pos/kds"
              target="_blank"
              class="btn-open-standalone-kds"
              title="เปิดจอครัวเต็มจอในแท็บใหม่ หรือบนจอแท็บเล็ตแยก (Standalone KDS)"
            >
              <span>↗ จอครัวแยก</span>
            </a>
            <button
              @click="toggleKdsSound"
              class="kds-sound-toggle-btn"
              :class="{ 'is-muted': !isKdsSoundEnabled }"
              :title="isKdsSoundEnabled ? 'คลิกเพื่อปิดเสียงเตือนครัว' : 'คลิกเพื่อเปิดเสียงเตือนครัว'"
            >
              {{ isKdsSoundEnabled ? '🔊 เสียงเตือน: เปิด' : '🔇 เสียงเตือน: ปิด' }}
            </button>
            <button
              @click="playKdsChime"
              class="kds-test-sound-btn"
              title="ทดสอบเสียงกระดิ่งครัว"
            >
              🔔 ทดสอบเสียง
            </button>
            <button @click="showKitchenModal = false" class="modal-close-btn kds-desktop-close-btn">✕</button>
          </div>
        </div>

        <div class="kds-tickets-container custom-scrollbar">
          <div v-if="kitchenOrders.length === 0" class="kds-empty-state">
            <div class="kds-empty-icon">✨</div>
            <div class="kds-empty-title">ไม่มีออเดอร์ค้างในครัว</div>
            <div class="kds-empty-sub">ทุกรายการปรุงและเสิร์ฟเรียบร้อยแล้ว</div>
          </div>

          <div v-else class="kds-tickets-grid">
            <div
              v-for="order in kitchenOrders"
              :key="order.order_id"
              class="kds-ticket-card"
              :class="{
                'is-all-served': isOrderAllServed(order),
                'auto-closing': order._autoClosing
              }"
            >
              <div class="ticket-header">
                <div>
                  <div class="ticket-table-name">
                    {{ order.table_name || (order.table_id === 'takeaway' ? '📦 กลับบ้าน' : `โต๊ะ ${order.table_id}`) }}
                  </div>
                  <div class="ticket-order-id">#{{ order.order_id.slice(-6) }}</div>
                </div>
                <div class="ticket-time-badge">
                  ⏱️ {{ elapsedMinutes(order.created_at) }}
                </div>
              </div>

              <!-- Item-level Served Progress Bar -->
              <div class="kds-item-progress">
                <span class="progress-label">
                  เสิร์ฟแล้ว {{ countServedItems(order) }}/{{ order.items?.length || 0 }} จาน
                </span>
                <div class="progress-track">
                  <div
                    class="progress-fill"
                    :style="{ width: `${(countServedItems(order) / (order.items?.length || 1)) * 100}%` }"
                  ></div>
                </div>
              </div>

              <!-- Clickable Items for Individual Serving -->
              <div class="ticket-items-list custom-scrollbar">
                <div
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
                </div>
              </div>

              <!-- Ticket Footer & Auto-Complete Banner -->
              <div class="ticket-footer">
                <div v-if="order._autoClosing" class="auto-complete-banner">
                  🟢 เสิร์ฟครบแล้ว! กำลังปิดตั๋วอัตโนมัติ...
                </div>
                <button
                  v-else
                  @click="completeKitchenOrder(order.order_id)"
                  class="btn-ticket-complete"
                  :class="{ 'is-ready': isOrderAllServed(order) }"
                >
                  {{ isOrderAllServed(order) ? '✓ เสิร์ฟครบแล้ว (ปิดตั๋ว)' : '✓ ปรุงเสร็จทั้งหมด' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- =================================================================== -->
    <!-- MODAL 5: UNPAID ORDERS & ORDER HISTORY (OPENED FROM CART)           -->
    <!-- =================================================================== -->
    <div v-if="showOrdersModal" class="pos-modal-overlay" @click.self="showOrdersModal = false">
      <div class="pos-modal-box orders-modal-box">
        <div class="modal-header">
          <div>
            <div class="modal-title">📋 รายการออเดอร์ค้างชำระ & ประวัติการขาย</div>
            <div class="modal-sub">
              แสดงออเดอร์ล่าสุดอยู่บนสุด • ค้นหาตามชื่อโต๊ะ ลูกค้า หรือเลขที่บิล
            </div>
          </div>
          <button @click="showOrdersModal = false" class="modal-close-btn">✕</button>
        </div>

        <!-- Filter Bar: Search, Status Tabs, Channel Tabs (Shop/Online), Date Filter -->
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
        </div>

        <!-- Orders Table List -->
        <div class="orders-table-wrapper custom-scrollbar">
          <div v-if="sortedFilteredOrders.length === 0" class="orders-empty-state">
            <div class="orders-empty-icon">🧾</div>
            <div class="orders-empty-title">ไม่พบรายการออเดอร์</div>
            <div class="orders-empty-sub">ไม่มีออเดอร์ตรงตามเงื่อนไขการค้นหา</div>
          </div>

          <template v-else>
            <!-- Desktop Table View (Hidden on mobile) -->
            <table class="orders-history-table desktop-only-orders-table">
              <thead>
                <tr>
                  <th>เลขที่บิล</th>
                  <th>เวลาสั่ง</th>
                  <th>โต๊ะ / ประเภท</th>
                  <th>ลูกค้า / สมาชิก</th>
                  <th>ยอดเงิน</th>
                  <th>สถานะ</th>
                  <th>การจัดการ</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="ord in sortedFilteredOrders"
                  :key="ord.order_id"
                  :class="{ 'is-unpaid-row': ord.status !== 'paid' && ord.status !== 'cancelled' }"
                >
                  <td class="font-mono font-bold">#{{ ord.order_id.slice(-6) }}</td>
                  <td>
                    <div class="time-main">{{ formatTimeOnly(ord.created_at) }}</div>
                    <div class="time-sub">{{ elapsedMinutes(ord.created_at) }}</div>
                  </td>
                  <td>
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
                  </td>
                  <td>
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
                  </td>
                  <td class="font-bold text-blue">฿{{ formatBaht(getOrderDisplayTotal(ord)) }}</td>
                  <td>
                    <span class="status-pill" :class="ord.status">
                      {{ ord.status === 'paid' ? '✓ ชำระแล้ว' : (ord.status === 'cancelled' ? '✕ ยกเลิก' : '⏳ รอชำระเงิน') }}
                    </span>
                  </td>
                  <td class="action-buttons-cell">
                    <!-- Direct Checkout and Edit Order Buttons -->
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
                    </button>
                    <button @click="viewReceiptForOrder(ord)" class="btn-sm-view" title="ดูใบเสร็จ">
                      🧾 ใบเสร็จ
                    </button>
                    <button
                      v-if="ord.status !== 'cancelled'"
                      @click="voidSpecificOrder(ord)"
                      class="btn-sm-void"
                      title="ยกเลิกบิลนี้เพื่อนำกลับไปแก้ไขในตะกร้า"
                    >
                      🚫 เปิดแก้ไข
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>

            <!-- Mobile Card View (Visible only on mobile <= 768px) -->
            <div class="orders-mobile-cards-list mobile-only-orders-cards">
              <div
                v-for="ord in sortedFilteredOrders"
                :key="ord.order_id"
                class="order-mobile-card"
                :class="{ 'is-unpaid-card': ord.status !== 'paid' && ord.status !== 'cancelled' }"
              >
                <!-- Card Top Bar: Bill No, Table, Channel, Status -->
                <div class="card-top-bar">
                  <div class="card-id-table">
                    <span class="card-order-id font-mono">#{{ ord.order_id.slice(-6) }}</span>
                    <span class="card-table-badge">
                      {{ ord.table_name || (ord.table_id === 'takeaway' ? '📦 กลับบ้าน' : `🪑 โต๊ะ ${ord.table_id}`) }}
                    </span>
                    <span class="card-channel-pill" :class="getOrderChannel(ord)">
                      {{ getOrderChannel(ord) === 'online' ? '📱 ออนไลน์' : '🏪 หน้าร้าน' }}
                    </span>
                  </div>
                  <span class="status-pill" :class="ord.status">
                    {{ ord.status === 'paid' ? '✓ ชำระแล้ว' : (ord.status === 'cancelled' ? '✕ ยกเลิก' : '⏳ รอชำระเงิน') }}
                  </span>
                </div>

                <!-- Card Info Row: Time & Customer/Member -->
                <div class="card-info-row">
                  <div class="card-time-block">
                    <span class="time-clock-icon">🕒</span>
                    <span class="time-main-txt">{{ formatTimeOnly(ord.created_at) }}</span>
                    <span class="time-elapsed-badge">({{ elapsedMinutes(ord.created_at) }})</span>
                  </div>
                  <div class="card-customer-block">
                    <div v-if="ord.member_name || ord.customer_name" class="customer-info-cell">
                      <div class="customer-name-row">
                        <span class="customer-badge-star">⭐</span>
                        <span class="customer-name-text">{{ ord.member_name || ord.customer_name }}</span>
                      </div>
                      <button @click="openAttachMemberModal(ord)" class="btn-change-member-card">เปลี่ยน</button>
                    </div>
                    <div v-else class="customer-info-cell">
                      <div class="guest-row">
                        <span class="guest-avatar">👤</span>
                        <span class="guest-name">Guest</span>
                      </div>
                      <button @click="openAttachMemberModal(ord)" class="btn-link-member-card">+ ผูกสมาชิก</button>
                    </div>
                  </div>
                </div>

                <!-- Card Items Summary (if items exist) -->
                <div v-if="ord.items && ord.items.length" class="card-items-preview">
                  <span class="items-count-badge">🍽️ {{ ord.items.reduce((s, i) => s + (i.quantity || 1), 0) }} รายการ</span>
                  <span class="items-preview-text">
                    {{ ord.items.slice(0, 2).map(i => `${i.quantity}x ${i.name}`).join(', ') }}{{ ord.items.length > 2 ? ` และอีก ${ord.items.length - 2} อย่าง` : '' }}
                  </span>
                </div>

                <!-- Card Total & Actions Bar -->
                <div class="card-bottom-bar">
                  <div class="card-total-group">
                    <span class="card-total-label">ยอดสุทธิ:</span>
                    <span class="card-total-value">฿{{ formatBaht(getOrderDisplayTotal(ord)) }}</span>
                  </div>
                  <div class="card-actions-group">
                    <template v-if="ord.status !== 'paid' && ord.status !== 'cancelled'">
                      <button @click="payOrderDirect(ord)" class="btn-card-pay">
                        💳 คิดเงินทันที
                      </button>
                      <button @click="loadOrderIntoCart(ord)" class="btn-card-add" title="สั่งเพิ่ม">
                        ➕ เพิ่ม
                      </button>
                      <button @click="voidSpecificOrder(ord)" class="btn-card-void" title="เปิดแก้ไข">
                        🚫 แก้ไข
                      </button>
                    </template>
                    <template v-else>
                      <button @click="viewReceiptForOrder(ord)" class="btn-card-receipt">
                        🧾 ดูใบเสร็จ
                      </button>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- =================================================================== -->
    <!-- =================================================================== -->
    <!-- MODAL: ATTACH MEMBER TO ORDER                                       -->
    <!-- =================================================================== -->
    <div v-if="showAttachMemberModal && orderToAttachMember" class="pos-modal-overlay attach-member-overlay" @click.self="showAttachMemberModal = false">
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
                <button @click.stop="selectMemberForOrder(mem)" class="btn-choose-member">เลือก</button>
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

    <!-- =================================================================== -->
    <!-- MODAL 6: SYSTEM DRAWER MENU                                         -->
    <!-- =================================================================== -->
    <div v-if="showSystemMenu" class="pos-modal-overlay" @click.self="showSystemMenu = false">
      <div class="pos-drawer-box">
        <div class="drawer-header">
          <div class="drawer-title">☰ เมนูระบบและการจัดการ</div>
          <button @click="showSystemMenu = false" class="modal-close-btn">✕</button>
        </div>

        <div class="drawer-menu-list">
          <button @click="viewMode = 'settings'; showSystemMenu = false" class="drawer-menu-item highlight">
            <span class="drawer-icon">⚙️</span>
            <div>
              <div class="drawer-label">การตั้งค่าร้านค้า & ระบบ (Settings)</div>
              <div class="drawer-desc">เปิดหน้าเต็มเพื่อจัดการร้าน สต็อก สมาชิก พนักงาน ปริ้นเตอร์</div>
            </div>
          </button>
          <button @click="showTableModal = true; showSystemMenu = false" class="drawer-menu-item">
            <span class="drawer-icon">🪑</span>
            <div>
              <div class="drawer-label">ผังโต๊ะอาหาร (Table Map)</div>
              <div class="drawer-desc">ตรวจสถานะโต๊ะว่าง / มีลูกค้า และเลือกโต๊ะ</div>
            </div>
          </button>
          <button @click="showKitchenModal = true; showSystemMenu = false" class="drawer-menu-item">
            <span class="drawer-icon">🍳</span>
            <div>
              <div class="drawer-label">หน้าจอห้องครัว (KDS)</div>
              <div class="drawer-desc">ดูออเดอร์ที่กำลังปรุง และติ๊กเสิร์ฟอาหาร</div>
            </div>
          </button>
          <button @click="openUnpaidOrdersModal(); showSystemMenu = false" class="drawer-menu-item">
            <span class="drawer-icon">📋</span>
            <div>
              <div class="drawer-label">ออเดอร์ค้างชำระ & ประวัติการขาย</div>
              <div class="drawer-desc">ค้นหาบิล เช็คออเดอร์รอชำระ และดึงกลับมาคิดเงิน</div>
            </div>
          </button>
        </div>
      </div>
    </div>

    <!-- =================================================================== -->
    <!-- MODAL 7: PRINT TABLE QR CODE MODAL (CLEAN & MENU HIGHLIGHTS)        -->
    <!-- =================================================================== -->
    <div v-if="showQrPrintModal && activePrintingTable" class="pos-modal-overlay" @click.self="showQrPrintModal = false">
      <div class="pos-modal-box qr-print-modal-box">
        <div class="modal-header no-print">
          <div>
            <div class="modal-title">🖨️ พิมพ์ป้าย QR Code สั่งอาหาร</div>
            <div class="modal-sub">
              {{ activePrintingTable.name }} • โซน {{ activePrintingTable.zone || 'Indoor' }}
            </div>
          </div>
          <button @click="showQrPrintModal = false" class="modal-close-btn">✕</button>
        </div>

        <!-- Template Selector Inside Modal (No Print) -->
        <div class="qr-modal-template-bar no-print">
          <button
            @click="qrPrintTemplate = 'clean'"
            class="modal-template-btn"
            :class="{ 'is-active': qrPrintTemplate === 'clean' }"
          >
            🏷️ แบบที่ 1: QR Code อย่างเดียว (Clean Stand)
          </button>
          <button
            @click="qrPrintTemplate = 'with_menu'"
            class="modal-template-btn"
            :class="{ 'is-active': qrPrintTemplate === 'with_menu' }"
          >
            🍲 แบบที่ 2: QR Code + รูปเมนูแนะนำ
          </button>
        </div>

        <!-- Printable Table Stand Element (Both on screen and via @media print) -->
        <div id="printable-table-qr" class="qr-printable-canvas" :class="qrPrintTemplate">
          <!-- Template Header -->
          <div class="qr-stand-header">
            <div class="qr-stand-logo">🍲</div>
            <div class="qr-stand-shop-name">{{ shopSettings.name || 'ก๋วยเตี๋ยวคุณย่า' }}</div>
            <div class="qr-stand-tagline">สแกนสั่งอาหารง่ายๆ สะดวก รวดเร็ว</div>
          </div>

          <!-- Table Number Badge -->
          <div class="qr-stand-table-box">
            <div class="qr-stand-table-title">{{ activePrintingTable.name }}</div>
            <div class="qr-stand-table-zone">โซน {{ activePrintingTable.zone || 'Indoor' }}</div>
          </div>

          <!-- Big QR Code Image -->
          <div class="qr-stand-qr-box">
            <img
              :src="getTableQrUrl(activePrintingTable.id, 280)"
              alt="Scan to Order QR"
              class="qr-stand-img"
            />
          </div>

          <div class="qr-stand-scan-text">
            📱 เปิดกล้องมือถือสแกน QR Code เพื่อสั่งอาหาร
          </div>
          <div class="qr-stand-url">
            https://pos.m2igen.com/customer/{{ activePrintingTable.id }}
          </div>

          <!-- Template 2: Recommended Menu Highlights (Only in 'with_menu' template) -->
          <div v-if="qrPrintTemplate === 'with_menu'" class="qr-menu-highlights-box">
            <div class="highlights-title">⭐ เมนูแนะนำยอดนิยมที่ไม่ควรพลาด ⭐</div>
            <div class="highlights-grid">
              <div v-for="dish in topRecommendedDishes" :key="dish.id" class="highlight-dish-card">
                <img :src="dish.image || dish.image_url" :alt="dish.name" class="dish-thumb-mini" />
                <div class="dish-name-mini">{{ dish.name }}</div>
                <div class="dish-price-mini">฿{{ formatBaht(dish.price) }}</div>
              </div>
            </div>
          </div>

          <div class="qr-stand-footer">
            🙏 ขอให้มีความสุขกับมื้ออาหาร ขอบพระคุณครับ 🙏
          </div>
        </div>

        <!-- Print Action Buttons -->
        <div class="modal-footer no-print">
          <button @click="showQrPrintModal = false" class="btn-cancel">ปิด</button>
          <button @click="doPrintQrCode" class="btn-confirm-pay">
            🖨️ สั่งพิมพ์ป้ายนี้
          </button>
        </div>
      </div>
    </div>

    <!-- Toast Notification -->
    <transition name="toast">
      <div v-if="toastMsg" class="pos-toast">
        {{ toastMsg }}
      </div>
    </transition>

  

    <!-- ── MOBILE BOTTOM NAVIGATION BAR (PWA UX) ───────────────────── -->
    <nav class="pos-mobile-bottom-nav">
      <button
        class="m-nav-tab"
        :class="{ 'is-active': viewMode === 'pos' && !showTableModal && !showOrdersModal && !showKitchenModal && !showPaymentModal }"
        @click="viewMode = 'pos'; closeAllModals()"
      >
        <span class="m-nav-icon">🍽️</span>
        <span class="m-nav-label">สั่งอาหาร</span>
      </button>

      <button
        class="m-nav-tab"
        :class="{ 'is-active': showTableModal }"
        @click="openTableModal()"
      >
        <span class="m-nav-icon">🪑</span>
        <span class="m-nav-label">{{ orderType === 'takeaway' ? 'กลับบ้าน' : (selectedTableId ? `โต๊ะ ${selectedTableId}` : 'เลือกโต๊ะ') }}</span>
      </button>

      <button
        class="m-nav-tab m-nav-unpaid-tab"
        :class="{ 'is-active': showOrdersModal }"
        @click="openUnpaidOrdersModal()"
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
        @click="openKitchenModal()"
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
        @click="openMobileSettings()"
      >
        <span class="m-nav-icon">⚙️</span>
        <span class="m-nav-label">ตั้งค่า</span>
      </button>
    </nav>

  </div>

    

  </template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getMenu,
  getTables,
  createOrder,
  getKitchenOrders,
  getOrders,
  processPayment,
  updateOrderStatus,
  markItemServed,
  getSettings,
  updateSettings,
  getInventory,
  updateInventory,
  deleteInventory,
  getMembers,
  updateMember,
  deleteMember,
  getStaff,
  createStaff,
  deleteStaff,
  getRewards,
  updateReward,
  deleteReward
} from '../api/index.js'
import axios from 'axios'
import { activeAlarm, acknowledge } from '../alarmBus.js'

const route = useRoute()
const router = useRouter()
const apiNotif = axios.create({ baseURL: '/api' })

// ── View Mode: 'pos' or 'settings' ─────────────────────────────────────
const viewMode = ref(route.query.tab === 'settings' ? 'settings' : 'pos')
const mobileSettingsView = ref('menu') // 'menu' | 'detail'
const isSidebarCollapsed = ref(false)

// Item Notes Modal State
const showNoteModal = ref(false)
const editingItem = ref(null)
const editingItemIndex = ref(-1)
const itemNoteText = ref('')
const quickNoteChips = [
  'ไม่เผ็ด', 'เผ็ดน้อย', 'เผ็ดมาก',
  'ไม่ใส่ผัก', 'ไม่ใส่กระเทียม', 'ไม่ใส่ต้นหอม/ผักชี',
  'หวานน้อย', 'ไม่หวาน',
  'แยกน้ำ', 'แยกน้ำแข็ง',
  'ไข่ดาวไม่สุก', 'ไข่ดาวสุก',
  'กรอบๆ', 'ไม่ใส่ผงชูรส'
]

function openItemNoteModal(item, idx) {
  editingItem.value = item
  editingItemIndex.value = idx
  itemNoteText.value = item.notes || ''
  showNoteModal.value = true
}

function isChipSelected(chip) {
  if (!itemNoteText.value) return false
  return itemNoteText.value.includes(chip)
}

function toggleQuickNote(chip) {
  if (!itemNoteText.value) {
    itemNoteText.value = chip
    return
  }
  const parts = itemNoteText.value.split(',').map(s => s.trim()).filter(Boolean)
  if (parts.includes(chip)) {
    itemNoteText.value = parts.filter(p => p !== chip).join(', ')
  } else {
    parts.push(chip)
    itemNoteText.value = parts.join(', ')
  }
}

function clearCurrentNote() {
  itemNoteText.value = ''
  if (editingItem.value) {
    editingItem.value.notes = ''
  }
  showNoteModal.value = false
  showToast('ลบโน้ตเรียบร้อย')
}

function saveItemNote() {
  if (editingItem.value) {
    editingItem.value.notes = itemNoteText.value.trim()
  }
  showNoteModal.value = false
  showToast('บันทึกโน้ตเรียบร้อย 📝')
}

// Settings Navigation
function selectSettingsTab(tabId) {
  activeSettingsTab.value = tabId
  mobileSettingsView.value = 'detail'
}

const currentSettingsTabTitle = computed(() => {
  const t = settingsTabs.find(tab => tab.id === activeSettingsTab.value)
  return t ? t.title : ''
})

// Centralized Modal Management
function closeAllModals() {
  showTableModal.value = false
  showOrdersModal.value = false
  showPaymentModal.value = false
  showKitchenModal.value = false
  showReceiptModal.value = false
  showAttachMemberModal.value = false
  showNoteModal.value = false
  showReportsModal.value = false
  showSystemMenu.value = false
  isMobileCartOpen.value = false
}

function openTableModal() {
  closeAllModals()
  viewMode.value = 'pos'
  showTableModal.value = true
}

function openKitchenModal() {
  closeAllModals()
  viewMode.value = 'pos'
  showKitchenModal.value = true
}

function openMobileSettings() {
  closeAllModals()
  viewMode.value = 'settings'
  mobileSettingsView.value = 'menu'
}

// ── State ─────────────────────────────────────────────────────────────
const menu = ref([])
const tables = ref([])
const allOrders = ref([])
const kitchenOrders = ref([])
const loading = ref(true)
const isSubmitting = ref(false)

const search = ref('')
const activeCat = ref('ทั้งหมด')

// Enforce Table / Takeaway Selection FIRST (No default table pre-assigned)
const orderType = ref(route.query.type || '')
const selectedTableId = ref(route.query.table || null)

const cart = ref([])
const toastMsg = ref('')

// Modals
const showTableModal = ref(false)
const showPaymentModal = ref(false)
const showKitchenModal = ref(false)
const showOrdersModal = ref(false)
const showReportsModal = ref(false)
const showSystemMenu = ref(false)
const showReceiptModal = ref(false)
const showQrPrintModal = ref(false)
const activePrintingTable = ref(null)

// QR Template Mode: 'clean' (Standard Stand) or 'with_menu' (With Menu Highlights)
const qrPrintTemplate = ref('with_menu')

const selectedZone = ref('ทั้งหมด')
const selectedPaymentMethod = ref('PromptPay')
const cashReceived = ref(0)
const lastCompletedOrder = ref(null)
const activeCheckoutOrder = ref(null)

// Orders History & Unpaid Filters
const orderSearchQuery = ref('')
const showAttachMemberModal = ref(false)
const orderToAttachMember = ref(null)
const memberSearchQuery = ref('')
const showQuickAddMember = ref(false)
const newMemberName = ref('')
const newMemberPhone = ref('')
const isSubmittingMember = ref(false)
const orderChannelFilter = ref('all')
const isMobileCartOpen = ref(false)
const orderDatePicker = ref(null)
const orderStatusFilter = ref('unpaid') // 'unpaid' or 'all'
const orderDateFilter = ref('')

// Alarm & Audio
const activeAlarmBanner = ref(null)
const dismissedNotifIds = new Set()
let pollTimer = null

// Clock
const clockTime = ref('')
const clockDate = ref('')
let clockTimer = null
let refreshTimer = null

// ── Settings View State ────────────────────────────────────────────────
const activeSettingsTab = ref('shop')
const isSavingSettings = ref(false)
const settingsSuccessMsg = ref('')
const settingsErrorMsg = ref('')

const shopSettings = ref({
  name: 'ก๋วยเตี๋ยวคุณย่า',
  tax_id: '0-1055-67012-34-5',
  address: '123 ถนนสุขุมวิท กรุงเทพฯ',
  phone: '02-123-4567',
  email: 'info@ourrestaurant.com',
  vat: 7,
  service_charge: 0,
  open_time: '10:00',
  close_time: '22:00',
  printer_type: 'thermal',
  printer_port: '/dev/usb/lp0',
  auto_print: false
})

const inventoryList = ref([])
const membersList = ref([])
const staffList = ref([])
const rewardsList = ref([])

const settingsTabs = [
  { id: 'shop', title: 'ข้อมูลร้านค้า & ภาษี', desc: 'ชื่อร้าน เลขภาษี ที่อยู่ VAT', icon: '🏪' },
  { id: 'inventory', title: 'คลังสต็อกวัตถุดิบ', desc: 'รายการวัตถุดิบ จุดเตือน ต้นทุน', icon: '📦' },
  { id: 'members', title: 'ระบบสมาชิก & CRM', desc: 'เบอร์โทร แต้มสะสม ระดับลูกค้า', icon: '👥' },
  { id: 'staff', title: 'พนักงาน & สิทธิ์ PIN', desc: 'รายชื่อ ตำแหน่ง รหัสผ่าน', icon: '🪪' },
  { id: 'rewards', title: 'แต้มสะสม & รางวัล', desc: 'เงื่อนไขการแลกส่วนลด', icon: '🎁' },
  { id: 'printer', title: 'เครื่องพิมพ์ & ใบเสร็จ', desc: 'Thermal 80mm พิมพ์อัตโนมัติ', icon: '🖨️' },
  { id: 'qr', title: 'QR Code สั่งอาหาร', desc: 'QR ประจำแต่ละโต๊ะ', icon: '📱' },
  { id: 'shift', title: 'จัดการกะ (Shift)', desc: 'เปิด-ปิดกะ สรุปยอดขาย', icon: '🕒' }
]

// ── Derived Data ──────────────────────────────────────────────────────
const currentTableDisplayTitle = computed(() => {
  if (orderType.value === 'takeaway') return 'สั่งกลับบ้าน'
  if (selectedTableId.value) return 'ทานที่ร้าน'
  return 'ยังไม่ได้เลือกโต๊ะ'
})

const currentTableDisplayName = computed(() => {
  if (orderType.value === 'takeaway') return '📦 Takeaway'
  if (selectedTableId.value) {
    const found = tables.value.find(t => String(t.id) === String(selectedTableId.value))
    return found ? found.name : `โต๊ะ ${selectedTableId.value}`
  }
  return '⚠️ กรุณาเลือกโต๊ะ'
})

const currentTableSubText = computed(() => {
  if (orderType.value === 'takeaway') return 'รับหน้าร้าน / ใส่กล่อง'
  if (selectedTableId.value) {
    const found = tables.value.find(t => String(t.id) === String(selectedTableId.value))
    return found ? `โซน ${found.zone || 'Indoor'}` : 'ในร้าน'
  }
  return 'คลิกเพื่อเลือกโต๊ะก่อนสั่ง'
})

const categoryList = computed(() => {
  const map = {}
  for (const item of menu.value) {
    const c = item.category || 'ทั่วไป'
    map[c] = (map[c] || 0) + 1
  }

  const result = [{ name: 'ทั้งหมด', icon: '🌟', count: menu.value.length }]
  const icons = {
    'อาหารทานเล่น': '🥟',
    'อาหารจานหลัก': '🍛',
    'ของหวาน': '🍧',
    'เครื่องดื่ม': '🥤',
    'เครื่องเคียง': '🍚',
    'Appetizer': '🥟',
    'Main Course': '🍛',
    'Dessert': '🍧',
    'Beverage': '🥤',
    'Side Dish': '🍚',
    'ทั่วไป': '🍲'
  }

  for (const cat of Object.keys(map)) {
    result.push({
      name: cat,
      icon: icons[cat] || '🍽️',
      count: map[cat]
    })
  }
  return result
})

const filteredMenu = computed(() => {
  let list = menu.value
  if (activeCat.value !== 'ทั้งหมด') {
    list = list.filter(item => item.category === activeCat.value)
  }
  if (search.value.trim()) {
    const q = search.value.toLowerCase().trim()
    list = list.filter(item =>
      (item.name && item.name.toLowerCase().includes(q)) ||
      (item.category && item.category.toLowerCase().includes(q))
    )
  }
  return list
})

const zoneOptions = computed(() => {
  const zones = new Set(tables.value.map(t => t.zone || 'Indoor'))
  return ['ทั้งหมด', ...Array.from(zones)]
})

const filteredTables = computed(() => {
  if (selectedZone.value === 'ทั้งหมด') return tables.value
  return tables.value.filter(t => (t.zone || 'Indoor') === selectedZone.value)
})

// Unpaid Orders Count and List
const unpaidOrders = computed(() => {
  return allOrders.value.filter(o => o.status !== 'paid' && o.status !== 'cancelled')
})

const unpaidOrdersCount = computed(() => {
  return unpaidOrders.value.length
})

// Sorted and Filtered Orders for the Orders Modal (Latest on Top)
const sortedFilteredOrders = computed(() => {
  let list = [...allOrders.value]

  // Filter by status tab
  if (orderStatusFilter.value === 'unpaid') {
    list = list.filter(o => o.status !== 'paid' && o.status !== 'cancelled')
  }

  // Filter by channel: shop vs online
  if (orderChannelFilter.value !== 'all') {
    list = list.filter(o => getOrderChannel(o) === orderChannelFilter.value)
  }

  // Filter by date
  if (orderDateFilter.value) {
    list = list.filter(o => {
      try {
        const d = new Date(o.created_at).toISOString().slice(0, 10)
        return d === orderDateFilter.value
      } catch {
        return false
      }
    })
  }

  // Search filter (Order ID, Table name, items)
  if (orderSearchQuery.value.trim()) {
    const q = orderSearchQuery.value.toLowerCase().trim()
    list = list.filter(o =>
      (o.order_id && o.order_id.toLowerCase().includes(q)) ||
      (o.table_name && o.table_name.toLowerCase().includes(q)) ||
      (String(o.table_id || '').toLowerCase().includes(q)) ||
      (o.customer_name && o.customer_name.toLowerCase().includes(q))
    )
  }

  // Sort: Latest on top
  list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  return list
})

// Top 4 recommended dishes for the QR Stand with Menu template
const topRecommendedDishes = computed(() => {
  return menu.value.slice(0, 4)
})

// Cart Financial Calculations
const cartTotalQty = computed(() => {
  return cart.value.reduce((sum, item) => sum + (item.quantity || 0), 0)
})

const cartSubtotal = computed(() => {
  return cart.value.reduce((sum, item) => sum + (item.price || 0) * (item.quantity || 0), 0)
})

const cartVat = computed(() => {
  const vatRate = (shopSettings.value.vat || 7) / 100
  return Math.round(cartSubtotal.value * vatRate * 100) / 100
})

const cartGrandTotal = computed(() => {
  return Math.round((cartSubtotal.value + cartVat.value) * 100) / 100
})

const cashChange = computed(() => {
  return Math.round(((cashReceived.value || 0) - cartGrandTotal.value) * 100) / 100
})

const qrCodeUrl = computed(() => {
  const amt = cartGrandTotal.value.toFixed(2)
  return `https://promptpay.io/0812345678/${amt}.png`
})

// Reports Stats
const reportStats = computed(() => {
  const paidOrders = allOrders.value.filter(o => o.status === 'paid')
  const totalSales = paidOrders.reduce((sum, o) => sum + (o.total || 0), 0)
  const totalBills = paidOrders.length
  const avgPerBill = totalBills > 0 ? totalSales / totalBills : 0

  const itemCounts = {}
  for (const o of paidOrders) {
    for (const it of (o.items || [])) {
      itemCounts[it.name] = (itemCounts[it.name] || 0) + (it.quantity || 1)
    }
  }

  const topSellers = Object.entries(itemCounts)
    .map(([name, qty]) => ({ name, qty }))
    .sort((a, b) => b.qty - a.qty)
    .slice(0, 5)

  return { totalSales, totalBills, avgPerBill, topSellers }
})

// ── Methods ───────────────────────────────────────────────────────────
function formatBaht(num) {
  if (num === null || num === undefined || isNaN(num)) return '0.00'
  return Number(num).toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatTimeOnly(isoStr) {
  if (!isoStr) return '-'
  try {
    const d = new Date(isoStr)
    return d.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return isoStr
  }
}

function formatDateTime(isoStr) {
  if (!isoStr) return '-'
  try {
    const d = new Date(isoStr)
    return `${d.toLocaleDateString('th-TH')} ${d.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' })}`
  } catch {
    return isoStr
  }
}

function elapsedMinutes(isoStr) {
  if (!isoStr) return '0 นาที'
  const diff = Date.now() - new Date(isoStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'เมื่อสักครู่'
  if (mins < 60) return `${mins} นาทีที่แล้ว`
  const hrs = Math.floor(mins / 60)
  return `${hrs} ชม. ${mins % 60} น.`
}

function getCatEmoji(cat) {
  const map = {
    'อาหารทานเล่น': '🥟',
    'อาหารจานหลัก': '🍛',
    'ของหวาน': '🍧',
    'เครื่องดื่ม': '🥤',
    'เครื่องเคียง': '🍚',
    'Appetizer': '🥟',
    'Main Course': '🍛',
    'Dessert': '🍧',
    'Beverage': '🥤',
    'Side Dish': '🍚'
  }
  return map[cat] || '🍲'
}

function formatItemsSummary(items) {
  if (!items || items.length === 0) return 'ไม่มีรายการ'
  return items.map(i => `${i.quantity}x ${i.name}`).slice(0, 2).join(', ') + (items.length > 2 ? '...' : '')
}

function formatItemsTooltip(items) {
  if (!items) return ''
  return items.map(i => `${i.quantity}x ${i.name} (฿${formatBaht(i.price)})`).join('\n')
}

function showToast(msg) {
  toastMsg.value = msg
  setTimeout(() => { toastMsg.value = '' }, 3000)
}

function updateClock() {
  const now = new Date()
  clockTime.value = now.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
  const days = ['อาทิตย์', 'จันทร์', 'อังคาร', 'พุธ', 'พฤหัส', 'ศุกร์', 'เสาร์']
  const months = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
  clockDate.value = `วัน${days[now.getDay()]} ${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear() + 543}`
}

// Table / Takeaway Selection Enforcement
function setOrderType(type) {
  orderType.value = type
  if (type === 'takeaway') {
    selectedTableId.value = null
    showToast('เลือกประเภท: 📦 สั่งกลับบ้าน (Takeaway)')
  } else {
    showTableModal.value = true
  }
}

function getOrderDisplayTotal(order) {
  if (!order) return 0
  if (order.items && order.items.length > 0) {
    const subtotal = order.items.reduce((sum, it) => sum + ((Number(it.price) || 0) * (Number(it.quantity) || 1)), 0)
    const scPct = Number(shopSettings.value.service_charge || 0) / 100
    const vatPct = Number(shopSettings.value.vat || 7) / 100
    const sc = Math.round(subtotal * scPct * 100) / 100
    const vat = Math.round((subtotal + sc) * vatPct * 100) / 100
    return Math.round((subtotal + sc + vat) * 100) / 100
  }
  return Number(order.total || order.grand_total || 0)
}

// Helper: get active unpaid order for a table
function getTableActiveOrder(tableId) {
  if (!tableId) return null
  return unpaidOrders.value.find(o => String(o.table_id) === String(tableId)) || null
}

function selectTakeaway() {
  orderType.value = 'takeaway'
  selectedTableId.value = null
  closeAllModals()
  viewMode.value = 'pos'

  const existingOrder = getTableActiveOrder('takeaway')
  if (existingOrder) {
    loadOrderIntoCart(existingOrder)
    showToast(`ดึงบิลสั่งกลับบ้าน (#${existingOrder.order_id.slice(-6)}) ยอด ฿${formatBaht(getOrderDisplayTotal(existingOrder))} เรียบร้อย 💳`)
  } else {
    showToast('เลือก: 📦 สั่งกลับบ้าน (Takeaway) เรียบร้อย ✨ แตะเลือกเมนูได้เลย')
  }
}

function selectTable(tableId) {
  selectedTableId.value = tableId
  orderType.value = 'dinein'
  closeAllModals()
  viewMode.value = 'pos'

  const existingOrder = getTableActiveOrder(tableId)
  if (existingOrder) {
    loadOrderIntoCart(existingOrder)
    showToast(`ดึงบิลโต๊ะ ${tableId} (#${existingOrder.order_id.slice(-6)}) ยอด ฿${formatBaht(getOrderDisplayTotal(existingOrder))} เรียบร้อย 💳`)
  } else {
    showToast(`เลือก: โต๊ะ ${tableId} เรียบร้อย ✨ แตะเลือกเมนูได้เลย`)
  }
}

// Quick checkout directly for a table (Opens payment modal directly without overlap)
function checkoutTableDirect(tableId) {
  const existingOrder = getTableActiveOrder(tableId)
  if (existingOrder) {
    loadOrderIntoCart(existingOrder)
    openPaymentModal('Cash')
  } else {
    selectTable(tableId)
  }
}

// Quick direct payment from unpaid orders list (Opens payment modal directly without overlap)
function payOrderDirect(ord) {
  loadOrderIntoCart(ord)
  openPaymentModal('Cash')
}

// Cart Management
function handleFoodCardClick(item) {
  if (!selectedTableId.value && orderType.value !== 'takeaway') {
    showToast('⚠️ กรุณาเลือกโต๊ะ หรือ สั่งกลับบ้าน ก่อนเริ่มสั่งอาหาร')
    showTableModal.value = true
    return
  }
  addToCart(item)
}

function addToCart(item) {
  const existing = cart.value.find(ci => ci.id === item.id)
  if (existing) {
    existing.quantity += 1
  } else {
    cart.value.push({
      id: item.id,
      item_id: item.id,
      name: item.name,
      price: item.price,
      quantity: 1,
      notes: ''
    })
  }
  showToast(`เพิ่ม "${item.name}" ลงในรายการแล้ว`)
}

function increaseQty(idx) {
  cart.value[idx].quantity += 1
}

function decreaseQty(idx) {
  if (cart.value[idx].quantity > 1) {
    cart.value[idx].quantity -= 1
  } else {
    cart.value.splice(idx, 1)
  }
}

function clearCart() {
  cart.value = []
  activeCheckoutOrder.value = null
}

// Unpaid Orders Modal Controls

const filteredMembersList = computed(() => {
  if (!memberSearchQuery.value.trim()) return membersList.value
  const q = memberSearchQuery.value.toLowerCase().trim()
  return membersList.value.filter(m =>
    (m.name && m.name.toLowerCase().includes(q)) ||
    (m.phone && m.phone.includes(q))
  )
})


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

function openUnpaidOrdersModal() {
  closeAllModals()
  orderStatusFilter.value = 'unpaid'
  showOrdersModal.value = true
}

function loadOrderIntoCart(order) {
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
}

// Checkout & Payments
function openPaymentModal(method) {
  closeAllModals()
  selectedPaymentMethod.value = method || 'Cash'
  cashReceived.value = Number(cartGrandTotal.value)
  showPaymentModal.value = true
}

async function submitPayment() {
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
    const paymentMethodParam = selectedPaymentMethod.value === 'Credit' ? 'Card' : selectedPaymentMethod.value
    const amountParam = paymentMethodParam === 'Cash' ? Math.max(Number(cashReceived.value || 0), Number(cartGrandTotal.value || 0)) : Number(cartGrandTotal.value)
    const memberIdParam = (activeCheckoutOrder.value && activeCheckoutOrder.value.member_id) ? activeCheckoutOrder.value.member_id : null

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
        paymentMethodParam,
        amountParam,
        memberIdParam
      )
    } else {
      // 2. Creating and paying a fresh new walk-in order
      const newOrder = await createOrder(tableIdParam, itemsPayload)
      finalOrderId = newOrder.order_id
      await processPayment(
        finalOrderId,
        paymentMethodParam,
        amountParam,
        memberIdParam
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

    closeAllModals()
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
}

async function sendOrderToKitchenOnly() {
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
    showToast(`ส่งออเดอร์เข้าครัวเรียบร้อย! (#${newOrder.order_id.slice(-6)}) 🍳`)
    cart.value = []
    fetchData()
  } catch (err) {
    console.error('Send to kitchen error:', err)
    showToast(`เกิดข้อผิดพลาด: ${err.response?.data?.detail || err.message}`)
  } finally {
    isSubmitting.value = false
  }
}

// ── Void & Re-open Order (แก้ไขออเดอร์ / ยกเลิกบิล) ────────────────────
async function voidAndReopenOrder() {
  if (!lastCompletedOrder.value) return
  const confirmVoid = window.confirm(
    `คุณต้องการยกเลิกบิล #${lastCompletedOrder.value.order_id.slice(-6)} เพื่อดึงรายการอาหารกลับมาแก้ไขในตะกร้าใช่หรือไม่?`
  )
  if (!confirmVoid) return

  try {
    await updateOrderStatus(lastCompletedOrder.value.order_id, 'cancelled')
    cart.value = lastCompletedOrder.value.items.map(it => ({
      id: it.id || it.item_id,
      item_id: it.id || it.item_id,
      name: it.name,
      price: it.price,
      quantity: it.quantity,
      notes: it.notes || ''
    }))

    if (lastCompletedOrder.value.table_id === 'takeaway') {
      orderType.value = 'takeaway'
      selectedTableId.value = null
    } else {
      orderType.value = 'dinein'
      selectedTableId.value = lastCompletedOrder.value.table_id
    }

    showReceiptModal.value = false
    showToast(`ยกเลิกบิลเรียบร้อย! ดึงรายการกลับมาที่ตะกร้าแล้ว สามารถแก้ไขและชำระเงินใหม่ได้ทันที ✅`)
    fetchData()
  } catch (err) {
    console.error('Void order error:', err)
    showToast(`ยกเลิกบิลไม่สำเร็จ: ${err.message}`)
  }
}

async function voidSpecificOrder(order) {
  const confirmVoid = window.confirm(
    `ต้องการยกเลิกบิล #${order.order_id.slice(-6)} และเปิดแก้ไขในตะกร้าหรือไม่?`
  )
  if (!confirmVoid) return

  try {
    await updateOrderStatus(order.order_id, 'cancelled')
    cart.value = (order.items || []).map(it => ({
      id: it.item_id || it.id,
      item_id: it.item_id || it.id,
      name: it.name,
      price: it.price,
      quantity: it.quantity,
      notes: it.notes || ''
    }))

    if (order.table_id === 'takeaway') {
      orderType.value = 'takeaway'
      selectedTableId.value = null
    } else {
      orderType.value = 'dinein'
      selectedTableId.value = order.table_id
    }

    showOrdersModal.value = false
    showToast(`นำออเดอร์ #${order.order_id.slice(-6)} กลับมาในตะกร้าแล้ว สามารถปรับแก้จานได้เลย ✅`)
  } catch (err) {
    showToast(`เกิดข้อผิดพลาด: ${err.message}`)
  }
}

function viewReceiptForOrder(order) {
  lastCompletedOrder.value = {
    order_id: order.order_id,
    table_id: order.table_id,
    table_name: order.table_name || (order.table_id === 'takeaway' ? 'สั่งกลับบ้าน' : `โต๊ะ ${order.table_id}`),
    items: order.items || [],
    subtotal: order.subtotal || order.total * 100 / 107,
    vat: order.vat || order.total * 7 / 107,
    total: order.total,
    payment_method: order.payment_method || 'เงินสด',
    cash_received: order.cash_received || null,
    change: order.change || 0,
    created_at: order.created_at
  }
  showOrdersModal.value = false
  showReceiptModal.value = true
}

// Receipt & Next Order Actions
function printReceipt() {
  window.print()
}

function startNextOrder() {
  showReceiptModal.value = false
  cart.value = []
  selectedTableId.value = null
  orderType.value = ''
  setTimeout(() => {
    showTableModal.value = true
  }, 300)
}

// ── Kitchen KDS: Item Serving & Auto-Complete ─────────────────────────
function countServedItems(order) {
  if (!order.items) return 0
  return order.items.filter(i => i.item_served).length
}

function isOrderAllServed(order) {
  if (!order.items || order.items.length === 0) return false
  return order.items.every(i => i.item_served)
}

async function toggleItemServed(order, item, lineIdx) {
  const lineNo = item.line !== undefined ? item.line : (lineIdx + 1)
  try {
    await markItemServed(order.order_id, lineNo)
    item.item_served = !item.item_served

    // Check for Auto-Complete when all items are served
    if (isOrderAllServed(order)) {
      order._autoClosing = true
      showToast(`🎉 ออเดอร์ #${order.order_id.slice(-6)} เสิร์ฟครบแล้ว! ระบบกำลังปิดตั๋วอัตโนมัติ...`)
      setTimeout(async () => {
        await completeKitchenOrder(order.order_id)
      }, 1400)
    } else {
      showToast(`เสิร์ฟ: "${item.name}" เรียบร้อย ✓`)
    }
  } catch (err) {
    console.error('Mark item served error:', err)
    item.item_served = !item.item_served
    if (isOrderAllServed(order)) {
      order._autoClosing = true
      setTimeout(async () => {
        await completeKitchenOrder(order.order_id)
      }, 1400)
    }
  }
}

// ── KDS Sound & Audio Synthesis ──────────────────────────────────────
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
}

// ── Alarm Handling ────────────────────────────────────────────────────
function dismissOrderAlarm() {
  if (activeAlarmBanner.value) {
    const curId = activeAlarmBanner.value.id || activeAlarmBanner.value.orderId
    if (curId) dismissedNotifIds.add(String(curId))
    activeAlarmBanner.value = null
  }
  acknowledge()
  apiNotif.post('/notifications/ack', { id: 'all' }).catch(() => {})
  showToast('✓ รับทราบและปิดเสียงเตือนแล้ว')
}

function acceptOrderAlarm() {
  dismissOrderAlarm()
  showKitchenModal.value = true
}

async function pollNotifications() {
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
}

watch(activeAlarm, (alm) => {
  if (alm && alm.orderId) {
    if (!dismissedNotifIds.has(String(alm.orderId))) {
      activeAlarmBanner.value = {
        id: alm.orderId,
        orderId: alm.orderId,
        table: alm.table || 'หน้าร้าน',
        total: alm.total || 0,
        message: `🔔 มีออเดอร์ใหม่ #${String(alm.orderId).slice(-6)} • โต๊ะ ${alm.table || 'หน้าร้าน'} • ฿${formatBaht(alm.total)}`
      }
    }
  } else if (!activeAlarmBanner.value?.id) {
    activeAlarmBanner.value = null
  }
})

// ── Settings CRUD Handlers ────────────────────────────────────────────
async function loadSettingsData() {
  try {
    const [s, inv, mem, stf, rwd] = await Promise.all([
      getSettings().catch(() => null),
      getInventory().catch(() => []),
      getMembers().catch(() => []),
      getStaff().catch(() => []),
      getRewards().catch(() => [])
    ])
    if (s) shopSettings.value = { ...shopSettings.value, ...s }
    inventoryList.value = Array.isArray(inv) ? inv : []
    membersList.value = Array.isArray(mem) ? mem : []
    staffList.value = Array.isArray(stf) ? stf : []
    rewardsList.value = Array.isArray(rwd) ? rwd : []
  } catch (err) {
    console.error('Load settings data error:', err)
  }
}

async function saveShopSettings() {
  isSavingSettings.value = true
  settingsSuccessMsg.value = ''
  settingsErrorMsg.value = ''
  try {
    await updateSettings(shopSettings.value)
    settingsSuccessMsg.value = 'บันทึกข้อมูลร้านค้าเรียบร้อยแล้ว'
    setTimeout(() => { settingsSuccessMsg.value = '' }, 3000)
  } catch (err) {
    settingsErrorMsg.value = 'บันทึกไม่สำเร็จ: ' + err.message
  } finally {
    isSavingSettings.value = false
  }
}

async function openAddInventoryModal() {
  const name = window.prompt('ระบุชื่อวัตถุดิบ:')
  if (!name) return
  const stock = parseFloat(window.prompt('จำนวนสต็อกคงเหลือ:', '10')) || 0
  const cost = parseFloat(window.prompt('ต้นทุนต่อหน่วย (บาท):', '25')) || 0
  const unit = window.prompt('หน่วยนับ (เช่น กก., ชิ้น, ซอง):', 'ชิ้น') || 'ชิ้น'

  try {
    const newItem = await updateInventory({ name, stock, cost, unit, min_stock: 5, category: 'วัตถุดิบ' })
    inventoryList.value.push(newItem)
    showToast(`เพิ่มวัตถุดิบ "${name}" เรียบร้อย`)
  } catch (err) {
    showToast(`เพิ่มไม่สำเร็จ: ${err.message}`)
  }
}

async function removeInventoryItem(id) {
  if (!window.confirm('ต้องการลบวัตถุดิบนี้ใช่หรือไม่?')) return
  try {
    await deleteInventory(id)
    inventoryList.value = inventoryList.value.filter(i => i.id !== id)
    showToast('ลบวัตถุดิบเรียบร้อย')
  } catch (err) {
    showToast(`ลบไม่สำเร็จ: ${err.message}`)
  }
}

async function openAddMemberModal() {
  const name = window.prompt('ชื่อสมาชิก:')
  if (!name) return
  const phone = window.prompt('เบอร์โทรศัพท์:')
  if (!phone) return

  try {
    const newMem = await updateMember({ name, phone, points: 50, tier: 'Regular' })
    membersList.value.push(newMem)
    showToast(`เพิ่มสมาชิก "${name}" เรียบร้อย`)
  } catch (err) {
    showToast(`เพิ่มไม่สำเร็จ: ${err.message}`)
  }
}

async function removeMemberItem(id) {
  if (!window.confirm('ต้องการลบสมาชิกนี้ใช่หรือไม่?')) return
  try {
    await deleteMember(id)
    membersList.value = membersList.value.filter(m => m.id !== id)
    showToast('ลบสมาชิกเรียบร้อย')
  } catch (err) {
    showToast(`ลบไม่สำเร็จ: ${err.message}`)
  }
}

async function openAddStaffModal() {
  const name = window.prompt('ชื่อพนักงาน:')
  if (!name) return
  const role = window.prompt('ตำแหน่ง (พนักงานเสิร์ฟ / แคชเชียร์ / ผู้จัดการ):', 'พนักงานเสิร์ฟ') || 'พนักงานเสิร์ฟ'
  const pin = window.prompt('รหัส PIN (4 หลัก):', '1234') || '1234'

  try {
    const st = await createStaff({ name, role, pin })
    staffList.value.push(st)
    showToast(`เพิ่มพนักงาน "${name}" เรียบร้อย`)
  } catch (err) {
    showToast(`เพิ่มไม่สำเร็จ: ${err.message}`)
  }
}

async function removeStaffItem(id) {
  if (!window.confirm('ต้องการลบพนักงานนี้ใช่หรือไม่?')) return
  try {
    await deleteStaff(id)
    staffList.value = staffList.value.filter(s => s.id !== id)
    showToast('ลบพนักงานเรียบร้อย')
  } catch (err) {
    showToast(`ลบไม่สำเร็จ: ${err.message}`)
  }
}

async function openAddRewardModal() {
  const name = window.prompt('ชื่อรางวัล (เช่น ส่วนลด 50 บาท):')
  if (!name) return
  const points_required = parseInt(window.prompt('แต้มสะสมที่ต้องใช้:', '100')) || 100
  const discount_value = parseFloat(window.prompt('มูลค่าส่วนลด (บาท):', '50')) || 50

  try {
    const rw = await updateReward({ name, points_required, discount_value, discount_type: 'fixed' })
    rewardsList.value.push(rw)
    showToast(`เพิ่มรางวัล "${name}" เรียบร้อย`)
  } catch (err) {
    showToast(`เพิ่มไม่สำเร็จ: ${err.message}`)
  }
}

async function removeRewardItem(id) {
  if (!window.confirm('ต้องการลบรางวัลนี้ใช่หรือไม่?')) return
  try {
    await deleteReward(id)
    rewardsList.value = rewardsList.value.filter(r => r.id !== id)
    showToast('ลบรางวัลเรียบร้อย')
  } catch (err) {
    showToast(`ลบไม่สำเร็จ: ${err.message}`)
  }
}

// ── Table QR Code Methods ─────────────────────────────────────────────
function getTableQrUrl(tableId, size = 200) {
  const customerUrl = `https://pos.m2igen.com/customer/${tableId}`
  return `https://api.qrserver.com/v1/create-qr-code/?size=${size}x${size}&data=${encodeURIComponent(customerUrl)}`
}

function openTableQrPrintModal(table) {
  activePrintingTable.value = table
  showQrPrintModal.value = true
}

function doPrintQrCode() {
  window.print()
}

function closeCurrentShift() {
  if (window.confirm('ต้องการปิดกะการขายปัจจุบัน และสรุปยอดเงินใช่หรือไม่?')) {
    showToast('ปิดกะการขายเรียบร้อย! พิมพ์สรุปยอดส่งกะแล้ว')
  }
}

function onImgError(e) {
  e.target.style.display = 'none'
  if (e.target.nextElementSibling) {
    e.target.nextElementSibling.style.display = 'flex'
  }
}

function onQrError(e) {
  e.target.src = 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https://pos.m2igen.com'
}

async function fetchData() {
  try {
    const [menuData, tablesData, kOrders, ords] = await Promise.all([
      getMenu(),
      getTables(),
      getKitchenOrders().catch(() => []),
      getOrders().catch(() => [])
    ])
    menu.value = Array.isArray(menuData) ? menuData : []
    tables.value = Array.isArray(tablesData) ? tablesData : []
    const sortedK = (Array.isArray(kOrders) ? kOrders : []).sort((a, b) => {
      const tA = new Date(a.updated_at || a.created_at || 0).getTime()
      const tB = new Date(b.updated_at || b.created_at || 0).getTime()
      return tB - tA
    })
    kitchenOrders.value = sortedK
    allOrders.value = Array.isArray(ords) ? ords : []
  } catch (err) {
    console.error('Fetch data error:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  fetchData()
  loadSettingsData()
  refreshTimer = setInterval(fetchData, 10000)
  pollTimer = setInterval(pollNotifications, 3000)

  // Enforce table / takeaway selection on start if in POS mode and not yet chosen
  if (viewMode.value === 'pos' && !selectedTableId.value && orderType.value !== 'takeaway') {
    setTimeout(() => {
      showTableModal.value = true
    }, 400)
  }
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
  if (refreshTimer) clearInterval(refreshTimer)
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700;800;900&family=Inter:wght@400;500;600;700&family=Courier+Prime:wght@400;700&display=swap');

/* ── Container Layout ─────────────────────────────────────────────── */
.pos-restodash {
  display: flex;
  flex-direction: row !important;
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  z-index: 99999 !important;
  background: #F4F6F9 !important;
  font-family: 'Prompt', sans-serif !important;
  overflow: hidden !important;
  margin: 0 !important;
  padding: 0 !important;
  color: #1E293B;
}

.pos-restodash * {
  box-sizing: border-box;
}

/* ── Top Alarm Banner ─────────────────────────────────────────────── */
.pos-alarm-banner {
  position: sticky;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000000;
  background: linear-gradient(135deg, #DC2626, #EA580C);
  color: #ffffff;
  padding: 12px 24px;
  box-shadow: 0 10px 30px rgba(220, 38, 38, 0.4);
  animation: pulse-border 1.5s infinite alternate;
}
@keyframes pulse-border {
  from { filter: brightness(1); }
  to { filter: brightness(1.15); }
}
.alarm-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.alarm-icon-box {
  font-size: 28px;
  animation: bounce-bell 0.6s infinite alternate;
}
@keyframes bounce-bell {
  from { transform: scale(0.9) rotate(-10deg); }
  to { transform: scale(1.15) rotate(10deg); }
}
.alarm-text-box {
  flex: 1;
}
.alarm-title {
  font-size: 16px;
  font-weight: 800;
  letter-spacing: -0.2px;
}
.alarm-desc {
  font-size: 13px;
  opacity: 0.95;
  margin-top: 2px;
}
.alarm-actions {
  display: flex;
  gap: 10px;
}
.alarm-btn-accept {
  background: #ffffff;
  color: #DC2626;
  border: none;
  padding: 8px 18px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  transition: all 0.15s;
}
.alarm-btn-accept:hover {
  transform: translateY(-1px);
  background: #FEE2E2;
}
.alarm-btn-dismiss {
  background: rgba(0,0,0,0.25);
  color: #ffffff;
  border: 1px solid rgba(255,255,255,0.4);
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.alarm-btn-dismiss:hover {
  background: rgba(0,0,0,0.4);
}

/* ── LEFT SIDEBAR: Brand, Categories, Bottom Collapse Button ──────── */
.pos-sidebar-left {
  width: 220px !important;
  min-width: 220px !important;
  max-width: 220px !important;
  height: 100vh !important;
  background: #ffffff !important;
  border-right: 1px solid #E2E8F0 !important;
  display: flex !important;
  flex-direction: column !important;
  flex: 0 0 220px !important;
  overflow: hidden !important;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
}

/* Brand Box (Clean without top arrow button) */
.brand-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid #E2E8F0;
}
.brand-avatar {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #EFF6FF, #DBEAFE);
  border: 1px solid #BFDBFE;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}
.brand-info {
  flex: 1;
  overflow: hidden;
}
.brand-title {
  font-size: 14px;
  font-weight: 800;
  color: #0F172A;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.brand-sub {
  font-size: 10.5px;
  color: #64748B;
  font-weight: 500;
}

.table-chip-box {
  margin: 12px 14px;
  padding: 10px 12px;
  background: #F8FAFC;
  border: 1.5px solid #E2E8F0;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.table-chip-box:hover {
  border-color: #2563EB;
  background: #EFF6FF;
}
.table-chip-box.is-empty {
  border-color: #F59E0B;
  background: #FFFBEB;
}
.table-chip-label {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  font-weight: 600;
  color: #64748B;
}
.table-chip-change {
  color: #2563EB;
  font-weight: 700;
}
.table-chip-num {
  font-size: 15px;
  font-weight: 800;
  color: #0F172A;
  margin-top: 2px;
}
.table-chip-type {
  font-size: 10.5px;
  color: #64748B;
  margin-top: 2px;
}

.clock-box {
  padding: 6px 16px;
  color: #94A3B8;
  font-size: 11px;
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid #F1F5F9;
}
.clock-time {
  font-weight: 700;
  color: #475569;
}

.category-nav-box {
  flex: 1;
  padding: 10px 10px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.category-nav-header {
  font-size: 11px;
  font-weight: 700;
  color: #94A3B8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 6px 8px 4px;
}
.category-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 12px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #475569;
  font-size: 13px;
  font-weight: 600;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: left;
}
.category-btn:hover {
  background: #F1F5F9;
  color: #0F172A;
}
.category-btn.is-active {
  background: #2563EB;
  color: #ffffff;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
}
.cat-label {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}
.cat-icon {
  font-size: 16px;
}
.cat-count-pill {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 10px;
  background: #F1F5F9;
  color: #64748B;
}
.category-btn.is-active .cat-count-pill {
  background: rgba(255,255,255,0.25);
  color: #ffffff;
}

.sidebar-bottom {
  padding: 12px;
  border-top: 1px solid #E2E8F0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.system-menu-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  border-radius: 10px;
  border: 1px solid #CBD5E1;
  background: #F8FAFC;
  color: #334155;
  font-size: 12.5px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  transition: all 0.15s ease;
}
.system-menu-btn:hover {
  background: #0F172A;
  color: #ffffff;
  border-color: #0F172A;
}

/* Sidebar Collapse Button at the Bottom */
.sidebar-collapse-bottom-btn {
  width: 100%;
  padding: 7px;
  border-radius: 8px;
  border: 1px dashed #CBD5E1;
  background: transparent;
  color: #64748B;
  font-size: 11.5px;
  font-weight: 600;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.15s;
}
.sidebar-collapse-bottom-btn:hover {
  background: #F1F5F9;
  color: #2563EB;
  border-color: #2563EB;
}

/* Floating Expand Button when Sidebar is fully hidden */
.floating-sidebar-expand-btn {
  position: fixed;
  bottom: 20px;
  left: 20px;
  z-index: 10000;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 30px;
  border: 1px solid #CBD5E1;
  background: #0F172A;
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(0,0,0,0.2);
  transition: all 0.2s ease;
}
.floating-sidebar-expand-btn:hover {
  background: #2563EB;
  transform: translateY(-2px);
}
.expand-icon {
  font-size: 14px;
}
.expand-arrow {
  color: #60A5FA;
}

/* ── CENTER: Menu Grid & Horizontal Category Slider ────────────────── */
.pos-center-main {
  flex: 1 !important;
  height: 100vh !important;
  display: flex !important;
  flex-direction: column !important;
  overflow: hidden !important;
  background: #F8FAFC !important;
  transition: all 0.2s ease;
}

.center-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 20px;
  background: #ffffff;
  border-bottom: 1px solid #E2E8F0;
}
.search-box-wrapper {
  flex: 1;
  max-width: 450px;
  display: flex;
  align-items: center;
  background: #F1F5F9;
  border: 1px solid #CBD5E1;
  border-radius: 10px;
  padding: 0 12px;
  transition: all 0.15s;
}
.search-box-wrapper:focus-within {
  border-color: #2563EB;
  background: #ffffff;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}
.search-icon {
  font-size: 14px;
  color: #94A3B8;
  margin-right: 8px;
}
.search-input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 9px 0;
  font-size: 13.5px;
  font-family: 'Prompt', sans-serif;
  outline: none;
  color: #0F172A;
}
.search-clear-btn {
  border: none;
  background: transparent;
  color: #94A3B8;
  cursor: pointer;
  font-size: 13px;
  padding: 2px 6px;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.quick-pill-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 9px;
  border: 1px solid #CBD5E1;
  background: #ffffff;
  font-size: 13px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  color: #0F172A;
  cursor: pointer;
  transition: all 0.15s;
}
.quick-pill-btn:hover {
  border-color: #2563EB;
  color: #2563EB;
}
.quick-pill-btn.is-empty {
  background: #FEF3C7;
  border-color: #F59E0B;
  color: #92400E;
}
.pill-arrow {
  color: #94A3B8;
  font-size: 11px;
}

.quick-kds-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 9px;
  border: 1px solid #DBEAFE;
  background: #EFF6FF;
  color: #2563EB;
  font-size: 13px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  transition: all 0.15s;
}
.quick-kds-btn:hover {
  background: #2563EB;
  color: #ffffff;
}
.kds-badge {
  background: #EF4444;
  color: #ffffff;
  font-size: 11px;
  font-weight: 800;
  padding: 1px 6px;
  border-radius: 10px;
}

.quick-settings-btn {
  padding: 8px 14px;
  border-radius: 9px;
  border: 1px solid #E2E8F0;
  background: #F8FAFC;
  color: #475569;
  font-size: 13px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  transition: all 0.15s;
}
.quick-settings-btn:hover {
  background: #0F172A;
  color: #ffffff;
}

/* ── HORIZONTAL CATEGORY SLIDE BAR (Above Thumbnails) ─────────────── */
.category-slide-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: #ffffff;
  border-bottom: 1px solid #E2E8F0;
  overflow-x: auto;
  white-space: nowrap;
}
.slide-cat-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 20px;
  border: 1.5px solid #E2E8F0;
  background: #F8FAFC;
  color: #475569;
  font-size: 12.5px;
  font-weight: 600;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
}
.slide-cat-tab:hover {
  border-color: #94A3B8;
  color: #0F172A;
  background: #F1F5F9;
}
.slide-cat-tab.is-active {
  background: #2563EB;
  color: #ffffff;
  border-color: #2563EB;
  font-weight: 700;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);
}
.slide-cat-icon {
  font-size: 14px;
}
.slide-cat-count {
  font-size: 10.5px;
  font-weight: 800;
  padding: 1px 6px;
  border-radius: 10px;
  background: #E2E8F0;
  color: #475569;
}
.slide-cat-tab.is-active .slide-cat-count {
  background: rgba(255,255,255,0.25);
  color: #ffffff;
}

/* Food Grid Container */
.food-scroll-container {
  flex: 1;
  padding: 18px 20px;
  overflow-y: auto;
}
.food-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 14px;
}
.food-card {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #E2E8F0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 6px rgba(0,0,0,0.03);
}
.food-card:hover {
  transform: translateY(-2px);
  border-color: #2563EB;
  box-shadow: 0 8px 16px rgba(37, 99, 235, 0.12);
}
.food-thumb-wrap {
  position: relative;
  width: 100%;
  height: 110px;
  background: #F1F5F9;
  overflow: hidden;
}
.food-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}
.food-card:hover .food-img {
  transform: scale(1.05);
}
.food-img-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  background: linear-gradient(135deg, #F8FAFC, #E2E8F0);
}
.food-badge-cat {
  position: absolute;
  top: 6px;
  left: 6px;
  background: rgba(15, 23, 42, 0.75);
  backdrop-filter: blur(4px);
  color: #ffffff;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 6px;
}

.food-info {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  flex: 1;
  justify-content: space-between;
}
.food-name {
  font-size: 13.5px;
  font-weight: 700;
  color: #0F172A;
  line-height: 1.3;
  margin-bottom: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.food-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.food-price {
  font-size: 15px;
  font-weight: 800;
  color: #2563EB;
}
.food-add-btn {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  border: none;
  background: #EFF6FF;
  color: #2563EB;
  font-size: 15px;
  font-weight: 800;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.food-card:hover .food-add-btn {
  background: #2563EB;
  color: #fff;
}

/* ── Right Sidebar (340px) ─────────────────────────────────────────── */
.pos-sidebar-right {
  width: 340px !important;
  min-width: 340px !important;
  max-width: 340px !important;
  height: 100vh !important;
  flex: 0 0 340px !important;
  display: flex !important;
  flex-direction: column !important;
  background: #ffffff !important;
  border-left: 1px solid #E2E8F0 !important;
  overflow: hidden !important;
}

.cart-header {
  padding: 14px 16px;
  border-bottom: 1px solid #E2E8F0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.cart-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.cart-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 800;
  color: #0F172A;
}
.cart-badge {
  background: #EFF6FF;
  color: #2563EB;
  font-size: 12px;
  font-weight: 800;
  padding: 2px 8px;
  border-radius: 10px;
}
.cart-title-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Unpaid Orders Action Button in Cart Header */
.btn-cart-unpaid {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid #FCD34D;
  background: #FFFBEB;
  color: #B45309;
  font-size: 11.5px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-cart-unpaid:hover {
  background: #FDE68A;
  color: #78350F;
}
.unpaid-badge-pill {
  background: #EF4444;
  color: #ffffff;
  font-size: 10px;
  font-weight: 800;
  padding: 1px 6px;
  border-radius: 10px;
}

.clear-cart-btn {
  border: none;
  background: transparent;
  color: #EF4444;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.order-type-switch {
  display: flex;
  background: #F1F5F9;
  border-radius: 10px;
  padding: 3px;
  gap: 4px;
}
.type-btn {
  flex: 1;
  padding: 7px 6px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: #64748B;
  font-size: 12px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  transition: all 0.15s;
}
.type-btn.is-active {
  background: #ffffff;
  color: #0F172A;
  box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}

.cart-items-container {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px;
}
.cart-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 220px;
  color: #94A3B8;
  text-align: center;
}
.cart-empty-icon {
  font-size: 38px;
  margin-bottom: 8px;
}
.cart-empty-text {
  font-size: 14px;
  font-weight: 700;
  color: #64748B;
}
.cart-empty-sub {
  font-size: 11.5px;
  margin-top: 4px;
  max-width: 200px;
}

.cart-item-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.cart-item-row {
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
  padding: 10px;
}
.cart-item-details {
  margin-bottom: 8px;
}
.cart-item-name {
  font-size: 13.5px;
  font-weight: 700;
  color: #0F172A;
}
.cart-item-sub {
  font-size: 11px;
  color: #64748B;
  margin-top: 1px;
}
.cart-item-notes-input {
  width: 100%;
  margin-top: 6px;
  border: 1px dashed #CBD5E1;
  background: #ffffff;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 11px;
  font-family: 'Prompt', sans-serif;
  color: #475569;
  outline: none;
}
.cart-item-notes-input:focus {
  border-color: #2563EB;
}

.cart-item-control {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.qty-control-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #ffffff;
  border: 1px solid #CBD5E1;
  border-radius: 8px;
  padding: 2px 6px;
}
.qty-btn {
  border: none;
  background: transparent;
  color: #0F172A;
  font-weight: 800;
  font-size: 14px;
  width: 20px;
  height: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.qty-btn:hover {
  color: #2563EB;
}
.qty-num {
  font-size: 13px;
  font-weight: 800;
  min-width: 16px;
  text-align: center;
}
.cart-item-line-total {
  font-size: 14px;
  font-weight: 800;
  color: #0F172A;
}

.cart-footer {
  padding: 14px 16px;
  border-top: 1px solid #E2E8F0;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.financial-row {
  display: flex;
  justify-content: space-between;
  font-size: 12.5px;
  color: #64748B;
}
.financial-row.vat-row {
  font-size: 12px;
  color: #94A3B8;
}
.financial-row.total-row {
  font-size: 16px;
  font-weight: 800;
  color: #0F172A;
  padding-top: 6px;
  border-top: 1px dashed #E2E8F0;
  margin-top: 2px;
}
.grand-total-amount {
  font-size: 20px;
  color: #2563EB;
}

.checkout-actions-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 6px;
}
.btn-pay-qr {
  padding: 11px 8px;
  border-radius: 10px;
  border: none;
  background: #2563EB;
  color: #ffffff;
  font-size: 13.5px;
  font-weight: 800;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);
}
.btn-pay-qr:hover:not(:disabled) {
  background: #1D4ED8;
}
.btn-pay-qr:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-pay-cash {
  padding: 11px 8px;
  border-radius: 10px;
  border: none;
  background: #10B981;
  color: #ffffff;
  font-size: 13.5px;
  font-weight: 800;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 0 4px 10px rgba(16, 185, 129, 0.25);
}
.btn-pay-cash:hover:not(:disabled) {
  background: #059669;
}
.btn-pay-cash:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-send-kitchen {
  width: 100%;
  padding: 9px;
  border-radius: 10px;
  border: 1px solid #CBD5E1;
  background: #F8FAFC;
  color: #475569;
  font-size: 12.5px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-send-kitchen:hover:not(:disabled) {
  background: #F1F5F9;
  color: #0F172A;
}
.btn-send-kitchen:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ===================================================================== */
/* FULL PAGE SETTINGS VIEW STYLES                                        */
/* ===================================================================== */
.settings-fullpage {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #F8FAFC;
}
.settings-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 28px;
  background: #ffffff;
  border-bottom: 1px solid #E2E8F0;
}
.settings-topbar-left {
  display: flex;
  align-items: center;
  gap: 18px;
}
.btn-back-to-pos {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 10px;
  border: 1.5px solid #2563EB;
  background: #EFF6FF;
  color: #2563EB;
  font-size: 13.5px;
  font-weight: 800;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-back-to-pos:hover {
  background: #2563EB;
  color: #ffffff;
}
.btn-back-icon {
  font-size: 16px;
}
.settings-title-group {
  display: flex;
  flex-direction: column;
}
.settings-main-title {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: #0F172A;
}
.settings-sub-title {
  font-size: 12px;
  color: #64748B;
  margin-top: 2px;
}

.settings-topbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}
.settings-alert-success {
  background: #ECFDF5;
  color: #059669;
  border: 1px solid #A7F3D0;
  font-size: 12.5px;
  font-weight: 700;
  padding: 6px 14px;
  border-radius: 8px;
}
.settings-alert-error {
  background: #FEF2F2;
  color: #DC2626;
  border: 1px solid #FECACA;
  font-size: 12.5px;
  font-weight: 700;
  padding: 6px 14px;
  border-radius: 8px;
}
.store-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #F1F5F9;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.settings-body-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}
.settings-nav-sidebar {
  width: 280px;
  min-width: 280px;
  background: #ffffff;
  border-right: 1px solid #E2E8F0;
  padding: 16px 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.settings-nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
  border-radius: 12px;
  border: none;
  background: transparent;
  color: #475569;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  text-align: left;
  transition: all 0.15s ease;
  width: 100%;
}
.settings-nav-item:hover {
  background: #F1F5F9;
  color: #0F172A;
}
.settings-nav-item.is-active {
  background: #EFF6FF;
  color: #2563EB;
  font-weight: 700;
  border: 1px solid #BFDBFE;
}
.nav-item-icon {
  font-size: 22px;
}
.nav-item-text {
  flex: 1;
}
.nav-item-title {
  font-size: 13.5px;
  font-weight: 700;
}
.nav-item-desc {
  font-size: 11px;
  color: #94A3B8;
  margin-top: 1px;
}
.settings-nav-item.is-active .nav-item-desc {
  color: #60A5FA;
}

.settings-content-panel {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
}
.settings-card {
  background: #ffffff;
  border: 1px solid #E2E8F0;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.03);
}
.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  border-bottom: 1px solid #F1F5F9;
  padding-bottom: 16px;
}
.card-title {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: #0F172A;
}
.card-subtitle {
  margin: 4px 0 0;
  font-size: 12.5px;
  color: #64748B;
}

.btn-primary-save, .btn-primary-add {
  padding: 9px 18px;
  border-radius: 10px;
  border: none;
  background: #2563EB;
  color: #ffffff;
  font-size: 13.5px;
  font-weight: 800;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);
}
.btn-primary-save:hover, .btn-primary-add:hover {
  background: #1D4ED8;
}

.qr-template-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #F1F5F9;
  padding: 4px 8px;
  border-radius: 10px;
}
.selector-label {
  font-size: 11.5px;
  font-weight: 700;
  color: #64748B;
}
.btn-template-toggle {
  padding: 6px 12px;
  border-radius: 7px;
  border: none;
  background: transparent;
  font-size: 12px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-template-toggle.is-active {
  background: #ffffff;
  color: #2563EB;
  box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}

.form-grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.form-group.span-2 {
  grid-column: span 2;
}
.form-group label {
  font-size: 12.5px;
  font-weight: 700;
  color: #334155;
}
.form-input {
  border: 1.5px solid #CBD5E1;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13.5px;
  font-family: 'Prompt', sans-serif;
  outline: none;
  color: #0F172A;
  transition: all 0.15s;
}
.form-input:focus {
  border-color: #2563EB;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #0F172A;
}

.settings-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.settings-table th {
  background: #F8FAFC;
  padding: 10px 14px;
  text-align: left;
  font-weight: 700;
  color: #475569;
  border-bottom: 2px solid #E2E8F0;
}
.settings-table td {
  padding: 12px 14px;
  border-bottom: 1px solid #F1F5F9;
  vertical-align: middle;
}
.btn-sm-del {
  border: 1px solid #FECACA;
  background: #FEF2F2;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 11.5px;
  color: #DC2626;
  cursor: pointer;
}
.badge-sub {
  background: #F1F5F9;
  color: #475569;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 12px;
}
.badge-alert {
  background: #FEE2E2;
  color: #DC2626;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 12px;
}
.badge-success {
  background: #ECFDF5;
  color: #059669;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 12px;
}
.badge-tier {
  background: #EFF6FF;
  color: #2563EB;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 12px;
}
.badge-role {
  background: #F3E8FF;
  color: #7E22CE;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 12px;
}

.qr-tables-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 16px;
}
.table-qr-card {
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  padding: 14px;
  text-align: center;
  background: #F8FAFC;
}
.qr-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.qr-table-num {
  font-weight: 800;
  font-size: 14px;
}
.qr-zone-pill {
  font-size: 10.5px;
  color: #64748B;
  background: #ffffff;
  padding: 2px 6px;
  border-radius: 6px;
  border: 1px solid #E2E8F0;
}
.qr-preview-box {
  margin: 8px auto;
  width: 140px;
  height: 140px;
  background: #ffffff;
  border-radius: 8px;
  padding: 8px;
  border: 1px solid #E2E8F0;
}
.qr-img {
  width: 100%;
  height: 100%;
}
.qr-url-text {
  font-size: 9.5px;
  color: #94A3B8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}
.qr-template-hint {
  font-size: 11px;
  font-weight: 600;
  color: #2563EB;
  margin-bottom: 8px;
}
.btn-qr-print {
  width: 100%;
  padding: 8px;
  border-radius: 8px;
  border: 1.5px solid #2563EB;
  background: #EFF6FF;
  font-size: 12px;
  font-weight: 800;
  font-family: 'Prompt', sans-serif;
  color: #2563EB;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-qr-print:hover {
  background: #2563EB;
  color: #ffffff;
}

.shift-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 20px;
}
.shift-kpi-card {
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  padding: 14px;
}
.shift-actions-row {
  display: flex;
  gap: 12px;
}
.btn-shift-close {
  padding: 10px 20px;
  border-radius: 10px;
  border: none;
  background: #EF4444;
  color: #ffffff;
  font-size: 13.5px;
  font-weight: 800;
  cursor: pointer;
}

/* ===================================================================== */
/* MODALS STYLES                                                         */
/* ===================================================================== */
.pos-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.65);
  backdrop-filter: blur(4px);
  z-index: 100000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.pos-modal-box {
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 25px 60px rgba(0,0,0,0.3);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  animation: modal-pop 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes modal-pop {
  from { transform: scale(0.95); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

.modal-header {
  padding: 18px 24px;
  border-bottom: 1px solid #E2E8F0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.modal-title {
  font-size: 17px;
  font-weight: 800;
  color: #0F172A;
}
.modal-sub {
  font-size: 12px;
  color: #64748B;
  margin-top: 2px;
}
.modal-close-btn {
  border: none;
  background: #F1F5F9;
  color: #64748B;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.modal-close-btn:hover {
  background: #E2E8F0;
  color: #0F172A;
}

/* Table Select Modal */
.table-select-modal {
  width: 640px;
  padding: 0 0 16px;
}
.takeaway-option-card {
  margin: 16px 24px 8px;
  padding: 14px 18px;
  border-radius: 14px;
  border: 2px solid #E2E8F0;
  background: #F8FAFC;
  display: flex;
  align-items: center;
  gap: 14px;
  cursor: pointer;
  transition: all 0.15s;
}
.takeaway-option-card:hover {
  border-color: #2563EB;
  background: #EFF6FF;
}
.takeaway-option-card.is-selected {
  border-color: #2563EB;
  background: #EFF6FF;
}
.takeaway-icon {
  font-size: 32px;
}
.takeaway-info {
  flex: 1;
}
.takeaway-title {
  font-size: 15px;
  font-weight: 800;
  color: #0F172A;
}
.takeaway-desc {
  font-size: 12px;
  color: #64748B;
  margin-top: 2px;
}
.takeaway-select-btn {
  padding: 8px 16px;
  border-radius: 8px;
  border: none;
  background: #2563EB;
  color: #ffffff;
  font-size: 12.5px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
}

.table-modal-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 12px 24px;
  font-size: 12px;
  font-weight: 600;
  color: #94A3B8;
}

.zone-filter-row {
  display: flex;
  gap: 8px;
  padding: 0 24px 12px;
  overflow-x: auto;
}
.zone-btn {
  padding: 5px 12px;
  border-radius: 20px;
  border: 1px solid #CBD5E1;
  background: #ffffff;
  font-size: 12px;
  font-weight: 600;
  font-family: 'Prompt', sans-serif;
  color: #475569;
  cursor: pointer;
}
.zone-btn.is-active {
  background: #0F172A;
  color: #ffffff;
  border-color: #0F172A;
}

.tables-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  padding: 0 24px 12px;
  max-height: 320px;
  overflow-y: auto;
}
.table-card {
  border: 1.5px solid #E2E8F0;
  background: #ffffff;
  border-radius: 12px;
  padding: 10px 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.table-card:hover {
  border-color: #2563EB;
  transform: translateY(-1px);
}
.table-card.is-active {
  border-color: #2563EB;
  background: #EFF6FF;
}
.table-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.table-number {
  font-size: 14px;
  font-weight: 800;
  color: #0F172A;
}
.table-zone-badge {
  font-size: 10px;
  color: #64748B;
  background: #F1F5F9;
  padding: 1px 5px;
  border-radius: 4px;
}
.table-capacity {
  font-size: 11px;
  color: #64748B;
  margin-top: 4px;
}
.table-status-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10.5px;
  font-weight: 600;
  margin-top: 6px;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.status-dot.green { background: #10B981; }
.status-dot.red { background: #EF4444; }

/* Payment Modal */
.payment-modal {
  width: 880px !important;
  max-width: 95vw !important;
}
.payment-tabs-row {
  display: flex;
  padding: 12px 20px 0;
  gap: 8px;
  border-bottom: 1px solid #E2E8F0;
}
.pay-tab-btn {
  flex: 1;
  padding: 10px 8px;
  border: none;
  background: transparent;
  font-size: 13px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  color: #64748B;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.pay-tab-btn.is-active {
  color: #2563EB;
  border-bottom-color: #2563EB;
}

.qr-payment-view {
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.qr-box {
  width: 220px;
  height: 220px;
  background: #ffffff;
  border: 1px solid #E2E8F0;
  border-radius: 16px;
  padding: 10px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.06);
}
.qr-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.qr-guide {
  margin-top: 14px;
}
.qr-guide-title {
  font-size: 14px;
  font-weight: 700;
  color: #0F172A;
}
.qr-guide-sub {
  font-size: 13px;
  color: #64748B;
  margin-top: 2px;
}

.cash-payment-view {
  padding: 0 !important;
}
.cash-input-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cash-label {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}
.cash-input {
  border: 2px solid #CBD5E1;
  border-radius: 10px;
  padding: 12px;
  font-size: 20px;
  font-weight: 800;
  color: #0F172A;
  outline: none;
}
.cash-input:focus {
  border-color: #2563EB;
}

.quick-cash-row {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.quick-cash-btn {
  flex: 1;
  padding: 8px 4px;
  border-radius: 8px;
  border: 1px solid #CBD5E1;
  background: #F8FAFC;
  font-size: 12px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  color: #334155;
  cursor: pointer;
}
.quick-cash-btn:hover {
  background: #EFF6FF;
  border-color: #2563EB;
  color: #2563EB;
}

.change-display-box {
  margin-top: 16px;
  padding: 12px 16px;
  background: #F1F5F9;
  border-radius: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 700;
  color: #64748B;
}
.change-display-box.has-change {
  background: #ECFDF5;
  color: #059669;
}
.change-amount {
  font-size: 18px;
  font-weight: 800;
}

.credit-payment-view {
  padding: 40px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.credit-icon {
  font-size: 48px;
  margin-bottom: 8px;
}
.credit-title {
  font-size: 15px;
  font-weight: 700;
}
.credit-sub {
  font-size: 13px;
  color: #64748B;
  margin-top: 4px;
}

.modal-footer {
  padding: 14px 20px;
  border-top: 1px solid #E2E8F0;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.btn-cancel {
  padding: 10px 18px;
  border-radius: 10px;
  border: 1px solid #CBD5E1;
  background: #ffffff;
  font-size: 13px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  color: #64748B;
  cursor: pointer;
}
.btn-confirm-pay {
  padding: 10px 22px;
  border-radius: 10px;
  border: none;
  background: #2563EB;
  color: #ffffff;
  font-size: 14px;
  font-weight: 800;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
}
.btn-confirm-pay:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── Thermal Receipt Modal (440px) ─────────────────────────────────── */
.receipt-modal-box {
  width: 440px;
  max-height: 94vh;
}
.thermal-receipt {
  padding: 20px 28px;
  background: #ffffff;
  font-family: 'Courier Prime', 'Prompt', monospace;
  color: #000000;
  overflow-y: auto;
}
.receipt-header {
  text-align: center;
}
.receipt-store-logo {
  font-size: 32px;
  margin-bottom: 2px;
}
.receipt-store-name {
  font-size: 17px;
  font-weight: 800;
  font-family: 'Prompt', sans-serif;
}
.receipt-store-sub {
  font-size: 11px;
  color: #555;
}
.receipt-store-tax, .receipt-store-addr, .receipt-store-phone {
  font-size: 10.5px;
  margin-top: 2px;
  color: #333;
}

.receipt-divider-dashed {
  border-top: 1px dashed #000000;
  margin: 12px 0;
}

.receipt-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  font-size: 11px;
}

.receipt-items-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}
.receipt-items-table th {
  padding: 4px 0;
  text-align: left;
  border-bottom: 1px dashed #000;
}
.receipt-items-table td {
  padding: 4px 0;
}
.col-item { width: 50%; text-align: left; }
.col-qty { width: 15%; text-align: center; }
.col-price { width: 15%; text-align: right; }
.col-total { width: 20%; text-align: right; }

.receipt-summary-box {
  display: flex;
  flex-direction: column;
  gap: 3px;
  font-size: 11.5px;
}
.receipt-sum-row {
  display: flex;
  justify-content: space-between;
}
.receipt-grand-total {
  font-size: 14px;
  font-weight: 800;
  border-top: 1px solid #000;
  border-bottom: 1px solid #000;
  padding: 4px 0;
  margin: 4px 0;
}

.receipt-footer {
  text-align: center;
  font-size: 10.5px;
  color: #444;
}
.thank-you-text {
  font-weight: 700;
  font-size: 12px;
}
.wifi-info {
  margin-top: 2px;
}

.receipt-actions-footer {
  padding: 14px 20px;
  background: #F8FAFC;
  border-top: 1px solid #E2E8F0;
  display: flex;
  gap: 8px;
}
.btn-print-receipt {
  flex: 1;
  padding: 10px;
  border-radius: 9px;
  border: 1px solid #CBD5E1;
  background: #ffffff;
  color: #0F172A;
  font-size: 12.5px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
}
.btn-void-order {
  padding: 10px 12px;
  border-radius: 9px;
  border: 1px solid #FECACA;
  background: #FEF2F2;
  color: #DC2626;
  font-size: 12px;
  font-weight: 800;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-void-order:hover {
  background: #DC2626;
  color: #ffffff;
}
.btn-next-order {
  flex: 1.2;
  padding: 10px;
  border-radius: 9px;
  border: none;
  background: #2563EB;
  color: #ffffff;
  font-size: 13px;
  font-weight: 800;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);
}

/* ── KDS Kitchen Display Modal (840px) ─────────────────────────────── */
.btn-open-standalone-kds {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: #2563EB;
  color: #ffffff !important;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-open-standalone-kds:hover {
  background: #1D4ED8;
  transform: translateY(-1px);
}
.kds-sound-toggle-btn {
  padding: 6px 12px;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.35);
  color: #059669;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.kds-sound-toggle-btn.is-muted {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.35);
  color: #DC2626;
}
.kds-test-sound-btn {
  padding: 6px 12px;
  background: #FFFBEB;
  border: 1px solid #FDE68A;
  color: #D97706;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.kds-modal-box {
  width: 840px;
}
.kds-tickets-container {
  padding: 20px;
  max-height: 520px;
  overflow-y: auto;
}
.kds-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #94A3B8;
  text-align: center;
}
.kds-empty-icon {
  font-size: 48px;
  margin-bottom: 10px;
}
.kds-empty-title {
  font-size: 16px;
  font-weight: 800;
  color: #475569;
}
.kds-empty-sub {
  font-size: 12px;
}

.kds-tickets-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
.kds-ticket-card {
  background: #ffffff;
  border: 1.5px solid #CBD5E1;
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0,0,0,0.04);
  transition: all 0.3s ease;
}
.kds-ticket-card.is-all-served {
  border-color: #10B981;
  background: #F0FDF4;
}
.kds-ticket-card.auto-closing {
  animation: ticket-glow 1s infinite alternate;
}
@keyframes ticket-glow {
  from { box-shadow: 0 0 10px rgba(16, 185, 129, 0.3); }
  to { box-shadow: 0 0 25px rgba(16, 185, 129, 0.8); }
}

.ticket-header {
  padding: 12px 16px;
  background: #F8FAFC;
  border-bottom: 1px solid #E2E8F0;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.ticket-table-name {
  font-size: 15px;
  font-weight: 800;
  color: #0F172A;
}
.ticket-order-id {
  font-size: 11px;
  color: #64748B;
  font-family: monospace;
}
.ticket-time-badge {
  font-size: 11.5px;
  font-weight: 700;
  color: #EA580C;
  background: #FFF7ED;
  border: 1px solid #FED7AA;
  padding: 2px 8px;
  border-radius: 8px;
}

.kds-item-progress {
  padding: 8px 16px 4px;
  background: #ffffff;
}
.progress-label {
  font-size: 11px;
  font-weight: 700;
  color: #64748B;
}
.progress-track {
  width: 100%;
  height: 6px;
  background: #E2E8F0;
  border-radius: 10px;
  overflow: hidden;
  margin-top: 4px;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3B82F6, #10B981);
  transition: width 0.3s ease;
}

.ticket-items-list {
  padding: 10px 16px;
  flex: 1;
  max-height: 200px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ticket-item-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  border-radius: 8px;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  cursor: pointer;
  transition: all 0.15s ease;
}
.ticket-item-row:hover {
  background: #F1F5F9;
  border-color: #CBD5E1;
}
.ticket-item-row.is-served {
  background: #ECFDF5;
  border-color: #A7F3D0;
  opacity: 0.8;
}
.ticket-item-check-icon {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 800;
  background: #ffffff;
  border: 1.5px solid #CBD5E1;
  color: #94A3B8;
  flex-shrink: 0;
}
.ticket-item-row.is-served .ticket-item-check-icon {
  background: #10B981;
  border-color: #10B981;
  color: #ffffff;
}
.ticket-item-qty {
  font-weight: 800;
  font-size: 13px;
  color: #2563EB;
  min-width: 22px;
}
.ticket-item-name-box {
  flex: 1;
}
.item-name {
  font-size: 13px;
  font-weight: 700;
  color: #0F172A;
}
.item-name.line-through {
  text-decoration: line-through;
  color: #64748B;
}
.badge-served-mini {
  margin-left: 6px;
  font-size: 9.5px;
  font-weight: 800;
  color: #059669;
  background: #D1FAE5;
  padding: 1px 5px;
  border-radius: 4px;
}
.ticket-item-notes {
  font-size: 10.5px;
  color: #D97706;
  margin-top: 1px;
}

.ticket-footer {
  padding: 10px 16px;
  border-top: 1px solid #E2E8F0;
  background: #F8FAFC;
}
.auto-complete-banner {
  text-align: center;
  font-size: 12px;
  font-weight: 800;
  color: #059669;
  background: #D1FAE5;
  padding: 8px;
  border-radius: 8px;
  animation: pulse-border 0.8s infinite alternate;
}
.btn-ticket-complete {
  width: 100%;
  padding: 9px;
  border-radius: 8px;
  border: none;
  background: #2563EB;
  color: #ffffff;
  font-size: 12.5px;
  font-weight: 800;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-ticket-complete.is-ready {
  background: #10B981;
  box-shadow: 0 4px 10px rgba(16, 185, 129, 0.3);
}

/* ── MODAL 5: UNPAID ORDERS & ORDERS HISTORY (780px) ───────────────── */
.orders-modal-box {
  width: 800px;
}
.orders-filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: #F8FAFC;
  border-bottom: 1px solid #E2E8F0;
  flex-wrap: wrap;
}
.orders-search-wrap {
  flex: 1;
  min-width: 200px;
  display: flex;
  align-items: center;
  background: #ffffff;
  border: 1px solid #CBD5E1;
  border-radius: 8px;
  padding: 0 10px;
}
.orders-search-input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 7px 0;
  font-size: 12.5px;
  font-family: 'Prompt', sans-serif;
  outline: none;
}
.orders-tabs-toggle {
  display: flex;
  background: #E2E8F0;
  padding: 3px;
  border-radius: 8px;
  gap: 3px;
}
.order-tab-btn {
  padding: 5px 12px;
  border-radius: 6px;
  border: none;
  background: transparent;
  font-size: 12px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  color: #64748B;
  cursor: pointer;
  transition: all 0.15s;
}
.order-tab-btn.is-active {
  background: #ffffff;
  color: #0F172A;
  box-shadow: 0 2px 4px rgba(0,0,0,0.08);
}
.orders-date-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}
.date-label {
  font-size: 11.5px;
  font-weight: 700;
  color: #64748B;
}
.orders-date-input {
  border: 1px solid #CBD5E1;
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 11.5px;
  font-family: 'Prompt', sans-serif;
  background: #ffffff;
}
.btn-clear-date {
  border: none;
  background: transparent;
  color: #EF4444;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}

.orders-table-wrapper {
  padding: 12px 20px;
  max-height: 460px;
  overflow-y: auto;
}
.orders-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 50px 20px;
  color: #94A3B8;
  text-align: center;
}
.orders-empty-icon {
  font-size: 44px;
  margin-bottom: 6px;
}
.orders-empty-title {
  font-size: 15px;
  font-weight: 800;
  color: #475569;
}
.orders-empty-sub {
  font-size: 11.5px;
}

.orders-history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}
.orders-history-table th {
  padding: 9px 10px;
  background: #F8FAFC;
  border-bottom: 2px solid #E2E8F0;
  text-align: left;
  font-weight: 700;
  color: #475569;
}
.orders-history-table td {
  padding: 10px;
  border-bottom: 1px solid #F1F5F9;
  vertical-align: middle;
}
.is-unpaid-row {
  background: #FFFBEB !important;
}
.time-main {
  font-weight: 700;
  color: #0F172A;
}
.time-sub {
  font-size: 10px;
  color: #94A3B8;
}
.table-pill {
  background: #F1F5F9;
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 700;
}
.order-items-preview {
  font-size: 11.5px;
  color: #475569;
  max-width: 240px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.status-pill {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 700;
}
.status-pill.paid { background: #ECFDF5; color: #059669; }
.status-pill.cancelled { background: #FEF2F2; color: #DC2626; }
.action-buttons-cell {
  display: flex;
  gap: 6px;
}
.btn-sm-checkout {
  border: 1px solid #2563EB;
  background: #EFF6FF;
  color: #2563EB;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 11.5px;
  font-weight: 800;
  cursor: pointer;
  white-space: nowrap;
}
.btn-sm-checkout:hover {
  background: #2563EB;
  color: #ffffff;
}
.btn-sm-view {
  border: 1px solid #CBD5E1;
  background: #ffffff;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 11.5px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}
.btn-sm-void {
  border: 1px solid #FECACA;
  background: #FEF2F2;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 11.5px;
  font-weight: 700;
  color: #DC2626;
  cursor: pointer;
  white-space: nowrap;
}

/* ── MODAL 7: TABLE QR PRINT PREVIEW MODAL ─────────────────────────── */
.qr-print-modal-box {
  width: 500px;
  max-height: 94vh;
}
.qr-modal-template-bar {
  display: flex;
  gap: 8px;
  padding: 10px 20px;
  background: #F8FAFC;
  border-bottom: 1px solid #E2E8F0;
}
.modal-template-btn {
  flex: 1;
  padding: 7px 10px;
  border-radius: 8px;
  border: 1px solid #CBD5E1;
  background: #ffffff;
  font-size: 11.5px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  color: #475569;
  cursor: pointer;
}
.modal-template-btn.is-active {
  background: #2563EB;
  color: #ffffff;
  border-color: #2563EB;
}

/* Printable QR Canvas (Supports @media print) */
.qr-printable-canvas {
  padding: 24px 28px;
  background: #ffffff;
  text-align: center;
  overflow-y: auto;
}
.qr-stand-header {
  margin-bottom: 12px;
}
.qr-stand-logo {
  font-size: 32px;
}
.qr-stand-shop-name {
  font-size: 18px;
  font-weight: 900;
  color: #0F172A;
}
.qr-stand-tagline {
  font-size: 11px;
  color: #64748B;
  margin-top: 1px;
}
.qr-stand-table-box {
  display: inline-block;
  background: #EFF6FF;
  border: 1.5px solid #BFDBFE;
  padding: 6px 20px;
  border-radius: 10px;
  margin-bottom: 14px;
}
.qr-stand-table-title {
  font-size: 20px;
  font-weight: 900;
  color: #1E3A8A;
}
.qr-stand-table-zone {
  font-size: 11px;
  color: #3B82F6;
  font-weight: 700;
}

.qr-stand-qr-box {
  width: 200px;
  height: 200px;
  margin: 0 auto;
  background: #ffffff;
  border: 2px solid #000000;
  border-radius: 12px;
  padding: 8px;
}
.qr-stand-img {
  width: 100%;
  height: 100%;
}
.qr-stand-scan-text {
  font-size: 13px;
  font-weight: 800;
  color: #0F172A;
  margin-top: 12px;
}
.qr-stand-url {
  font-size: 10px;
  color: #94A3B8;
  font-family: monospace;
  margin-top: 2px;
}

/* Template 2: Menu Highlights in Print */
.qr-menu-highlights-box {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1.5px dashed #CBD5E1;
}
.highlights-title {
  font-size: 12px;
  font-weight: 800;
  color: #0F172A;
  margin-bottom: 10px;
}
.highlights-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.highlight-dish-card {
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  padding: 4px;
  text-align: center;
}
.dish-thumb-mini {
  width: 100%;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
}
.dish-name-mini {
  font-size: 9.5px;
  font-weight: 700;
  color: #0F172A;
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dish-price-mini {
  font-size: 10px;
  font-weight: 800;
  color: #2563EB;
}

.qr-stand-footer {
  margin-top: 16px;
  font-size: 11px;
  color: #64748B;
  font-weight: 600;
}

/* ── System Drawer Menu (320px) ────────────────────────────────────── */
.pos-drawer-box {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 330px;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  box-shadow: 10px 0 30px rgba(0,0,0,0.15);
  animation: drawer-slide 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes drawer-slide {
  from { transform: translateX(-100%); }
  to { transform: translateX(0); }
}
.drawer-header {
  padding: 18px 20px;
  border-bottom: 1px solid #E2E8F0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.drawer-title {
  font-size: 15px;
  font-weight: 800;
  color: #0F172A;
}
.drawer-menu-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.drawer-menu-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font-family: 'Prompt', sans-serif;
  transition: all 0.15s;
}
.drawer-menu-item:hover {
  background: #F1F5F9;
}
.drawer-menu-item.highlight {
  background: #EFF6FF;
  border-color: #BFDBFE;
}
.drawer-icon {
  font-size: 24px;
}
.drawer-label {
  font-size: 13.5px;
  font-weight: 700;
  color: #0F172A;
}
.drawer-desc {
  font-size: 11px;
  color: #64748B;
  margin-top: 1px;
}

/* ── States & Notifications ────────────────────────────────────────── */
.state-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 50px 20px;
  color: #94A3B8;
  text-align: center;
}
.spinner {
  width: 34px;
  height: 34px;
  border: 3px solid #E2E8F0;
  border-top-color: #2563EB;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 12px;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.state-text {
  font-size: 13.5px;
  font-weight: 600;
}
.empty-icon {
  font-size: 38px;
  margin-bottom: 8px;
}
.empty-title {
  font-size: 15px;
  font-weight: 800;
  color: #475569;
}
.empty-sub {
  font-size: 11.5px;
  color: #94A3B8;
  margin-top: 3px;
}
.reset-filter-btn {
  margin-top: 12px;
  padding: 7px 14px;
  border-radius: 8px;
  border: none;
  background: #2563EB;
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
  font-family: 'Prompt', sans-serif;
  cursor: pointer;
}

.pos-toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: #0F172A;
  color: #ffffff;
  padding: 10px 20px;
  border-radius: 30px;
  font-size: 13px;
  font-weight: 700;
  box-shadow: 0 10px 25px rgba(0,0,0,0.25);
  z-index: 1000000;
}
.toast-enter-active, .toast-leave-active {
  transition: all 0.25s ease;
}
.toast-enter-from, .toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 15px);
}
.slide-down-enter-active, .slide-down-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.slide-down-enter-from, .slide-down-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}

/* ── Print Media Query for Receipts & QR Stands ───────────────────── */
@media print {
  body * {
    visibility: hidden;
  }
  .no-print {
    display: none !important;
  }
  #printable-receipt, #printable-receipt *,
  #printable-table-qr, #printable-table-qr * {
    visibility: visible;
  }
  #printable-receipt {
    position: absolute;
    left: 0;
    top: 0;
    width: 80mm;
    margin: 0;
    padding: 0;
    box-shadow: none;
  }
  #printable-table-qr {
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
    margin: 0;
    padding: 20px;
    box-shadow: none;
  }
}

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


/* Settings Mobile Elements (Hidden on Desktop) */
.settings-mobile-menu-header {
  display: none;
}
.settings-mobile-back-bar {
  display: none;
}
.settings-nav-item .nav-item-arrow {
  display: none;
}
.mobile-floating-cart-bar {
  display: none;
}


/* ── CART ITEM NOTE BUTTON & LARGE CART TYPOGRAPHY ──────────────────── */
.cart-item-details {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.cart-item-name {
  font-size: 16.5px !important;
  font-weight: 800 !important;
  color: #0F172A !important;
  line-height: 1.3 !important;
}
.cart-item-sub {
  font-size: 14.5px !important;
  color: #2563EB !important;
  font-weight: 700 !important;
}
.cart-item-note-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #F1F5F9;
  border: 1px dashed #CBD5E1;
  border-radius: 8px;
  color: #475569;
  font-family: 'Prompt', sans-serif;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
  margin-top: 3px;
  max-width: fit-content;
  transition: all 0.15s ease;
}
.cart-item-note-btn:hover {
  background: #E2E8F0;
  border-color: #94A3B8;
  color: #0F172A;
}
.cart-item-note-btn.has-note {
  background: #FEF3C7;
  border: 1px solid #FCD34D;
  color: #92400E;
  font-weight: 700;
}
.note-btn-content {
  display: flex;
  align-items: center;
  gap: 6px;
}
.note-text-snippet {
  max-width: 170px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.note-edit-tag {
  font-size: 11px;
  background: rgba(146, 64, 14, 0.15);
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 800;
}

/* ── NOTE POPUP MODAL STYLES ────────────────────────────────────────── */
/* ── High Priority Note Modal Over Mobile Cart Drawer ── */
.pos-modal-overlay.note-modal-overlay {
  z-index: 200050 !important;
  position: fixed !important;
  inset: 0 !important;
  background: rgba(15, 23, 42, 0.72) !important;
  backdrop-filter: blur(4px) !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  padding: 16px !important;
}

.note-modal-box {
  position: relative !important;
  z-index: 200051 !important;
  width: 480px !important;
  max-width: 95vw !important;
  background: #FFFFFF !important;
  border-radius: 18px !important;
  overflow: hidden !important;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.45) !important;
}
.note-modal-body {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.quick-notes-label {
  font-size: 13.5px;
  font-weight: 700;
  color: #64748B;
}
.quick-notes-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-height: 140px;
  overflow-y: auto;
}
.quick-note-chip {
  padding: 7px 14px;
  border-radius: 20px;
  background: #F1F5F9;
  border: 1.5px solid #E2E8F0;
  color: #334155;
  font-family: 'Prompt', sans-serif;
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s ease;
}
.quick-note-chip:hover {
  background: #E2E8F0;
}
.quick-note-chip.is-selected {
  background: #EFF6FF;
  border-color: #2563EB;
  color: #1D4ED8;
  font-weight: 800;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.15);
}
.note-input-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.note-field-label {
  font-size: 13.5px;
  font-weight: 800;
  color: #0F172A;
}
.note-textarea {
  width: 100%;
  padding: 12px 14px;
  border: 2px solid #CBD5E1;
  border-radius: 12px;
  font-family: 'Prompt', sans-serif;
  font-size: 16px;
  color: #0F172A;
  line-height: 1.5;
  resize: vertical;
}
.note-textarea:focus {
  border-color: #2563EB;
  outline: none;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}
.note-modal-footer {
  padding: 12px 20px;
  background: #F8FAFC;
  border-top: 1px solid #E2E8F0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.btn-clear-note {
  padding: 10px 16px;
  background: #FEF2F2;
  border: 1px solid #FECACA;
  color: #DC2626;
  border-radius: 10px;
  font-family: 'Prompt', sans-serif;
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
}
.btn-save-note {
  padding: 10px 22px;
  background: linear-gradient(135deg, #2563EB, #1D4ED8);
  border: none;
  color: #FFFFFF;
  border-radius: 10px;
  font-family: 'Prompt', sans-serif;
  font-size: 14.5px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}

/* ── WIDE PAYMENT MODAL & TOP-RIGHT OUTSTANDING BALANCE HERO ───────── */
.payment-modal.payment-modal-wide {
  width: 860px !important;
  max-width: 95vw !important;
}

/* Payment Modal Desktop/Mobile Display Rules */
.mobile-only-header-block {
  display: none !important;
}
.desktop-only-header-block,
.desktop-only-hero {
  display: block;
}
.kds-header-top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.kds-mobile-close-btn {
  display: none !important;
}
.kds-desktop-close-btn {
  display: flex !important;
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


/* ── COMPREHENSIVE 2-COLUMN PAYMENT MODAL STYLES ───────────────────── */
.payment-modal {
  width: 880px !important;
  max-width: 95vw !important;
  background: #ffffff !important;
  border-radius: 16px !important;
  overflow: hidden !important;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.25) !important;
}

.payment-modal-header {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  padding: 16px 24px !important;
  border-bottom: 1px solid #E2E8F0 !important;
  background: #FFFFFF !important;
  gap: 16px !important;
}

.payment-header-left {
  flex: 1 !important;
}

/* YOD KHANG JAI HERO BADGE AT TOP RIGHT */
.header-outstanding-balance-box {
  background: linear-gradient(135deg, #0F172A, #1E293B) !important;
  border: 1.5px solid #38BDF8 !important;
  border-radius: 12px !important;
  padding: 8px 18px !important;
  text-align: right !important;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.25) !important;
  min-width: 170px !important;
  display: flex !important;
  flex-direction: column !important;
  align-items: flex-end !important;
  margin-right: 12px !important;
}

.header-outstanding-balance-box .due-tag {
  font-size: 11px !important;
  font-weight: 800 !important;
  color: #94A3B8 !important;
  letter-spacing: 0.5px !important;
  text-transform: uppercase !important;
  white-space: nowrap !important;
}

.header-outstanding-balance-box .due-amount-hero {
  font-size: 24px !important;
  font-weight: 900 !important;
  color: #38BDF8 !important;
  line-height: 1.15 !important;
  font-family: 'Prompt', monospace !important;
  white-space: nowrap !important;
}

/* 2-Column POS Payment Body */
.payment-modal-body-grid {
  display: grid !important;
  grid-template-columns: 360px 1fr !important;
  min-height: 440px !important;
  background: #FFFFFF !important;
}

/* Left Column: Order Items & Financial Summary */
.payment-order-summary-panel {
  background: #F8FAFC !important;
  border-right: 1px solid #E2E8F0 !important;
  padding: 20px !important;
  display: flex !important;
  flex-direction: column !important;
}

.summary-panel-title {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  font-size: 14px !important;
  font-weight: 800 !important;
  color: #0F172A !important;
  padding-bottom: 12px !important;
  border-bottom: 1px solid #E2E8F0 !important;
  margin-bottom: 12px !important;
}

.summary-items-count {
  font-size: 12px !important;
  font-weight: 700 !important;
  color: #64748B !important;
  background: #E2E8F0 !important;
  padding: 2px 8px !important;
  border-radius: 12px !important;
}

.payment-summary-items-list {
  flex: 1 !important;
  max-height: 250px !important;
  overflow-y: auto !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 8px !important;
  padding-right: 4px !important;
}

.payment-summary-item-row {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  padding: 8px 0 !important;
  border-bottom: 1px dashed #E2E8F0 !important;
  font-size: 13px !important;
}

.summary-item-name-col {
  flex: 1 !important;
}

.summary-item-name {
  font-weight: 700 !important;
  color: #1E293B !important;
}

.summary-item-notes {
  font-size: 11px !important;
  color: #94A3B8 !important;
}

.summary-item-qty-col {
  font-weight: 800 !important;
  color: #64748B !important;
  margin: 0 12px !important;
}

.summary-item-price-col {
  font-weight: 800 !important;
  color: #0F172A !important;
}

.payment-summary-financials {
  margin-top: auto !important;
  padding-top: 14px !important;
  border-top: 2px solid #E2E8F0 !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 6px !important;
}

.payment-summary-financials .financial-row {
  display: flex !important;
  justify-content: space-between !important;
  font-size: 13px !important;
  color: #64748B !important;
}

.payment-summary-financials .total-highlight-row {
  background: #EFF6FF !important;
  padding: 8px 12px !important;
  border-radius: 8px !important;
  margin-top: 6px !important;
  border: 1px solid #BFDBFE !important;
  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
}

.payment-summary-financials .total-highlight-row .total-label {
  font-size: 14px !important;
  font-weight: 800 !important;
  color: #1E40AF !important;
}

.payment-summary-financials .total-highlight-row .total-val {
  font-size: 18px !important;
  font-weight: 900 !important;
  color: #1D4ED8 !important;
}

/* Right Column: Tender & Cash Controls */
.payment-tender-panel {
  padding: 20px 24px !important;
  display: flex !important;
  flex-direction: column !important;
  background: #FFFFFF !important;
}

.payment-tender-panel .payment-tabs-row {
  display: flex !important;
  padding: 0 0 16px 0 !important;
  gap: 8px !important;
  border-bottom: 1px solid #E2E8F0 !important;
  margin-bottom: 16px !important;
}

.cash-input-row {
  display: flex !important;
  flex-direction: column !important;
  gap: 6px !important;
}

.cash-label {
  font-size: 13px !important;
  font-weight: 800 !important;
  color: #334155 !important;
}

.cash-input-wrapper {
  position: relative !important;
  display: flex !important;
  align-items: center !important;
}

.currency-prefix {
  position: absolute !important;
  left: 14px !important;
  font-size: 22px !important;
  font-weight: 900 !important;
  color: #64748B !important;
  z-index: 2 !important;
}

.cash-input-wrapper .cash-input {
  width: 100% !important;
  padding: 12px 40px 12px 38px !important;
  font-size: 24px !important;
  font-weight: 900 !important;
  border: 2px solid #CBD5E1 !important;
  border-radius: 12px !important;
  color: #0F172A !important;
  font-family: 'Prompt', monospace !important;
  background: #F8FAFC !important;
}

.cash-input-wrapper .cash-input:focus {
  border-color: #2563EB !important;
  background: #FFFFFF !important;
  outline: none !important;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15) !important;
}

.btn-clear-cash {
  position: absolute !important;
  right: 12px !important;
  background: #E2E8F0 !important;
  border: none !important;
  border-radius: 50% !important;
  width: 24px !important;
  height: 24px !important;
  font-size: 12px !important;
  font-weight: 800 !important;
  color: #64748B !important;
  cursor: pointer !important;
}

.quick-cash-label {
  font-size: 12px !important;
  font-weight: 700 !important;
  color: #64748B !important;
  margin: 14px 0 6px !important;
}

.quick-cash-row {
  display: flex !important;
  gap: 8px !important;
  flex-wrap: wrap !important;
}

.quick-cash-btn {
  padding: 8px 14px !important;
  border-radius: 8px !important;
  border: 1px solid #CBD5E1 !important;
  background: #FFFFFF !important;
  font-size: 13px !important;
  font-weight: 800 !important;
  color: #1E293B !important;
  cursor: pointer !important;
  transition: all 0.15s !important;
}

.quick-cash-btn:hover {
  border-color: #2563EB !important;
  color: #2563EB !important;
  background: #EFF6FF !important;
}

.quick-cash-btn.exact-btn {
  background: #EFF6FF !important;
  border-color: #93C5FD !important;
  color: #1D4ED8 !important;
}

.cash-add-row {
  display: flex !important;
  gap: 8px !important;
  flex-wrap: wrap !important;
}

.cash-add-pill {
  padding: 7px 14px !important;
  background: #F1F5F9 !important;
  border: 1px solid #CBD5E1 !important;
  border-radius: 8px !important;
  font-size: 13px !important;
  font-weight: 800 !important;
  color: #334155 !important;
  cursor: pointer !important;
  transition: all 0.15s !important;
}

.cash-add-pill:hover {
  background: #E2E8F0 !important;
  border-color: #94A3B8 !important;
  transform: translateY(-1px) !important;
}

.change-display-box {
  margin-top: 16px !important;
  padding: 14px 18px !important;
  border-radius: 12px !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 4px !important;
}

.change-display-box.has-change {
  background: #F0FDF4 !important;
  border: 1.5px solid #86EFAC !important;
}

.change-display-box.is-short {
  background: #FFFBEB !important;
  border: 1.5px solid #FCD34D !important;
}

.change-line {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
}

.change-title {
  font-size: 14px !important;
  font-weight: 800 !important;
  color: #0F172A !important;
}

.change-amount {
  font-size: 22px !important;
  font-weight: 900 !important;
  font-family: 'Prompt', monospace !important;
}

.has-change .change-amount {
  color: #16A34A !important;
}

.is-short .change-amount {
  color: #D97706 !important;
}

.change-sub-detail {
  display: flex !important;
  gap: 8px !important;
  font-size: 12px !important;
  color: #64748B !important;
  font-weight: 600 !important;
}



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



/* Z-Index for Nested Member Modal */
.pos-modal-overlay.attach-member-overlay {
  z-index: 100050 !important;
}
.attach-member-modal {
  position: relative !important;
  z-index: 100051 !important;
}



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


/* ── Direct Table Checkout in Modal ─────────────────────────────── */
.table-card-unpaid-box {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed #CBD5E1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.table-unpaid-sum {
  font-size: 12px;
  font-weight: 800;
  color: #1E40AF;
}
.btn-table-checkout-direct {
  padding: 4px 8px;
  background: linear-gradient(135deg, #10B981, #059669);
  color: #ffffff;
  border: none;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-table-checkout-direct:hover {
  transform: scale(1.03);
  box-shadow: 0 2px 6px rgba(16, 185, 129, 0.4);
}

/* ── Topbar Quick Buttons ────────────────────────────────────────── */
.quick-unpaid-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 12px;
  border-radius: 9px;
  border: 1px solid #CBD5E1;
  background: #FFFBEB;
  color: #B45309;
  font-weight: 700;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.quick-unpaid-btn:hover {
  background: #FEF3C7;
  border-color: #F59E0B;
}

.quick-checkout-header-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  border-radius: 9px;
  border: none;
  background: linear-gradient(135deg, #10B981, #059669);
  color: #ffffff;
  font-weight: 800;
  font-size: 13px;
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(16, 185, 129, 0.35);
}

.btn-sm-edit-order {
  padding: 4px 8px;
  background: #EFF6FF;
  border: 1px solid #BFDBFE;
  border-radius: 6px;
  color: #1D4ED8;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  margin-left: 4px;
}

/* ── Bottom Nav default hidden on Desktop ────────────────────────── */
.pos-mobile-bottom-nav {
  display: none;
}

/* ── MOBILE RESPONSIVE STYLES (max-width: 768px) ────────────────────── */
@media (max-width: 768px) {
  /* CONTAINER FLEX DIRECTION ON MOBILE */
  .pos-restodash {
    flex-direction: column !important;
  }

  /* 0. COMPACT ALARM BANNER ON MOBILE */
  .pos-alarm-banner {
    padding: 8px 12px !important;
    border-radius: 0 0 12px 12px !important;
  }
  .alarm-content {
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 6px !important;
  }
  .alarm-icon-box {
    display: none !important;
  }
  .alarm-text-box {
    width: 100% !important;
  }
  .alarm-title {
    font-size: 13.5px !important;
    font-weight: 800 !important;
    white-space: normal !important;
    line-height: 1.3 !important;
  }
  .alarm-desc {
    font-size: 11.5px !important;
    white-space: normal !important;
    line-height: 1.3 !important;
    opacity: 0.9 !important;
  }
  .alarm-actions {
    display: flex !important;
    align-items: center !important;
    justify-content: flex-end !important;
    gap: 8px !important;
    width: 100% !important;
    margin-top: 2px !important;
  }
  .alarm-btn-checkout,
  .alarm-btn-accept,
  .alarm-btn-dismiss {
    padding: 5px 12px !important;
    font-size: 12px !important;
    border-radius: 6px !important;
  }

  /* 1. HIDE LEFT SIDEBAR AND EXPAND BUTTON COMPLETELY ON MOBILE */
  .pos-sidebar-left {
    display: none !important;
    width: 0 !important;
    min-width: 0 !important;
    max-width: 0 !important;
    overflow: hidden !important;
    position: absolute !important;
    pointer-events: none !important;
  }
  .floating-sidebar-expand-btn {
    display: none !important;
  }

  /* 2. CENTER MAIN: FULL 100vw ON MOBILE */
  .pos-center-main {
    width: 100vw !important;
    max-width: 100vw !important;
    height: 100vh !important;
    overflow-x: hidden !important;
    display: flex !important;
    flex-direction: column !important;
  }

  /* 3. CLEAN 2-ROW TOP BAR ON MOBILE */
  .center-topbar {
    display: flex !important;
    flex-direction: column !important;
    padding: 8px 10px !important;
    gap: 6px !important;
    background: #ffffff !important;
    border-bottom: 1px solid #E2E8F0 !important;
    height: auto !important;
    flex-shrink: 0 !important;
  }

  .topbar-actions {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    width: 100% !important;
    order: 1 !important;
    gap: 6px !important;
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch !important;
  }

  .quick-pill-btn {
    flex: 1 !important;
    padding: 6px 10px !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    white-space: nowrap !important;
    text-overflow: ellipsis !important;
    overflow: hidden !important;
  }

  .quick-unpaid-btn {
    padding: 6px 9px !important;
    font-size: 11.5px !important;
    font-weight: 700 !important;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
  }

  .quick-kds-btn {
    padding: 6px 9px !important;
    font-size: 11.5px !important;
    font-weight: 700 !important;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
  }

  .quick-checkout-header-btn {
    padding: 6px 10px !important;
    font-size: 12px !important;
    font-weight: 800 !important;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
  }

  .quick-settings-btn {
    display: none !important; /* Managed via bottom nav on mobile */
  }

  .search-box-wrapper {
    order: 2 !important;
    width: 100% !important;
    max-width: 100% !important;
    height: 36px !important;
    margin-top: 2px !important;
  }

  /* 4. HORIZONTAL CATEGORY SLIDER */
  .category-slide-bar {
    display: flex !important;
    align-items: center !important;
    padding: 6px 10px !important;
    gap: 6px !important;
    background: #F8FAFC !important;
    border-bottom: 1px solid #E2E8F0 !important;
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch !important;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
  }

  .slide-cat-tab {
    padding: 4px 10px !important;
    font-size: 11.5px !important;
    font-weight: 600 !important;
    border-radius: 20px !important;
    flex-shrink: 0 !important;
  }

  /* 5. FOOD GRID: COMPACT & SHORTER FOR MORE SCREEN REAL ESTATE */
  .food-scroll-container {
    flex: 1 !important;
    padding: 8px 8px 130px 8px !important; /* Space for floating cart & bottom nav */
    overflow-y: auto !important;
    -webkit-overflow-scrolling: touch !important;
  }

  .food-grid {
    display: grid !important;
    grid-template-columns: repeat(2, 1fr) !important;
    gap: 8px !important;
    width: 100% !important;
  }

  .food-card {
    border-radius: 10px !important;
    overflow: hidden !important;
    background: #ffffff !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04) !important;
    display: flex !important;
    flex-direction: column !important;
  }

  .food-thumb-wrap {
    height: 85px !important; /* Shorter card image */
    width: 100% !important;
    position: relative !important;
  }

  .food-img {
    width: 100% !important;
    height: 100% !important;
    object-fit: cover !important;
  }

  .food-info {
    padding: 6px 8px 8px 8px !important;
    display: flex !important;
    flex-direction: column !important;
    flex: 1 !important;
    justify-content: space-between !important;
  }

  .food-name {
    font-size: 11.5px !important;
    font-weight: 700 !important;
    line-height: 1.25 !important;
    height: 28px !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    display: -webkit-box !important;
    -webkit-line-clamp: 2 !important;
    -webkit-box-orient: vertical !important;
    margin-bottom: 4px !important;
  }

  .food-meta {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    margin-top: auto !important;
  }

  .food-price {
    font-size: 13.5px !important;
    font-weight: 800 !important;
    color: #2563EB !important;
  }

  .food-add-btn {
    width: 28px !important;
    height: 28px !important;
    border-radius: 6px !important;
    background: #2563EB !important;
    color: #ffffff !important;
    border: none !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    cursor: pointer !important;
  }

  /* 6. RIGHT CART: MOBILE SLIDE-OVER DRAWER */
  .pos-sidebar-right {
    display: none !important;
  }

  .pos-sidebar-right.is-mobile-open {
    display: flex !important;
    position: fixed !important;
    top: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    width: 88vw !important;
    max-width: 400px !important;
    z-index: 100020 !important;
    box-shadow: -8px 0 30px rgba(0, 0, 0, 0.3) !important;
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
    padding: 4px 10px !important;
    border-radius: 6px !important;
    font-size: 12px !important;
    font-weight: 800 !important;
    cursor: pointer !important;
    margin-left: 6px !important;
  }

  /* 7. FLOATING BOTTOM CART BAR (FLOATS ABOVE BOTTOM NAV) */
  .mobile-floating-cart-btn {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    position: fixed !important;
    bottom: 64px !important; /* Floats above the 56px bottom nav */
    right: 12px !important;
    left: 12px !important;
    background: linear-gradient(135deg, #2563EB, #1D4ED8) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 10px 14px !important;
    font-size: 13.5px !important;
    font-weight: 800 !important;
    font-family: 'Prompt', sans-serif !important;
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.45) !important;
    z-index: 99999 !important;
    cursor: pointer !important;
    animation: pop-up-bounce 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
  }

  .m-cart-left {
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
  }
  .m-cart-icon {
    font-size: 16px !important;
  }
  .m-cart-text {
    font-size: 13px !important;
    font-weight: 800 !important;
  }
  .m-cart-right {
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
  }
  .m-cart-total {
    font-size: 14.5px !important;
    font-weight: 900 !important;
  }
  .m-cart-arrow {
    background: rgba(255, 255, 255, 0.25) !important;
    padding: 3px 8px !important;
    border-radius: 6px !important;
    font-size: 11.5px !important;
    font-weight: 800 !important;
  }

  /* 8. PWA MOBILE BOTTOM NAVIGATION BAR */
  .pos-mobile-bottom-nav {
    display: flex !important;
    align-items: center !important;
    justify-content: space-around !important;
    position: fixed !important;
    bottom: 0 !important;
    left: 0 !important;
    right: 0 !important;
    width: 100vw !important;
    height: 56px !important;
    background: #ffffff !important;
    border-top: 1px solid #E2E8F0 !important;
    box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.08) !important;
    z-index: 900 !important;
    padding: 0 4px !important;
    padding-bottom: env(safe-area-inset-bottom, 0px) !important;
  }

  .m-nav-tab {
    flex: 1 1 0 !important;
    min-width: 0 !important;
    width: 20% !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    height: 100% !important;
    background: transparent !important;
    border: none !important;
    color: #64748B !important;
    font-family: 'Prompt', sans-serif !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
    padding: 2px !important;
    position: relative !important;
  }

  .m-nav-tab.is-active {
    color: #2563EB !important;
    font-weight: 700 !important;
  }

  .m-nav-icon-wrap {
    position: relative !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
  }

  .m-nav-icon {
    font-size: 19px !important;
    line-height: 1 !important;
    margin-bottom: 2px !important;
  }

  .m-nav-label {
    font-size: 10px !important;
    font-weight: 600 !important;
    letter-spacing: -0.2px !important;
    white-space: nowrap !important;
  }

  .m-nav-badge {
    position: absolute !important;
    top: -4px !important;
    right: -8px !important;
    background: #EF4444 !important;
    color: #ffffff !important;
    font-size: 9px !important;
    font-weight: 900 !important;
    padding: 1px 4px !important;
    border-radius: 10px !important;
    min-width: 14px !important;
    text-align: center !important;
    line-height: 1.2 !important;
  }

  .m-nav-badge.kds-pulse {
    background: #F97316 !important;
  }

  /* 9. SETTINGS FULLPAGE: MOBILE RESPONSIVE OVERHAUL */
  .settings-fullpage {
    width: 100vw !important;
    height: 100vh !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
  }
  .settings-topbar {
    padding: 10px 14px !important;
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 8px !important;
  }
  .settings-topbar-left {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    width: 100% !important;
  }
  .settings-main-title {
    font-size: 16px !important;
  }
  .settings-sub-title {
    display: none !important;
  }
  .settings-topbar-right {
    display: none !important;
  }
  /* ── 9. MOBILE SETTINGS 2-STEP DRILL-DOWN NAVIGATION ── */
  .settings-body-layout {
    flex-direction: column !important;
    overflow-y: auto !important;
    flex: 1 !important;
    background: #F8FAFC !important;
  }
  .settings-nav-sidebar {
    width: 100% !important;
    min-width: 100% !important;
    max-width: 100% !important;
    height: auto !important;
    flex-direction: column !important;
    overflow-y: auto !important;
    padding: 14px 14px 110px 14px !important;
    gap: 8px !important;
    border-right: none !important;
    background: #F8FAFC !important;
  }
  .settings-nav-sidebar.mobile-hidden {
    display: none !important;
  }
  .settings-mobile-menu-header {
    display: block !important;
    margin-bottom: 10px !important;
    padding: 4px 2px 8px 2px !important;
    border-bottom: 1px solid #E2E8F0 !important;
  }
  .settings-mobile-title {
    font-size: 17px !important;
    font-weight: 800 !important;
    color: #0F172A !important;
    margin: 0 0 4px !important;
  }
  .settings-mobile-sub {
    font-size: 12px !important;
    color: #64748B !important;
    margin: 0 !important;
  }
  .settings-nav-item {
    display: flex !important;
    align-items: center !important;
    padding: 12px 14px !important;
    background: #FFFFFF !important;
    border: 1.5px solid #E2E8F0 !important;
    border-radius: 14px !important;
    box-shadow: 0 2px 6px rgba(15, 23, 42, 0.03) !important;
    gap: 12px !important;
    width: 100% !important;
    text-align: left !important;
  }
  .settings-nav-item:active {
    background: #EFF6FF !important;
    border-color: #BFDBFE !important;
  }
  .settings-nav-item .nav-item-icon {
    font-size: 22px !important;
  }
  .settings-nav-item .nav-item-text {
    flex: 1 !important;
  }
  .settings-nav-item .nav-item-title {
    font-size: 14px !important;
    font-weight: 800 !important;
    color: #0F172A !important;
  }
  .settings-nav-item .nav-item-desc {
    display: block !important;
    font-size: 11.5px !important;
    color: #64748B !important;
    margin-top: 1px !important;
  }
  .settings-nav-item .nav-item-arrow {
    display: block !important;
    font-size: 20px !important;
    color: #94A3B8 !important;
    font-weight: 700 !important;
  }
  .settings-content-panel.mobile-hidden {
    display: none !important;
  }
  .settings-content-panel {
    padding: 12px 14px 110px 14px !important;
    width: 100% !important;
  }
  .settings-mobile-back-bar {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    margin-bottom: 12px !important;
    padding-bottom: 10px !important;
    border-bottom: 1.5px solid #E2E8F0 !important;
  }
  .btn-settings-back {
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
    padding: 8px 12px !important;
    background: #EFF6FF !important;
    border: 1px solid #BFDBFE !important;
    color: #1D4ED8 !important;
    border-radius: 10px !important;
    font-family: 'Prompt', sans-serif !important;
    font-size: 13px !important;
    font-weight: 800 !important;
    cursor: pointer !important;
  }
  .current-tab-badge {
    font-size: 12px !important;
    font-weight: 800 !important;
    color: #64748B !important;
    background: #F1F5F9 !important;
    padding: 4px 10px !important;
    border-radius: 12px !important;
  }
  .settings-card {
    padding: 14px !important;
    border-radius: 12px !important;
  }
  .card-header-row {
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 10px !important;
  }
  .card-title {
    font-size: 16px !important;
  }
  .card-subtitle {
    font-size: 12px !important;
  }
  .btn-primary-save {
    width: 100% !important;
    justify-content: center !important;
    padding: 10px !important;
  }
  .form-grid-2 {
    grid-template-columns: 1fr !important;
    gap: 10px !important;
  }
  .form-group.span-2 {
    grid-column: span 1 !important;
  }

  /* ── 10. MODALS & PAYMENT RESPONSIVE ON MOBILE ── */
  .table-select-modal,
  .orders-modal-box {
    width: 96vw !important;
    max-width: 96vw !important;
    max-height: 92vh !important;
    overflow-y: auto !important;
  }
  .tables-grid {
    grid-template-columns: repeat(2, 1fr) !important;
    gap: 8px !important;
    padding: 10px !important;
  }
  .orders-filter-bar {
    padding: 8px 10px !important;
    gap: 6px !important;
  }

  /* KDS IN POS ON MOBILE: 1 COLUMN GRID FOR CLEAR VISIBILITY */
  .kds-tickets-grid {
    grid-template-columns: 1fr !important;
    gap: 12px !important;
  }

  /* PAYMENT MODAL ON MOBILE: NO STRETCH, SCROLLABLE BODY, FIXED BOTTOM FOOTER */
  .payment-modal.payment-modal-wide {
    width: 96vw !important;
    max-width: 96vw !important;
    max-height: calc(100vh - 40px) !important;
    height: auto !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
    border-radius: 18px !important;
    padding: 0 !important;
    margin-bottom: 20px !important;
  }
  .payment-modal-header {
    padding: 10px 14px !important;
    flex-shrink: 0 !important;
    background: #FFFFFF !important;
    border-bottom: 1px solid #E2E8F0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    min-height: 48px !important;
  }
  .desktop-only-header-block,
  .desktop-only-hero {
    display: none !important;
  }
  .mobile-only-header-block {
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
    flex: 1 !important;
    min-width: 0 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
  }
  .payment-header-mobile-single-row .m-header-title {
    font-size: 14.5px !important;
    font-weight: 800 !important;
    color: #0F172A !important;
    white-space: nowrap !important;
  }
  .payment-header-mobile-single-row .m-header-sep {
    color: #94A3B8 !important;
    font-weight: 700 !important;
    font-size: 12px !important;
  }
  .payment-header-mobile-single-row .m-header-target-chip {
    background: #EFF6FF !important;
    color: #1D4ED8 !important;
    padding: 3px 7px !important;
    border-radius: 6px !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    white-space: nowrap !important;
    text-overflow: ellipsis !important;
    overflow: hidden !important;
    max-width: 120px !important;
  }
  .payment-header-mobile-single-row .m-header-total-chip {
    background: #ECFDF5 !important;
    color: #059669 !important;
    padding: 3px 8px !important;
    border-radius: 6px !important;
    font-size: 13.5px !important;
    font-weight: 800 !important;
    white-space: nowrap !important;
  }
  .payment-modal-body-grid {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 !important;
    overflow-y: auto !important;
    min-height: 0 !important;
  }
  .payment-order-summary-panel {
    border-right: none !important;
    border-bottom: 1.5px solid #E2E8F0 !important;
    padding: 10px 14px !important;
    flex-shrink: 0 !important;
    background: #F8FAFC !important;
  }
  .payment-summary-items-list {
    max-height: 100px !important;
    overflow-y: auto !important;
  }
  .payment-tender-panel {
    padding: 12px 14px 20px 14px !important;
    flex: 1 !important;
  }
  .payment-modal-footer {
    position: sticky !important;
    bottom: 0 !important;
    background: #FFFFFF !important;
    border-top: 1.5px solid #E2E8F0 !important;
    padding: 12px 14px max(14px, env(safe-area-inset-bottom, 14px)) !important;
    z-index: 20 !important;
    box-shadow: 0 -4px 14px rgba(0,0,0,0.06) !important;
    display: flex !important;
    gap: 8px !important;
  }
  .payment-modal-footer .btn-cancel {
    flex: 1 !important;
    padding: 10px !important;
  }
  .payment-modal-footer .btn-confirm-pay {
    flex: 2 !important;
    padding: 12px 10px !important;
    font-size: 13.5px !important;
  }

  /* KDS MODAL HEADER ON MOBILE */
  .kds-modal-box {
    width: 96vw !important;
    max-width: 96vw !important;
  }
  .kds-header-flex {
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 10px !important;
    padding: 12px 14px !important;
  }
  .kds-header-top-row {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    width: 100% !important;
  }
  .kds-title-sub-wrap .modal-title {
    font-size: 15px !important;
    font-weight: 800 !important;
    margin: 0 !important;
  }
  .kds-title-sub-wrap .modal-sub {
    font-size: 11.5px !important;
    color: #64748B !important;
  }
  .kds-mobile-close-btn {
    display: flex !important;
  }
  .kds-desktop-close-btn {
    display: none !important;
  }
  .kds-header-controls {
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
    width: 100% !important;
    overflow-x: auto !important;
    padding-bottom: 2px !important;
  }
  .btn-open-standalone-kds,
  .kds-sound-toggle-btn,
  .kds-test-sound-btn {
    font-size: 11.5px !important;
    padding: 6px 10px !important;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
  }

  /* ── 11. MOBILE FLOATING CART BAR (WITH DIRECT CHECKOUT) ── */
  .mobile-floating-cart-btn {
    display: none !important;
  }
  .mobile-floating-cart-bar {
    position: fixed !important;
    bottom: 64px !important; /* Above bottom nav */
    left: 10px !important;
    right: 10px !important;
    z-index: 105 !important;
    background: linear-gradient(135deg, #0F172A, #1E293B) !important;
    border-radius: 14px !important;
    padding: 7px 10px !important;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.4) !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 10px !important;
  }
  .m-cart-summary-btn {
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
    flex: 1 !important;
    cursor: pointer !important;
    min-width: 0 !important;
  }
  .m-cart-summary-btn .m-cart-icon {
    font-size: 20px !important;
  }
  .m-cart-summary-btn .m-cart-info {
    display: flex !important;
    flex-direction: column !important;
    min-width: 0 !important;
  }
  .m-cart-summary-btn .m-cart-text {
    font-size: 11px !important;
    color: #94A3B8 !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
  }
  .m-cart-summary-btn .m-cart-total {
    font-size: 15px !important;
    font-weight: 900 !important;
    color: #38BDF8 !important;
    font-family: 'Prompt', monospace !important;
    line-height: 1.2 !important;
  }
  .m-cart-summary-btn .m-cart-arrow {
    font-size: 10px !important;
    color: #64748B !important;
    margin-left: 2px !important;
  }
  .m-cart-direct-pay-btn {
    background: linear-gradient(135deg, #10B981, #059669) !important;
    border: none !important;
    border-radius: 10px !important;
    color: #FFFFFF !important;
    font-family: 'Prompt', sans-serif !important;
    font-size: 13.5px !important;
    font-weight: 800 !important;
    padding: 9px 14px !important;
    cursor: pointer !important;
    white-space: nowrap !important;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.35) !important;
    display: flex !important;
    align-items: center !important;
    gap: 4px !important;
  }
  .m-cart-direct-pay-btn:active {
    transform: scale(0.97) !important;
  }
}



  /* ── NOTE MODAL FLOATS EXCLUSIVELY ABOVE MOBILE CART DRAWER ── */
  .pos-modal-overlay.note-modal-overlay {
    z-index: 200050 !important;
    padding: 12px !important;
    align-items: center !important;
    justify-content: center !important;
  }
  .note-modal-box {
    width: 94vw !important;
    max-width: 420px !important;
    max-height: 88vh !important;
    border-radius: 16px !important;
    z-index: 200051 !important;
  }
  .note-modal-body {
    padding: 14px 16px !important;
    gap: 12px !important;
    overflow-y: auto !important;
  }
  .quick-notes-chips {
    gap: 6px !important;
    max-height: 120px !important;
  }
  .quick-note-chip {
    padding: 6px 12px !important;
    font-size: 13px !important;
  }
  .note-textarea {
    font-size: 16.5px !important;
    padding: 12px 14px !important;
    min-height: 100px !important;
  }
  .note-modal-footer {
    padding: 12px 16px !important;
    gap: 10px !important;
  }
  .btn-save-note {
    font-size: 14.5px !important;
    padding: 10px 20px !important;
  }

/* ── Unpaid Orders Mobile Cards Styling ───────────────────────────── */
.desktop-only-orders-table {
  display: table !important;
  width: 100% !important;
}
.mobile-only-orders-cards {
  display: none !important;
}

@media (max-width: 768px) {
  .desktop-only-orders-table {
    display: none !important;
  }
  .mobile-only-orders-cards {
    display: flex !important;
    flex-direction: column !important;
    gap: 12px !important;
    padding: 10px 4px !important;
  }
  .order-mobile-card {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 14px !important;
    padding: 14px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05) !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 10px !important;
    transition: all 0.2s !important;
  }
  .order-mobile-card.is-unpaid-card {
    border-left: 5px solid #F59E0B !important;
    background: #FFFDF9 !important;
  }
  .card-top-bar {
    display: flex !important;
    justify-content: space-between !important;
    align-items: center !important;
    gap: 8px !important;
  }
  .card-id-table {
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
    flex-wrap: wrap !important;
  }
  .card-order-id {
    font-size: 14.5px !important;
    font-weight: 800 !important;
    color: #0F172A !important;
  }
  .card-table-badge {
    background: #EFF6FF !important;
    color: #1D4ED8 !important;
    font-size: 11.5px !important;
    font-weight: 700 !important;
    padding: 2px 8px !important;
    border-radius: 6px !important;
    border: 1px solid #BFDBFE !important;
  }
  .card-channel-pill {
    font-size: 10.5px !important;
    font-weight: 700 !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
  }
  .card-channel-pill.shop {
    background: #F1F5F9 !important;
    color: #475569 !important;
  }
  .card-channel-pill.online {
    background: #ECFDF5 !important;
    color: #059669 !important;
  }
  .card-info-row {
    display: flex !important;
    justify-content: space-between !important;
    align-items: center !important;
    gap: 8px !important;
    font-size: 12px !important;
    color: #64748B !important;
  }
  .card-time-block {
    display: flex !important;
    align-items: center !important;
    gap: 4px !important;
  }
  .time-main-txt {
    font-weight: 700 !important;
    color: #334155 !important;
  }
  .time-elapsed-badge {
    color: #94A3B8 !important;
    font-size: 11px !important;
  }
  .card-customer-block {
    display: flex !important;
    align-items: center !important;
  }
  .btn-change-member-card,
  .btn-link-member-card {
    background: #F1F5F9 !important;
    border: 1px solid #CBD5E1 !important;
    color: #2563EB !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    cursor: pointer !important;
    margin-left: 6px !important;
  }
  .card-items-preview {
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
    font-size: 11.5px !important;
    background: #F8FAFC !important;
    padding: 6px 10px !important;
    border-radius: 8px !important;
    border: 1px dashed #CBD5E1 !important;
    overflow: hidden !important;
  }
  .items-count-badge {
    font-weight: 700 !important;
    color: #0F172A !important;
    white-space: nowrap !important;
  }
  .items-preview-text {
    color: #64748B !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
  }
  .card-bottom-bar {
    display: flex !important;
    justify-content: space-between !important;
    align-items: center !important;
    gap: 10px !important;
    padding-top: 8px !important;
    border-top: 1px solid #F1F5F9 !important;
  }
  .card-total-group {
    display: flex !important;
    align-items: baseline !important;
    gap: 6px !important;
  }
  .card-total-label {
    font-size: 12px !important;
    color: #64748B !important;
    font-weight: 600 !important;
  }
  .card-total-value {
    font-size: 17px !important;
    font-weight: 900 !important;
    color: #2563EB !important;
    font-family: 'Prompt', sans-serif !important;
  }
  .card-actions-group {
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
  }
  .btn-card-pay {
    background: linear-gradient(135deg, #10B981, #059669) !important;
    color: #FFFFFF !important;
    font-size: 12.5px !important;
    font-weight: 800 !important;
    padding: 7px 14px !important;
    border-radius: 8px !important;
    border: none !important;
    cursor: pointer !important;
    box-shadow: 0 2px 6px rgba(16, 185, 129, 0.3) !important;
    display: flex !important;
    align-items: center !important;
    gap: 4px !important;
  }
  .btn-card-pay:active {
    transform: scale(0.97) !important;
  }
  .btn-card-add {
    background: #F8FAFC !important;
    color: #334155 !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    padding: 7px 10px !important;
    border-radius: 8px !important;
    border: 1px solid #CBD5E1 !important;
    cursor: pointer !important;
  }
  .btn-card-void {
    background: #FEF2F2 !important;
    color: #DC2626 !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    padding: 7px 8px !important;
    border-radius: 8px !important;
    border: 1px solid #FECACA !important;
    cursor: pointer !important;
  }
  .btn-card-receipt {
    background: #EFF6FF !important;
    color: #2563EB !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    padding: 7px 12px !important;
    border-radius: 8px !important;
    border: 1px solid #BFDBFE !important;
    cursor: pointer !important;
  }
}

</style>
