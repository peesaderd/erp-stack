/* ═══════════════════════════════════════════════════════════════════════════
   ERP Modular — Auth Client (JWT management)
   ═══════════════════════════════════════════════════════════════════════════
   จัดการ JWT token, login/logout, ส่ง token ไปยัง Mini Apps
   ═══════════════════════════════════════════════════════════════════════════ */

const ERPAuth = (() => {
  const STORAGE_KEY = 'erp_auth_token';
  const GATEWAY_URL = (window.ERP_CONFIG && window.ERP_CONFIG.gatewayUrl) || '/gateway';

  let _token = localStorage.getItem(STORAGE_KEY) || null;
  let _tokenData = null;
  let _listeners = [];

  /* ─── JWT Decode (ไม่ต้องใช้ lib) ─── */
  function _decodePayload(token) {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) return null;
      return JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
    } catch { return null; }
  }

  /* ─── ตรวจสอบว่า token หมดอายุหรือยัง ─── */
  function _isExpired(payload) {
    if (!payload || !payload.exp) return true;
    return Date.now() >= payload.exp * 1000;
  }

  /* ─── แจ้ง listeners ─── */
  function _notify() {
    _listeners.forEach(fn => { try { fn(_tokenData); } catch {} });
  }

  /* ─── API ─── */

  function getToken() { return _token; }

  function getTokenData() { return _tokenData; }

  function isAuthenticated() { return !!_token && !_isExpired(_tokenData); }

  function getRole() { return _tokenData?.role || 'viewer'; }

  function hasPermission(perm) {
    return _tokenData?.permissions?.includes(perm) || false;
  }

  async function login(clientId, role = 'viewer') {
    const url = `${GATEWAY_URL}/auth/token?client_id=${encodeURIComponent(clientId)}&role=${encodeURIComponent(role)}`;
    const resp = await fetch(url, { method: 'POST' });
    if (!resp.ok) throw new Error(`Login failed: ${resp.statusText}`);

    const data = await resp.json();
    setToken(data.access_token);
    return data;
  }

  function setToken(token) {
    _token = token;
    _tokenData = _decodePayload(token);

    if (_token && _tokenData) {
      localStorage.setItem(STORAGE_KEY, token);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }

    _notify();
  }

  function logout() {
    _token = null;
    _tokenData = null;
    localStorage.removeItem(STORAGE_KEY);
    _notify();
  }

  /* ─── สร้าง Authorization header ─── */
  function authHeader() {
    return _token ? { 'Authorization': `Bearer ${_token}` } : {};
  }

  /* ─── ส่ง token ไปยัง Mini App ใน iframe ─── */
  function shareTokenWithApp(iframe, appSlug) {
    if (!iframe || !_token) return;
    iframe.contentWindow.postMessage({
      type: 'erp-auth',
      token: _token,
      tokenData: _tokenData,
      appSlug: appSlug,
    }, '*');
  }

  /* ─── ตรวจสอบ token เมื่อเริ่มต้น ─── */
  function init() {
    if (_token) {
      _tokenData = _decodePayload(_token);
      if (_isExpired(_tokenData)) {
        console.warn('[Auth] Token หมดอายุแล้ว');
        logout();
      } else {
        console.log('[Auth] มี token แล้ว — role:', _tokenData?.role);
      }
    }
    _notify();
  }

  function onChange(fn) {
    _listeners.push(fn);
    return () => { _listeners = _listeners.filter(f => f !== fn); };
  }

  return {
    init, login, logout, setToken,
    getToken, getTokenData, isAuthenticated,
    getRole, hasPermission, authHeader,
    shareTokenWithApp, onChange,
  };
})();
