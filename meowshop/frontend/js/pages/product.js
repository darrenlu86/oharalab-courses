/**
 * product.js — 商品詳情頁
 *
 * 用途：依網址 ?id=N 打 GET /api/products/{id}，畫出大圖/描述/數量選擇器/加入購物車。
 * 未登入時按「加入購物車」不會直接打 API（後端會回 401），而是先在前端擋下來，
 * 顯示 toast 並導去登入頁——體驗比讓使用者送出後才被拒絕好。
 */

function getProductIdFromUrl() {
  const params = new URLSearchParams(location.search);
  const id = params.get('id');
  return id ? Number(id) : null;
}

let currentProduct = null;
let selectedQty = 1;

function renderProductDetail(product) {
  currentProduct = product;
  selectedQty = product.stock > 0 ? 1 : 0;

  const root = document.getElementById('product-detail-root');
  root.innerHTML = `
    <div class="product-detail">
      <div class="product-detail-image">
        <img src="${escapeHtml(product.image_url)}" alt="${escapeHtml(product.name)}">
      </div>
      <div class="product-detail-info">
        <h1>${escapeHtml(product.name)}</h1>
        <div class="product-detail-price">${formatCurrency(product.price)}</div>
        <div class="product-detail-meta">${stockBadgeHtml(product.stock)}</div>
        <p class="product-detail-desc">${escapeHtml(product.description)}</p>

        <div class="product-actions">
          <div class="qty-selector" id="qty-selector" ${product.stock <= 0 ? 'style="display:none;"' : ''}>
            <button type="button" class="qty-btn" id="qty-minus" aria-label="減少數量">－</button>
            <input type="text" class="qty-input" id="qty-input" value="${selectedQty}" inputmode="numeric" aria-label="數量">
            <button type="button" class="qty-btn" id="qty-plus" aria-label="增加數量">＋</button>
          </div>
          <button type="button" class="btn btn-primary btn-lg" id="add-to-cart-btn" ${product.stock <= 0 ? 'disabled' : ''}>
            ${product.stock <= 0 ? '補貨中' : '加入購物車'}
          </button>
        </div>
      </div>
    </div>
  `;

  if (product.stock > 0) bindQtySelector(product);
  document.getElementById('add-to-cart-btn').addEventListener('click', () => handleAddToCart(product));
}

function clampQty(q, stock) {
  if (Number.isNaN(q) || q < 1) return 1;
  if (q > stock) return stock;
  return q;
}

function bindQtySelector(product) {
  const input = document.getElementById('qty-input');
  const minusBtn = document.getElementById('qty-minus');
  const plusBtn = document.getElementById('qty-plus');

  const syncButtons = () => {
    minusBtn.disabled = selectedQty <= 1;
    plusBtn.disabled = selectedQty >= product.stock;
  };

  minusBtn.addEventListener('click', () => {
    selectedQty = clampQty(selectedQty - 1, product.stock);
    input.value = selectedQty;
    syncButtons();
  });
  plusBtn.addEventListener('click', () => {
    selectedQty = clampQty(selectedQty + 1, product.stock);
    input.value = selectedQty;
    syncButtons();
  });
  input.addEventListener('change', () => {
    selectedQty = clampQty(parseInt(input.value, 10), product.stock);
    input.value = selectedQty;
    syncButtons();
  });
  syncButtons();
}

async function handleAddToCart(product) {
  if (!Auth.isLoggedIn()) {
    showToast('要先登入才能加入購物車喔', 'info');
    // 不要馬上導頁：showToast 存活 3.2 秒，但如果緊接著同步執行 location.href，
    // 瀏覽器幾乎立刻開始換頁，使用者根本來不及看清楚這句提示，會覺得
    // 「莫名其妙被送去登入頁」。延遲 1.2 秒再導頁，讓提示先進到眼裡，
    // 使用者才知道「喔，是因為我還沒登入」。
    setTimeout(() => {
      location.href = 'login.html';
    }, 1200);
    return;
  }
  const btn = document.getElementById('add-to-cart-btn');
  btn.disabled = true;
  try {
    await api.post('/cart/items', { product_id: product.id, quantity: selectedQty });
    showToast('已加入購物車', 'success');
    updateCartBadge();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
  }
}

async function loadProduct() {
  const root = document.getElementById('product-detail-root');
  const id = getProductIdFromUrl();
  if (!id) {
    root.innerHTML = `<p class="loading-text">找不到這個商品</p>`;
    return;
  }
  try {
    const product = await api.get(`/products/${id}`);
    renderProductDetail(product);
  } catch (err) {
    root.innerHTML = `<p class="loading-text">${escapeHtml(err.message)}</p>`;
  }
}

document.addEventListener('DOMContentLoaded', loadProduct);
