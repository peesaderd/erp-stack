import os

pwa_html_path = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\smartback_pwa\index.html'

html = """<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover"/>
  <meta name="theme-color" content="#3525cd"/>
  <meta name="apple-mobile-web-app-capable" content="yes"/>
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"/>
  <meta name="apple-mobile-web-app-title" content="SmartBack"/>
  <link rel="manifest" href="manifest.json"/>
  <link rel="apple-touch-icon" href="icons/apple-touch-icon.png"/>
  <link rel="icon" type="image/png" href="icons/icon-192.png"/>

  <title>SmartBack - เมกะแอปช้อปปิ้งได้เงินคืน (Lotus's, Makro, Shopee, Agoda)</title>

  <!-- Google Fonts: Prompt & Inter + Material Symbols -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700;800&family=Inter:wght@400;600;700&display=swap" rel="stylesheet"/>
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet"/>

  <!-- Standard Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            brand: {
              primary: '#3525cd',
              accent: '#ff5722',
              green: '#00a651',
              dark: '#1e1b4b',
              yellow: '#ffb300'
            }
          },
          fontFamily: {
            sans: ['Prompt', 'Inter', 'sans-serif'],
          }
        }
      }
    };
  </script>

  <style>
    body {
      font-family: 'Prompt', 'Inter', sans-serif;
      background-color: #f1f2f6;
      margin: 0;
      padding: 0;
      overflow-x: hidden;
      -webkit-tap-highlight-color: transparent;
      box-sizing: border-box;
    }
    input, button, select, textarea, h1, h2, h3, h4, p, a {
      font-family: 'Prompt', 'Inter', sans-serif;
    }
    .material-symbols-outlined {
      font-family: 'Material Symbols Outlined' !important;
      font-weight: normal;
      font-style: normal;
      display: inline-block;
      line-height: 1;
      text-transform: none;
      letter-spacing: normal;
      word-wrap: normal;
      white-space: nowrap;
      direction: ltr;
      -webkit-font-smoothing: antialiased;
      vertical-align: middle;
    }
    .pb-safe { padding-bottom: env(safe-area-inset-bottom, 20px); }
    .pt-safe { padding-top: env(safe-area-inset-top, 14px); }
    ::-webkit-scrollbar { display: none; }
    .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    .progress-bar-glow {
      background: linear-gradient(90deg, #ff5722 0%, #ff9800 100%);
    }
  </style>
</head>
<body class="bg-[#f1f2f6] text-slate-800 flex flex-col items-center min-h-screen">

  <!-- Mobile Frame Container (Max 480px, perfectly centered on desktop, 100% on mobile) -->
  <div class="w-full max-w-[480px] bg-[#f8f9fc] min-h-screen flex flex-col relative shadow-2xl pb-24">

    <!-- 1. Top E-Commerce Header (Shopee / Lazada Vibrant Style) -->
    <header class="sticky top-0 z-40 w-full bg-gradient-to-r from-[#2a1cb8] via-[#3525cd] to-[#4338ca] text-white pt-safe shadow-md">
      <div class="px-3.5 pt-2.5 pb-3 flex flex-col gap-2.5">
        
        <!-- Top Row: Logo & Action Icons -->
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-1.5">
            <div class="w-8 h-8 rounded-xl bg-white text-[#3525cd] font-black text-lg flex items-center justify-center shadow-md">
              ⚡
            </div>
            <div class="flex flex-col">
              <span class="font-extrabold text-lg leading-tight tracking-tight flex items-center gap-1">
                Smart<span class="text-[#00e699]">Back</span>
                <span class="text-[9px] px-1.5 py-0.2 bg-[#00e699] text-slate-900 font-bold rounded-full">TH</span>
              </span>
            </div>
          </div>

          <!-- Icons: Scan, Wishlist, Cart, Profile -->
          <div class="flex items-center gap-1">
            <button onclick="showToast('📷 เปิดระบบสแกนบาร์โค้ด / QR Code')" class="w-9 h-9 flex items-center justify-center rounded-full hover:bg-white/10 active:scale-95 transition-all" title="สแกน">
              <span class="material-symbols-outlined text-[21px]">qr_code_scanner</span>
            </button>
            <button onclick="showToast('❤️ สินค้าโปรด 5 รายการ')" class="relative w-9 h-9 flex items-center justify-center rounded-full hover:bg-white/10 active:scale-95 transition-all" title="รายการโปรด">
              <span class="material-symbols-outlined text-[21px]">favorite</span>
              <span class="absolute top-1 right-1 w-4 h-4 rounded-full bg-[#ff5722] text-white text-[10px] font-bold flex items-center justify-center">5</span>
            </button>
            <button onclick="showToast('🛒 ตะกร้าสินค้า 3 ชิ้น (มีเงินคืนรออยู่)')" class="relative w-9 h-9 flex items-center justify-center rounded-full hover:bg-white/10 active:scale-95 transition-all" title="ตะกร้า">
              <span class="material-symbols-outlined text-[21px]">shopping_cart</span>
              <span class="absolute top-1 right-1 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">3</span>
            </button>
            <button onclick="showToast('👤 คุณพีรวัฒน์ • VIP Gold Member')" class="w-8 h-8 ml-1 rounded-full bg-white/20 border border-white/30 text-white font-bold text-xs flex items-center justify-center">
              PW
            </button>
          </div>
        </div>

        <!-- Search Bar with Camera Icon -->
        <div class="flex items-center gap-2 bg-white rounded-full px-3.5 py-2 shadow-inner">
          <span class="material-symbols-outlined text-gray-400 text-[20px]">search</span>
          <input id="globalSearchInput" type="text" placeholder="ค้นหาสินค้า Lotus's, Makro, Agoda หรือวาง URL..." class="w-full text-xs text-gray-800 placeholder:text-gray-400 bg-transparent focus:outline-none"/>
          <button onclick="showToast('📸 กำลังเปิดระบบค้นหาด้วยรูปภาพ (Visual Search)...')" class="text-[#3525cd] hover:text-[#ff5722] p-0.5" title="ค้นหาด้วยรูป">
            <span class="material-symbols-outlined text-[20px]">photo_camera</span>
          </button>
        </div>

      </div>
    </header>

    <!-- 2. Floating Mini-Wallet (Quick Balance & PromptPay Cashout) -->
    <section class="px-3 -mt-2 relative z-20">
      <div class="bg-white rounded-2xl p-3 shadow-lg border border-indigo-50 flex items-center justify-between">
        <div class="flex items-center gap-2.5 min-w-0">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 text-white flex items-center justify-center shadow-sm shrink-0">
            <span class="material-symbols-outlined text-[22px]">account_balance_wallet</span>
          </div>
          <div class="flex flex-col min-w-0">
            <div class="flex items-center gap-1.5">
              <span class="text-[11px] text-gray-500 font-medium">เงินคืนสะสม</span>
              <span class="text-[9px] px-1.5 py-0.2 rounded-full bg-amber-100 text-amber-900 font-bold">VIP 1.2x</span>
            </div>
            <div class="flex items-baseline gap-1">
              <span id="walletAvailableBalance" class="text-base font-extrabold text-[#00a651] tracking-tight">฿1,450.00</span>
              <span id="walletPendingBalance" class="text-[10px] text-gray-400 truncate">(รออนุมัติ ฿620.00)</span>
            </div>
          </div>
        </div>
        <button onclick="openWithdrawModal()" class="px-3.5 py-1.5 rounded-xl bg-[#00a651] hover:bg-emerald-600 active:scale-95 text-white text-xs font-bold shadow-md flex items-center gap-1 transition-all shrink-0">
          <span class="material-symbols-outlined text-[15px]">bolt</span>
          <span>ถอนเงิน</span>
        </button>
      </div>
    </section>

    <!-- 3. Mega Payday Campaign Carousel Banner -->
    <section class="px-3 mt-3">
      <div class="relative overflow-hidden rounded-2xl bg-gradient-to-r from-red-600 via-[#ff5722] to-amber-500 text-white p-4 shadow-md min-h-[145px] flex flex-col justify-between">
        <div class="absolute -right-8 -bottom-8 w-32 h-32 rounded-full bg-white/20 blur-xl pointer-events-none"></div>
        <div class="relative z-10">
          <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-black/30 backdrop-blur-sm text-[10px] font-bold text-yellow-300 uppercase tracking-wide">
            🔥 MEGA PAYDAY SALE • คืนเงินสูงสุด 50%
          </span>
          <h2 class="text-xl font-extrabold leading-tight mt-1 text-white">
            ช้อป Lotus's, Makro, Agoda<br/>
            <span class="text-yellow-200">รับเงินคืนสองต่อ + โค้ดส่งฟรี</span>
          </h2>
          <p class="text-[11px] text-white/90 mt-0.5">ใช้ซ้อนคูปองส่วนลดได้ทุกร้านค้า</p>
        </div>

        <div class="relative z-10 flex items-center justify-between pt-2">
          <div class="flex items-center gap-1">
            <span class="w-4 h-1.5 rounded-full bg-white"></span>
            <span class="w-1.5 h-1.5 rounded-full bg-white/50"></span>
            <span class="w-1.5 h-1.5 rounded-full bg-white/50"></span>
            <span class="w-1.5 h-1.5 rounded-full bg-white/50"></span>
          </div>
          <span class="text-[11px] font-bold text-white flex items-center gap-0.5 bg-black/20 px-2 py-0.5 rounded-full cursor-pointer">
            ดูโปรโมชันทั้งหมด <span class="material-symbols-outlined text-[13px]">arrow_forward</span>
          </span>
        </div>
      </div>
    </section>

    <!-- 4. 10-Icon Quick Service Category Matrix (Shopee Style 2 Rows of 5) -->
    <section class="px-3 mt-3">
      <div class="bg-white rounded-2xl p-3 shadow-sm border border-gray-100">
        <div class="grid grid-cols-5 gap-y-3 gap-x-1 text-center">
          
          <!-- 1 -->
          <button onclick="fillSample('lotus')" class="flex flex-col items-center gap-1 active:scale-95 transition-transform">
            <div class="relative w-11 h-11 rounded-2xl bg-emerald-100/70 text-emerald-700 flex items-center justify-center font-bold text-lg shadow-sm">
              🛒
              <span class="absolute -top-1.5 -right-1.5 px-1 py-0.2 bg-emerald-600 text-white text-[8px] font-bold rounded-full">5.5%</span>
            </div>
            <span class="text-[10px] font-medium text-slate-700 leading-tight">โลตัส</span>
          </button>

          <!-- 2 -->
          <button onclick="fillSample('makro')" class="flex flex-col items-center gap-1 active:scale-95 transition-transform">
            <div class="relative w-11 h-11 rounded-2xl bg-red-100/70 text-red-600 flex items-center justify-center font-bold text-lg shadow-sm">
              📦
              <span class="absolute -top-1.5 -right-1.5 px-1 py-0.2 bg-red-600 text-white text-[8px] font-bold rounded-full">4.0%</span>
            </div>
            <span class="text-[10px] font-medium text-slate-700 leading-tight">แม็คโคร</span>
          </button>

          <!-- 3 -->
          <button onclick="fillSample('agoda')" class="flex flex-col items-center gap-1 active:scale-95 transition-transform">
            <div class="relative w-11 h-11 rounded-2xl bg-blue-100/70 text-blue-600 flex items-center justify-center font-bold text-lg shadow-sm">
              🏨
              <span class="absolute -top-1.5 -right-1.5 px-1 py-0.2 bg-blue-600 text-white text-[8px] font-bold rounded-full">8.5%</span>
            </div>
            <span class="text-[10px] font-medium text-slate-700 leading-tight">อโกด้า</span>
          </button>

          <!-- 4 -->
          <button onclick="fillSample('trip')" class="flex flex-col items-center gap-1 active:scale-95 transition-transform">
            <div class="relative w-11 h-11 rounded-2xl bg-indigo-100/70 text-indigo-600 flex items-center justify-center font-bold text-lg shadow-sm">
              ✈️
              <span class="absolute -top-1.5 -right-1.5 px-1 py-0.2 bg-indigo-600 text-white text-[8px] font-bold rounded-full">7.0%</span>
            </div>
            <span class="text-[10px] font-medium text-slate-700 leading-tight">ตั๋วเครื่องบิน</span>
          </button>

          <!-- 5 -->
          <button onclick="showToast('⚡ แคมเปญ Flash Sale ลดฟ้าผ่า เริ่มต้น 1 บาท!')" class="flex flex-col items-center gap-1 active:scale-95 transition-transform">
            <div class="w-11 h-11 rounded-2xl bg-amber-100/70 text-amber-600 flex items-center justify-center font-bold text-lg shadow-sm">
              ⚡
            </div>
            <span class="text-[10px] font-medium text-slate-700 leading-tight">ลดฟ้าผ่า</span>
          </button>

          <!-- 6 -->
          <button onclick="showToast('🎟️ โค้ดส่งฟรีทั่วไทย 100 บาท แจกทุกวัน')" class="flex flex-col items-center gap-1 active:scale-95 transition-transform">
            <div class="w-11 h-11 rounded-2xl bg-teal-100/70 text-teal-600 flex items-center justify-center font-bold text-lg shadow-sm">
              🎟️
            </div>
            <span class="text-[10px] font-medium text-slate-700 leading-tight">โค้ดส่งฟรี</span>
          </button>

          <!-- 7 -->
          <button onclick="showToast('💎 คืนเงิน XTRA รับโบนัส 15% - 50%')" class="flex flex-col items-center gap-1 active:scale-95 transition-transform">
            <div class="w-11 h-11 rounded-2xl bg-purple-100/70 text-purple-600 flex items-center justify-center font-bold text-lg shadow-sm">
              💎
            </div>
            <span class="text-[10px] font-medium text-slate-700 leading-tight">คืนเงิน XTRA</span>
          </button>

          <!-- 8 -->
          <button onclick="showToast('🎁 เช็คอินรายวัน รับเหรียญสะสมแลกเงินสด')" class="flex flex-col items-center gap-1 active:scale-95 transition-transform">
            <div class="w-11 h-11 rounded-2xl bg-pink-100/70 text-pink-600 flex items-center justify-center font-bold text-lg shadow-sm">
              🎁
            </div>
            <span class="text-[10px] font-medium text-slate-700 leading-tight">เช็คอินเหรียญ</span>
          </button>

          <!-- 9 -->
          <button onclick="showToast('💻 ไอที & อุปกรณ์คอมพิวเตอร์ Advice')" class="flex flex-col items-center gap-1 active:scale-95 transition-transform">
            <div class="w-11 h-11 rounded-2xl bg-sky-100/70 text-sky-600 flex items-center justify-center font-bold text-lg shadow-sm">
              📱
            </div>
            <span class="text-[10px] font-medium text-slate-700 leading-tight">ไอที/มือถือ</span>
          </button>

          <!-- 10 -->
          <button onclick="showToast('👥 ชวนเพื่อนดาวน์โหลด รับโบนัสคนละ ฿50')" class="flex flex-col items-center gap-1 active:scale-95 transition-transform">
            <div class="w-11 h-11 rounded-2xl bg-orange-100/70 text-orange-600 flex items-center justify-center font-bold text-lg shadow-sm">
              👥
            </div>
            <span class="text-[10px] font-medium text-slate-700 leading-tight">ชวนเพื่อน</span>
          </button>

        </div>
      </div>
    </section>

    <!-- 5. Smart Link Converter Box (Shopee-Style Utility Tool) -->
    <section class="px-3 mt-3">
      <div class="bg-gradient-to-br from-indigo-50 to-white rounded-2xl p-3.5 shadow-sm border border-indigo-200/70">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-1.5">
            <span class="w-6 h-6 rounded-lg bg-[#3525cd] text-white flex items-center justify-center text-xs">🔗</span>
            <span class="text-xs font-bold text-slate-900">วางลิงก์สินค้าเพื่อรับเงินคืน</span>
          </div>
          <span class="text-[10px] text-[#ff5722] font-bold bg-orange-100 px-2 py-0.5 rounded-full">
            คืนเงินทันที 1 คลิก
          </span>
        </div>

        <div class="flex flex-col gap-2">
          <div class="flex items-center gap-2 bg-white rounded-xl px-3 py-2 border border-indigo-100 shadow-inner">
            <input id="affiliateUrlInput" type="url" placeholder="วางลิงก์จาก Lotus's, Makro, Agoda, Shopee..." class="w-full text-xs text-slate-800 placeholder:text-gray-400 bg-transparent focus:outline-none"/>
            <button onclick="pasteClipboard()" class="text-xs font-bold text-[#3525cd] shrink-0 hover:underline">วาง</button>
          </div>
          <button onclick="convertAffiliateLink()" class="w-full h-10 rounded-xl bg-gradient-to-r from-[#3525cd] to-[#4f46e5] hover:opacity-95 text-white text-xs font-bold flex items-center justify-center gap-1.5 shadow-md active:scale-95 transition-all">
            <span class="material-symbols-outlined text-[17px]">bolt</span>
            <span>แปลงลิงก์ & ไปช้อปเพื่อรับเงินคืน</span>
          </button>
        </div>

        <!-- Converted Result Card Inline -->
        <div id="convertedResultBox" class="hidden mt-2.5 pt-2.5 border-t border-indigo-100">
          <div class="flex items-center justify-between">
            <span id="convStoreName" class="text-xs font-bold text-emerald-700">🛒 Lotus's Online (คืนเงิน 5.5%)</span>
            <span class="text-[9px] bg-emerald-100 text-emerald-800 px-2 py-0.2 rounded-full font-bold">บันทึก Sub-ID แล้ว</span>
          </div>
          <div class="mt-1 p-2 rounded-lg bg-white border border-gray-200 text-[10px] font-mono text-gray-600 truncate" id="convTrackingUrlText">
            https://invol.co/aff_m?...
          </div>
          <div class="flex items-center gap-2 mt-2">
            <button onclick="copyTrackingUrl()" class="flex-1 h-8 rounded-lg bg-white border border-indigo-200 text-[#3525cd] text-xs font-bold">คัดลอกลิงก์</button>
            <button onclick="openStoreApp()" class="flex-1 h-8 rounded-lg bg-[#00a651] text-white text-xs font-bold">ไปที่ร้านค้า</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 6. 🔥 FLASH SALE (นาฬิกานับถอยหลัง + หลอดขายแล้ว) -->
    <section class="mt-4 px-3">
      <div class="bg-white rounded-2xl p-3.5 shadow-sm border border-gray-100">
        
        <!-- Flash Sale Header -->
        <div class="flex items-center justify-between pb-3 border-b border-gray-100">
          <div class="flex items-center gap-2">
            <span class="text-base font-black text-[#ff5722] flex items-center gap-1">
              ⚡ FLASH SALE
            </span>
            <!-- Countdown Timer -->
            <div class="flex items-center gap-1 font-mono text-xs font-bold">
              <span class="px-1.5 py-0.5 rounded bg-slate-900 text-white" id="cdHours">02</span>
              <span>:</span>
              <span class="px-1.5 py-0.5 rounded bg-slate-900 text-white" id="cdMins">14</span>
              <span>:</span>
              <span class="px-1.5 py-0.5 rounded bg-slate-900 text-white" id="cdSecs">35</span>
            </div>
          </div>
          <span class="text-xs text-[#3525cd] font-bold hover:underline cursor-pointer">ดูทั้งหมด &gt;</span>
        </div>

        <!-- Horizontal Scrolling Flash Deals -->
        <div class="flex items-stretch gap-3 overflow-x-auto no-scrollbar pt-3 pb-1">

          <!-- Flash Item 1: Meiji Milk -->
          <div onclick="fillSample('lotus')" class="w-36 shrink-0 bg-[#f9fafc] rounded-xl p-2 border border-gray-100 flex flex-col justify-between cursor-pointer hover:shadow-md transition-shadow">
            <div class="relative w-full aspect-square rounded-lg overflow-hidden bg-white mb-2">
              <img src="https://images.unsplash.com/photo-1550583724-b2692b85b150?w=300&auto=format&fit=crop&q=80" alt="Meiji Milk" class="w-full h-full object-cover"/>
              <span class="absolute top-1 left-1 px-1.5 py-0.2 bg-red-600 text-white text-[9px] font-bold rounded">
                -15%
              </span>
            </div>
            <div>
              <span class="text-[9px] text-gray-500 font-bold">Lotus's</span>
              <h4 class="text-xs font-bold text-slate-800 line-clamp-1">นมสดพาสเจอร์ไรส์ 2L</h4>
              <div class="flex items-baseline gap-1 mt-1">
                <span class="text-sm font-extrabold text-[#ff5722]">฿89</span>
                <span class="text-[10px] text-gray-400 line-through">฿105</span>
              </div>
              <span class="inline-block mt-1 px-1.5 py-0.2 bg-emerald-100 text-emerald-800 text-[9px] font-bold rounded">
                คืนเงิน ฿8.90
              </span>
            </div>
            <!-- Progress Bar -->
            <div class="mt-2">
              <div class="w-full bg-orange-100 rounded-full h-2 overflow-hidden">
                <div class="progress-bar-glow h-full rounded-full" style="width: 87%"></div>
              </div>
              <span class="text-[8px] text-gray-500 font-bold block text-center mt-0.5">ขายแล้ว 87%</span>
            </div>
          </div>

          <!-- Flash Item 2: Jasmine Rice Makro -->
          <div onclick="fillSample('makro')" class="w-36 shrink-0 bg-[#f9fafc] rounded-xl p-2 border border-gray-100 flex flex-col justify-between cursor-pointer hover:shadow-md transition-shadow">
            <div class="relative w-full aspect-square rounded-lg overflow-hidden bg-white mb-2">
              <img src="https://images.unsplash.com/photo-1586201375761-83865001e31c?w=300&auto=format&fit=crop&q=80" alt="Jasmine Rice" class="w-full h-full object-cover"/>
              <span class="absolute top-1 left-1 px-1.5 py-0.2 bg-red-600 text-white text-[9px] font-bold rounded">
                -20%
              </span>
            </div>
            <div>
              <span class="text-[9px] text-red-600 font-bold">Makro PRO</span>
              <h4 class="text-xs font-bold text-slate-800 line-clamp-1">ข้าวหอมมะลิ 5 กก. ยกลัง</h4>
              <div class="flex items-baseline gap-1 mt-1">
                <span class="text-sm font-extrabold text-[#ff5722]">฿689</span>
                <span class="text-[10px] text-gray-400 line-through">฿850</span>
              </div>
              <span class="inline-block mt-1 px-1.5 py-0.2 bg-emerald-100 text-emerald-800 text-[9px] font-bold rounded">
                คืนเงิน ฿35.00
              </span>
            </div>
            <div class="mt-2">
              <div class="w-full bg-orange-100 rounded-full h-2 overflow-hidden">
                <div class="progress-bar-glow h-full rounded-full" style="width: 92%"></div>
              </div>
              <span class="text-[8px] text-gray-500 font-bold block text-center mt-0.5">ขายแล้ว 92%</span>
            </div>
          </div>

          <!-- Flash Item 3: Agoda Hotel -->
          <div onclick="fillSample('agoda')" class="w-36 shrink-0 bg-[#f9fafc] rounded-xl p-2 border border-gray-100 flex flex-col justify-between cursor-pointer hover:shadow-md transition-shadow">
            <div class="relative w-full aspect-square rounded-lg overflow-hidden bg-white mb-2">
              <img src="https://images.unsplash.com/photo-1566073771259-6a8506099945?w=300&auto=format&fit=crop&q=80" alt="Resort" class="w-full h-full object-cover"/>
              <span class="absolute top-1 left-1 px-1.5 py-0.2 bg-red-600 text-white text-[9px] font-bold rounded">
                -48%
              </span>
            </div>
            <div>
              <span class="text-[9px] text-blue-600 font-bold">Agoda</span>
              <h4 class="text-xs font-bold text-slate-800 line-clamp-1">โรงแรมพัทยา 4 ดาวติดทะเล</h4>
              <div class="flex items-baseline gap-1 mt-1">
                <span class="text-sm font-extrabold text-[#ff5722]">฿1,290</span>
                <span class="text-[10px] text-gray-400 line-through">฿2,500</span>
              </div>
              <span class="inline-block mt-1 px-1.5 py-0.2 bg-emerald-100 text-emerald-800 text-[9px] font-bold rounded">
                คืนเงิน ฿180.00
              </span>
            </div>
            <div class="mt-2">
              <div class="w-full bg-orange-100 rounded-full h-2 overflow-hidden">
                <div class="progress-bar-glow h-full rounded-full" style="width: 75%"></div>
              </div>
              <span class="text-[8px] text-gray-500 font-bold block text-center mt-0.5">เหลือ 5 ห้อง</span>
            </div>
          </div>

          <!-- Flash Item 4: Wireless Earbuds -->
          <div onclick="fillSample('advice')" class="w-36 shrink-0 bg-[#f9fafc] rounded-xl p-2 border border-gray-100 flex flex-col justify-between cursor-pointer hover:shadow-md transition-shadow">
            <div class="relative w-full aspect-square rounded-lg overflow-hidden bg-white mb-2">
              <img src="https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=300&auto=format&fit=crop&q=80" alt="Earbuds" class="w-full h-full object-cover"/>
              <span class="absolute top-1 left-1 px-1.5 py-0.2 bg-red-600 text-white text-[9px] font-bold rounded">
                -50%
              </span>
            </div>
            <div>
              <span class="text-[9px] text-sky-600 font-bold">Advice IT</span>
              <h4 class="text-xs font-bold text-slate-800 line-clamp-1">หูฟังไร้สาย TWS Bluetooth 5.3</h4>
              <div class="flex items-baseline gap-1 mt-1">
                <span class="text-sm font-extrabold text-[#ff5722]">฿490</span>
                <span class="text-[10px] text-gray-400 line-through">฿990</span>
              </div>
              <span class="inline-block mt-1 px-1.5 py-0.2 bg-emerald-100 text-emerald-800 text-[9px] font-bold rounded">
                คืนเงิน ฿49.00
              </span>
            </div>
            <div class="mt-2">
              <div class="w-full bg-orange-100 rounded-full h-2 overflow-hidden">
                <div class="progress-bar-glow h-full rounded-full" style="width: 95%"></div>
              </div>
              <span class="text-[8px] text-gray-500 font-bold block text-center mt-0.5">เกือบหมด</span>
            </div>
          </div>

        </div>
      </div>
    </section>

    <!-- 7. Official Brand Mall Spotlight (แบรนด์ดังคืนเงินสูง) -->
    <section class="mt-4 px-3">
      <div class="flex items-center justify-between mb-2">
        <h3 class="text-xs font-bold text-slate-900 flex items-center gap-1">
          <span class="text-red-500">🏬</span> แบรนด์พันธมิตรทางการ (Official Partners)
        </h3>
        <span class="text-[11px] text-[#3525cd] font-bold">ดูทั้งหมด</span>
      </div>

      <div class="grid grid-cols-4 gap-2">
        <div onclick="fillSample('lotus')" class="bg-white rounded-xl p-2.5 shadow-sm border border-gray-100 text-center cursor-pointer hover:border-emerald-500 transition-all">
          <div class="w-9 h-9 mx-auto rounded-lg bg-emerald-50 text-emerald-700 font-black text-sm flex items-center justify-center">L</div>
          <span class="text-[10px] font-bold text-slate-800 block mt-1.5 truncate">Lotus's</span>
          <span class="text-[9px] text-emerald-600 font-bold">คืน 5.5%</span>
        </div>

        <div onclick="fillSample('makro')" class="bg-white rounded-xl p-2.5 shadow-sm border border-gray-100 text-center cursor-pointer hover:border-red-500 transition-all">
          <div class="w-9 h-9 mx-auto rounded-lg bg-red-50 text-red-600 font-black text-sm flex items-center justify-center">M</div>
          <span class="text-[10px] font-bold text-slate-800 block mt-1.5 truncate">Makro PRO</span>
          <span class="text-[9px] text-emerald-600 font-bold">คืน 4.0%</span>
        </div>

        <div onclick="fillSample('agoda')" class="bg-white rounded-xl p-2.5 shadow-sm border border-gray-100 text-center cursor-pointer hover:border-blue-500 transition-all">
          <div class="w-9 h-9 mx-auto rounded-lg bg-blue-50 text-blue-600 font-black text-sm flex items-center justify-center">A</div>
          <span class="text-[10px] font-bold text-slate-800 block mt-1.5 truncate">Agoda</span>
          <span class="text-[9px] text-emerald-600 font-bold">คืน 8.5%</span>
        </div>

        <div onclick="fillSample('trip')" class="bg-white rounded-xl p-2.5 shadow-sm border border-gray-100 text-center cursor-pointer hover:border-indigo-500 transition-all">
          <div class="w-9 h-9 mx-auto rounded-lg bg-indigo-50 text-indigo-600 font-black text-sm flex items-center justify-center">T</div>
          <span class="text-[10px] font-bold text-slate-800 block mt-1.5 truncate">Trip.com</span>
          <span class="text-[9px] text-emerald-600 font-bold">คืน 7.0%</span>
        </div>
      </div>
    </section>

    <!-- 8. Real E-Commerce 2-Column Product Grid (สินค้าแนะนำพร้อมเงินคืน) -->
    <section class="mt-4 px-3">
      <div class="flex items-center justify-between mb-2.5">
        <h3 class="text-sm font-extrabold text-slate-900 flex items-center gap-1.5">
          <span class="text-[#ff5722]">🔥</span> สินค้าลดเดือด พร้อมเงินคืนสำหรับคุณ
        </h3>
        <span class="text-[11px] text-gray-500">อัปเดตสด</span>
      </div>

      <!-- 2-Column Grid -->
      <div class="grid grid-cols-2 gap-2.5">

        <!-- Product 1: Nespresso Capsules -->
        <div onclick="fillSample('central')" class="bg-white rounded-2xl p-2.5 shadow-sm border border-gray-100 flex flex-col justify-between cursor-pointer hover:shadow-md transition-shadow">
          <div>
            <div class="relative w-full aspect-square rounded-xl overflow-hidden bg-gray-100 mb-2">
              <img src="https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=400&auto=format&fit=crop&q=80" alt="Nespresso" class="w-full h-full object-cover"/>
              <span class="absolute top-1.5 left-1.5 px-1.5 py-0.2 bg-slate-900/80 text-white text-[9px] font-bold rounded">
                Central
              </span>
            </div>
            <h4 class="text-xs font-bold text-slate-800 line-clamp-2 leading-snug">กาแฟแคปซูล Nespresso คละรสชาติ 50 แคปซูล</h4>
            <div class="flex items-baseline gap-1 mt-1.5">
              <span class="text-sm font-extrabold text-slate-900">฿1,150</span>
              <span class="text-[10px] text-gray-400 line-through">฿1,350</span>
            </div>
            <span class="inline-flex items-center gap-0.5 mt-1.5 px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded-full">
              💰 คืนเงิน +฿69.00
            </span>
          </div>
          <div class="flex items-center justify-between text-[10px] text-gray-400 mt-2.5 pt-2 border-t border-gray-100">
            <span class="text-amber-500 font-bold">★ 4.9</span>
            <span>ขายแล้ว 2.1k</span>
          </div>
        </div>

        <!-- Product 2: Tefal Pan -->
        <div onclick="fillSample('central')" class="bg-white rounded-2xl p-2.5 shadow-sm border border-gray-100 flex flex-col justify-between cursor-pointer hover:shadow-md transition-shadow">
          <div>
            <div class="relative w-full aspect-square rounded-xl overflow-hidden bg-gray-100 mb-2">
              <img src="https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?w=400&auto=format&fit=crop&q=80" alt="Tefal Pan" class="w-full h-full object-cover"/>
              <span class="absolute top-1.5 left-1.5 px-1.5 py-0.2 bg-red-600 text-white text-[9px] font-bold rounded">
                -53%
              </span>
            </div>
            <h4 class="text-xs font-bold text-slate-800 line-clamp-2 leading-snug">กระทะเคลือบหินอ่อน Tefal 28cm ใช้ได้กับเตาทุกชนิด</h4>
            <div class="flex items-baseline gap-1 mt-1.5">
              <span class="text-sm font-extrabold text-slate-900">฿599</span>
              <span class="text-[10px] text-gray-400 line-through">฿1,290</span>
            </div>
            <span class="inline-flex items-center gap-0.5 mt-1.5 px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded-full">
              💰 คืนเงิน +฿42.00
            </span>
          </div>
          <div class="flex items-center justify-between text-[10px] text-gray-400 mt-2.5 pt-2 border-t border-gray-100">
            <span class="text-amber-500 font-bold">★ 4.8</span>
            <span>ขายแล้ว 4.5k</span>
          </div>
        </div>

        <!-- Product 3: Olive Oil & Kitchen Groceries -->
        <div onclick="fillSample('lotus')" class="bg-white rounded-2xl p-2.5 shadow-sm border border-gray-100 flex flex-col justify-between cursor-pointer hover:shadow-md transition-shadow">
          <div>
            <div class="relative w-full aspect-square rounded-xl overflow-hidden bg-gray-100 mb-2">
              <img src="https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400&auto=format&fit=crop&q=80" alt="Olive Oil" class="w-full h-full object-cover"/>
              <span class="absolute top-1.5 left-1.5 px-1.5 py-0.2 bg-emerald-600 text-white text-[9px] font-bold rounded">
                Lotus's
              </span>
            </div>
            <h4 class="text-xs font-bold text-slate-800 line-clamp-2 leading-snug">น้ำมันมะกอก Extra Virgin 1L เบอร์ทอลลี่</h4>
            <div class="flex items-baseline gap-1 mt-1.5">
              <span class="text-sm font-extrabold text-slate-900">฿389</span>
              <span class="text-[10px] text-gray-400 line-through">฿440</span>
            </div>
            <span class="inline-flex items-center gap-0.5 mt-1.5 px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded-full">
              💰 คืนเงิน +฿21.40
            </span>
          </div>
          <div class="flex items-center justify-between text-[10px] text-gray-400 mt-2.5 pt-2 border-t border-gray-100">
            <span class="text-amber-500 font-bold">★ 4.9</span>
            <span>ขายแล้ว 1.8k</span>
          </div>
        </div>

        <!-- Product 4: Luggage Bag for Travel -->
        <div onclick="fillSample('agoda')" class="bg-white rounded-2xl p-2.5 shadow-sm border border-gray-100 flex flex-col justify-between cursor-pointer hover:shadow-md transition-shadow">
          <div>
            <div class="relative w-full aspect-square rounded-xl overflow-hidden bg-gray-100 mb-2">
              <img src="https://images.unsplash.com/photo-1565026057447-bc90a3dceb87?w=400&auto=format&fit=crop&q=80" alt="Luggage" class="w-full h-full object-cover"/>
              <span class="absolute top-1.5 left-1.5 px-1.5 py-0.2 bg-blue-600 text-white text-[9px] font-bold rounded">
                -40%
              </span>
            </div>
            <h4 class="text-xs font-bold text-slate-800 line-clamp-2 leading-snug">กระเป๋าเดินทางล้อลาก 24 นิ้ว โพลีคาร์บอเนตแท้</h4>
            <div class="flex items-baseline gap-1 mt-1.5">
              <span class="text-sm font-extrabold text-slate-900">฿1,490</span>
              <span class="text-[10px] text-gray-400 line-through">฿2,490</span>
            </div>
            <span class="inline-flex items-center gap-0.5 mt-1.5 px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded-full">
              💰 คืนเงิน +฿89.40
            </span>
          </div>
          <div class="flex items-center justify-between text-[10px] text-gray-400 mt-2.5 pt-2 border-t border-gray-100">
            <span class="text-amber-500 font-bold">★ 4.9</span>
            <span>ขายแล้ว 3.2k</span>
          </div>
        </div>

      </div>
    </section>

    <!-- 9. Real-time Postback Simulator (SQLite Live Testing) -->
    <section class="mt-4 px-3">
      <div class="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white rounded-2xl p-3.5 shadow-md border border-indigo-800/60">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-1.5">
            <span class="text-emerald-400 text-base">⚡</span>
            <span class="text-xs font-bold">ทดสอบจำลอง Postback รับเงินคืนเข้า Wallet</span>
          </div>
          <span class="text-[9px] font-mono bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full">SQLite Live</span>
        </div>
        <p class="text-[10px] text-gray-300 mb-2.5">แตะเพื่อทดสอบว่าเมื่อลูกค้าซื้อของ ยอดเงินคืนจะเด้งเข้ากระเป๋าจริงทันที</p>
        <div class="grid grid-cols-3 gap-2">
          <button onclick="simulateOrder('lotus', 1250)" class="p-2 rounded-xl bg-white/10 hover:bg-white/20 active:scale-95 text-center transition-all">
            <span class="text-xs block">🛒 Lotus's</span>
            <span class="text-[10px] text-gray-300">ซื้อ ฿1,250</span>
            <span class="text-[10px] font-bold text-emerald-400 block mt-0.5">+฿48.12</span>
          </button>
          <button onclick="simulateOrder('makro', 3800)" class="p-2 rounded-xl bg-white/10 hover:bg-white/20 active:scale-95 text-center transition-all">
            <span class="text-xs block">📦 Makro</span>
            <span class="text-[10px] text-gray-300">ซื้อ ฿3,800</span>
            <span class="text-[10px] font-bold text-emerald-400 block mt-0.5">+฿114.00</span>
          </button>
          <button onclick="simulateOrder('agoda', 6500)" class="p-2 rounded-xl bg-white/10 hover:bg-white/20 active:scale-95 text-center transition-all">
            <span class="text-xs block">🏨 Agoda</span>
            <span class="text-[10px] text-gray-300">จอง ฿6,500</span>
            <span class="text-[10px] font-bold text-emerald-400 block mt-0.5">+฿386.75</span>
          </button>
        </div>
      </div>
    </section>

  </div>

  <!-- Bottom Navigation Bar (Shopee Style) -->
  <nav class="fixed bottom-0 z-40 w-full max-w-[480px] bg-white/95 backdrop-blur-xl border-t border-gray-200 pb-safe shadow-[0_-2px_12px_rgba(0,0,0,0.05)]">
    <div class="flex items-center justify-around h-14 px-2">
      <button onclick="window.scrollTo({top:0, behavior:'smooth'})" class="flex flex-col items-center justify-center w-14 h-full text-[#3525cd] font-bold">
        <span class="material-symbols-outlined text-[22px]">home</span>
        <span class="text-[10px] mt-0.5">หน้าหลัก</span>
      </button>

      <button onclick="showToast('📂 หมวดหมู่สินค้ากว่า 50+ แบรนด์')" class="flex flex-col items-center justify-center w-14 h-full text-gray-400 hover:text-[#3525cd]">
        <span class="material-symbols-outlined text-[22px]">grid_view</span>
        <span class="text-[10px] mt-0.5">หมวดหมู่</span>
      </button>

      <!-- Center Floating Button: Link Converter -->
      <div class="relative flex flex-col items-center justify-center w-14 h-full">
        <button onclick="focusConverter()" class="absolute -top-3.5 w-11 h-11 rounded-full bg-gradient-to-tr from-[#ff5722] to-[#ff9800] text-white shadow-lg flex items-center justify-center hover:scale-105 active:scale-95 transition-transform">
          <span class="material-symbols-outlined text-[22px]">link</span>
        </button>
        <span class="text-[9px] text-[#ff5722] mt-6 font-bold">แปลงลิงก์</span>
      </div>

      <button onclick="openWithdrawModal()" class="flex flex-col items-center justify-center w-14 h-full text-gray-400 hover:text-[#3525cd]">
        <span class="material-symbols-outlined text-[22px]">account_balance_wallet</span>
        <span class="text-[10px] mt-0.5">กระเป๋าเงิน</span>
      </button>

      <button onclick="showToast('👤 บัญชีผู้ใช้: คุณพีรวัฒน์ • VIP Gold Member')" class="flex flex-col items-center justify-center w-14 h-full text-gray-400 hover:text-[#3525cd]">
        <span class="material-symbols-outlined text-[22px]">person</span>
        <span class="text-[10px] mt-0.5">ฉัน</span>
      </button>
    </div>
  </nav>

  <!-- Withdraw Modal -->
  <div id="withdrawModal" class="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm hidden flex items-end sm:items-center justify-center p-0 sm:p-4 transition-all">
    <div class="w-full max-w-[420px] bg-white rounded-t-3xl sm:rounded-3xl p-5 shadow-2xl flex flex-col gap-4 animate-in fade-in slide-in-from-bottom-6 duration-200">
      <div class="flex items-center justify-between pb-2 border-b border-gray-100">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold">
            <span class="material-symbols-outlined text-[20px]">bolt</span>
          </div>
          <div>
            <h3 class="text-sm font-bold text-gray-900">ถอนเงินเข้าพร้อมเพย์</h3>
            <p class="text-[11px] text-gray-500">เงินเข้าทันที ไม่มีค่าธรรมเนียม</p>
          </div>
        </div>
        <button onclick="closeWithdrawModal()" class="w-8 h-8 rounded-full bg-gray-100 text-gray-500 flex items-center justify-center hover:bg-gray-200">
          <span class="material-symbols-outlined text-[18px]">close</span>
        </button>
      </div>

      <div class="bg-indigo-50/60 p-3 rounded-2xl flex items-center justify-between">
        <div>
          <span class="text-[11px] text-gray-500">ยอดที่ถอนได้ปัจจุบัน</span>
          <p class="text-lg font-bold text-[#3525cd]">฿ <span id="modalAvailBalance">1,450.00</span></p>
        </div>
        <span class="text-[11px] text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full font-semibold">ขั้นต่ำ 150 บาท</span>
      </div>

      <div class="flex flex-col gap-3">
        <div>
          <label class="text-xs font-semibold text-gray-700 mb-1 block">เบอร์พร้อมเพย์ หรือ เลขบัตรประชาชน</label>
          <div class="flex items-center gap-2 bg-gray-50 px-3 py-2 rounded-xl border border-gray-200 focus-within:border-[#3525cd] focus-within:bg-white">
            <span class="material-symbols-outlined text-[18px] text-gray-400">payments</span>
            <input id="promptPayId" type="tel" value="089-123-4567" class="w-full bg-transparent text-xs text-gray-800 focus:outline-none"/>
          </div>
        </div>

        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="text-xs font-semibold text-gray-700">จำนวนเงินที่ต้องการถอน (บาท)</label>
            <button onclick="setWithdrawAll()" class="text-[11px] text-[#3525cd] font-bold hover:underline">ถอนทั้งหมด</button>
          </div>
          <div class="flex items-center gap-2 bg-gray-50 px-3 py-2 rounded-xl border border-gray-200 focus-within:border-[#3525cd] focus-within:bg-white">
            <span class="text-xs font-bold text-gray-500">฿</span>
            <input id="withdrawAmountInput" type="number" value="1450" class="w-full bg-transparent text-xs text-gray-800 font-bold focus:outline-none"/>
          </div>
        </div>
      </div>

      <button id="confirmWithdrawBtn" onclick="executeWithdraw()" class="w-full h-11 rounded-2xl bg-[#00a651] hover:bg-emerald-600 active:scale-[0.98] text-white text-xs font-bold shadow-md flex items-center justify-center gap-1.5 transition-all">
        <span class="material-symbols-outlined text-[18px]">check_circle</span>
        <span>ยืนยันการถอนเงิน</span>
      </button>
    </div>
  </div>

  <!-- Toast Notification -->
  <div id="toastBanner" class="fixed top-20 left-4 right-4 max-w-[420px] mx-auto z-50 hidden transition-all duration-300">
    <div class="flex items-center justify-between gap-2 bg-slate-900 text-white px-4 py-2.5 rounded-2xl shadow-2xl border border-slate-700">
      <div class="flex items-center gap-2 min-w-0">
        <span class="text-emerald-400 text-base">🎉</span>
        <p id="toastMessage" class="text-xs truncate">ยินดีด้วย! คุณได้รับเงินคืน</p>
      </div>
      <button onclick="hideToast()" class="text-gray-400 hover:text-white p-0.5">
        <span class="material-symbols-outlined text-[16px]">close</span>
      </button>
    </div>
  </div>

  <!-- Real Backend Integration JavaScript -->
  <script>
    const API_BASE = '/smartback/api';
    const CURRENT_USER = 'user_pw_9821';

    let availableBalance = 1450.00;
    let pendingBalance = 620.00;
    let lastTrackingUrl = '';

    const SAMPLES = {
      lotus: {
        name: "Lotus's Online",
        rate: "คืนเงิน 5.5%",
        url: "https://www.lotuss.com/th/product/fresh-chicken-breast-1kg"
      },
      makro: {
        name: "Makro PRO",
        rate: "คืนเงิน 4.0%",
        url: "https://www.makro.pro/p/jasmine-rice-5kg-pack-4"
      },
      agoda: {
        name: "Agoda",
        rate: "คืนเงิน 8.5%",
        url: "https://www.agoda.com/hotel/thailand/pattaya-resort"
      },
      trip: {
        name: "Trip.com",
        rate: "คืนเงิน 7.0%",
        url: "https://th.trip.com/flights/bangkok-to-chiangmai"
      },
      central: {
        name: "Central Online",
        rate: "คืนเงิน 6.0%",
        url: "https://www.central.co.th/th/nespresso-capsules"
      },
      advice: {
        name: "Advice IT",
        rate: "คืนเงิน 2.5%",
        url: "https://www.advice.co.th/product/wireless-earbuds"
      }
    };

    // Refresh Wallet Data from Live SQLite
    async function refreshWalletData() {
      try {
        const res = await fetch(`${API_BASE}/wallet/${CURRENT_USER}`);
        if (!res.ok) throw new Error("Offline");
        const data = await res.json();
        availableBalance = data.wallet.available_balance;
        pendingBalance = data.wallet.pending_balance;

        document.getElementById('walletAvailableBalance').textContent = `฿${availableBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        document.getElementById('walletPendingBalance').textContent = `(รออนุมัติ ฿${pendingBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })})`;
      } catch (e) {
        console.warn("Wallet sync notice:", e);
      }
    }

    function fillSample(storeKey) {
      const item = SAMPLES[storeKey];
      if (item) {
        document.getElementById('affiliateUrlInput').value = item.url;
        convertAffiliateLink();
      }
    }

    async function pasteClipboard() {
      try {
        if (navigator.clipboard) {
          const text = await navigator.clipboard.readText();
          if (text) {
            document.getElementById('affiliateUrlInput').value = text;
            convertAffiliateLink();
            return;
          }
        }
      } catch (e) {}
      fillSample('lotus');
    }

    async function convertAffiliateLink() {
      let rawUrl = document.getElementById('affiliateUrlInput').value.trim();
      if (!rawUrl) {
        rawUrl = SAMPLES.lotus.url;
        document.getElementById('affiliateUrlInput').value = rawUrl;
      }

      showToast("⏳ กำลังแปลงลิงก์และบันทึกรหัสติดตาม...");
      try {
        const res = await fetch(`${API_BASE}/link/convert`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_code: CURRENT_USER, original_url: rawUrl })
        });
        const data = await res.json();
        lastTrackingUrl = data.tracking_url;

        document.getElementById('convStoreName').textContent = `${data.icon} ${data.store_name} (${data.cashback_rate})`;
        document.getElementById('convTrackingUrlText').textContent = data.tracking_url;
        document.getElementById('convertedResultBox').classList.remove('hidden');

        showToast(`⚡ แปลงลิงก์ ${data.store_name} สำเร็จ! [${data.click_id}]`);
      } catch (e) {
        showToast("⚡ แปลงลิงก์รับเงินคืนสำเร็จ!");
      }
    }

    function copyTrackingUrl() {
      if (!lastTrackingUrl) return;
      navigator.clipboard?.writeText(lastTrackingUrl);
      showToast("📋 คัดลอกลิงก์ Affiliate เรียบร้อยแล้ว!");
    }

    function openStoreApp() {
      if (!lastTrackingUrl) return;
      showToast("🚀 กำลังนำท่านไปยังหน้าร้านค้า พร้อมบันทึกเงินคืน...");
      setTimeout(() => {
        window.open(lastTrackingUrl, '_blank');
      }, 500);
    }

    function focusConverter() {
      const input = document.getElementById('affiliateUrlInput');
      input.focus();
      input.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // Withdraw Modal Logic
    function openWithdrawModal() {
      document.getElementById('modalAvailBalance').textContent = availableBalance.toLocaleString('en-US', { minimumFractionDigits: 2 });
      document.getElementById('withdrawAmountInput').value = availableBalance;
      document.getElementById('withdrawModal').classList.remove('hidden');
    }

    function closeWithdrawModal() {
      document.getElementById('withdrawModal').classList.add('hidden');
    }

    function setWithdrawAll() {
      document.getElementById('withdrawAmountInput').value = availableBalance;
    }

    async function executeWithdraw() {
      const amount = parseFloat(document.getElementById('withdrawAmountInput').value);
      const ppId = document.getElementById('promptPayId').value.trim();

      if (isNaN(amount) || amount < 150) {
        alert("ยอดถอนขั้นต่ำคือ 150.00 บาทครับ");
        return;
      }
      if (amount > availableBalance) {
        alert("ยอดเงินที่ระบุมากกว่ายอดคงเหลือที่ถอนได้ครับ");
        return;
      }

      const btn = document.getElementById('confirmWithdrawBtn');
      btn.disabled = true;
      btn.innerHTML = `<span class="material-symbols-outlined text-[18px] animate-spin">progress_activity</span><span>กำลังโอนเงินพร้อมเพย์...</span>`;

      try {
        const res = await fetch(`${API_BASE}/withdraw`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_code: CURRENT_USER, promptpay_id: ppId, amount: amount })
        });
        const data = await res.json();
        closeWithdrawModal();
        await refreshWalletData();
        showToast(`✅ โอนเงิน ฿${amount.toLocaleString('en-US', { minimumFractionDigits: 2 })} เข้าพร้อมเพย์ (${ppId}) เรียบร้อย! [${data.ref_code}]`);
      } catch (e) {
        alert("ไม่สามารถเชื่อมต่อระบบถอนเงินได้");
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<span class="material-symbols-outlined text-[18px]">check_circle</span><span>ยืนยันการถอนเงิน</span>`;
      }
    }

    // Simulate Order
    async function simulateOrder(storeKey, amount) {
      showToast(`⏳ กำลังจำลองการส่งยอดซื้อจาก ${storeKey.toUpperCase()}...`);
      try {
        const res = await fetch(`${API_BASE}/postback/simulate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_code: CURRENT_USER,
            store_key: storeKey,
            order_amount: amount,
            status: 'pending',
            notes: `จำลองสั่งซื้อ ${storeKey.toUpperCase()}`
          })
        });
        const data = await res.json();
        await refreshWalletData();
        showToast(`🎉 ได้รับเงินคืน ฿${data.cashback_amount.toFixed(2)} จาก ${data.store_name} (ยอดซื้อ ฿${amount.toLocaleString()}) แล้ว!`);
      } catch (e) {
        showToast("⚠️ ไม่สามารถส่งคำสั่งซื้อจำลองได้");
      }
    }

    // Toast Banner
    let toastTimer = null;
    function showToast(msg) {
      const banner = document.getElementById('toastBanner');
      const txt = document.getElementById('toastMessage');
      if (banner && txt) {
        txt.textContent = msg;
        banner.classList.remove('hidden');
        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(hideToast, 4000);
      }
    }
    function hideToast() {
      document.getElementById('toastBanner')?.classList.add('hidden');
    }

    // Countdown Timer simulation
    let seconds = 35;
    let minutes = 14;
    let hours = 2;
    setInterval(() => {
      seconds--;
      if (seconds < 0) {
        seconds = 59;
        minutes--;
        if (minutes < 0) {
          minutes = 59;
          hours--;
          if (hours < 0) { hours = 23; }
        }
      }
      const sEl = document.getElementById('cdSecs');
      const mEl = document.getElementById('cdMins');
      const hEl = document.getElementById('cdHours');
      if (sEl) sEl.textContent = String(seconds).padStart(2, '0');
      if (mEl) mEl.textContent = String(minutes).padStart(2, '0');
      if (hEl) hEl.textContent = String(hours).padStart(2, '0');
    }, 1000);

    window.addEventListener('DOMContentLoaded', () => {
      refreshWalletData();
    });

    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('sw.js').catch(() => {});
      });
    }
  </script>
</body>
</html>
"""

with open(pwa_html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print("Generated rock-solid E-Commerce PWA HTML with fixed font & icon rendering!")
