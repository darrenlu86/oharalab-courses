/**
 * orders.js — 我的訂單頁
 *
 * 用途：GET /api/orders 列出目前使用者的訂單（後端已按時間新到舊排序），
 * pending / failed 狀態的訂單顯示「重新付款」導去 checkout.html?order_id=N；
 * 每張卡片可以展開查看明細（GET /api/orders/{id}，含 order_items 快照與付款紀錄），
 * 明細只在使用者點開時才打 API，不用一次把所有訂單的明細都抓下來。
 */

function formatDate(raw) {
  if (!raw) return '';
  const d = new Date(raw.includes('T') || raw.endsWith('Z') ? raw : raw.replace(' ', 'T') + 'Z');
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function canRetryPayment(status) {
  return status === 'pending' || status === 'failed';
}

function orderCardHtml(order) {
  return `
    <div class="order-card" data-order-id="${order.id}">
      <div class="order-card-header">
        <span class="order-card-id">訂單 #${order.id}</span>
        ${orderStatusBadgeHtml(order.status)}
      </div>
      <div class="order-card-date">${formatDate(order.created_at)}</div>
      <div class="order-card-footer">
        <span class="order-card-amount">${formatCurrency(order.total_amount)}</span>
        <div>
          ${canRetryPayment(order.status)
            ? `<a href="checkout.html?order_id=${order.id}" class="btn btn-primary btn-sm">重新付款</a>`
            : ''}
          <button type="button" class="order-detail-toggle" data-order-id="${order.id}">查看明細</button>
        </div>
      </div>
      <div class="order-items-detail" id="order-detail-${order.id}"></div>
    </div>
  `;
}

function renderEmptyOrders(root) {
  root.innerHTML = `
    <div class="empty-state">
      <p>還沒有任何訂單，去挑點喜歡的商品吧。</p>
      <a href="products.html" class="btn btn-primary" style="margin-top:14px;">去逛逛</a>
    </div>
  `;
}

async function toggleOrderDetail(orderId) {
  const detailEl = document.getElementById(`order-detail-${orderId}`);
  const alreadyLoaded = detailEl.dataset.loaded === 'true';

  if (!alreadyLoaded) {
    detailEl.innerHTML = `<p class="loading-text">明細載入中...</p>`;
    try {
      const order = await api.get(`/orders/${orderId}`);
      // 後端回傳的品項欄位名以 SPEC 為準；這裡多做一層 fallback（items / order_items）
      // 是為了避免後端實作跟前端對「訂單詳情」JSON 欄位命名的認知有落差時整頁報錯。
      const itemsHtml = (order.items || order.order_items || []).map((item) => `
        <div class="order-item-row">
          <span>${escapeHtml(item.product_name)} × ${item.quantity}</span>
          <span>${formatCurrency(item.unit_price * item.quantity)}</span>
        </div>
      `).join('');
      const payment = order.payment || (order.payments && order.payments[0]);
      const paymentHtml = payment
        ? `<div class="order-item-row"><span>付款方式</span><span>信用卡尾號 ${escapeHtml(payment.card_last4)}</span></div>`
        : '';
      detailEl.innerHTML = `
        <div class="order-item-row"><span>收件人</span><span>${escapeHtml(order.recipient_name)}</span></div>
        <div class="order-item-row"><span>收件地址</span><span>${escapeHtml(order.recipient_address)}</span></div>
        ${itemsHtml}
        ${paymentHtml}
      `;
      detailEl.dataset.loaded = 'true';
    } catch (err) {
      detailEl.innerHTML = `<p class="loading-text">明細載入失敗：${escapeHtml(err.message)}</p>`;
    }
  }

  detailEl.classList.toggle('open');
}

function bindOrderDetailToggles() {
  document.querySelectorAll('.order-detail-toggle').forEach((btn) => {
    btn.addEventListener('click', () => toggleOrderDetail(Number(btn.dataset.orderId)));
  });
}

async function loadOrders() {
  const root = document.getElementById('orders-root');
  try {
    const data = await api.get('/orders');
    const items = data.items || [];
    if (items.length === 0) {
      renderEmptyOrders(root);
      return;
    }
    root.innerHTML = `<div class="order-list">${items.map(orderCardHtml).join('')}</div>`;
    bindOrderDetailToggles();
  } catch (err) {
    root.innerHTML = `<p class="loading-text">訂單載入失敗：${escapeHtml(err.message)}</p>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (!Auth.requireLogin()) return;
  loadOrders();
});
