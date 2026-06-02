/* ═══════════════════════════════════════════════════════════════════════════
   ERP Modular — Shell Configuration
   ═══════════════════════════════════════════════════════════════════════════
   แก้ไขไฟล์นี้เพื่อกำหนดค่า Mini Apps และ Gateway URL
   ═══════════════════════════════════════════════════════════════════════════ */

window.ERP_CONFIG = {
  /* URL ของ API Gateway (ไม่ต้องเปลี่ยนถ้า Shell อยู่บน origin เดียวกับ Gateway) */
  gatewayUrl: '/gateway',

  /* Mini Apps — ไม่ต้อง hardcode แล้ว
     Shell จะโหลดจาก Gateway API (GET /gateway/apps) โดยอัตโนมัติ
     โดยใช้ ERPAppRegistry.loadFromGateway()
  */
  apps: {},
};
