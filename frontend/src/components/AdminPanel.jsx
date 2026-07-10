import { useState, useEffect } from 'react';

// Admin Panel Component - Full management interface for users, roles, and permissions
export default function AdminPanel({ userToken, currentUser, theme }) {
  const [adminTab, setAdminTab] = useState('users'); // 'users', 'roles', 'permissions', 'transactions', 'apps'
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Modal states
  const [showCreateUserModal, setShowCreateUserModal] = useState(false);
  const [showEditUserModal, setShowEditUserModal] = useState(false);
  const [showEditRoleModal, setShowEditRoleModal] = useState(false);
  const [showQRModal, setShowQRModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [selectedRole, setSelectedRole] = useState(null);
  const [selectedApp, setSelectedApp] = useState(null);

  // Create user form
  const [newUser, setNewUser] = useState({
    name: '',
    email: '',
    password: '',
    roles: ['user']
  });

  // Edit user form
  const [editUserData, setEditUserData] = useState({
    name: '',
    email: '',
    is_active: true,
    credits: 0,
    roles: []
  });

  // Edit role form
  const [editRoleData, setEditRoleData] = useState({
    name: '',
    permissions: []
  });

  // QR generation
  const [qrData, setQrData] = useState(null);
  const [qrAmount, setQrAmount] = useState(0);

  const API_BASE = '';

  // Fetch all admin data
  useEffect(() => {
    if (userToken) {
      fetchUsers();
      fetchRoles();
      fetchPermissions();
      fetchTransactions();
      fetchApps();
    }
  }, [userToken]);

  const fetchUsers = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/users`, {
        headers: { Authorization: `Bearer ${userToken}` }
      });
      if (!res.ok) throw new Error('Failed to fetch users');
      const data = await res.json();
      setUsers(data.users || []);
    } catch (err) {
      console.error('Fetch users error:', err);
      setError('ไม่สามารถโหลดข้อมูลผู้ใช้ได้');
    }
  };

  const fetchRoles = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/roles`, {
        headers: { Authorization: `Bearer ${userToken}` }
      });
      if (!res.ok) throw new Error('Failed to fetch roles');
      const data = await res.json();
      setRoles(data.roles || []);
    } catch (err) {
      console.error('Fetch roles error:', err);
    }
  };

  const fetchPermissions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/permissions`, {
        headers: { Authorization: `Bearer ${userToken}` }
      });
      if (!res.ok) throw new Error('Failed to fetch permissions');
      const data = await res.json();
      setPermissions(data.permissions || []);
    } catch (err) {
      console.error('Fetch permissions error:', err);
    }
  };

  const fetchTransactions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/transactions`, {
        headers: { Authorization: `Bearer ${userToken}` }
      });
      if (!res.ok) throw new Error('Failed to fetch transactions');
      const data = await res.json();
      setTransactions(data.transactions || []);
    } catch (err) {
      console.error('Fetch transactions error:', err);
    }
  };

  const fetchApps = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/admin/apps`, {
        headers: { Authorization: `Bearer ${userToken}` }
      });
      if (!res.ok) throw new Error('Failed to fetch apps');
      const data = await res.json();
      setApps(data.apps || data || []);
    } catch (err) {
      console.error('Fetch apps error:', err);
    }
  };

  const handleUpdatePrice = async (appId, newPrice) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/apps/${appId}/price`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${userToken}`
        },
        body: JSON.stringify({ price: newPrice })
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed to update price');
      }
      
      fetchApps();
      alert('อัปเดตราคาสำเร็จ!');
    } catch (err) {
      alert(`เกิดข้อผิดพลาด: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleStatus = async (appId, currentStatus) => {
    const newStatus = currentStatus === 'active' ? 'inactive' : 'active';
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/apps/${appId}/status`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${userToken}`
        },
        body: JSON.stringify({ status: newStatus })
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed to update status');
      }
      
      fetchApps();
      alert(`เปลี่ยนสถานะเป็น "${newStatus === 'active' ? 'ใช้งาน' : 'ระงับ'}" สำเร็จ!`);
    } catch (err) {
      alert(`เกิดข้อผิดพลาด: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const openQRModal = (app) => {
    setSelectedApp(app);
    setQrAmount(app.price || 0);
    setQrData(null);
    setShowQRModal(true);
  };

  const handleGenerateQR = async () => {
    if (!selectedApp || qrAmount <= 0) {
      alert('กรุณาระบุจำนวนเงินที่ถูกต้อง');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/apps/${selectedApp.id}/qr`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${userToken}`
        },
        body: JSON.stringify({
          amount: qrAmount,
          userId: currentUser?.id,
          reference1: `M2I-${selectedApp.id.slice(0, 8)}`,
          reference2: Date.now().toString()
        })
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed to generate QR');
      }
      
      const data = await res.json();
      setQrData(data);
    } catch (err) {
      alert(`เกิดข้อผิดพลาด: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/users`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${userToken}`
        },
        body: JSON.stringify(newUser)
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed to create user');
      }
      
      setShowCreateUserModal(false);
      setNewUser({ name: '', email: '', password: '', roles: ['user'] });
      fetchUsers();
      alert('สร้างผู้ใช้สำเร็จ!');
    } catch (err) {
      alert(`เกิดข้อผิดพลาด: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleEditUser = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/users/${selectedUser.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${userToken}`
        },
        body: JSON.stringify(editUserData)
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed to update user');
      }
      
      setShowEditUserModal(false);
      setSelectedUser(null);
      fetchUsers();
      alert('อัปเดตผู้ใช้สำเร็จ!');
    } catch (err) {
      alert(`เกิดข้อผิดพลาด: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteUser = async (userId, userName) => {
    if (!confirm(`ต้องการลบผู้ใช้ "${userName}" ใช่หรือไม่? การกระทำนี้ไม่สามารถย้อนกลับได้`)) {
      return;
    }
    
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/users/${userId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${userToken}` }
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed to delete user');
      }
      
      fetchUsers();
      alert('ลบผู้ใช้สำเร็จ!');
    } catch (err) {
      alert(`เกิดข้อผิดพลาด: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleEditRole = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/roles/${selectedRole.id}/permissions`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${userToken}`
        },
        body: JSON.stringify({ permissions: editRoleData.permissions })
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed to update role');
      }
      
      setShowEditRoleModal(false);
      setSelectedRole(null);
      fetchRoles();
      alert('อัปเดตบทบาทสำเร็จ!');
    } catch (err) {
      alert(`เกิดข้อผิดพลาด: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const openEditUserModal = (user) => {
    setSelectedUser(user);
    setEditUserData({
      name: user.name,
      email: user.email,
      is_active: user.is_active,
      credits: user.credits,
      roles: user.roles || []
    });
    setShowEditUserModal(true);
  };

  const openEditRoleModal = (role) => {
    setSelectedRole(role);
    setEditRoleData({
      name: role.name,
      permissions: role.permissions || []
    });
    setShowEditRoleModal(true);
  };

  const togglePermission = (permName) => {
    setEditRoleData(prev => ({
      ...prev,
      permissions: prev.permissions.includes(permName)
        ? prev.permissions.filter(p => p !== permName)
        : [...prev.permissions, permName]
    }));
  };

  return (
    <div className="admin-panel">
      {/* Admin Header */}
      <div className="admin-header">
        <div className="admin-header-content">
          <h1 className="admin-title">🛡️ Admin Panel</h1>
          <p className="admin-subtitle">จัดการระบบ M2I App Store</p>
        </div>
        <div className="admin-user-info">
          <span className="admin-badge">Admin</span>
          <span className="admin-user-name">{currentUser?.name}</span>
        </div>
      </div>

      {/* Admin Tabs */}
      <div className="admin-tabs">
        <button
          className={`admin-tab ${adminTab === 'users' ? 'active' : ''}`}
          onClick={() => setAdminTab('users')}
        >
          👥 ผู้ใช้ ({users.length})
        </button>
        <button
          className={`admin-tab ${adminTab === 'roles' ? 'active' : ''}`}
          onClick={() => setAdminTab('roles')}
        >
          🔐 บทบาท ({roles.length})
        </button>
        <button
          className={`admin-tab ${adminTab === 'permissions' ? 'active' : ''}`}
          onClick={() => setAdminTab('permissions')}
        >
          ⚙️ สิทธิ์ ({permissions.length})
        </button>
        <button
          className={`admin-tab ${adminTab === 'transactions' ? 'active' : ''}`}
          onClick={() => setAdminTab('transactions')}
        >
          💳 ธุรกรรม ({transactions.length})
        </button>
        <button
          className={`admin-tab ${adminTab === 'apps' ? 'active' : ''}`}
          onClick={() => setAdminTab('apps')}
        >
          📦 แอป ({apps.length})
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div className="admin-error">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Users Tab */}
      {adminTab === 'users' && (
        <div className="admin-content">
          <div className="admin-actions">
            <button
              className="admin-btn primary"
              onClick={() => setShowCreateUserModal(true)}
            >
              ➕ สร้างผู้ใช้ใหม่
            </button>
          </div>

          <div className="admin-table-container">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>ชื่อ</th>
                  <th>อีเมล</th>
                  <th>บทบาท</th>
                  <th>Credits</th>
                  <th>สถานะ</th>
                  <th>สร้างเมื่อ</th>
                  <th>จัดการ</th>
                </tr>
              </thead>
              <tbody>
                {users.map(user => (
                  <tr key={user.id}>
                    <td>{user.name}</td>
                    <td>{user.email}</td>
                    <td>
                      <div className="role-badges">
                        {user.roles?.map(role => (
                          <span key={role} className={`role-badge ${role}`}>
                            {role}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>{parseFloat(user.credits).toFixed(2)}</td>
                    <td>
                      <span className={`status-badge ${user.is_active ? 'active' : 'inactive'}`}>
                        {user.is_active ? 'ใช้งาน' : 'ระงับ'}
                      </span>
                    </td>
                    <td>{new Date(user.created_at).toLocaleDateString('th-TH')}</td>
                    <td>
                      <div className="action-buttons">
                        <button
                          className="action-btn edit"
                          onClick={() => openEditUserModal(user)}
                          title="แก้ไข"
                        >
                          ✏️
                        </button>
                        <button
                          className="action-btn delete"
                          onClick={() => handleDeleteUser(user.id, user.name)}
                          title="ลบ"
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Roles Tab */}
      {adminTab === 'roles' && (
        <div className="admin-content">
          <div className="roles-grid">
            {roles.map(role => (
              <div key={role.id} className="role-card">
                <div className="role-card-header">
                  <h3>{role.name}</h3>
                  <button
                    className="admin-btn small"
                    onClick={() => openEditRoleModal(role)}
                  >
                    แก้ไข
                  </button>
                </div>
                <p className="role-description">{role.description}</p>
                <div className="role-permissions">
                  <strong>สิทธิ์ ({role.permissions?.length || 0}):</strong>
                  <div className="permission-tags">
                    {role.permissions?.map(perm => (
                      <span key={perm} className="permission-tag">
                        {perm}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Permissions Tab */}
      {adminTab === 'permissions' && (
        <div className="admin-content">
          <div className="permissions-overview">
            {['user_management', 'app_management', 'payment_management', 'reports', 'system'].map(category => {
              const categoryPerms = permissions.filter(p => p.category === category);
              const categoryNames = {
                user_management: '👥 การจัดการผู้ใช้',
                app_management: '📦 การจัดการแอป',
                payment_management: '💳 การจัดการการชำระเงิน',
                reports: '📊 รายงาน',
                system: '⚙️ ระบบ'
              };
              
              return (
                <div key={category} className="permission-category">
                  <h3>{categoryNames[category]}</h3>
                  <div className="permission-list">
                    {categoryPerms.map(perm => (
                      <div key={perm.id} className="permission-item">
                        <div className="permission-info">
                          <strong>{perm.name}</strong>
                          <p>{perm.description}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Transactions Tab */}
      {adminTab === 'transactions' && (
        <div className="admin-content">
          <div className="admin-table-container">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>TX ID</th>
                  <th>ผู้ใช้</th>
                  <th>จำนวนเงิน</th>
                  <th>วิธีชำระ</th>
                  <th>สถานะ</th>
                  <th>แอป</th>
                  <th>วันที่</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map(tx => (
                  <tr key={tx.id}>
                    <td className="tx-id">{tx.id.slice(0, 8)}...</td>
                    <td>
                      <div className="tx-user">
                        <strong>{tx.user_name}</strong>
                        <span>{tx.user_email}</span>
                      </div>
                    </td>
                    <td className="tx-amount">
                      ฿{parseFloat(tx.amount).toFixed(2)} {tx.currency}
                    </td>
                    <td>
                      <span className="payment-method-badge">
                        {tx.payment_method}
                      </span>
                    </td>
                    <td>
                      <span className={`status-badge ${tx.status}`}>
                        {tx.status}
                      </span>
                    </td>
                    <td>{tx.description}</td>
                    <td>{new Date(tx.created_at).toLocaleString('th-TH')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Apps Tab */}
      {adminTab === 'apps' && (
        <div className="admin-content">
          <div className="admin-table-container">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>แอป</th>
                  <th>คำอธิบาย</th>
                  <th>ราคา (฿)</th>
                  <th>ติดตั้ง</th>
                  <th>รายได้รวม</th>
                  <th>สถานะ</th>
                  <th>จัดการ</th>
                </tr>
              </thead>
              <tbody>
                {apps.map(app => (
                  <tr key={app.id}>
                    <td>
                      <div className="app-info">
                        {app.icon_url && <img src={app.icon_url} alt={app.name} className="app-icon-small" />}
                        <strong>{app.name}</strong>
                      </div>
                    </td>
                    <td className="app-description">{app.description?.slice(0, 50)}...</td>
                    <td className="app-price">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={app.price}
                        onChange={(e) => {
                          const newPrice = parseFloat(e.target.value);
                          setApps(apps.map(a => a.id === app.id ? {...a, price: newPrice} : a));
                        }}
                        onBlur={() => handleUpdatePrice(app.id, app.price)}
                        className="price-input"
                      />
                    </td>
                    <td>{app.install_count || 0}</td>
                    <td className="revenue">฿{parseFloat(app.total_revenue || 0).toFixed(2)}</td>
                    <td>
                      <span className={`status-badge ${app.status === 'active' ? 'active' : 'inactive'}`}>
                        {app.status === 'active' ? 'ใช้งาน' : 'ระงับ'}
                      </span>
                    </td>
                    <td>
                      <div className="action-buttons">
                        {app.price > 0 && (
                          <button
                            className="action-btn qr"
                            onClick={() => openQRModal(app)}
                            title="สร้าง QR PromptPay"
                          >
                            🏦
                          </button>
                        )}
                        <button
                          className={`action-btn ${app.status === 'active' ? 'pause' : 'play'}`}
                          onClick={() => handleToggleStatus(app.id, app.status)}
                          title={app.status === 'active' ? 'ระงับ' : 'เปิดใช้งาน'}
                        >
                          {app.status === 'active' ? '⏸️' : '▶️'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Create User Modal */}
      {showCreateUserModal && (
        <div className="modal-overlay" onClick={() => setShowCreateUserModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>สร้างผู้ใช้ใหม่</h2>
              <button className="modal-close" onClick={() => setShowCreateUserModal(false)}>
                ✕
              </button>
            </div>
            <form onSubmit={handleCreateUser}>
              <div className="form-group">
                <label>ชื่อ</label>
                <input
                  type="text"
                  value={newUser.name}
                  onChange={e => setNewUser({ ...newUser, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>อีเมล</label>
                <input
                  type="email"
                  value={newUser.email}
                  onChange={e => setNewUser({ ...newUser, email: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>รหัสผ่าน</label>
                <input
                  type="password"
                  value={newUser.password}
                  onChange={e => setNewUser({ ...newUser, password: e.target.value })}
                  required
                  minLength={6}
                />
              </div>
              <div className="form-group">
                <label>บทบาท</label>
                <select
                  multiple
                  value={newUser.roles}
                  onChange={e => {
                    const selected = Array.from(e.target.selectedOptions, opt => opt.value);
                    setNewUser({ ...newUser, roles: selected });
                  }}
                >
                  {roles.map(role => (
                    <option key={role.id} value={role.name}>
                      {role.name}
                    </option>
                  ))}
                </select>
                <small>กด Ctrl/Cmd ค้างไว้เพื่อเลือกหลายบทบาท</small>
              </div>
              <div className="modal-actions">
                <button type="button" className="admin-btn secondary" onClick={() => setShowCreateUserModal(false)}>
                  ยกเลิก
                </button>
                <button type="submit" className="admin-btn primary" disabled={loading}>
                  {loading ? 'กำลังสร้าง...' : 'สร้างผู้ใช้'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {showEditUserModal && selectedUser && (
        <div className="modal-overlay" onClick={() => setShowEditUserModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>แก้ไขผู้ใช้: {selectedUser.name}</h2>
              <button className="modal-close" onClick={() => setShowEditUserModal(false)}>
                ✕
              </button>
            </div>
            <form onSubmit={handleEditUser}>
              <div className="form-group">
                <label>ชื่อ</label>
                <input
                  type="text"
                  value={editUserData.name}
                  onChange={e => setEditUserData({ ...editUserData, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>อีเมล</label>
                <input
                  type="email"
                  value={editUserData.email}
                  onChange={e => setEditUserData({ ...editUserData, email: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>Credits</label>
                <input
                  type="number"
                  step="0.01"
                  value={editUserData.credits}
                  onChange={e => setEditUserData({ ...editUserData, credits: parseFloat(e.target.value) })}
                />
              </div>
              <div className="form-group">
                <label>สถานะ</label>
                <select
                  value={editUserData.is_active}
                  onChange={e => setEditUserData({ ...editUserData, is_active: e.target.value === 'true' })}
                >
                  <option value="true">ใช้งาน</option>
                  <option value="false">ระงับ</option>
                </select>
              </div>
              <div className="form-group">
                <label>บทบาท</label>
                <select
                  multiple
                  value={editUserData.roles}
                  onChange={e => {
                    const selected = Array.from(e.target.selectedOptions, opt => opt.value);
                    setEditUserData({ ...editUserData, roles: selected });
                  }}
                >
                  {roles.map(role => (
                    <option key={role.id} value={role.name}>
                      {role.name}
                    </option>
                  ))}
                </select>
                <small>กด Ctrl/Cmd ค้างไว้เพื่อเลือกหลายบทบาท</small>
              </div>
              <div className="modal-actions">
                <button type="button" className="admin-btn secondary" onClick={() => setShowEditUserModal(false)}>
                  ยกเลิก
                </button>
                <button type="submit" className="admin-btn primary" disabled={loading}>
                  {loading ? 'กำลังอัปเดต...' : 'อัปเดต'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Role Modal */}
      {showEditRoleModal && selectedRole && (
        <div className="modal-overlay" onClick={() => setShowEditRoleModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>แก้ไขบทบาท: {selectedRole.name}</h2>
              <button className="modal-close" onClick={() => setShowEditRoleModal(false)}>
                ✕
              </button>
            </div>
            <form onSubmit={handleEditRole}>
              <div className="form-group">
                <label>สิทธิ์ทั้งหมด ({editRoleData.permissions.length} / {permissions.length})</label>
                <div className="permissions-checkbox-grid">
                  {permissions.map(perm => (
                    <label key={perm.id} className="permission-checkbox">
                      <input
                        type="checkbox"
                        checked={editRoleData.permissions.includes(perm.name)}
                        onChange={() => togglePermission(perm.name)}
                      />
                      <span>
                        <strong>{perm.name}</strong>
                        <small>{perm.description}</small>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="modal-actions">
                <button type="button" className="admin-btn secondary" onClick={() => setShowEditRoleModal(false)}>
                  ยกเลิก
                </button>
                <button type="submit" className="admin-btn primary" disabled={loading}>
                  {loading ? 'กำลังอัปเดต...' : 'อัปเดตบทบาท'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* QR Code Modal */}
      {showQRModal && selectedApp && (
        <div className="modal-overlay" onClick={() => setShowQRModal(false)}>
          <div className="modal-content qr-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>🏦 QR PromptPay - {selectedApp.name}</h2>
              <button className="modal-close" onClick={() => setShowQRModal(false)}>
                ✕
              </button>
            </div>
            
            {!qrData ? (
              <>
                <div className="qr-form">
                  <div className="form-group">
                    <label>จำนวนเงิน (฿)</label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={qrAmount}
                      onChange={e => setQrAmount(parseFloat(e.target.value) || 0)}
                      className="qr-amount-input"
                    />
                  </div>
                  <div className="modal-actions">
                    <button 
                      type="button" 
                      className="admin-btn primary" 
                      onClick={handleGenerateQR}
                      disabled={loading || qrAmount <= 0}
                    >
                      {loading ? 'กำลังสร้าง...' : 'สร้าง QR Code'}
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="qr-result">
                  <div className="qr-image-container">
                    <img src={qrData.qrImage} alt="PromptPay QR Code" className="qr-image" />
                  </div>
                  <div className="qr-details">
                    <div className="qr-detail-item">
                      <strong>จำนวนเงิน:</strong>
                      <span className="qr-amount">฿{qrData.amount.toFixed(2)}</span>
                    </div>
                    <div className="qr-detail-item">
                      <strong>Transaction ID:</strong>
                      <span className="qr-tx-id">{qrData.transactionId}</span>
                    </div>
                    <div className="qr-detail-item">
                      <strong>Reference 1:</strong>
                      <span>{qrData.reference1}</span>
                    </div>
                    <div className="qr-detail-item">
                      <strong>Reference 2:</strong>
                      <span>{qrData.reference2}</span>
                    </div>
                    <div className="qr-detail-item">
                      <strong>PromptPay ID:</strong>
                      <span>{qrData.promptpayId}</span>
                    </div>
                  </div>
                  <div className="qr-actions">
                    <button 
                      className="admin-btn secondary" 
                      onClick={() => {
                        const link = document.createElement('a');
                        link.href = qrData.qrImage;
                        link.download = `qr-${selectedApp.name}-${Date.now()}.png`;
                        link.click();
                      }}
                    >
                      💾 ดาวน์โหลด QR
                    </button>
                    <button 
                      className="admin-btn primary" 
                      onClick={() => {
                        setQrData(null);
                        setQrAmount(selectedApp.price || 0);
                      }}
                    >
                      🔄 สร้าง QR ใหม่
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
