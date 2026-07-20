import { useState, useEffect } from 'react'
import { api } from '../lib/api'

interface VideoItem {
  task_id: string
  status: string
  prompt?: string
  provider?: string
  video_url?: string
  created_at?: string
  thumbnail?: string
}

export default function VideoGallery() {
  const [videos, setVideos] = useState<VideoItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Load from localStorage as a simple cache
    try {
      const saved = localStorage.getItem('i2m_video_history')
      if (saved) {
        setVideos(JSON.parse(saved))
      }
    } catch { /* ignore */ }
    setLoading(false)
  }, [])

  const clearHistory = () => {
    localStorage.removeItem('i2m_video_history')
    setVideos([])
  }

  const completed = videos.filter((v) => v.status === 'completed')
  const pending = videos.filter((v) => v.status !== 'completed')

  return (
    <div className="min-h-[calc(100vh-56px)] bg-white">
      <div className="max-w-4xl mx-auto px-4 py-6">

        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Video Gallery</h1>
            <p className="text-sm text-gray-500 mt-1">วีดีโอที่สร้างไว้แล้ว</p>
          </div>
          {videos.length > 0 && (
            <button onClick={clearHistory} className="text-sm text-red-500 hover:text-red-600">
              ล้างประวัติ
            </button>
          )}
        </div>

        {loading ? (
          <div className="text-center py-12 text-gray-400">กำลังโหลด...</div>
        ) : videos.length === 0 ? (
          <div className="text-center py-16">
            <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <p className="text-gray-400 text-sm mb-2">ยังไม่มีวีดีโอ</p>
            <p className="text-gray-400 text-xs">ไปที่ Product Studio เพื่อสร้างวีดีโอแรก</p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Completed */}
            {completed.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3">พร้อมใช้งาน ({completed.length})</h3>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {completed.map((v) => (
                    <div key={v.task_id} className="relative group rounded-xl overflow-hidden border border-gray-200 aspect-[9/16] bg-gray-100">
                      {v.video_url ? (
                        <video src={v.video_url} className="w-full h-full object-cover" />
                      ) : (
                        <div className="flex items-center justify-center h-full text-gray-400 text-xs p-2 text-center">
                          {v.prompt?.slice(0, 60)}...
                        </div>
                      )}
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100">
                        <button className="px-3 py-1.5 bg-white text-gray-800 text-xs rounded-lg font-medium">ดู</button>
                        {v.video_url && <button className="px-3 py-1.5 bg-white text-gray-800 text-xs rounded-lg font-medium">ดาวน์โหลด</button>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Pending */}
            {pending.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-500 mb-3">กำลังดำเนินการ ({pending.length})</h3>
                <div className="space-y-2">
                  {pending.map((v) => (
                    <div key={v.task_id} className="flex items-center gap-3 p-3 border border-gray-200 rounded-xl">
                      <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
                      <span className="text-sm text-gray-600 flex-1 truncate">{v.prompt?.slice(0, 80)}</span>
                      <span className="text-xs text-gray-400">{v.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
