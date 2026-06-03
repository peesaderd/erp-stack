export default function Dashboard() {
  const stats = [
    { label: 'Scripts Generated', value: '—', color: '#007AFF' },
    { label: 'Videos Created', value: '—', color: '#34C759' },
    { label: 'Images Generated', value: '—', color: '#FF9500' },
    { label: 'Credits Used', value: '—', color: '#FF3B30' },
  ]

  const recentItems = [
    { type: 'script', title: 'No recent activity', desc: 'Start by generating a script', time: '' },
  ]

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="py-4">
        <h1 className="title-ios-2">Today</h1>
        <p className="subhead-ios mt-1">Your content creation hub</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-3">
        {stats.map((stat) => (
          <div key={stat.label} className="card-ios p-4">
            <div className="text-3xl font-bold" style={{ color: stat.color }}>
              {stat.value}
            </div>
            <div className="footnote-ios mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="title-ios-3 mb-3">Quick Start</h2>
        <div className="space-y-2">
          <QuickActionCard
            icon="🎬"
            title="Generate UGC Script"
            desc="Create a TikTok-style review script"
            color="#007AFF"
          />
          <QuickActionCard
            icon="🎥"
            title="Generate Video"
            desc="Turn script into AI video"
            color="#34C759"
          />
          <QuickActionCard
            icon="🖼"
            title="Generate Image"
            desc="Create product images with AI"
            color="#FF9500"
          />
        </div>
      </div>

      {/* Recent Activity */}
      <div>
        <h2 className="title-ios-3 mb-3">Recent</h2>
        <div className="card-ios p-4">
          {recentItems.map((item, i) => (
            <div key={i} className="subhead-ios">{item.title}</div>
          ))}
        </div>
      </div>
    </div>
  )
}

function QuickActionCard({ icon, title, desc, color }: { icon: string; title: string; desc: string; color: string }) {
  return (
    <button className="card-ios p-4 w-full text-left flex items-center gap-4 btn-ios">
      <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xl" style={{ backgroundColor: `${color}15` }}>
        {icon}
      </div>
      <div className="flex-1">
        <div className="body-ios font-medium">{title}</div>
        <div className="footnote-ios">{desc}</div>
      </div>
      <div className="text-[var(--color-system-gray)]">›</div>
    </button>
  )
}
