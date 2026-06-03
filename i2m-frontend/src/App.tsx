import { useState } from 'react'
import ProductStudio from './pages/ProductStudio'
import Scripts from './pages/Scripts'
import VideoGallery from './pages/VideoGallery'
import ImageGallery from './pages/ImageGallery'
import Profile from './pages/Profile'

const tabs = [
  { id: 'studio', label: 'Studio', icon: 'studio' },
  { id: 'scripts', label: 'Scripts', icon: 'scripts' },
  { id: 'gallery-video', label: 'Video', icon: 'video' },
  { id: 'gallery-image', label: 'Images', icon: 'image' },
  { id: 'profile', label: 'Profile', icon: 'profile' },
]

function App() {
  const [activeTab, setActiveTab] = useState('studio')

  const renderPage = () => {
    switch (activeTab) {
      case 'studio': return <ProductStudio />
      case 'scripts': return <Scripts />
      case 'gallery-video': return <VideoGallery />
      case 'gallery-image': return <ImageGallery />
      case 'profile': return <Profile />
      default: return <ProductStudio />
    }
  }

  return (
    <div className="min-h-screen bg-[var(--color-system-background)] flex flex-col font-sans">
      {/* Status Bar spacer */}
      <div className="h-12" />

      {/* Navigation Bar */}
      <nav className="nav-ios fixed top-0 left-0 right-0 z-50 pt-3 pb-2 px-4 safe-area-top">
        <div className="flex items-center justify-between max-w-4xl mx-auto">
          <div className="title-ios">I2M Studio</div>
          <div className="flex items-center gap-3">
            <span className="footnote-ios text-gray-400">TikTok UGC</span>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 w-full pb-[130px]">
        {renderPage()}
      </main>

      {/* Tab Bar — slim, fixed bottom */}
      <div className="tab-ios fixed bottom-0 left-0 right-0 z-40 safe-area-bottom" style={{paddingBottom: 'calc(env(safe-area-inset-bottom, 8px) + 2px)', paddingTop: 4}}>
        <div className="flex justify-around items-center max-w-lg mx-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex flex-col items-center gap-0 transition-all duration-200 ${
                activeTab === tab.id
                  ? 'text-[var(--color-system-blue)]'
                  : 'text-[var(--color-system-gray)]'
              }`}
            >
              <TabIcon name={tab.icon} active={activeTab === tab.id} />
              <span className="text-[9px] font-medium tracking-tight leading-none mt-0">{tab.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function TabIcon({ name, active }: { name: string; active: boolean }) {
  const icons: Record<string, string> = {
    'studio': active ? '🎯' : '🎯',
    'scripts': active ? '📄' : '📝',
    'video': active ? '🎬' : '🎥',
    'image': active ? '🖼️' : '🖼️',
    'profile': active ? '👤' : '👤',
  }

  return (
    <span className="text-lg" style={{ opacity: active ? 1 : 0.45 }}>
      {icons[name] || '●'}
    </span>
  )
}

export default App
