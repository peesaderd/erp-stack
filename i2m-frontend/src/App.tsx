import { Routes, Route } from 'react-router-dom'
import ProductStudio from './pages/ProductStudio'
import ImageGallery from './pages/ImageGallery'
import Profile from './pages/Profile'

function App() {
  return (
    <div className="bg-background text-on-surface min-h-screen font-sans antialiased selection:bg-secondary/20 selection:text-secondary">
      <Routes>
        <Route path="/" element={<ProductStudio />} />
        <Route path="/gallery" element={<ImageGallery />} />
        <Route path="/profile" element={<Profile />} />
        {/* Catch-all redirect to / */}
        <Route path="*" element={<ProductStudio />} />
      </Routes>
    </div>
  )
}

export default App
