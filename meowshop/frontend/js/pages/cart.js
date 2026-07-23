/**
 * cart.js — 購物車頁
 *
 * 用途：GET /api/cart 取得目前購物車，畫出品項列表 + 摘要卡；
 * 改數量用 PATCH /api/cart/items/{product_id}（直接覆蓋新數量），
 * 移除用 DELETE /api/cart/items/{product_id}。
 * 每次操作完都整包重新打 GET /api/cart 重畫，不做本地樂觀更新——
 * 教學簡化：purchase 流程資料一致性比「畫面快 0.1 秒」更重要，
 * 而且順便同步 navbar 的購物車數量 badge。
 */

function cartItemRowHtml(item) {
  const atMax = item.quantity >= item.stock;
  return `
    <div class="cart-item" data-product-id="${item.product_id}">
      <div class="cart-item-image">
        <img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.name)}">
      </div>
      <div class="cart-item-info">
        <div class="cart-item-name">${escapeHtml(item.name)}</div>
        <div class="cart-item-unit-price">單價 ${formatCurrency(item.price)}</div>
      </div>
      <div class="qty-selector cart-item-qty">
        <button type="button" class="qty-btn" data-action="minus" aria-label="減少數量">－</button>
        <input type="text" class="qty-input" value="${item.quantity}" data-action="input" inputmode="numeric" aria-label="數量">
        <button type="button" class="qty-btn" data-action="plus" aria-label="增加數量" ${atMax ? 'disabled' : ''}>＋</button>
      </div>
      <div class="cart-item-subtotal">${formatCurrency(item.subtotal)}</div>
      <button type="button" class="cart-item-remove" data-action="remove" aria-label="移除商品">${Icons.trash}</button>
    </div>
  `;
}

function renderEmptyCart(root) {
  root.innerHTML = `
    <div class="empty-state">
      <img src="images/hero-cat.svg" alt="貓咪插畫">
      <p>購物車還是空的，先去挑點好東西吧。</p>
      <a href="products.html" class="btn btn-primary" style="margin-top:14px;">去逛逛</a>
    </div>
  `;
}

function renderCart(cart) {
  const root = document.getElementById('cart-root');
  if (!cart.items || cart.items.length === 0) {
    renderEmptyCart(root);
    return;
  }

  root.innerHTML = `
    <div class="cart-layout">
      <div class="cart-list" id="cart-list">
        ${cart.items.map(cartItemRowHtml).join('')}
      </div>
      <aside class="summary-card">
        <h3>訂單摘要</h3>
        <div class="summary-row"><span>商品數量</span><span>${cart.total_quantity} 件</span></div>
        <div class="summary-total"><span>總計</span><span>${formatCurrency(cart.total_amount)}</span></div>
        <a href="checkout.html" class="btn btn-primary btn-block">前往結帳</a>
      </aside>
    </div>
  `;

  bindCartListEvents();
}

async function reloadCart() {
  const root = document.getElementById('cart-root');
  try {
    const cart = await api.get('/cart');
    renderCart(cart);
    updateCartBadge();
  } catch (err) {
    root.innerHTML = `<p class="loading-text">購物車載入失敗：${escapeHtml(err.message)}</p>`;
  }
}

async function updateQuantity(productId, quantity) {
  try {
    const cart = await api.patch(`/cart/items/${productId}`, { quantity });
    renderCart(cart);
    updateCartBadge();
  } catch (err) {
    showToast(err.message, 'error');
    // 失敗要重新整理，避免畫面數字跟後端不同步
    reloadCart();
  }
}

async function removeItem(productId) {
  try {
    const cart = await api.del(`/cart/items/${productId}`);
    renderCart(cart);
    updateCartBadge();
    showToast('已移除商品', 'info');
  } catch (err) {
    showToast(err.message, 'error');
    reloadCart();
  }
}

function bindCartListEvents() {
  const list = document.getElementById('cart-list');
  if (!list) return;

  list.querySelectorAll('.cart-item').forEach((row) => {
    const productId = Number(row.dataset.productId);
    const input = row.querySelector('.qty-input');
    const minusBtn = row.querySelector('[data-action="minus"]');
    const plusBtn = row.querySelector('[data-action="plus"]');
    const removeBtn = row.querySelector('[data-action="remove"]');

    minusBtn.addEventListener('click', () => {
      const current = parseInt(input.value, 10) || 1;
      if (current <= 1) return;
      updateQuantity(productId, current - 1);
    });
    plusBtn.addEventListener('click', () => {
      const current = parseInt(input.value, 10) || 1;
      updateQuantity(productId, current + 1);
    });
    input.addEventListener('change', () => {
      const value = Math.max(1, parseInt(input.value, 10) || 1);
      updateQuantity(productId, value);
    });
    removeBtn.addEventListener('click', () => removeItem(productId));
  });
}

document.addEventListener('DOMContentLoaded', () => {
  if (!Auth.requireLogin()) return;
  reloadCart();
});
