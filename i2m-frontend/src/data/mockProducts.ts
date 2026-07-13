export interface MockProduct {
  id: string
  name: string
  description: string
  imageUrl: string
  category: string
  price: string
  features: string[]
  targetAudience: string
}

export const mockProducts: MockProduct[] = [
  {
    id: 'earbuds-pro',
    name: 'SoundPulse Pro Wireless Earbuds',
    description: 'Earbuds ไร้สายตัดเสียงรบกวน ANC ระบบ Hybrid ลดเสียงรบกวนได้ 42dB พร้อมไมค์ 6 ตัว คุยสายชัดเจน ใช้งานได้นาน 36 ชม. (กับเคส) กันน้ำ IPX5',
    imageUrl: '/mock-products/earbuds.png',
    category: 'Electronics',
    price: '฿1,890',
    features: ['ANC 42dB', 'Battery 36hrs', 'IPX5', 'Bluetooth 5.3'],
    targetAudience: 'วัยทำงาน, คนที่ชอบฟังเพลง, สาย WFH',
  },
  {
    id: 'serum-vitamin-c',
    name: 'GlowUp Vitamin C Serum',
    description: 'เซรั่มวิตามินซีเข้มข้น 20% พร้อม Hyaluronic Acid ช่วยลดเลือนจุดด่างดำ ผิวกระจ่างใส เหมาะสำหรับทุกสภาพผิว ขนาด 30ml',
    imageUrl: '/mock-products/serum.png',
    category: 'Beauty',
    price: '฿890',
    features: ['Vitamin C 20%', 'Hyaluronic Acid', 'Brightening', 'Anti-aging'],
    targetAudience: 'ผู้หญิง 25-40 ปี ที่ใส่ใจดูแลผิว',
  },
  {
    id: 'speaker-xbass',
    name: 'BoomBox X-Bass Portable Speaker',
    description: 'ลำโพงบลูทูธพกพา เสียงเบสแน่น 360° surround sound ใช้งานได้ 24 ชม. กันน้ำ IPX7 เชื่อมต่อ 2 ตัวพร้อมกัน Stereo Mode',
    imageUrl: '/mock-products/speaker.png',
    category: 'Electronics',
    price: '฿2,490',
    features: ['24hrs Battery', 'IPX7', '360° Sound', 'Stereo Pair'],
    targetAudience: 'สายปาร์ตี้, สายแคมป์ปิ้ง, คนรักเสียงเพลง',
  },
  {
    id: 'smartwatch-fit',
    name: 'FitPulse Smart Watch S3',
    description: 'นาฬิกาอัจฉริยะ AMOLED 1.75" ติดตามสุขภาพ วัด HR SpO2 นอน ออกกำลังกาย 20+ โหมด ทนน้ำ 5ATM แบต 14 วัน',
    imageUrl: '/mock-products/smartwatch.png',
    category: 'Electronics',
    price: '฿3,290',
    features: ['AMOLED 1.75"', 'HR + SpO2', '14 days battery', '5ATM'],
    targetAudience: 'สายสุขภาพ, สายออกกำลังกาย, วัยทำงาน',
  },
  {
    id: 'tote-canvas',
    name: 'Urban Canvas Tote Bag',
    description: 'กระเป๋าผ้าแคนวาสพรีเมียม หูหนังแท้ จุของได้เยอะ ดีไซน์มินิมอล เหมาะทั้งไปทำงาน ช้อปปิ้ง หรือเดินทาง ขนาด 38x42 ซม.',
    imageUrl: '/mock-products/tote-bag.png',
    category: 'Fashion',
    price: '฿690',
    features: ['Canvas Premium', 'Leather handles', 'Minimal design', 'Large capacity'],
    targetAudience: 'สายมินิมอล, นักศึกษา, วัยทำงาน',
  },
]
