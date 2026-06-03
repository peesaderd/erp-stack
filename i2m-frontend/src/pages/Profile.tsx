import { useState, useRef } from 'react'

interface ProfileData {
  storeName: string
  storeAvatar: string | null
  tiktokUrl: string
  shopUrl: string
  targetAudience: string
  voiceStyle: string
  affiliateShopee: string
  affiliateLazada: string
  affiliateTiktok: string
}

const defaultProfile: ProfileData = {
  storeName: '',
  storeAvatar: null,
  tiktokUrl: '',
  shopUrl: '',
  targetAudience: '',
  voiceStyle: 'casual',
  affiliateShopee: '',
  affiliateLazada: '',
  affiliateTiktok: '',
}

export default function Profile() {
  const [profile, setProfile] = useState<ProfileData>(() => {
    try {
      const saved = localStorage.getItem('i2m_profile')
      return saved ? { ...defaultProfile, ...JSON.parse(saved) } : defaultProfile
    } catch { return defaultProfile }
  })
  const [saved, setSaved] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleSave = () => {
    localStorage.setItem('i2m_profile', JSON.stringify(profile))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleAvatarUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => setProfile((p) => ({ ...p, storeAvatar: ev.target?.result as string }))
    reader.readAsDataURL(file)
  }

  return (
    <div className="min-h-[calc(100vh-56px)] bg-white">
      <div className="max-w-2xl mx-auto px-4 py-6">

        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-gray-900">Profile</h1>
          <p className="text-sm text-gray-500 mt-1">ข้อมูลร้านค้าและการตั้งค่า</p>
        </div>

        <div className="space-y-6">

          {/* Avatar + Store Name */}
          <div className="bg-white border border-gray-200 rounded-2xl p-6">
            <div className="flex items-center gap-5">
              <div
                onClick={() => fileInputRef.current?.click()}
                className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center overflow-hidden cursor-pointer hover:opacity-80 border-2 border-gray-200"
              >
                {profile.storeAvatar ? (
                  <img src={profile.storeAvatar} alt="Avatar" className="w-full h-full object-cover" />
                ) : (
                  <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                )}
              </div>
              <input ref={fileInputRef} type="file" accept="image/*" onChange={handleAvatarUpload} className="hidden" />
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">ชื่อร้าน</label>
                <input
                  type="text"
                  value={profile.storeName}
                  onChange={(e) => setProfile((p) => ({ ...p, storeName: e.target.value }))}
                  className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  placeholder="ชื่อร้านค้าของคุณ"
                />
              </div>
            </div>
          </div>

          {/* Store Links */}
          <div className="bg-white border border-gray-200 rounded-2xl p-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">ลิงก์ร้านค้า</h3>
            <div className="space-y-3">
              <ProfileInput label="TikTok URL" value={profile.tiktokUrl} onChange={(v) => setProfile((p) => ({ ...p, tiktokUrl: v }))} placeholder="https://tiktok.com/@..." />
              <ProfileInput label="ร้านค้า/Website" value={profile.shopUrl} onChange={(v) => setProfile((p) => ({ ...p, shopUrl: v }))} placeholder="https://..." />
            </div>
          </div>

          {/* Target & Style */}
          <div className="bg-white border border-gray-200 rounded-2xl p-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">กลุ่มเป้าหมาย & สไตล์</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">กลุ่มเป้าหมาย</label>
                <input
                  type="text"
                  value={profile.targetAudience}
                  onChange={(e) => setProfile((p) => ({ ...p, targetAudience: e.target.value }))}
                  className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  placeholder="เช่น วัยทำงาน 25-40, นักศึกษา"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">สไตล์เสียง</label>
                <select
                  value={profile.voiceStyle}
                  onChange={(e) => setProfile((p) => ({ ...p, voiceStyle: e.target.value }))}
                  className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                >
                  <option value="casual"> Casual — เป็นกันเอง</option>
                  <option value="professional"> Professional — ทางการ</option>
                  <option value="excited"> Excited — กระตือรือร้น</option>
                  <option value="storytelling"> Storytelling — เล่าเรื่อง</option>
                </select>
              </div>
            </div>
          </div>

          {/* Affiliate Links */}
          <div className="bg-white border border-gray-200 rounded-2xl p-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Affiliate / ลิงก์สินค้า</h3>
            <div className="space-y-3">
              <ProfileInput label="Shopee" value={profile.affiliateShopee} onChange={(v) => setProfile((p) => ({ ...p, affiliateShopee: v }))} placeholder="https://shopee.co.th/..." />
              <ProfileInput label="Lazada" value={profile.affiliateLazada} onChange={(v) => setProfile((p) => ({ ...p, affiliateLazada: v }))} placeholder="https://lazada.co.th/..." />
              <ProfileInput label="TikTok Shop" value={profile.affiliateTiktok} onChange={(v) => setProfile((p) => ({ ...p, affiliateTiktok: v }))} placeholder="https://..." />
            </div>
          </div>

          {/* Save Button */}
          <button
            onClick={handleSave}
            className="w-full py-3 bg-blue-600 text-white rounded-xl font-medium text-sm hover:bg-blue-700 transition-colors"
          >
            {saved ? '✓ บันทึกแล้ว' : 'บันทึก'}
          </button>

        </div>
      </div>
    </div>
  )
}

// Helper component
function ProfileInput({ label, value, onChange, placeholder }: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder: string
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border border-gray-300 rounded-xl px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
        placeholder={placeholder}
      />
    </div>
  )
}
