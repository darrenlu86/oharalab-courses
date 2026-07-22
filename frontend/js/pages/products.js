/**
 * products.js — 商品清單頁
 *
 * 用途：分類 filter + 關鍵字搜尋，呼叫 GET /api/products?category=&search=。
 * 支援從網址帶入初始分類（例如首頁分類卡連過來的 products.html?category=food），
 * 篩選/搜尋時同步更新網址（history.replaceState），這樣使用者複製連結分享，
 * 對方打開會是同樣的篩選結果——小細節但體驗差很多。
 */

const CATEGORY_ORDER = ['food', 'snack', 'toy', 'litter', 'supplies'];

// 目前的篩選狀態，單一變數集中管理，避免到處讀 DOM 猜狀態
const state = {
  category: '',
  search: '',
};

function readStateFromUrl() {
  const params = new URLSearchParams(location.search);
  state.category = params.get('category') || '';
  state.search = params.get('search') || '';
}

function writeStateToUrl() {
  const params = new URLSearchParams();
  if (state.category) params.set('category', state.category);
  if (state.search) params.set('search', state.search);
  const qs = params.toString();
  history.replaceState(null, '', qs ? `products.html?${qs}` : 'products.html');
}

function renderFilterChips() {
  const wrap = document.getElementById('filter-chips');
  const chips = [{ code: '', label: '全部' }, ...CATEGORY_ORDER.map((c) => ({ code: c, label: categoryLabel(c) }))];
  wrap.innerHTML = chips.map((c) => `
    <button type="button" class="filter-chip ${state.category === c.code ? 'active' : ''}" data-category="${c.code}">
      ${c.label}
    </button>
  `).join('');
  wrap.querySelectorAll('.filter-chip').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.category = btn.dataset.category;
      renderFilterChips();
      writeStateToUrl();
      loadProducts();
    });
  });
}

async function loadProducts() {
  const grid = document.getElementById('product-grid');
  grid.innerHTML = `<p class="loading-text">商品載入中...</p>`;
  const params = new URLSearchParams();
  if (state.category) params.set('category', state.category);
  if (state.search) params.set('search', state.search);
  const qs = params.toString();

  try {
    const data = await api.get(`/products${qs ? `?${qs}` : ''}`);
    const items = data.items || [];
    if (items.length === 0) {
      grid.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1;">
          <p>沒有找到符合的商品，換個分類或關鍵字試試看。</p>
        </div>
      `;
      return;
    }
    grid.innerHTML = items.map(productCardHtml).join('');
  } catch (err) {
    grid.innerHTML = `<p class="loading-text">商品載入失敗：${escapeHtml(err.message)}</p>`;
  }
}

// 搜尋框輸入防抖：不用每打一個字就打一次 API
let searchTimer = null;
function bindSearchInput() {
  const input = document.getElementById('search-input');
  input.value = state.search;
  input.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.search = input.value.trim();
      writeStateToUrl();
      loadProducts();
    }, 300);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('search-icon-slot').outerHTML = Icons.search;
  readStateFromUrl();
  renderFilterChips();
  bindSearchInput();
  loadProducts();
});
