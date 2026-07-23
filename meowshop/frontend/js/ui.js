/**
 * ui.js — 全站共用的 UI 元件
 *
 * 用途：
 *   1. 注入 navbar / footer —— 每一頁的 HTML 只放一個空的 <div id="navbar-root">
 *      和 <div id="footer-root">，實際內容由這裡在 DOMContentLoaded 時填進去。
 *      這樣改版（例如 navbar 加一個連結）只要改一個檔案，7 個頁面同時生效，
 *      不用複製貼上 7 次 HTML 再一個一個改。
 *   2. Toast 提示、金額格式化、庫存徽章、商品卡片這些「好幾頁都會用到」的小工具，
 *      集中在這裡，pages/*.js 只負責「這頁要打哪支 API、資料放哪裡」。
 *
 * 注意：這個檔案假設 api.js 和 auth.js 已經先載入（HTML 裡 <script> 順序：
 *   api.js → auth.js → ui.js → pages/xxx.js）。
 */

/* ---------- 共用小工具 ---------- */

// 金額千分位格式化：850000 → "NT$ 850,000"
function formatCurrency(amount) {
  const n = Number(amount) || 0;
  return 'NT$ ' + n.toLocaleString('zh-TW');
}

// 把使用者輸入 / API 回傳的文字塞進 innerHTML 前先跳脫，避免 XSS
// （教學點：即使資料來自「自己的後端」，只要最終顯示的內容可能包含使用者輸入
//  ——例如註冊時填的 name——就要跳脫，不能假設後端資料一定乾淨）
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

const CATEGORY_LABELS = {
  food: '貓糧',
  snack: '零食',
  toy: '玩具',
  litter: '貓砂',
  supplies: '用品',
};

function categoryLabel(code) {
  return CATEGORY_LABELS[code] || code;
}

/** 庫存徽章：依規格分三態（0 件 / ≤5 件 / 其他） */
function stockBadgeHtml(stock) {
  if (stock <= 0) {
    return `<span class="badge stock-badge--out">補貨中</span>`;
  }
  if (stock <= 5) {
    return `<span class="badge stock-badge--low">僅剩 ${stock} 件</span>`;
  }
  return `<span class="badge stock-badge--in">現貨 ${stock} 件</span>`;
}

/** 訂單狀態徽章 */
const ORDER_STATUS_LABELS = {
  pending: { text: '待付款', cls: 'order-status--pending' },
  paid: { text: '已付款', cls: 'order-status--paid' },
  failed: { text: '付款失敗', cls: 'order-status--failed' },
  cancelled: { text: '已取消', cls: 'order-status--cancelled' },
};

function orderStatusBadgeHtml(status) {
  const info = ORDER_STATUS_LABELS[status] || { text: status, cls: 'order-status--cancelled' };
  return `<span class="badge ${info.cls}">${info.text}</span>`;
}

/** 商品卡片（首頁精選 / 商品清單共用），data 來自 /api/products，不寫死任何欄位 */
function productCardHtml(product) {
  const outOfStock = product.stock <= 0;
  return `
    <a class="product-card" href="product.html?id=${product.id}">
      <div class="product-card-image">
        <img src="${escapeHtml(product.image_url)}" alt="${escapeHtml(product.name)}" loading="lazy">
      </div>
      <div class="product-card-body">
        <div class="product-card-name">${escapeHtml(product.name)}</div>
        <div class="product-card-desc">${escapeHtml(product.description)}</div>
        <div class="product-card-footer">
          <span class="product-price">${formatCurrency(product.price)}</span>
          ${stockBadgeHtml(product.stock)}
        </div>
      </div>
    </a>
  `;
}

/* ---------- Toast ---------- */
function showToast(message, type = 'info') {
  let root = document.getElementById('toast-root');
  if (!root) {
    root = document.createElement('div');
    root.id = 'toast-root';
    document.body.appendChild(root);
  }
  const el = document.createElement('div');
  el.className = `toast toast--${type}`;
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => {
    el.remove();
  }, 3200);
}

/* ---------- 購物車數量 badge（navbar 右上角紅點） ---------- */
async function updateCartBadge() {
  const badge = document.getElementById('cart-count-badge');
  if (!badge) return;
  if (!Auth.isLoggedIn()) {
    badge.style.display = 'none';
    return;
  }
  try {
    // 這是每個頁面載入 navbar 時都會偷偷打的「背景查詢」，不是使用者主動要求要做
    // 需要登入的事——他可能只是在逛完全公開的首頁/商品頁。所以帶 silent401：
    // 就算 token 過期／損毀，api.js 也只會清掉本機 token，不會把使用者導去登入頁
    // （跟「使用者主動按加入購物車 / 點我的訂單」那種 401 要導頁是不一樣的情境，
    // 對照 api.js docstring 第 2 點）。
    const cart = await api.get('/cart', { silent401: true });
    const qty = cart.total_quantity || 0;
    if (qty > 0) {
      badge.textContent = qty > 99 ? '99+' : String(qty);
      badge.style.display = 'flex';
    } else {
      badge.style.display = 'none';
    }
  } catch (err) {
    badge.style.display = 'none';
    if (err.status === 401) {
      // token 已經在 api.js 裡被清掉了，但 navbar 目前還畫著「已登入」的樣子
      // （使用者名稱、登出按鈕），要重繪一次讓畫面跟真實登入狀態同步。
      // 這裡呼叫 renderNavbar() 不會無限遞迴：它結尾一樣會呼叫 updateCartBadge()，
      // 但這時候 token 已經被清掉，Auth.isLoggedIn() 會是 false，
      // 直接在最上面那個 if 就 return 了，不會再走進這個 try/catch。
      renderNavbar();
      return;
    }
    // 其他錯誤（連線問題等）就默默隱藏，不用跳 toast 打擾使用者
  }
}

/* ---------- Icons（全部 inline SVG，UI 零 emoji） ---------- */
const Icons = {
  menu: `<svg viewBox="0 0 24 24" role="img" aria-hidden="true"><path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`,
  cart: `<svg viewBox="0 0 24 24" fill="none" role="img" aria-hidden="true"><path d="M3 4h2.2l2.2 12.2a2.2 2.2 0 0 0 2.2 1.8h7.6a2.2 2.2 0 0 0 2.2-1.8L21 8H6.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="9.5" cy="20.2" r="1.4" fill="currentColor"/><circle cx="17" cy="20.2" r="1.4" fill="currentColor"/></svg>`,
  search: `<svg viewBox="0 0 24 24" fill="none" role="img" aria-hidden="true"><circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="1.8"/><path d="M21 21l-4.3-4.3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`,
  trash: `<svg viewBox="0 0 24 24" fill="none" role="img" aria-hidden="true"><path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m-8 0 1 13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1l1-13" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  warning: `<svg viewBox="0 0 24 24" fill="none" role="img" aria-hidden="true"><path d="M12 3.5 22 20H2L12 3.5Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M12 10v4.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="12" cy="17.4" r="1" fill="currentColor"/></svg>`,
  checkCircle: `<svg viewBox="0 0 24 24" fill="none" role="img" aria-hidden="true"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.6"/><path d="m7.5 12.5 3 3 6-6.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  xCircle: `<svg viewBox="0 0 24 24" fill="none" role="img" aria-hidden="true"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.6"/><path d="m8.5 8.5 7 7m0-7-7 7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`,
  paw: `<svg viewBox="0 0 24 24" fill="currentColor" role="img" aria-hidden="true"><ellipse cx="12" cy="16" rx="5" ry="4.2"/><ellipse cx="5.5" cy="9" rx="2.1" ry="2.6"/><ellipse cx="10.3" cy="6" rx="2.1" ry="2.6"/><ellipse cx="15.7" cy="6" rx="2.1" ry="2.6"/><ellipse cx="20.5" cy="9" rx="2.1" ry="2.6"/></svg>`,
  bowlFood: `<svg viewBox="0 0 24 24" fill="none" role="img" aria-hidden="true"><path d="M3 12h18a8 8 0 0 1-8 8H11a8 8 0 0 1-8-8Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M8 6.5c.5-1.2 1.6-2 2.6-1.6M12 5.4c.2-1.3 1.3-2.3 2.5-2.1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,
  treat: `<svg viewBox="0 0 24 24" fill="none" role="img" aria-hidden="true"><path d="M9 4c1.6 0 2 1.4 3 1.4S13.4 4 15 4s2.5 1.7 2.2 3.2c1.5.5 2.3 1.7 2.3 3.3 0 2.8-3.3 3-3.3 5.5 0 1.8-1.8 3-4.2 3s-4.2-1.2-4.2-3c0-2.5-3.3-2.7-3.3-5.5 0-1.6.8-2.8 2.3-3.3C6.5 5.7 7.4 4 9 4Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`,
  toyBall: `<svg viewBox="0 0 24 24" fill="none" role="img" aria-hidden="true"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6"/><path d="M4.5 9.5c4 2.2 11 2.2 15 0M4.5 14.5c4-2.2 11-2.2 15 0" stroke="currentColor" stroke-width="1.4"/></svg>`,
  scoop: `<svg viewBox="0 0 24 24" fill="none" role="img" aria-hidden="true"><path d="M4 10h13a3 3 0 0 1 3 3v1a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4v-4Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M6 10V6a2 2 0 0 1 2-2h2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`,
  house: `<svg viewBox="0 0 24 24" fill="none" role="img" aria-hidden="true"><path d="m4 11 8-6.5 8 6.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M6 10v8a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-8" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>`,
};

function categoryIcon(code) {
  const map = {
    food: Icons.bowlFood,
    snack: Icons.treat,
    toy: Icons.toyBall,
    litter: Icons.scoop,
    supplies: Icons.house,
  };
  return map[code] || Icons.paw;
}

/* ---------- Navbar ---------- */
function renderNavbar() {
  const root = document.getElementById('navbar-root');
  if (!root) return;

  const loggedIn = Auth.isLoggedIn();
  const user = Auth.getUser();
  const currentPage = location.pathname.split('/').pop() || 'index.html';

  const navLink = (href, label) =>
    `<a href="${href}" class="${currentPage === href ? 'active' : ''}">${label}</a>`;

  root.innerHTML = `
    <header class="navbar">
      <div class="navbar-inner">
        <a class="navbar-brand" href="index.html">
          <img src="images/logo.svg" alt="喵喵商店" class="navbar-logo" width="40" height="40">
          <span class="navbar-wordmark">喵喵商店</span>
        </a>
        <button class="navbar-toggle" id="navbar-toggle" aria-label="開啟選單" aria-expanded="false">
          ${Icons.menu}
        </button>
        <nav class="navbar-links" id="navbar-links">
          ${navLink('index.html', '首頁')}
          ${navLink('products.html', '全部商品')}
          ${navLink('orders.html', '我的訂單')}
        </nav>
        <div class="navbar-actions">
          <a href="cart.html" class="navbar-cart" aria-label="購物車">
            ${Icons.cart}
            <span id="cart-count-badge" class="cart-badge">0</span>
          </a>
          ${loggedIn
            ? `<div class="navbar-user">
                 <span class="navbar-username">${escapeHtml(user && user.name ? user.name : '會員')}</span>
                 <button id="logout-btn" class="btn-text">登出</button>
               </div>`
            : `<a href="login.html" class="btn btn-outline btn-sm">登入</a>`
          }
        </div>
      </div>
    </header>
  `;

  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) logoutBtn.addEventListener('click', () => Auth.logout());

  const toggleBtn = document.getElementById('navbar-toggle');
  const links = document.getElementById('navbar-links');
  if (toggleBtn && links) {
    toggleBtn.addEventListener('click', () => {
      const isOpen = links.classList.toggle('open');
      toggleBtn.setAttribute('aria-expanded', String(isOpen));
    });
  }

  updateCartBadge();
}

/* ---------- Footer ---------- */
function renderFooter() {
  const root = document.getElementById('footer-root');
  if (!root) return;

  root.innerHTML = `
    <footer class="site-footer">
      <div class="footer-inner">
        <div>
          <div class="footer-brand">
            <img src="images/logo.svg" alt="喵喵商店">
            <span>喵喵商店</span>
          </div>
          <p class="footer-tagline">毛孩的好日子，從喵喵商店開始。</p>
        </div>
        <div class="footer-disclaimer">
          ${Icons.warning} 教學範例專案——本站為教學用途，付款為模擬金流，不會真實扣款。
        </div>
        <div class="footer-contact">
          <h4>作者與聯絡方式</h4>
          <ul>
            <li>呂紹民 Darren Lu</li>
            <li><a href="mailto:kevin868686@gmail.com">kevin868686@gmail.com</a></li>
            <li><a href="https://www.linkedin.com/in/shaominglu" target="_blank" rel="noopener">LinkedIn</a></li>
            <li><a href="https://www.facebook.com/darrenlu86" target="_blank" rel="noopener">Facebook</a></li>
          </ul>
        </div>
      </div>
      <div class="footer-bottom">&copy; ${new Date().getFullYear()} 喵喵商店 MeowShop — 教學範例專案</div>
    </footer>
  `;
}

document.addEventListener('DOMContentLoaded', () => {
  renderNavbar();
  renderFooter();
});
