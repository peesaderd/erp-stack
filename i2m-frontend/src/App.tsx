import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import Scripts from './pages/Scripts'
import Video from './pages/Video'
import ImageGen from './pages/ImageGen'

const tabs = [
  { id: 'dashboard', label: 'Dashboard', icon: 'square.grid.2x2' },
  { id: 'scripts', label: 'Scripts', icon: 'doc.text' },
  { id: 'video', label: 'Video', icon: 'video' },
  { id: 'images', label: 'Images', icon: 'photo' },
]

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')

  const renderPage = () => {
    switch (activeTab) {
      case 'dashboard': return <Dashboard />
      case 'scripts': return <Scripts />
      case 'video': return <Video />
      case 'images': return <ImageGen />
      default: return <Dashboard />
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
            <span className="w-2 h-2 rounded-full bg-[var(--color-system-green)]" />
            <span className="footnote-ios">Connected</span>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 max-w-4xl mx-auto w-full px-4 pb-24 pt-2">
        {renderPage()}
      </main>

      {/* Tab Bar */}
      <div className="tab-ios fixed bottom-0 left-0 right-0 z-50 pb-8 pt-2 safe-area-bottom">
        <div className="flex justify-around items-center max-w-md mx-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex flex-col items-center gap-1 px-4 py-1 transition-all duration-200 ${
                activeTab === tab.id
                  ? 'text-[var(--color-system-blue)]'
                  : 'text-[var(--color-system-gray)]'
              }`}
            >
              <TabIcon name={tab.icon} active={activeTab === tab.id} />
              <span className="text-[10px] font-medium tracking-tight">{tab.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function TabIcon({ name, active }: { name: string; active: boolean }) {
  const icons: Record<string, string> = {
    'square.grid.2x2': active ? '◆' : '◇',
    'doc.text': active ? '📄' : '📝',
    'video': active ? '🎬' : '🎥',
    'photo': active ? '🖼' : '🖼',
  }

  return (
    <span className="text-xl" style={{ opacity: active ? 1 : 0.6 }}>
      {icons[name] || '●'}
    </span>
  )
}

export default App
