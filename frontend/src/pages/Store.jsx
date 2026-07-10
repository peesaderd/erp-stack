import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const Store = () => {
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedApp, setSelectedApp] = useState(null);
  const [qrData, setQrData] = useState(null);
  const [polling, setPolling] = useState(false);
  const [purchasedApps, setPurchasedApps] = useState([]);
  const navigate = useNavigate();

  const token = localStorage.getItem('token');
  const user = JSON.parse(localStorage.getItem('user') || 'null');

  // Load available apps
  useEffect(() => {
    loadApps();
    if (token) loadPurchasedApps();
  }, [token]);

  const loadApps = async () => {
    try {
      const res = await fetch('/api/store/apps');
      if (res.ok) {
        const data = await res.json();
        setApps(data);
      }
    } catch (err) {
      console.error('Failed to load apps:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadPurchasedApps = async () => {
    try {
      const res = await fetch('/api/user/apps', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setPurchasedApps(data);
      }
    } catch (err) {
      console.error('Failed to load purchased apps:', err);
    }
  };

  const handleBuy = async (app) => {
    if (!token) {
      navigate('/login');
      return;
    }

    setSelectedApp(app);
    setQrData(null);

    try {
      const res = await fetch(`/api/store/checkout/${app.id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });

      if (res.ok) {
        const data = await res.json();
        setQrData(data);
        startPolling(data.transactionId);
      } else {
        alert('เกิดข้อผิดพลาดในการสร้าง QR Code');
      }
    } catch (err) {
      console.error('Checkout failed:', err);
      alert('เกิดข้อผิดพลาด');
    }
  };

  const startPolling = (transactionId) => {
    setPolling(true);
    let attempts = 0;
    const maxAttempts = 90; // 15 minutes

    const poll = setInterval(async () => {
      attempts++;
      if (attempts >= maxAttempts) {
        clearInterval(poll);
        setPolling(false);
        alert('QR Code หมดอายุแล้ว กรุณาสร้างใหม่');
        setQrData(null);
        return;
      }

      try {
        const res = await fetch(`/api/store/checkout/${transactionId}/status`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'completed') {
            clearInterval(poll);
            setPolling(false);
            alert('ชำระเงินสำเร็จ! คุณเป็นเจ้าของแอปนี้แล้ว');
            loadPurchasedApps();
            setQrData(null);
            setSelectedApp(null);
          }
        }
      } catch (err) {
        console.error('Polling failed:', err);
      }
    }, 10000); // Poll every 10 seconds
  };

  const isPurchased = (appId) => purchasedApps.includes(appId);

  if (loading) {
    return <div className="container mx-auto p-4">กำลังโหลด...</div>;
  }

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-6">🏪 M2I App Store</h1>

      {user && (
        <div className="mb-4 p-4 bg-blue-50 rounded">
          <p className="text-blue-800">
            สวัสดี, <strong>{user.name}</strong> ({user.email})
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {apps.map(app => (
          <div key={app.id} className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-bold mb-2">{app.name}</h2>
            <p className="text-gray-600 mb-4">{app.description}</p>
            <div className="flex justify-between items-center">
              <span className="text-2xl font-bold text-green-600">
                ฿{parseFloat(app.price).toFixed(2)}
              </span>
              {isPurchased(app.id) ? (
                <span className="bg-green-500 text-white px-4 py-2 rounded">
                  ✓ ซื้อแล้ว
                </span>
              ) : (
                <button
                  onClick={() => handleBuy(app)}
                  className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded"
                >
                  ซื้อเลย
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* QR Code Modal */}
      {selectedApp && qrData && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold">สแกนเพื่อชำระเงิน</h2>
              <button
                onClick={() => {
                  setQrData(null);
                  setSelectedApp(null);
                }}
                className="text-gray-500 hover:text-gray-700 text-2xl"
              >
                ×
              </button>
            </div>

            <div className="text-center">
              <div className="bg-gray-100 rounded p-4 mb-4">
                <img
                  src={qrData.qrImage}
                  alt="QR Code"
                  className="mx-auto max-w-xs"
                />
              </div>

              <div className="mb-4">
                <p className="text-lg font-semibold">{selectedApp.name}</p>
                <p className="text-3xl font-bold text-green-600">
                  ฿{qrData.amount.toFixed(2)}
                </p>
              </div>

              <div className="text-sm text-gray-600 mb-4">
                <p>Reference: {qrData.reference1}/{qrData.reference2}</p>
                <p>Transaction: {qrData.transactionId}</p>
              </div>

              {polling && (
                <div className="bg-yellow-50 p-3 rounded mb-4">
                  <p className="text-yellow-800">
                    ⏳ กำลังรอการยืนยันการชำระเงิน...
                  </p>
                </div>
              )}

              <div className="text-xs text-gray-500">
                QR Code จะหมดอายุใน 15 นาที
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Store;
