/* ═══════════════════════════════════════════════════════════════════════════
   ERP Modular — Event Bus (postMessage bridge)
   ═══════════════════════════════════════════════════════════════════════════
   ให้ Mini Apps ส่ง event ถึงกันผ่าน iframe + postMessage
   ใช้งาน:
     // ส่ง event
     ERPEventBus.emit('project.created', { id: 1, name: 'Project A' });

     // รับ event
     ERPEventBus.on('project.created', (data) => { ... });

     // Mini App (ใน iframe) ส่ง event ไปยัง Shell
     window.parent.postMessage({ type: 'erp-event', event: 'task.done', data: {...} }, '*');
   ═══════════════════════════════════════════════════════════════════════════ */

const ERPEventBus = (() => {
  const _listeners = {};
  const _appOrigins = {};  // appSlug -> origin URL

  function _getOrigin(url) {
    try { return new URL(url).origin; } catch { return '*'; }
  }

  /* ─── ฟัง event จาก Mini Apps (postMessage) ─── */
  function _handleMessage(event) {
    const msg = event.data;
    if (!msg || msg.type !== 'erp-event') return;

    const { event: eventName, data, source } = msg;
    if (!eventName) return;

    // ตรวจสอบ origin ถ้ารู้จัก
    const allowed = Object.values(_appOrigins);
    if (allowed.length > 0 && !allowed.includes(event.origin) && event.origin !== window.location.origin) {
      console.warn(`[EventBus] ละเว้น event จาก origin ไม่รู้จัก: ${event.origin}`);
      return;
    }

    _notify(eventName, data, source || 'mini-app');
  }

  /* ─── แจ้ง listeners ทั้งหมด ─── */
  function _notify(eventName, data, source) {
    const handlers = _listeners[eventName];
    if (!handlers || handlers.length === 0) return;

    const envelope = { event: eventName, data, source, timestamp: Date.now() };
    handlers.forEach(fn => {
      try { fn(envelope); } catch (err) {
        console.error(`[EventBus] handler error for "${eventName}":`, err);
      }
    });
  }

  /* ─── API ─── */

  function on(eventName, handler) {
    if (!_listeners[eventName]) _listeners[eventName] = [];
    _listeners[eventName].push(handler);
    return () => off(eventName, handler);  // return unsubscribe
  }

  function off(eventName, handler) {
    const handlers = _listeners[eventName];
    if (!handlers) return;
    _listeners[eventName] = handlers.filter(fn => fn !== handler);
  }

  function emit(eventName, data) {
    _notify(eventName, data, 'shell');
  }

  function registerApp(appSlug, origin) {
    if (origin) _appOrigins[appSlug] = origin;
  }

  function init() {
    window.addEventListener('message', _handleMessage);
    console.log('[EventBus] พร้อมทำงาน');
  }

  function destroy() {
    window.removeEventListener('message', _handleMessage);
    Object.keys(_listeners).forEach(k => delete _listeners[k]);
  }

  return { init, destroy, on, off, emit, registerApp };
})();
