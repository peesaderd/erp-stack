import { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import ProductStudio from './pages/ProductStudio'
import ImageGallery from './pages/ImageGallery'
import Profile from './pages/Profile'
import Payment from './pages/Payment'
import ProductScrape from './pages/ProductScrape'

function App() {
  // Initialize dark mode from localStorage on every mount (persists across navigation)
  useEffect(() => {
    const saved = localStorage.getItem('i2m_dark_mode') === 'true'
    document.documentElement.classList.toggle('dark', saved)
  }, [])
  return (
    <div className="bg-background text-on-surface min-h-screen font-sans antialiased selection:bg-secondary/20 selection:text-secondary">
      <Routes>
        <Route path="/" element={<ProductStudio />} />
        <Route path="/gallery" element={<ImageGallery />} />
        <Route path="/profile" element={<Profile />} />
        {/* Catch-all redirect to / */}
        <Route path="/payment" element={<Payment />} />
        <Route path="/scrape" element={<ProductScrape />} />
        <Route path="*" element={<ProductStudio />} />
      </Routes>
    </div>
  )
}

export default App
