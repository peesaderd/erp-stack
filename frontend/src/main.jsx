import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// Register service worker for PWA
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then((registration) => {
        console.log('[PWA] Registered, scope:', registration.scope)
      })
      .catch((error) => {
        console.log('[PWA] Registration failed:', error)
      })
  })
}

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import PosRestodash from './pages/PosRestodash.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/pos/restodash" element={<PosRestodash />} />
        <Route path="/*" element={<App />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
