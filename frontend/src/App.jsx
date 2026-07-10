import { useState, useEffect, useRef } from 'react';
import AdminPanel from './components/AdminPanel';
import './App.css';

// SVG Icons for general UI
const SearchIcon = ({ className = "" }) => (
  <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"></circle>
    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
  </svg>
);

const BellIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
    <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
  </svg>
);

const ChevronDownIcon = () => (
  <svg className="avatar-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="6 9 12 15 18 9"></polyline>
  </svg>
);

const CloseIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18"></line>
    <line x1="6" y1="6" x2="18" y2="18"></line>
  </svg>
);

const TerminalIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="4 17 10 11 4 5"></polyline>
    <line x1="12" y1="19" x2="20" y2="19"></line>
  </svg>
);

const CheckCircleIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
    <polyline points="22 4 12 14.01 9 11.01"></polyline>
  </svg>
);

const BackIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="19" y1="12" x2="5" y2="12"></line>
    <polyline points="12 19 5 12 12 5"></polyline>
  </svg>
);

const StarIcon = ({ filled }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill={filled ? "#ffc107" : "none"} stroke="#ffc107" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
  </svg>
);

// Bottom Navigation Icons
const NavStoreIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
    <polyline points="9 22 9 12 15 12 15 22"/>
  </svg>
);
const NavAppsIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7" rx="1"/>
    <rect x="14" y="3" width="7" height="7" rx="1"/>
    <rect x="3" y="14" width="7" height="7" rx="1"/>
    <rect x="14" y="14" width="7" height="7" rx="1"/>
  </svg>
);
const NavTxnIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/>
    <line x1="16" y1="17" x2="8" y2="17"/>
  </svg>
);
const NavProfileIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
    <circle cx="12" cy="7" r="4"/>
  </svg>
);
const NavSettingsIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </svg>
);

const ShieldCheckIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
  </svg>
);

const SunIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="5"></circle>
    <line x1="12" y1="1" x2="12" y2="3"></line>
    <line x1="12" y1="21" x2="12" y2="23"></line>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
    <line x1="1" y1="12" x2="3" y2="12"></line>
    <line x1="21" y1="12" x2="23" y2="12"></line>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
  </svg>
);

const MoonIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
  </svg>
);

// Fallback apps data matching the mockup layout
const DEFAULT_APPS = [
  {
    id: "lineman",
    name: "ไลน์แมน",
    description: "สั่งอาหาร ส่งของ แท็กซี่ และบริการอื่น ๆ ตอบโจทย์ทุกความต้องการ",
    longDescription: "ไลน์แมน (LINE MAN) แอปพลิเคชันผู้ช่วยอันดับหนึ่งของคนไทย รวบรวมบริการอำนวยความสะดวกในชีวิตประจำวันไว้ครบในที่เดียว ไม่ว่าจะเป็นสั่งอาหารจากร้านโปรด บริการรับส่งของด่วนด้วยแมสเซนเจอร์ บริการเรียกแท็กซี่ หรือซื้อของซูเปอร์มาร์เก็ตมาส่งถึงหน้าบ้าน มีบอทช่วยสแกนวิเคราะห์โปรโมชันเด็ด ๆ และจัดหมวดหมู่อาหารยอดนิยมเพื่อวางแผนการตลาดร้านค้า",
    developer: "LINE MAN Corporation",
    rating: 4.8,
    downloads: "500K+",
    size: "28 MB",
    price: 0,
    currency: "THB",
    iconColor: "#00C274",
    script: "scripts/lineman.sh",
    reviews: [
      { user: "กิตติพงษ์ ส.", rating: 5, date: "3 ก.ค. 2569", comment: "บอทรันสแกนเก็บข้อมูลร้านค้าอาหารได้เร็วมากครับ ดึงรายการสินค้าได้ครบถ้วน แนะนำเลย" },
      { user: "ณิชาภัทร ว.", rating: 4, date: "1 ก.ค. 2569", comment: "แอปใช้งานง่าย ฟังก์ชันค้นหาและกรองข้อมูลดีมากค่ะ ช่วยให้ได้ข้อมูลวิจัยตลาดโปรโมชันได้ดี" }
    ]
  },
  {
    id: "shopee",
    name: "ช้อปปี้",
    description: "ช้อปปิ้งออนไลน์ที่คุ้มค่า สินค้าหลากหลาย โปรโมชันจัดเต็ม",
    longDescription: "ช้อปปี้ (Shopee) แพลตฟอร์มอีคอมเมิร์ซชั้นนำในเอเชียตะวันออกเฉียงใต้และไต้หวัน มอบประสบการณ์การช้อปปิ้งออนไลน์ที่ไร้รอยต่อ ปลอดภัย และคุ้มค่าด้วยโปรโมชันแจกโค้ดส่งฟรีและดีลลดกระหน่ำ บอทตัวช่วยสแกนติดตามราคาสินค้ายอดนิยมและเปรียบเทียบประวัติราคา เพื่อให้แน่ใจว่าคุณไม่พลาดดีลที่ถูกที่สุดในตลาด",
    developer: "Shopee Southeast Asia Ltd.",
    rating: 4.7,
    downloads: "1M+",
    size: "35 MB",
    price: 199,
    currency: "THB",
    iconColor: "#EE4D2D",
    script: "scripts/shopee.sh",
    reviews: [
      { user: "ประเสริฐ ด.", rating: 5, date: "2 ก.ค. 2569", comment: "ชำระเงินผ่าน Stripe Sandbox สะดวกรวดเร็ว บอทสแกนเปรียบเทียบราคาสินค้าได้แม่นยำมาก คุ้มราคา 199 บาทครับ" },
      { user: "ธัญลักษณ์ พ.", rating: 5, date: "30 มิ.ย. 2569", comment: "ช่วยเซฟเวลาไปเยอะมาก บอทดึงข้อมูลรายงานออกมาเป็น CSV สวยงาม เปิดดูใน Excel ได้ทันทีค่ะ" }
    ]
  },
  {
    id: "grab",
    name: "Grab",
    description: "บริการรับส่งและสั่งอาหาร สะดวก รวดเร็ว ปลอดภัย ทุกการเดินทาง",
    longDescription: "แกร็บ (Grab) ซูเปอร์แอปชั้นนำในภูมิภาคเอเชียตะวันออกเฉียงใต้ นำเสนอบริการเรียกรถ สั่งอาหาร จัดส่งพัสดุ และชำระเงินแบบไร้เงินสด บอทผู้ช่วยสามารถสแกนเปรียบเทียบราคาค่าโดยสารและเวลาเดินทางเฉลี่ยในแต่ละช่วงเวลา เพื่อวางแผนค่าใช้จ่ายสำหรับการเดินทางขององค์กรและบันทึกรายงานรายเดือนได้อย่างแม่นยำ",
    developer: "Grab Holdings Inc.",
    rating: 4.9,
    downloads: "2M+",
    size: "42 MB",
    price: 0,
    currency: "THB",
    iconColor: "#00B159",
    script: "scripts/grab.sh",
    reviews: [
      { user: "อภิรักษ์ ม.", rating: 5, date: "4 ก.ค. 2569", comment: "บอทวิเคราะห์ข้อมูลการเดินทางทำงานเร็วมาก ช่วยวิเคราะห์ช่วงเวลาที่ราคาคุ้มค่าที่สุดได้ดีมาก" }
    ]
  },
  {
    id: "trueid",
    name: "ทรูไอดี",
    description: "ดูหนัง ซีรีส์ และทีวีออนไลน์ ความบันเทิงครบวงจรในแอปเดียว",
    longDescription: "ทรูไอดี (TrueID) แพลตฟอร์มความบันเทิงและไลฟ์สไตล์ระดับพรีเมียมของคนไทย รวมความบันเทิงครบทุกรสชาติ ทั้งหนังดัง ซีรีส์ฮิต ทีวีออนไลน์สด และฟุตบอลพรีเมียร์ลีกอังกฤษแบบฟรีและพรีเมียม บอทเสริมช่วยดึงข้อมูลรายการที่กำลังฮิตและเทรนด์หนังยอดนิยมประจำสัปดาห์มาสรุปทำเป็นแผนภูมิสถิติสำหรับการวางแผนสื่อโฆษณา",
    developer: "True Digital Group",
    rating: 4.6,
    downloads: "800K+",
    size: "24 MB",
    price: 0,
    currency: "THB",
    iconColor: "#EC1C24",
    script: "scripts/trueid.sh",
    reviews: [
      { user: "กวิน น.", rating: 4, date: "29 มิ.ย. 2569", comment: "บอทดึงข้อมูลวิเคราะห์แนวหนังยอดนิยมได้ดี เอาสถิติไปทำการตลาดต่อได้ง่ายมากครับ" }
    ]
  }
];

// Carousel Banner Graphics details matching the original mockup
const CAROUSEL_SLIDES = [
  {
    id: 1,
    title: "บอทวิเคราะห์การตลาดอีคอมเมิร์ซ",
    description: "ช่วยดึงราคาสินค้ายอดนิยม เปรียบเทียบเทรนด์การตลาด และส่งออกเป็นรายงานด่วนภายใน 1 นาที",
    badge: "แนะนำ",
    bg: "linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.95) 100%)",
    decor: (
      <div className="banner-decor-wrapper">
        <div className="decor-orb green-glow"></div>
        <div className="decor-orb blue-glow"></div>
        <svg className="decor-svg floating-icon-1" width="60" height="60" viewBox="0 0 24 24" fill="none">
          <rect width="24" height="24" rx="5" fill="#00C274" />
          <path d="M6 18V6H8.5L12 11.5L15.5 6H18V18H15.5V10L12 15L8.5 10V18H6Z" fill="white" />
        </svg>
        <svg className="decor-svg floating-icon-2" width="50" height="50" viewBox="0 0 24 24" fill="none">
          <rect width="24" height="24" rx="5" fill="#EE4D2D" />
          <path d="M16 10V8C16 5.8 14.2 4 12 4C9.8 4 8 5.8 8 8V10H6C5.4 10 5 10.4 5 11L6.2 18.2C6.4 19.3 7.3 20 8.4 20H15.6C16.7 20 17.6 19.3 17.8 18.2L19 11C19 10.4 18.6 10 18 10H16ZM10 8C10 6.9 10.9 6 12 6C13.1 6 14 6.9 14 8V10H10V8ZM10.5 13.5C10.5 12.7 11.2 12 12 12C12.8 12 13.5 12.7 13.5 13.5C13.5 14.3 12.8 15 12 15C11.2 15 10.5 14.3 10.5 13.5Z" fill="white" />
        </svg>
      </div>
    )
  },
  {
    id: 2,
    title: "ระบบชำระเงิน Sandbox ของ Stripe",
    description: "ทดสอบการซื้อขายแอปพรีเมียมอย่างปลอดภัยด้วยระบบแซนด์บอกซ์ พร้อมออกใบเสร็จรับเงินเสมือนจริงทันที",
    badge: "ปลอดภัย",
    bg: "linear-gradient(135deg, rgba(20, 26, 46, 0.8) 0%, rgba(10, 12, 22, 0.95) 100%)",
    decor: (
      <div className="banner-decor-wrapper">
        <div className="decor-orb purple-glow"></div>
        <div className="decor-orb indigo-glow"></div>
        <svg className="decor-svg floating-icon-1" width="56" height="56" viewBox="0 0 24 24" fill="none">
          <rect width="24" height="24" rx="5" fill="#EC1C24" />
          <path d="M6 8H10V10H8V16H6V8Z" fill="white" />
        </svg>
      </div>
    )
  }
];

function App() {
  // Main states
  const [apps, setApps] = useState(DEFAULT_APPS);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("store"); // 'store', 'my-apps', 'transactions', 'profile', 'settings', 'checkout', 'payment-success', 'checkout-mock'
  const [installedAppIds, setInstalledAppIds] = useState(new Set(["lineman"])); // Preinstall lineman for mockup accuracy
  const [installingStates, setInstallingStates] = useState({ lineman: "installed" }); // Map appId -> 'idle' | 'downloading' | 'installing' | 'installed'
  const [selectedApp, setSelectedApp] = useState(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [theme, setTheme] = useState("dark"); // 'dark' | 'light'

  // User Authentication states
  const [userToken, setUserToken] = useState(localStorage.getItem('authToken') || null);
  const [currentUser, setCurrentUser] = useState(JSON.parse(localStorage.getItem('authUser')) || null);
  const [isAdmin, setIsAdmin] = useState(localStorage.getItem('isAdmin') === 'true');
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authTab, setAuthTab] = useState('login'); // 'login' | 'register'
  const [showMobileSearch, setShowMobileSearch] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  // Terminal simulator state
  const [terminalLogs, setTerminalLogs] = useState([]);
  const [isTerminalRunning, setIsTerminalRunning] = useState(false);
  const [scriptFinished, setScriptFinished] = useState(false);

  // Stripe Checkout / Mock state
  const [checkoutApp, setCheckoutApp] = useState(null);
  const [mockPaymentSession, setMockPaymentSession] = useState(null);
  const [paymentProcessing, setPaymentProcessing] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState('card'); // 'card' or 'promptpay'
  const [cardHolder, setCardHolder] = useState("OpenHands Tester");
  const [cardNumber, setCardNumber] = useState("4242 4242 4242 4242");
  const [cardExpiry, setCardExpiry] = useState("12/28");
  const [cardCvc, setCardCvc] = useState("424");
  
  // PromptPay QR state
  const [promptPayQR, setPromptPayQR] = useState(null);
  const [promptPayTxData, setPromptPayTxData] = useState(null);

  // Profile overrides
  const [profileName, setProfileName] = useState(currentUser?.name || "OpenHands ERP");
  const [profileEmail, setProfileEmail] = useState(currentUser?.email || "admin@openhands.com");
  const [profileRole, setProfileRole] = useState("นักพัฒนาระบบบอทการตลาด");
  const [profileOrg, setProfileOrg] = useState("AI Agent Company Ltd.");
  const [githubKey, setGithubKey] = useState("ghp_1Vatz0b9QOvQQQUhCcPEILFomuQx004uVPg");
  const [telegramToken, setTelegramToken] = useState("8635403645:AAGprJr5h7Fz7ffkZ8NbKIsWEwzaMBfDZAE");
  const [telegramChatId, setTelegramChatId] = useState("7927273659");
  
  // SSH Settings
  const [serverIP, setServerIP] = useState("89.167.82.205");
  const [sshUser, setSshUser] = useState("openhands");
  const [sshPort, setSshPort] = useState("22");

  // OpenCode API Selection States
  const [opencodeModel, setOpencodeModel] = useState(localStorage.getItem('opencode_model') || "opencode-go/deepseek-v4-flash");
  const [opencodeModels, setOpencodeModels] = useState([
    { id: "opencode-go/deepseek-v4-flash", name: "DeepSeek V4 Flash" },
    { id: "opencode-go/deepseek-v4-pro", name: "DeepSeek V4 Pro" },
    { id: "opencode-go/qwen3.6-plus", name: "Qwen 3.6 Plus" },
    { id: "opencode-go/qwen3.7-max", name: "Qwen 3.7 Max" },
    { id: "opencode-go/glm-5.2", name: "GLM 5.2" },
    { id: "opencode-go/kimi-k2.7-code", name: "Kimi K2.7 Code" }
  ]);

  // Load OpenCode models and active model from backend
  useEffect(() => {
    fetch('/api/opencode/models')
      .then(res => res.json())
      .then(data => {
        if (data.data && Array.isArray(data.data)) {
          const formatted = data.data.map(m => {
            const shortName = m.id.replace('opencode-go/', '');
            const displayName = shortName.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            return { id: m.id, name: displayName };
          });
          setOpencodeModels(formatted);
        }
      })
      .catch(err => console.warn("Failed to load live OpenCode models:", err));

    fetch('/api/opencode/active-model')
      .then(res => res.json())
      .then(data => {
        if (data.model) {
          setOpencodeModel(data.model);
          localStorage.setItem('opencode_model', data.model);
        }
      })
      .catch(err => console.warn("Failed to load active OpenCode model:", err));
  }, []);

  const handleActiveModelChange = (model) => {
    setOpencodeModel(model);
    localStorage.setItem('opencode_model', model);
    fetch('/api/opencode/active-model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model })
    })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        showToast(`สลับโมเดลสำเร็จ! ขณะนี้ใช้ ${model}`, "success");
      } else {
        showToast("ไม่สามารถสลับโมเดลบนเซิร์ฟเวอร์ได้", "error");
      }
    })
    .catch(err => {
      console.error(err);
      showToast("สลับโมเดลบนเซิร์ฟเวอร์ล้มเหลว", "error");
    });
  };

  // Sync profile details when currentUser changes
  useEffect(() => {
    if (currentUser) {
      setProfileName(currentUser.name);
      setProfileEmail(currentUser.email);
    }
  }, [currentUser]);

  // Carousel slide active index
  const [currentSlide, setCurrentSlide] = useState(0);

  // Transactions State
  const [transactions, setTransactions] = useState([]);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [latestTxn, setLatestTxn] = useState(null);
  const [toasts, setToasts] = useState([]);

  // Sync theme state directly to the document body class
  useEffect(() => {
    document.body.className = `${theme}-theme`;
  }, [theme]);

  // Auto transition for carousel
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentSlide(prev => (prev + 1) % CAROUSEL_SLIDES.length);
    }, 6000);
    return () => clearInterval(timer);
  }, []);

  // Logout handler
  const handleLogout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('authUser');
    localStorage.removeItem('isAdmin');
    setUserToken(null);
    setCurrentUser(null);
    setIsAdmin(false);
    setInstalledAppIds(new Set([]));
    setInstallingStates({});
    setTransactions([]);
    showToast("ออกจากระบบสำเร็จ", "info");
    setActiveTab("store");
  };

  // Profile data fetch helper
  const fetchUserData = (token) => {
    // Fetch profile
    fetch('/api/auth/me', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(res => {
      if (!res.ok) throw new Error("Unauthorized");
      return res.json();
    })
    .then(data => {
      if (data.ok) {
        setCurrentUser(data.user);
        localStorage.setItem('authUser', JSON.stringify(data.user));
        
        // Fetch admin permissions
        fetch('/api/admin/my-permissions', {
          headers: { 'Authorization': `Bearer ${token}` }
        })
        .then(res => res.json())
        .then(permData => {
          if (permData.permissions && permData.permissions.length > 0) {
            setIsAdmin(true);
            localStorage.setItem('isAdmin', 'true');
          } else {
            setIsAdmin(false);
            localStorage.removeItem('isAdmin');
          }
        })
        .catch(err => {
          console.error('Failed to fetch admin permissions:', err);
          setIsAdmin(false);
          localStorage.removeItem('isAdmin');
        });
      }
    })
    .catch(err => {
      console.error(err);
      handleLogout();
    });

    // Fetch purchased apps
    fetch('/api/user/apps', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(res => res.json())
    .then(data => {
      if (Array.isArray(data)) {
        setInstalledAppIds(new Set(data));
        const states = {};
        data.forEach(id => { states[id] = 'installed'; });
        setInstallingStates(states);
      }
    })
    .catch(err => console.error(err));

    // Fetch billing transactions
    fetch('/api/user/transactions', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(res => res.json())
    .then(data => {
      if (Array.isArray(data)) {
        const mapped = data.map(tx => ({
          id: tx.id,
          appId: tx.app_id,
          appName: apps.find(a => a.id === tx.app_id)?.name || tx.app_id,
          date: new Date(tx.created_at).toLocaleString('th-TH', { hour12: false }),
          amount: parseFloat(tx.amount),
          status: tx.status === 'completed' ? 'สำเร็จ' : tx.status === 'pending' ? 'รอดำเนินการ' : 'ล้มเหลว',
          method: tx.payment_method === 'stripe_mock' ? 'Stripe Simulator' : tx.payment_method || 'บัตรเครดิต'
        }));
        setTransactions(mapped);
      }
    })
    .catch(err => console.error(err));
  };

  // Fetch apps and check token redirect on mount
  useEffect(() => {
    fetch('/api/apps')
      .then((res) => {
        if (!res.ok) throw new Error("Backend server not started yet");
        return res.json();
      })
      .then((data) => {
        if (data && data.length > 0) {
          setApps(data);
        }
      })
      .catch((err) => {
        console.warn("Using fallback mock data because:", err.message);
      });

    // Check query params for tokens or redirects
    const params = new URLSearchParams(window.location.search);
    const path = window.location.pathname;
    const tokenParam = params.get('token');

    if (tokenParam) {
      localStorage.setItem('authToken', tokenParam);
      setUserToken(tokenParam);
      window.history.replaceState({}, document.title, '/');
      fetchUserData(tokenParam);
      showToast("เข้าสู่ระบบเรียบร้อยแล้ว!", "success");
    } else if (userToken) {
      fetchUserData(userToken);
    }

    if (path === '/success' || (params.has('session_id') && !params.has('app_id'))) {
      const sessId = params.get('session_id');
      window.history.replaceState({}, document.title, '/');
      showToast("ธุรกรรมชำระเงินของคุณเสร็จสมบูรณ์!", "success");
      if (userToken) fetchUserData(userToken);
    }

    if (path === '/cancel') {
      window.history.replaceState({}, document.title, '/');
      showToast("ยกเลิกการชำระเงินแล้ว", "info");
    }

    if (params.has('session_id') && params.has('app_id')) {
      const sessId = params.get('session_id');
      const appId = params.get('app_id');
      setMockPaymentSession({ sessionId: sessId, appId });
      setCheckoutApp(DEFAULT_APPS.find(a => a.id === appId));
      setActiveTab("checkout-mock");
    }
  }, [userToken]);

  // Helper to trigger Toast Alert
  const showToast = (message, type = "info") => {
    const newToast = { id: Date.now(), message, type };
    setToasts(prev => [...prev, newToast]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== newToast.id));
    }, 4000);
  };

  // Filter apps by search query
  const filteredApps = apps.filter((app) => {
    const query = searchQuery.toLowerCase();
    return (
      app.name.toLowerCase().includes(query) ||
      app.description.toLowerCase().includes(query)
    );
  });

  // Local login / register form submit handler
  const handleAuthSubmit = (e) => {
    e.preventDefault();
    const endpoint = authTab === 'login' ? '/api/auth/login' : '/api/auth/register';
    const body = authTab === 'login' ? { email, password } : { name, email, password };

    fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    .then(res => res.json())
    .then(data => {
      if (data.error) {
        showToast(data.error, "error");
      } else if (data.token) {
        localStorage.setItem('authToken', data.token);
        setUserToken(data.token);
        setCurrentUser(data.user);
        localStorage.setItem('authUser', JSON.stringify(data.user));
        setShowAuthModal(false);
        showToast(authTab === 'login' ? "เข้าสู่ระบบสำเร็จ!" : "ลงทะเบียนสำเร็จและเข้าสู่ระบบแล้ว!", "success");
        fetchUserData(data.token);
      }
    })
    .catch(err => {
      console.error(err);
      showToast("การเชื่อมต่อฐานข้อมูลล้มเหลว", "error");
    });
  };

  const handleInstallClick = (e, app) => {
    if (e) e.stopPropagation();
    
    // Check authentication
    if (!userToken) {
      setShowAuthModal(true);
      showToast("กรุณาเข้าสู่ระบบก่อนทำการสั่งซื้อหรือติดตั้งบอท", "warn");
      return;
    }

    // Check if it's already installed
    if (installedAppIds.has(app.id)) {
      setSelectedApp(app);
      setActiveTab("store");
      return;
    }

    // Check if app has a price (Stripe integration)
    if (app.price > 0) {
      showToast(`กำลังติดต่อเซิร์ฟเวอร์เพื่อสร้างหน้าชำระเงินสำหรับ ${app.name}...`, "info");
      fetch('/api/create-checkout-session', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${userToken}`
        },
        body: JSON.stringify({ appId: app.id })
      })
      .then(res => res.json())
      .then(data => {
        if (data.url) {
          window.location.href = data.url;
        } else {
          showToast("ไม่สามารถเรียกหน้าชำระเงินได้ในขณะนี้", "error");
        }
      })
      .catch(err => {
        console.error(err);
        showToast("เซิร์ฟเวอร์ตัดการทำงาน", "error");
      });
      return;
    }

    startInstallation(app.id);
  };

  const startInstallation = (appId) => {
    showToast(`กำลังเริ่มต้นดาวน์โหลดแอป: ${apps.find(a => a.id === appId)?.name || appId}`, "info");
    setInstallingStates(prev => ({ ...prev, [appId]: "downloading" }));

    setTimeout(() => {
      setInstallingStates(prev => ({ ...prev, [appId]: "installing" }));

      setTimeout(() => {
        setInstallingStates(prev => ({ ...prev, [appId]: "installed" }));
        setInstalledAppIds(prev => {
          const newSet = new Set(prev);
          newSet.add(appId);
          return newSet;
        });
        
        // Add to purchase history inside DB via mock payment-complete
        fetch('/api/create-checkout-session', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${userToken}`
          },
          body: JSON.stringify({ appId })
        })
        .then(res => res.json())
        .then(data => {
          if (data.url) {
            // Extracts mock tx ID
            const urlObj = new URL(data.url, window.location.origin);
            const sessId = urlObj.searchParams.get('session_id');
            // Complete it
            fetch('/api/payment-complete', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${userToken}`
              },
              body: JSON.stringify({ sessionId: sessId })
            })
            .then(() => fetchUserData(userToken));
          }
        });

        showToast(`ติดตั้งแอป ${apps.find(a => a.id === appId)?.name} สำเร็จและพร้อมใช้งาน!`, "success");
      }, 1500);
    }, 1500);
  };

  const handleStripeSubmit = (e) => {
    e.preventDefault();
    if (!mockPaymentSession) return;
    setPaymentProcessing(true);
    showToast("กำลังประมวลผลการชำระเงินจำลอง...", "info");

    fetch('/api/payment-complete', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userToken}`
      },
      body: JSON.stringify({ sessionId: mockPaymentSession.sessionId })
    })
    .then(res => res.json())
    .then(data => {
      setPaymentProcessing(false);
      if (data.success) {
        const completedTxn = {
          id: mockPaymentSession.sessionId,
          appName: checkoutApp.name,
          amount: checkoutApp.price,
          method: "Stripe Simulator (•••• 4242)"
        };
        setLatestTxn(completedTxn);
        fetchUserData(userToken);
        showToast("หักเงินสำเร็จ! บันทึกธุรกรรมลง Postgres เรียบร้อย", "success");
        setActiveTab("payment-success");
        setMockPaymentSession(null);
      } else {
        showToast("การชำระเงินไม่ผ่าน", "error");
      }
    })
    .catch(err => {
      setPaymentProcessing(false);
      console.error(err);
      showToast("เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล", "error");
    });
  };

  // Generate PromptPay QR Code
  const generatePromptPayQR = async () => {
    try {
      const response = await fetch('/api/promptpay/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount: checkoutApp.price,
          appId: checkoutApp.id,
          email: profileEmail,
          userId: currentUser?.id
        })
      });
      
      if (!response.ok) throw new Error('Failed to generate QR');
      
      const data = await response.json();
      setPromptPayQR(data.qrCode);
      setPromptPayTxData(data);
      showToast("สร้าง QR Code สำเร็จ กรุณาสแกนเพื่อชำระเงิน", "success");
    } catch (error) {
      console.error('PromptPay QR error:', error);
      showToast("ไม่สามารถสร้าง QR Code ได้", "error");
    }
  };

  // Run real shell script on the backend
  const runScriptSimulator = (app) => {
    setTerminalLogs([]);
    setIsTerminalRunning(true);
    setScriptFinished(false);
    showToast(`กำลังเริ่มต้นส่งคำสั่งรันสคริปต์จริงสำหรับ: ${app.name}...`, "info");

    setTerminalLogs(prev => [...prev, { type: "info", text: "[SYSTEM] กำลังส่งคำขอเพื่อรันสคริปต์ผ่านเซิร์ฟเวอร์หลัก..." }]);

    fetch('/api/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ appId: app.id })
    })
      .then(res => {
        if (!res.ok) throw new Error("ไม่สามารถเริ่มต้นรันสคริปต์บนเซิร์ฟเวอร์ได้ (404/500)");
        return res.json();
      })
      .then(data => {
        setIsTerminalRunning(false);
        setScriptFinished(true);

        const newLogs = [];
        if (data.stdout) {
          data.stdout.split('\n').filter(Boolean).forEach(line => {
            if (line.includes("[SUCCESS]")) {
              newLogs.push({ type: "success", text: line });
            } else if (line.includes("[WARN]")) {
              newLogs.push({ type: "warn", text: line });
            } else {
              newLogs.push({ type: "info", text: line });
            }
          });
        }
        if (data.stderr) {
          data.stderr.split('\n').filter(Boolean).forEach(line => {
            newLogs.push({ type: "error", text: `[STDERR] ${line}` });
          });
        }

        setTerminalLogs(prev => [
          ...prev, 
          ...newLogs, 
          { type: "success", text: `[SYSTEM] บอททำงานเสร็จสมบูรณ์ด้วยรหัสการทำงาน: ${data.exitCode}` }
        ]);
        showToast(`เซิร์ฟเวอร์ประมวลผลดึงรายงานสำหรับ ${app.name} สำเร็จ!`, "success");
      })
      .catch(err => {
        setIsTerminalRunning(false);
        setTerminalLogs(prev => [...prev, { type: "error", text: `[ERROR] ${err.message}` }]);
        showToast(`เกิดข้อผิดพลาด: ${err.message}`, "warn");
      });
  };

  // Custom Inline Vector App Logos
  const getAppLogo = (appId, size = 42) => {
    const style = { width: size, height: size };
    if (appId === "lineman") {
      return (
        <svg style={style} viewBox="0 0 24 24" fill="none">
          <rect width="24" height="24" rx="5" fill="#00C274" />
          <path d="M6 18V6H8.5L12 11.5L15.5 6H18V18H15.5V10L12 15L8.5 10V18H6Z" fill="white" />
        </svg>
      );
    }
    if (appId === "shopee") {
      return (
        <svg style={style} viewBox="0 0 24 24" fill="none">
          <rect width="24" height="24" rx="5" fill="#EE4D2D" />
          <path d="M16 10V8C16 5.8 14.2 4 12 4C9.8 4 8 5.8 8 8V10H6C5.4 10 5 10.4 5 11L6.2 18.2C6.4 19.3 7.3 20 8.4 20H15.6C16.7 20 17.6 19.3 17.8 18.2L19 11C19 10.4 18.6 10 18 10H16ZM10 8C10 6.9 10.9 6 12 6C13.1 6 14 6.9 14 8V10H10V8ZM10.5 13.5C10.5 12.7 11.2 12 12 12C12.8 12 13.5 12.7 13.5 13.5C13.5 14.3 12.8 15 12 15C11.2 15 10.5 14.3 10.5 13.5Z" fill="white" />
        </svg>
      );
    }
    if (appId === "grab") {
      return (
        <svg style={style} viewBox="0 0 24 24" fill="none">
          <rect width="24" height="24" rx="5" fill="#00B159" />
          <path d="M12 5C8.13 5 5 8.13 5 12C5 15.87 8.13 19 12 19C15.87 19 19 15.87 19 12C19 8.13 15.87 5 12 5ZM12 17C9.24 17 7 14.76 7 12C7 9.24 9.24 7 12 7C14.76 7 17 9.24 17 12C17 14.76 14.76 17 12 17ZM13 11V15H11V11H8V9H16V11H13Z" fill="white" />
        </svg>
      );
    }
    if (appId === "trueid") {
      return (
        <svg style={style} viewBox="0 0 24 24" fill="none">
          <rect width="24" height="24" rx="5" fill="#EC1C24" />
          <path d="M6 8H10V10H8V16H6V8ZM14.5 12V16H12.5V12C12.5 10.9 13.4 10 14.5 10H16.5V12H14.5ZM19 11.5C19 10.7 19.7 10 20.5 10H22V16H20.5C19.7 16 19 15.3 19 14.5V11.5Z" fill="white" />
        </svg>
      );
    }
    // Default logo
    return (
      <svg style={style} viewBox="0 0 24 24" fill="none">
        <rect width="24" height="24" rx="5" fill="#3B82F6" />
        <path d="M12 6L6 14H18L12 6Z" fill="white" />
      </svg>
    );
  };

  const handleDownloadExcel = (app) => {
    const csvContent = "data:text/csv;charset=utf-8,ลำดับ,ราคาสินค้าเฉลี่ย,ยอดนิยม,สิทธิ์โปรโมชัน\n1,ไลน์แมนวิเคราะห์ตลาด,150,ดีมาก,โค้ดส่งฟรี\n2,แนวโน้มแคมเปญ,350,ปานกลาง,ไม่มีโค้ด\n3,เปรียบเทียบตลาดอื่น,280,ดีเยี่ยม,โค้ดส่วนลด";
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `trending_${app.id}_analysis.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast("ดาวน์โหลดไฟล์รายงาน CSV สำเร็จ!", "success");
  };

  const navigateToTab = (tab) => {
    setActiveTab(tab);
    setSelectedApp(null);
    setShowDropdown(false);
  };

  const getAvatarUrl = () => {
    if (currentUser?.avatar_url && currentUser.avatar_url.trim() !== "" && currentUser.avatar_url !== "https://profile.line-scdn.net/default-avatar") {
      return currentUser.avatar_url;
    }
    return `https://ui-avatars.com/api/?name=${encodeURIComponent(currentUser?.name || "User")}&background=3b82f6&color=fff&bold=true`;
  };

  return (
    <div className={`app-container ${theme}-theme`}>
      {/* Background ambient lighting */}
      <div className="ambient-glow-1"></div>
      <div className="ambient-glow-2"></div>
      <div className="ambient-glow-3"></div>
      <div className="ambient-glow-4"></div>

      {/* Toast notifications rendering */}
      <div className="toast-wrapper">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast-notification toast-${toast.type}`}>
            <span className="toast-icon">
              {toast.type === "success" ? "✓" : toast.type === "warn" ? "⚠" : "ℹ"}
            </span>
            <div className="toast-message">{toast.message}</div>
          </div>
        ))}
      </div>

      {/* Header Bar */}
      <header className="glass-header">
        <div className="brand-section" style={{ cursor: 'pointer' }} onClick={() => navigateToTab("store")}>
          <div className="brand-logo">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <rect width="24" height="24" rx="5" fill="#3B82F6" />
              <path d="M12 6L6 14H18L12 6Z" fill="white" />
            </svg>
          </div>
          <span className="brand-name">แอปสโตร์</span>
        </div>

        <div className="search-section">
          <div className="search-input-wrapper">
            <SearchIcon className="search-icon" />
            <input
              type="text"
              className="search-input"
              placeholder="ค้นหาแอป แอนิเมชัน เกม..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        <div className="user-section">
          {/* Theme switcher button */}
          <div 
            className="notification-bell theme-toggle-btn" 
            style={{ marginRight: '4px' }}
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            title={theme === 'dark' ? "สลับเป็น Light Theme" : "สลับเป็น Dark Theme"}
          >
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </div>

          <div className="notification-bell" onClick={() => showToast("เข้าสู่โหมด Sandbox ของ Stripe และ Play Store แล้ว", "success")}>
            <BellIcon />
            <span className="bell-badge"></span>
          </div>

          {userToken ? (
            <div className="user-avatar-wrapper" onClick={() => setShowDropdown(!showDropdown)}>
              <img
                src={getAvatarUrl()}
                alt="User profile"
                className="user-avatar"
                onError={(e) => {
                  e.target.onerror = null;
                  e.target.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(currentUser?.name || "User")}&background=3b82f6&color=fff&bold=true`;
                }}
              />
              <ChevronDownIcon />
              
              {/* User Dropdown Menu */}
              {showDropdown && (
                <div className="user-dropdown-menu" onClick={(e) => e.stopPropagation()}>
                  <div className="dropdown-user-info" style={{ padding: '10px 16px', borderBottom: '1px solid rgba(255,255,255,0.08)', marginBottom: '4px' }}>
                    <div style={{ fontWeight: '500', fontSize: '13px', color: 'var(--text-primary)' }}>{currentUser?.name || 'OpenHands User'}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{currentUser?.email}</div>
                  </div>
                  <button className={`dropdown-item ${activeTab === 'store' ? 'active' : ''}`} onClick={() => navigateToTab("store")}>
                    ร้านค้าแอป
                  </button>
                  <button className={`dropdown-item ${activeTab === 'my-apps' ? 'active' : ''}`} onClick={() => navigateToTab("my-apps")}>
                    แอปของฉัน ({installedAppIds.size})
                  </button>
                  <button className={`dropdown-item ${activeTab === 'transactions' ? 'active' : ''}`} onClick={() => navigateToTab("transactions")}>
                    ประวัติการชำระเงิน
                  </button>
                  <button className={`dropdown-item ${activeTab === 'profile' ? 'active' : ''}`} onClick={() => navigateToTab("profile")}>
                    โปรไฟล์ผู้ใช้
                  </button>
                  <button className={`dropdown-item ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => navigateToTab("settings")}>
                    ตั้งค่าเซิร์ฟเวอร์
                  </button>
                  <hr style={{ border: 'none', borderTop: '1px solid rgba(255,255,255,0.08)', margin: '4px 0' }} />
                  <button className="dropdown-item" style={{ color: '#ef4444' }} onClick={handleLogout}>
                    ออกจากระบบ
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button 
              className="action-btn-primary" 
              style={{ padding: '8px 18px', fontSize: '13px', borderRadius: '20px' }} 
              onClick={() => { setAuthTab('login'); setShowAuthModal(true); }}
            >
              เข้าสู่ระบบ
            </button>
          )}
        </div>
      </header>

      {/* Tabs Navigation (Elegant top-bar menu below header) */}
      <nav className="tabs-navigation">
        <button className={`tab-btn ${activeTab === 'store' ? 'active' : ''}`} onClick={() => navigateToTab("store")}>
          ร้านค้าแอป
        </button>
        <button className={`tab-btn ${activeTab === 'my-apps' ? 'active' : ''}`} onClick={() => navigateToTab("my-apps")}>
          แอปของฉัน ({installedAppIds.size})
        </button>
        <button className={`tab-btn ${activeTab === 'transactions' ? 'active' : ''}`} onClick={() => navigateToTab("transactions")}>
          ประวัติธุรกรรม
        </button>
        <button className={`tab-btn ${activeTab === 'profile' ? 'active' : ''}`} onClick={() => navigateToTab("profile")}>
          โปรไฟล์ผู้ใช้
        </button>
        <button className={`tab-btn ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => navigateToTab("settings")}>
          ตั้งค่าเซิร์ฟเวอร์
        </button>
      </nav>

      {/* Bottom Navigation - Mobile Only */}
      <nav className="bottom-nav">
        <button
          className={`bottom-nav-item ${activeTab === 'store' ? 'active' : ''}`}
          onClick={() => navigateToTab("store")}
        >
          <NavStoreIcon />
          <span>ร้านค้า</span>
        </button>
        <button
          className={`bottom-nav-item ${activeTab === 'my-apps' ? 'active' : ''}`}
          onClick={() => navigateToTab("my-apps")}
        >
          <NavAppsIcon />
          <span>แอปของฉัน</span>
        </button>
        <button
          className="bottom-nav-item"
          onClick={() => setShowMobileSearch(true)}
        >
          <SearchIcon className="bottom-nav-icon" />
          <span>ค้นหา</span>
        </button>
        <button
          className={`bottom-nav-item ${activeTab === 'profile' ? 'active' : ''}`}
          onClick={() => navigateToTab("profile")}
        >
          <NavProfileIcon />
          <span>โปรไฟล์</span>
        </button>
        <button
          className={`bottom-nav-item ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => navigateToTab("settings")}
        >
          <NavSettingsIcon />
          <span>ตั้งค่า</span>
        </button>
      </nav>

      {/* DEDICATED CHECKOUT PAGE (STRIPE SIMULATOR) */}
      {activeTab === "checkout-mock" && checkoutApp && (
        <div className="stripe-checkout-page anim-slide-up">
          <button className="back-btn" onClick={() => navigateToTab("store")}>
            <BackIcon />
            <span>ย้อนกลับไปร้านค้า</span>
          </button>

          <div className="checkout-layout">
            {/* Left Box: Product Details */}
            <div className="checkout-product-details">
              <span className="checkout-sandbox-badge">SANDBOX TEST MODE</span>
              <h2 className="checkout-title">ชำระเงินผ่าน Stripe</h2>
              
              <div className="checkout-app-box">
                <div className="checkout-app-icon" style={{ backgroundColor: checkoutApp.iconColor }}>
                  {getAppLogo(checkoutApp.id, 40)}
                </div>
                <div>
                  <h3 className="checkout-app-name">{checkoutApp.name}</h3>
                  <p className="checkout-app-dev">{checkoutApp.developer}</p>
                </div>
              </div>

              <div className="checkout-invoice-summary">
                <div className="invoice-row">
                  <span>ราคาแอป</span>
                  <span>฿{checkoutApp.price}.00</span>
                </div>
                <div className="invoice-row">
                  <span>ภาษีมูลค่าเพิ่ม (VAT 7%)</span>
                  <span>฿0.00</span>
                </div>
                <hr className="checkout-divider" />
                <div className="invoice-row total">
                  <span>ยอดชำระสุทธิ</span>
                  <span>฿{checkoutApp.price}.00</span>
                </div>
              </div>

              <div className="checkout-security-note">
                <ShieldCheckIcon />
                <span>การเชื่อมต่อปลอดภัยระดับ SSL เข้ารหัสผ่าน Sandbox</span>
              </div>
            </div>

            {/* Right Box: Credit Card Form */}
            <div className="checkout-card-form">
              <form onSubmit={handleStripeSubmit}>
                <h3 className="form-title">เลือกวิธีการชำระเงิน</h3>
                
                <div className="payment-method-selector">
                  <button
                    type="button"
                    className={`payment-method-btn ${paymentMethod === 'card' ? 'active' : ''}`}
                    onClick={() => setPaymentMethod('card')}
                  >
                    💳 บัตรเครดิต/เดบิต
                  </button>
                  <button
                    type="button"
                    className={`payment-method-btn ${paymentMethod === 'promptpay' ? 'active' : ''}`}
                    onClick={() => setPaymentMethod('promptpay')}
                  >
                    🏦 PromptPay
                  </button>
                </div>

                {paymentMethod === 'card' ? (
                  <>
                    <div className="form-group">
                      <label>อีเมลผู้รับใบเสร็จ</label>
                      <input type="email" defaultValue={profileEmail} required />
                    </div>

                    <div className="form-group">
                      <label>ชื่อบนบัตรเครดิต</label>
                      <input 
                        type="text" 
                        value={cardHolder} 
                        onChange={(e) => setCardHolder(e.target.value)} 
                        placeholder="NAME ON CARD" 
                        required 
                      />
                    </div>

                    <div className="form-group">
                      <label>หมายเลขบัตรเครดิต (ใช้หมายเลขทดสอบของ Stripe)</label>
                      <input 
                        type="text" 
                        value={cardNumber} 
                        onChange={(e) => setCardNumber(e.target.value)} 
                        placeholder="4242 4242 4242 4242" 
                        required 
                      />
                    </div>

                    <div className="form-row">
                      <div className="form-group">
                        <label>วันหมดอายุ (MM/YY)</label>
                        <input 
                          type="text" 
                          value={cardExpiry} 
                          onChange={(e) => setCardExpiry(e.target.value)} 
                          placeholder="12/28" 
                          required 
                        />
                      </div>
                      <div className="form-group">
                        <label>CVC (รหัสหลังบัตร)</label>
                        <input 
                          type="text" 
                          value={cardCvc} 
                          onChange={(e) => setCardCvc(e.target.value)} 
                          placeholder="424" 
                          required 
                        />
                      </div>
                    </div>

                    <button 
                      type="submit" 
                      className="action-btn-primary checkout-pay-btn" 
                      disabled={paymentProcessing}
                    >
                      {paymentProcessing ? "กำลังส่งธุรกรรมผ่าน Sandbox..." : `จ่ายเงินชำระ ฿${checkoutApp.price}.00`}
                    </button>
                  </>
                ) : (
                  <>
                    <div className="form-group">
                      <label>อีเมลผู้รับใบเสร็จ</label>
                      <input type="email" defaultValue={profileEmail} required />
                    </div>

                    <div className="promptpay-qr-section">
                      {promptPayQR ? (
                        <>
                          <div className="qr-code-container">
                            <img src={promptPayQR} alt="PromptPay QR" style={{ width: 280, height: 280, borderRadius: 12 }} />
                          </div>
                          <p className="qr-amount" style={{ fontSize: 22, fontWeight: 700, color: '#10b981', margin: '12px 0 6px' }}>
                            ฿{checkoutApp.price}.00
                          </p>
                          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', margin: '10px 0', fontSize: 13 }}>
                            <div style={{ background: 'rgba(255,255,255,0.05)', padding: '6px 12px', borderRadius: 8 }}>
                              <span style={{ color: 'var(--text-secondary)' }}>Ref1: </span>
                              <strong>{promptPayTxData?.reference1}</strong>
                            </div>
                            <div style={{ background: 'rgba(255,255,255,0.05)', padding: '6px 12px', borderRadius: 8 }}>
                              <span style={{ color: 'var(--text-secondary)' }}>Ref2: </span>
                              <strong>{promptPayTxData?.reference2}</strong>
                            </div>
                          </div>
                          <p className="qr-instruction">
                            สแกน QR ผ่านแอปธนาคาร → ระบุเลขอ้างอิง → กดยืนยัน
                          </p>
                          <button
                            type="button"
                            className="tab-btn"
                            onClick={() => { setPromptPayQR(null); setPromptPayTxData(null); }}
                            style={{ marginTop: 6 }}
                          >
                            สร้าง QR ใหม่
                          </button>
                        </>
                      ) : (
                        <>
                          <div className="qr-code-container" style={{ background: 'rgba(255,255,255,0.03)', border: '1px dashed rgba(255,255,255,0.15)', borderRadius: 16, padding: 40, textAlign: 'center' }}>
                            <p style={{ color: 'var(--text-secondary)', margin: 0 }}>กดปุ่มด้านล่างเพื่อสร้าง QR Code</p>
                          </div>
                          <p className="qr-instruction" style={{ marginTop: 12 }}>
                            ระบบจะสร้าง QR Code พร้อมจำนวนเงิน {checkoutApp.price} บาท
                          </p>
                        </>
                      )}
                    </div>

                    <button 
                      type="button"
                      className="action-btn-primary checkout-pay-btn" 
                      disabled={paymentProcessing}
                      onClick={generatePromptPayQR}
                    >
                      {paymentProcessing ? "กำลังสร้าง QR Code..." : (promptPayQR ? "สร้าง QR ใหม่" : `สร้าง QR PromptPay ฿${checkoutApp.price}.00`)}
                    </button>
                  </>
                )}
              </form>
            </div>
          </div>
        </div>
      )}

      {/* PAYMENT SUCCESS PAGE */}
      {activeTab === "payment-success" && latestTxn && (
        <div className="payment-success-page anim-slide-up">
          <div className="success-icon-wrapper">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="3">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </div>
          <h2 className="success-title">ชำระเงินเสร็จสมบูรณ์!</h2>
          <p className="success-subtitle">แอปสิทธิ์พรีเมียมของคุณได้รับการเปิดใช้งานและเริ่มดำเนินการติดตั้งแล้ว</p>

          <div className="success-receipt-card">
            <div className="receipt-row">
              <span>หมายเลขสั่งซื้อ (Transaction ID)</span>
              <strong>{latestTxn.id}</strong>
            </div>
            <div className="receipt-row">
              <span>ชื่อสินค้า</span>
              <strong>{latestTxn.appName}</strong>
            </div>
            <div className="receipt-row">
              <span>ยอดหักบัญชี</span>
              <strong style={{ color: 'var(--success-color)' }}>฿{latestTxn.amount}.00</strong>
            </div>
            <div className="receipt-row">
              <span>สถานะการชำระเงิน</span>
              <strong className="badge-success">สำเร็จ</strong>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
            <button className="tab-btn active" onClick={() => { setActiveTab("my-apps"); setLatestTxn(null); }}>
              ไปรันบอทที่แอปของฉัน
            </button>
            <button className="tab-btn" onClick={() => navigateToTab("store")}>
              ย้อนกลับหน้าแรก
            </button>
          </div>
        </div>
      )}

      {/* DEDICATED PROFILE PAGE */}
      {activeTab === "profile" && (
        <div className="profile-page anim-slide-up">
          <div className="main-title-section" style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
            <button className="back-btn" style={{ margin: 0 }} onClick={() => navigateToTab("store")}>
              <BackIcon />
              <span>ย้อนกลับ</span>
            </button>
            <h2 className="main-title" style={{ margin: 0 }}>ข้อมูลโปรไฟล์ผู้ใช้งานและคีย์สิทธิ์</h2>
          </div>

          {!userToken ? (
            <div className="empty-state-card" style={{ marginTop: '20px', padding: '40px 20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
              <div style={{ fontSize: '48px' }}>🔐</div>
              <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>กรุณาเข้าสู่ระบบ</h3>
              <p style={{ margin: 0, color: 'var(--text-secondary)', textAlign: 'center', maxWidth: '300px' }}>
                คุณจำเป็นต้องเข้าสู่ระบบเพื่อดูโปรไฟล์และสิทธิ์การใช้งานคีย์บอทของคุณ
              </p>
              <button className="action-btn-primary" style={{ padding: '10px 28px' }} onClick={() => { setAuthTab('login'); setShowAuthModal(true); }}>
                เข้าสู่ระบบทันที
              </button>
            </div>
          ) : (
            <div className="profile-layout">
              {/* Left side: Avatar and Stats */}
              <div className="profile-sidebar">
                <div className="profile-avatar-card">
                  <img
                    src={getAvatarUrl()}
                    alt="User Avatar Large"
                    className="profile-large-avatar"
                    onError={(e) => {
                      e.target.onerror = null;
                      e.target.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(currentUser?.name || "User")}&background=3b82f6&color=fff&bold=true`;
                    }}
                  />
                  <h3>{profileName}</h3>
                  <span className="profile-badge" style={{ textTransform: 'uppercase' }}>{currentUser?.member_tier || 'bronze'} TIER</span>
                  
                  <button 
                    className="tab-btn active" 
                    style={{ marginTop: '24px', width: '100%', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171' }} 
                    onClick={handleLogout}
                  >
                    ออกจากระบบ
                  </button>
                </div>

                <div className="profile-stats-card">
                  <div className="p-stat">
                    <span>แอปที่ติดตั้ง</span>
                    <strong>{installedAppIds.size} แอป</strong>
                  </div>
                  <div className="p-stat">
                    <span>ธุรกรรม Sandbox</span>
                    <strong>{transactions.length} รายการ</strong>
                  </div>
                </div>
              </div>

              {/* Right side: Credentials Form */}
              <div className="profile-form-card">
                <h3>แก้ไขข้อมูลโปรไฟล์และรหัสผ่าน API</h3>
                
                <div className="settings-grid">
                  <div className="settings-form-group">
                    <label>ชื่อผู้แสดงผล</label>
                    <input type="text" value={profileName} onChange={(e) => setProfileName(e.target.value)} />
                  </div>
                  <div className="settings-form-group">
                    <label>อีเมลผู้ใช้งาน</label>
                    <input type="email" value={profileEmail} disabled style={{ opacity: 0.6 }} />
                  </div>
                  <div className="settings-form-group">
                    <label>ตำแหน่ง / บทบาทงาน</label>
                    <input type="text" value={profileRole} onChange={(e) => setProfileRole(e.target.value)} />
                  </div>
                  <div className="settings-form-group">
                    <label>องค์กร / บริษัท</label>
                    <input type="text" value={profileOrg} onChange={(e) => setProfileOrg(e.target.value)} />
                  </div>
                </div>

                <h3 style={{ marginTop: '32px' }}>ข้อมูลรหัสและคีย์การเชื่อมต่ออัตโนมัติ (API Keys)</h3>
                
                <div className="settings-form-group">
                  <label>Github Class Key (Token สำหรับดาวน์โหลดโค้ดบอท)</label>
                  <input type="password" value={githubKey} onChange={(e) => setGithubKey(e.target.value)} />
                </div>

                <div className="settings-grid">
                  <div className="settings-form-group">
                    <label>Telegram Notify Bot Token</label>
                    <input type="password" value={telegramToken} onChange={(e) => setTelegramToken(e.target.value)} />
                  </div>
                  <div className="settings-form-group">
                    <label>Telegram Chat ID</label>
                    <input type="text" value={telegramChatId} onChange={(e) => setTelegramChatId(e.target.value)} />
                  </div>
                </div>

                <div className="settings-form-group" style={{ marginTop: '20px' }}>
                  <label style={{ fontWeight: 600, color: 'var(--text-primary)' }}>OpenCode AI Model (โมเดลในการสร้างสคริปต์และประมวลผล)</label>
                  <select 
                    value={opencodeModel} 
                    onChange={(e) => handleActiveModelChange(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '10px 14px',
                      borderRadius: 'var(--rad)',
                      background: 'var(--bg-secondary)',
                      color: 'var(--text-primary)',
                      border: '1px solid var(--border-primary)',
                      marginTop: '8px',
                      fontSize: '13px',
                      outline: 'none'
                    }}
                  >
                    {opencodeModels.map(m => (
                      <option key={m.id} value={m.id}>{m.name || m.id}</option>
                    ))}
                  </select>
                </div>

                <button 
                  className="tab-btn active" 
                  style={{ marginTop: '24px', padding: '10px 24px' }} 
                  onClick={() => showToast("บันทึกโปรไฟล์ผู้ใช้และคีย์ API สำเร็จ!", "success")}
                >
                  บันทึกการแก้ไขโปรไฟล์
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* DETAIL PAGE VIEW */}
      {selectedApp && activeTab !== "checkout-mock" && activeTab !== "payment-success" && (
        <div className="detail-page anim-slide-up">
          <button className="back-btn" onClick={() => setSelectedApp(null)} disabled={isTerminalRunning}>
            <BackIcon />
            <span>ย้อนกลับไปร้านค้า</span>
          </button>

          <div className="detail-layout">
            {/* Left Column - Core Info */}
            <div className="detail-left-col">
              <div className="detail-header-card">
                <div className="detail-icon-wrapper" style={{ backgroundColor: selectedApp.iconColor }}>
                  {getAppLogo(selectedApp.id, 64)}
                </div>
                <div className="detail-header-info">
                  <h1 className="detail-app-name">{selectedApp.name}</h1>
                  <p className="detail-app-developer">{selectedApp.developer}</p>
                  <div className="detail-stats-row">
                    <div className="detail-stat-item">
                      <span className="detail-stat-val">{selectedApp.rating} ★</span>
                      <span className="detail-stat-lbl">เรตติ้งผู้ใช้</span>
                    </div>
                    <div className="detail-divider"></div>
                    <div className="detail-stat-item">
                      <span className="detail-stat-val">{selectedApp.downloads}</span>
                      <span className="detail-stat-lbl">ดาวน์โหลด</span>
                    </div>
                    <div className="detail-divider"></div>
                    <div className="detail-stat-item">
                      <span className="detail-stat-val">{selectedApp.size}</span>
                      <span className="detail-stat-lbl">ขนาดไฟล์</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Screenshot mockup section */}
              <div className="detail-section">
                <h3 className="section-title">รูปภาพตัวอย่างแอปพลิเคชัน</h3>
                <div className="screenshots-grid">
                  <div className="screenshot-mock" style={{ background: `linear-gradient(45deg, ${selectedApp.iconColor}33, #151722)` }}>
                    <div className="mock-ui-header"></div>
                    <div className="mock-ui-circle" style={{ borderColor: selectedApp.iconColor }}></div>
                    <div className="mock-ui-line"></div>
                    <div className="mock-ui-line short"></div>
                  </div>
                  <div className="screenshot-mock" style={{ background: `linear-gradient(-45deg, ${selectedApp.iconColor}33, #151722)` }}>
                    <div className="mock-ui-header"></div>
                    <div className="mock-ui-grid">
                      <div></div><div></div><div></div><div></div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Detailed Description */}
              <div className="detail-section">
                <h3 className="section-title">เกี่ยวกับแอปนี้</h3>
                <p className="detail-long-desc">{selectedApp.longDescription}</p>
              </div>

              {/* Reviews and feedback */}
              <div className="detail-section">
                <h3 className="section-title">รีวิวและความเห็นจากผู้ใช้</h3>
                <div className="reviews-summary-card">
                  <div className="avg-rating-box">
                    <span className="avg-rating-val">{selectedApp.rating}</span>
                    <div className="stars-row">
                      <StarIcon filled={true}/><StarIcon filled={true}/><StarIcon filled={true}/><StarIcon filled={true}/><StarIcon filled={true}/>
                    </div>
                    <span className="avg-rating-lbl">จากทั้งหมด 25,102 รีวิว</span>
                  </div>
                  <div className="rating-bars-box">
                    <div className="rating-bar-item">
                      <span>5 ★</span>
                      <div className="rating-progress"><div className="rating-fill" style={{ width: '85%' }}></div></div>
                    </div>
                    <div className="rating-bar-item">
                      <span>4 ★</span>
                      <div className="rating-progress"><div className="rating-fill" style={{ width: '10%' }}></div></div>
                    </div>
                    <div className="rating-bar-item">
                      <span>3 ★</span>
                      <div className="rating-progress"><div className="rating-fill" style={{ width: '5%' }}></div></div>
                    </div>
                  </div>
                </div>

                <div className="reviews-list">
                  {selectedApp.reviews.map((rev, index) => (
                    <div key={index} className="review-item-card">
                      <div className="review-item-header">
                        <div className="review-user-avatar">{rev.user[0]}</div>
                        <div>
                          <h5 className="review-user-name">{rev.user}</h5>
                          <span className="review-date">{rev.date}</span>
                        </div>
                        <div className="review-user-rating" style={{ marginLeft: 'auto' }}>
                          {Array.from({ length: 5 }).map((_, i) => (
                            <StarIcon key={i} filled={i < rev.rating} />
                          ))}
                        </div>
                      </div>
                      <p className="review-content">{rev.comment}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right Column - Script Trigger Sidebar */}
            <div className="detail-right-col">
              <div className="action-sidebar-card">
                <h3 className="sidebar-title">แผงควบคุมสคริปต์</h3>
                <p className="sidebar-subtitle">เปิดรันบอทวิเคราะห์ตลาดเพื่อดึงข้อมูลสรุปรายวัน</p>

                <div className="sidebar-action-zone">
                  {installedAppIds.has(selectedApp.id) ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '100%' }}>
                      <button
                        className="action-btn-primary"
                        style={{ width: '100%', justifyContent: 'center', padding: '14px' }}
                        onClick={() => runScriptSimulator(selectedApp)}
                        disabled={isTerminalRunning}
                      >
                        <TerminalIcon />
                        {isTerminalRunning ? "กำลังวิเคราะห์ข้อมูล..." : "เริ่มรันบอทอัตโนมัติ"}
                      </button>

                      {scriptFinished && (
                        <button
                          className="action-btn-primary"
                          style={{ width: '100%', justifyContent: 'center', background: 'var(--success-color)', padding: '14px' }}
                          onClick={() => handleDownloadExcel(selectedApp)}
                        >
                          <CheckCircleIcon />
                          ดาวน์โหลดรายงาน (CSV)
                        </button>
                      )}
                    </div>
                  ) : (
                    <button
                      className="action-btn-primary"
                      style={{ width: '100%', justifyContent: 'center', padding: '14px' }}
                      onClick={(e) => { handleInstallClick(e, selectedApp); }}
                    >
                      {selectedApp.price > 0 ? `ซื้อแอปราคา ฿${selectedApp.price}` : "ติดตั้งสิทธิ์ฟรี"}
                    </button>
                  )}
                </div>

                {/* Simulated Console Logs inside Details Sidebar */}
                {(terminalLogs.length > 0 || isTerminalRunning) && (
                  <div className="sidebar-console-zone">
                    <h4 className="console-title">ประวัติการทำงาน (Live Console Log)</h4>
                    <div className="terminal-window">
                      {terminalLogs.map((log, index) => (
                        <div key={index} className={`terminal-line term-${log.type}`}>
                          {log.text}
                        </div>
                      ))}
                      {isTerminalRunning && (
                        <div className="terminal-line term-info cursor-blink">|</div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ADMIN PANEL */}
      {activeTab === "admin" && isAdmin && (
        <AdminPanel userToken={userToken} currentUser={currentUser} theme={theme} />
      )}

      {/* DASHBOARD VIEWS */}
      {!selectedApp && activeTab !== "checkout-mock" && activeTab !== "payment-success" && activeTab !== "admin" && (
        <div>
          {/* TAB 1: STORE FRONT */}
          {activeTab === "store" && (
            <div>
              {/* Carousel Banner Container */}
              <div className="hero-carousel-container">
                <div className="hero-carousel" style={{ background: CAROUSEL_SLIDES[currentSlide].bg }}>
                  <div className="hero-carousel-text">
                    <span className="hero-badge">{CAROUSEL_SLIDES[currentSlide].badge}</span>
                    <h2 className="hero-title">{CAROUSEL_SLIDES[currentSlide].title}</h2>
                    <p className="hero-desc">{CAROUSEL_SLIDES[currentSlide].description}</p>
                  </div>
                  {CAROUSEL_SLIDES[currentSlide].decor}
                </div>
                
                {/* Custom Carousel Dot Indicators matching the mockup */}
                <div className="carousel-dots">
                  {CAROUSEL_SLIDES.map((_, idx) => (
                    <span
                      key={idx}
                      className={`carousel-dot ${currentSlide === idx ? 'active' : ''}`}
                      onClick={() => setCurrentSlide(idx)}
                    ></span>
                  ))}
                </div>
              </div>

              {/* Main title matching mockup */}
              <div className="main-title-section">
                <h2 className="main-title">แอปแนะนำยอดนิยม</h2>
              </div>

              {/* Apps grid (3 Columns) */}
              <div className="app-grid">
                {filteredApps.map((app) => {
                  const state = installingStates[app.id] || "idle";
                  const isPaid = app.price > 0;
                  return (
                    <div 
                      className="app-card" 
                      key={app.id} 
                      onClick={() => setSelectedApp(app)}
                      style={{ "--glow-color": app.iconColor + "33" }}
                    >
                      {/* Top section: Icon + App Info side-by-side */}
                      <div className="app-card-top">
                        <div className="app-icon-wrapper" style={{ backgroundColor: app.iconColor }}>
                          {getAppLogo(app.id, 56)}
                        </div>
                        <div className="app-info">
                          <h3 className="app-name">{app.name}</h3>
                          <p className="app-desc">{app.description}</p>
                        </div>
                      </div>
                      
                      {/* Bottom section: Price + Install Button side-by-side */}
                      <div className="app-card-bottom">
                        <span className="app-price">
                          {isPaid ? `฿${app.price}` : "ฟรี"}
                        </span>
                        
                        <button
                          className={`install-btn ${state === 'downloading' || state === 'installing' ? 'downloading' : ''} ${state === 'installed' ? 'installed' : ''}`}
                          onClick={(e) => handleInstallClick(e, app)}
                          disabled={state === 'downloading' || state === 'installing'}
                        >
                          {state === 'idle' && "ติดตั้ง"}
                          {state === 'downloading' && "กำลังโหลด..."}
                          {state === 'installing' && "กำลังเขียน..."}
                          {state === 'installed' && "รันบอท"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 2: MY INSTALLED APPS */}
          {activeTab === "my-apps" && (
            <div>
              <div className="main-title-section" style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <button className="back-btn" style={{ margin: 0 }} onClick={() => navigateToTab("store")}>
                  <BackIcon />
                  <span>ย้อนกลับ</span>
                </button>
                <h2 className="main-title" style={{ margin: 0 }}>แอปของฉันที่ติดตั้งแล้ว</h2>
              </div>

              {!userToken ? (
                <div className="empty-state-card" style={{ marginTop: '20px', padding: '40px 20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
                  <div style={{ fontSize: '48px' }}>🔐</div>
                  <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>กรุณาเข้าสู่ระบบ</h3>
                  <p style={{ margin: 0, color: 'var(--text-secondary)', textAlign: 'center', maxWidth: '300px' }}>
                    คุณจำเป็นต้องเข้าสู่ระบบเพื่อดูแอปของคุณ
                  </p>
                  <button className="action-btn-primary" style={{ padding: '10px 28px' }} onClick={() => { setAuthTab('login'); setShowAuthModal(true); }}>
                    เข้าสู่ระบบทันที
                  </button>
                </div>
              ) : apps.filter(a => installedAppIds.has(a.id)).length === 0 ? (
                <div className="empty-state-card" style={{ marginTop: '20px' }}>
                  <p>คุณยังไม่ได้ดาวน์โหลดหรือเปิดใช้งานแอปพลิเคชันใด ๆ</p>
                  <button className="tab-btn active" onClick={() => navigateToTab("store")}>ไปหน้าร้านค้าแอป</button>
                </div>
              ) : (
                <div className="app-grid" style={{ marginTop: '20px' }}>
                  {apps.filter(a => installedAppIds.has(a.id)).map((app) => (
                    <div className="app-card" key={app.id} onClick={() => setSelectedApp(app)} style={{ "--glow-color": app.iconColor + "33" }}>
                      <div className="app-card-top">
                        <div className="app-icon-wrapper" style={{ backgroundColor: app.iconColor }}>
                          {getAppLogo(app.id, 56)}
                        </div>
                        <div className="app-info">
                          <h3 className="app-name">{app.name}</h3>
                          <p className="app-desc">{app.description}</p>
                        </div>
                      </div>
                      <div className="app-card-bottom">
                        <span className="app-price-free">ติดตั้งแล้ว</span>
                        <button className="install-btn installed" onClick={(e) => { e.stopPropagation(); setSelectedApp(app); }}>
                          ตั้งค่ารัน
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: TRANSACTIONS & BILLING HISTORY */}
          {activeTab === "transactions" && (
            <div className="transactions-page anim-slide-up">
              <div className="main-title-section" style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <button className="back-btn" style={{ margin: 0 }} onClick={() => navigateToTab("store")}>
                  <BackIcon />
                  <span>ย้อนกลับ</span>
                </button>
                <h2 className="main-title" style={{ margin: 0 }}>ประวัติการชำระเงินและใบเสร็จ</h2>
              </div>

              {!userToken ? (
                <div className="empty-state-card" style={{ marginTop: '20px', padding: '40px 20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
                  <div style={{ fontSize: '48px' }}>🔐</div>
                  <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>กรุณาเข้าสู่ระบบ</h3>
                  <p style={{ margin: 0, color: 'var(--text-secondary)', textAlign: 'center', maxWidth: '300px' }}>
                    คุณจำเป็นต้องเข้าสู่ระบบเพื่อดูประวัติการทำรายการชำระเงิน
                  </p>
                  <button className="action-btn-primary" style={{ padding: '10px 28px' }} onClick={() => { setAuthTab('login'); setShowAuthModal(true); }}>
                    เข้าสู่ระบบทันที
                  </button>
                </div>
              ) : transactions.length === 0 ? (
                <div className="empty-state-card" style={{ marginTop: '20px' }}>
                  <p>ไม่พบรายการประวัติการสั่งซื้อสำหรับบัญชีของคุณในระบบ</p>
                </div>
              ) : (
                <div className="transactions-table-wrapper">
                  <table className="transactions-table">
                    <thead>
                      <tr>
                        <th>รหัสธุรกรรม</th>
                        <th>ชื่อแอปพลิเคชัน</th>
                        <th>วันที่ทำรายการ</th>
                        <th>ยอดชำระ</th>
                        <th>วิธีชำระเงิน</th>
                        <th>สถานะ</th>
                        <th>การดำเนินการ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {transactions.map(txn => (
                        <tr key={txn.id}>
                          <td className="txn-id" style={{ maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{txn.id}</td>
                          <td className="txn-name">
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <div style={{ width: '24px', height: '24px', borderRadius: '6px', background: apps.find(a => a.id === txn.appId)?.iconColor, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                {getAppLogo(txn.appId, 16)}
                              </div>
                              {txn.appName}
                            </div>
                          </td>
                          <td>{txn.date}</td>
                          <td className="txn-amount">{txn.amount === 0 ? "ฟรี" : `฿${txn.amount}`}</td>
                          <td>{txn.method}</td>
                          <td><span className="badge-success">{txn.status}</span></td>
                          <td>
                            <button className="invoice-btn" onClick={() => setSelectedInvoice(txn)}>ดูใบเสร็จ</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* TAB 5: SETTINGS */}
          {activeTab === "settings" && (
            <div className="settings-page anim-slide-up">
              <div className="main-title-section" style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <button className="back-btn" style={{ margin: 0 }} onClick={() => navigateToTab("store")}>
                  <BackIcon />
                  <span>ย้อนกลับ</span>
                </button>
                <h2 className="main-title" style={{ margin: 0 }}>การตั้งค่าเชื่อมต่อเซิร์ฟเวอร์หลัก (SSH)</h2>
              </div>

              <div className="settings-grid" style={{ marginTop: '20px' }}>
                {/* Server Preview Config */}
                <div className="settings-card">
                  <h3>ข้อมูลการเชื่อมต่อ SSH</h3>
                  <div className="settings-form-group">
                    <label>หมายเลข IP เซิร์ฟเวอร์ (Host IP)</label>
                    <input type="text" value={serverIP} onChange={(e) => setServerIP(e.target.value)} />
                  </div>
                  <div className="settings-form-group">
                    <label>ผู้ใช้งานระบบ (User)</label>
                    <input type="text" value={sshUser} onChange={(e) => setSshUser(e.target.value)} />
                  </div>
                  <div className="settings-form-group">
                    <label>พอร์ตเชื่อมต่อ (Port)</label>
                    <input type="text" value={sshPort} onChange={(e) => setSshPort(e.target.value)} />
                  </div>
                  <button className="tab-btn active" style={{ marginTop: '16px' }} onClick={() => showToast("บันทึกการเชื่อมต่อเซิร์ฟเวอร์เป้าหมายแล้ว!", "success")}>
                    ทดสอบและบันทึกการเชื่อมต่อ
                  </button>
                </div>

                {/* Developer Instructions */}
                <div className="settings-card">
                  <h3>ความปลอดภัยและการควบคุม</h3>
                  <p style={{ fontSize: '13.5px', color: 'var(--text-secondary)', lineHeight: '1.6', fontFamily: 'var(--font-sarabun)' }}>
                    ระบบ Sandbox นี้เชื่อมต่อโดยใช้สิทธิ์จำลองระดับองค์กร การตั้งค่าคีย์ API และโทเค็นของโปรแกรมจะถูกจัดเก็บภายในเครือข่าย Docker และเข้ารหัสก่อนส่งออก เพื่อป้องกันข้อมูลหลุดรั่วไปยังสภาพแวดล้อมสาธารณะ
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Invoice Details Modal */}
      {selectedInvoice && (
        <div className="modal-overlay" onClick={() => setSelectedInvoice(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '460px' }}>
            <button className="close-modal-btn" onClick={() => setSelectedInvoice(null)}><CloseIcon /></button>
            
            <div className="invoice-header" style={{ textAlign: 'center', marginBottom: '24px', borderBottom: '1px dashed rgba(255,255,255,0.1)', paddingBottom: '16px' }}>
              <h3 style={{ margin: '0 0 6px 0', fontSize: '18px', color: 'var(--text-primary)' }}>ใบเสร็จรับเงินจำลอง</h3>
              <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)' }}>STRIPE PAYMENT PORTAL (SANDBOX)</p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '14px', fontFamily: 'var(--font-sarabun)', color: 'var(--text-secondary)', marginBottom: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>รหัสสั่งซื้อ:</span>
                <strong style={{ color: 'white' }}>{selectedInvoice.id}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>ซื้อรายการแอป:</span>
                <strong style={{ color: 'white' }}>{selectedInvoice.appName}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>วันที่ทำธุรกรรม:</span>
                <strong style={{ color: 'white' }}>{selectedInvoice.date}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>ช่องทางชำระเงิน:</span>
                <strong style={{ color: 'white' }}>{selectedInvoice.method}</strong>
              </div>
              <hr style={{ border: 'none', borderTop: '1px dashed rgba(255,255,255,0.1)', margin: '8px 0' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '16px' }}>
                <span style={{ color: 'white', fontWeight: '500' }}>ราคาสุทธิ:</span>
                <strong style={{ color: 'var(--success-color)' }}>{selectedInvoice.amount === 0 ? "ฟรี" : `฿${selectedInvoice.amount}.00`}</strong>
              </div>
            </div>

            <button className="action-btn-primary" style={{ width: '100%', justifyContent: 'center' }} onClick={() => { setSelectedInvoice(null); showToast("พิมพ์ใบเสร็จจำลองสำเร็จ!", "success"); }}>
              สั่งพิมพ์ / บันทึกไฟล์ใบเสร็จ
            </button>
          </div>
        </div>
      )}
      {/* Mobile Search Modal */}
      {showMobileSearch && (
        <div className="mobile-search-overlay" onClick={() => setShowMobileSearch(false)}>
          <div className="mobile-search-modal glass-card anim-slide-up" onClick={(e) => e.stopPropagation()}>
            <div className="mobile-search-header">
              <div className="mobile-search-input-wrapper">
                <SearchIcon className="search-icon" />
                <input
                  type="text"
                  className="mobile-search-input"
                  placeholder="ค้นหาแอปพลิเคชัน..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  autoFocus
                />
              </div>
              <button className="mobile-search-close" onClick={() => setShowMobileSearch(false)}>
                <CloseIcon />
              </button>
            </div>
            <div className="mobile-search-results">
              {searchQuery && (
                <>
                  {apps
                    .filter(app => 
                      app.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                      app.description.toLowerCase().includes(searchQuery.toLowerCase())
                    )
                    .map(app => (
                      <div
                        key={app.id}
                        className="mobile-search-result-item"
                        onClick={() => {
                          setSelectedApp(app);
                          setShowMobileSearch(false);
                          setSearchQuery("");
                        }}
                      >
                        <div className="mobile-search-result-icon" style={{ background: app.iconColor }}>
                          {getAppLogo(app.id, 32)}
                        </div>
                        <div className="mobile-search-result-info">
                          <div className="mobile-search-result-name">{app.name}</div>
                          <div className="mobile-search-result-desc">{app.description}</div>
                        </div>
                      </div>
                    ))
                  }
                  {apps.filter(app => 
                    app.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                    app.description.toLowerCase().includes(searchQuery.toLowerCase())
                  ).length === 0 && (
                    <div className="mobile-search-empty">
                      <div style={{ fontSize: '48px', marginBottom: '12px' }}>🔍</div>
                      <div>ไม่พบแอปพลิเคชันที่ค้นหา</div>
                    </div>
                  )}
                </>
              )}
              {!searchQuery && (
                <div className="mobile-search-suggestions">
                  <div className="mobile-search-suggestion-title">หมวดหมู่ยอดนิยม</div>
                  <div className="mobile-search-suggestion-tags">
                    <span className="mobile-search-tag" onClick={() => setSearchQuery("การเงิน")}>💰 การเงิน</span>
                    <span className="mobile-search-tag" onClick={() => setSearchQuery("อาหาร")}>🍔 อาหาร</span>
                    <span className="mobile-search-tag" onClick={() => setSearchQuery("ขนส่ง")}>🚚 ขนส่ง</span>
                    <span className="mobile-search-tag" onClick={() => setSearchQuery("สุขภาพ")}>🏥 สุขภาพ</span>
                    <span className="mobile-search-tag" onClick={() => setSearchQuery("การศึกษา")}>📚 การศึกษา</span>
                    <span className="mobile-search-tag" onClick={() => setSearchQuery("ความบันเทิง")}>🎬 ความบันเทิง</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Auth Modal Overlay */}
      {showAuthModal && (
        <div className="auth-overlay-backdrop" onClick={() => setShowAuthModal(false)}>
          <div className="auth-modal-card glass-card anim-scale-up" onClick={(e) => e.stopPropagation()}>
            <div className="auth-modal-header">
              <h3>{authTab === 'login' ? '🔐 เข้าสู่ระบบบัญชี erp_stack' : '📝 สมัครสมาชิกใหม่'}</h3>
              <button className="auth-close-btn" onClick={() => setShowAuthModal(false)}>✕</button>
            </div>
            
            <form onSubmit={handleAuthSubmit} className="auth-form">
              {authTab === 'register' && (
                <div className="auth-input-group">
                  <label>ชื่อผู้แสดงผล (Display Name)</label>
                  <input 
                    type="text" 
                    required 
                    placeholder="กรอกชื่อของคุณ" 
                    value={name} 
                    onChange={(e) => setName(e.target.value)} 
                  />
                </div>
              )}
              <div className="auth-input-group">
                <label>อีเมลผู้ใช้งาน (Email Address)</label>
                <input 
                  type="email" 
                  required 
                  placeholder="example@domain.com" 
                  value={email} 
                  onChange={(e) => setEmail(e.target.value)} 
                />
              </div>
              <div className="auth-input-group">
                <label>รหัสผ่าน (Password)</label>
                <input 
                  type="password" 
                  required 
                  placeholder="••••••••" 
                  value={password} 
                  onChange={(e) => setPassword(e.target.value)} 
                />
              </div>
              
              <button type="submit" className="action-btn-primary auth-submit-btn">
                {authTab === 'login' ? 'เข้าสู่ระบบ' : 'สร้างบัญชีผู้ใช้'}
              </button>
            </form>
            
            <div className="auth-toggle-link">
              {authTab === 'login' ? (
                <p>ยังไม่มีบัญชีผู้ใช้? <span onClick={() => setAuthTab('register')}>สมัครสมาชิกที่นี่</span></p>
              ) : (
                <p>มีบัญชีผู้ใช้งานแล้ว? <span onClick={() => setAuthTab('login')}>เข้าสู่ระบบที่นี่</span></p>
              )}
            </div>
            
            <div className="auth-divider">
              <span>หรือล็อกอินผ่านระบบ TUS (OAuth)</span>
            </div>
            
            <div className="auth-social-buttons">
              <a href="/api/auth/google/login" className="social-btn google-btn">
                <svg width="18" height="18" viewBox="0 0 48 48" style={{ marginRight: '8px' }}>
                  <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                  <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                  <path fill="#FBBC05" d="M10.54 28.59A14.5 14.5 0 0 1 9.5 24c0-1.59.28-3.14.76-4.59l-7.98-6.19A23.99 23.99 0 0 0 0 24c0 3.77.87 7.35 2.56 10.56l7.98-5.97z"/>
                  <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 5.97C6.51 42.62 14.62 48 24 48z"/>
                </svg>
                Google
              </a>
              <a href="/api/auth/line/login" className="social-btn line-btn">
                💬 LINE Login
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
