/**
 * home.js — 首頁邏輯
 *
 * 用途：撐起首頁兩塊動態內容——
 *   1. 分類入口卡（5 個固定分類，連去 products.html?category=xxx）
 *   2. 精選商品 grid（打 /api/products，取前 8 筆）
 * 商品資料完全來自 API，這裡不寫死任何商品名稱/價格。
 */

const FEATURED_LIMIT = 8;

// 5 個分類的顯示順序（值域跟後端 products.category 完全一致：food/snack/toy/litter/supplies）
const CATEGORY_ORDER = ['food', 'snack', 'toy', 'litter', 'supplies'];

function renderCategoryGrid() {
  const grid = document.getElementById('category-grid');
  if (!grid) return;
  grid.innerHTML = CATEGORY_ORDER.map((code) => `
    <a class="category-card" href="products.html?category=${code}">
      <span class="category-card-icon">${categoryIcon(code)}</span>
      <div class="category-card-label">${categoryLabel(code)}</div>
    </a>
  `).join('');
}

async function renderFeaturedProducts() {
  const grid = document.getElementById('featured-grid');
  if (!grid) return;
  try {
    const data = await api.get('/products');
    const items = (data.items || []).slice(0, FEATURED_LIMIT);
    if (items.length === 0) {
      grid.innerHTML = `<p class="loading-text">目前還沒有上架商品，晚點再來看看。</p>`;
      return;
    }
    grid.innerHTML = items.map(productCardHtml).join('');
  } catch (err) {
    grid.innerHTML = `<p class="loading-text">商品載入失敗：${escapeHtml(err.message)}</p>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  renderCategoryGrid();
  renderFeaturedProducts();
});
