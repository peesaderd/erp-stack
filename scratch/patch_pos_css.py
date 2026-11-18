with open('scratch/PosRestodash.vue', 'r', encoding='utf-8') as f:
    content = f.read()

# Desktop CSS additions
desktop_css = '''
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
'''

# Find end of <style> or near mobile query
mobile_idx = content.find('/* ── MOBILE RESPONSIVE STYLES (max-width: 768px)')
assert mobile_idx != -1, "mobile query comment not found!"
content = content[:mobile_idx] + desktop_css + '\n' + content[mobile_idx:]

# Now replace the mobile styles block with the complete enhanced version
mobile_target_start = content.find('/* ── MOBILE RESPONSIVE STYLES (max-width: 768px)')
mobile_target_end = content.rfind('</style>')

enhanced_mobile_css = '''/* ── MOBILE RESPONSIVE STYLES (max-width: 768px) ────────────────────── */
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
    height: 56px !important;
    background: #ffffff !important;
    border-top: 1px solid #E2E8F0 !important;
    box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05) !important;
    z-index: 100010 !important;
    padding-bottom: env(safe-area-inset-bottom, 0px) !important;
  }

  .m-nav-tab {
    flex: 1 !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    height: 100% !important;
    background: none !important;
    border: none !important;
    color: #64748B !important;
    font-family: 'Prompt', sans-serif !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
    padding: 4px 2px !important;
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
  .settings-body-layout {
    flex-direction: column !important;
    overflow-y: auto !important;
  }
  .settings-nav-sidebar {
    width: 100% !important;
    min-width: 100% !important;
    max-width: 100% !important;
    height: auto !important;
    flex-direction: row !important;
    overflow-x: auto !important;
    padding: 6px 10px !important;
    gap: 6px !important;
    border-right: none !important;
    border-bottom: 1px solid #E2E8F0 !important;
    background: #ffffff !important;
    flex-shrink: 0 !important;
    white-space: nowrap !important;
    -webkit-overflow-scrolling: touch !important;
  }
  .settings-nav-item {
    padding: 6px 12px !important;
    border-radius: 20px !important;
    flex-shrink: 0 !important;
    gap: 6px !important;
    border: 1px solid #E2E8F0 !important;
  }
  .settings-nav-item .nav-item-icon {
    font-size: 16px !important;
  }
  .settings-nav-item .nav-item-desc {
    display: none !important;
  }
  .settings-nav-item .nav-item-title {
    font-size: 12px !important;
  }
  .settings-content-panel {
    padding: 12px 12px 90px 12px !important;
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

  /* 10. MODALS RESPONSIVE ON MOBILE */
  .table-select-modal,
  .orders-modal-box,
  .payment-modal-wide {
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
}
'''

content = content[:mobile_target_start] + enhanced_mobile_css + '\n' + content[mobile_target_end:]

with open('scratch/PosRestodash.vue', 'w', encoding='utf-8') as f:
    f.write(content)

print("CSS enhanced successfully!")
