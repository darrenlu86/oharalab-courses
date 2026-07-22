/**
 * checkout.js — 結帳頁（本專案最複雜的流程，仔細看註解）
 *
 * 兩種進入方式：
 *   1. 一般結帳：cart.html「前往結帳」點過來，網址是 checkout.html，
 *      要填收件人表單 + 模擬信用卡表單。
 *   2. 訂單重新付款：orders.html 對 pending/failed 訂單按「重新付款」，
 *      網址是 checkout.html?order_id=N，只走付款這一步（收件資訊已經在建單時存過了）。
 *
 * 流程對應後端（SPEC §4）：
 *   先 POST /api/orders 建單（此時會清空購物車、狀態是 pending）
 *   → 再 POST /api/payments/mock 付款。
 *   這是兩支獨立 API、兩個步驟，不是一支「一次結帳」的 API——
 *   教學點：真實金流也是先建訂單、使用者才去收銀台輸入卡號，
 *   拆成兩步是因為付款這件事本來就可能失敗/重試，訂單不該因為付款失敗就消失。
 *
 * 「模擬付款」的兩種失敗要分開處理：
 *   (a) 卡號剛好是 4000 0000 0000 0002 → 後端回 200，但 payment.status = 'failed'
 *       （這是「模擬銀行拒絕」的業務結果，不是 API 錯誤）
 *   (b) 訂單不存在/別人的/已經付過/付款當下庫存不足 → 後端回 4xx，err.message 是 detail
 *   兩種都要讓使用者看到「付款失敗」畫面，但文案來源不同。
 */

const TEST_CARD_SUCCESS = '4242 4242 4242 4242';
const TEST_CARD_FAIL = '4000 0000 0000 0002';

function getOrderIdFromUrl() {
  const params = new URLSearchParams(location.search);
  const id = params.get('order_id');
  return id ? Number(id) : null;
}

function setOrderIdInUrl(id) {
  history.replaceState(null, '', `checkout.html?order_id=${id}`);
}

function renderWarningBar() {
  const slot = document.getElementById('checkout-warning-slot');
  slot.innerHTML = `${Icons.warning} 模擬付款——不會真實扣款，本站沒有串接任何真實金流。`;
}

/* ---------- 信用卡號輸入自動加空格，方便閱讀 ---------- */
function bindCardNumberFormatting(input) {
  input.addEventListener('input', () => {
    const digits = input.value.replace(/\D/g, '').slice(0, 16);
    input.value = digits.replace(/(.{4})/g, '$1 ').trim();
  });
}

function paymentFormHtml() {
  return `
    <div class="checkout-form-card">
      <h3>模擬信用卡付款</h3>
      <div class="test-card-hint">
        測試卡號——<span class="ok">${TEST_CARD_SUCCESS}</span> 一定成功；
        <span class="fail">${TEST_CARD_FAIL}</span> 一定失敗（模擬餘額不足）。其餘 16 碼一律視為成功。
      </div>
      <div class="form-error" id="payment-error"></div>
      <form id="payment-form">
        <div class="form-group">
          <label class="form-label" for="card-number">卡號</label>
          <input type="text" id="card-number" class="form-input" required maxlength="19" placeholder="4242 4242 4242 4242" inputmode="numeric" autocomplete="cc-number">
        </div>
        <div class="form-group">
          <label class="form-label" for="card-holder">持卡人姓名</label>
          <input type="text" id="card-holder" class="form-input" required autocomplete="cc-name">
        </div>
        <button type="submit" class="btn btn-primary btn-block btn-lg" id="pay-submit-btn">確認付款</button>
      </form>
    </div>
  `;
}

function summaryCardHtml({ orderId, recipientName, recipientAddress, totalAmount }) {
  return `
    <aside class="summary-card">
      <h3>訂單摘要</h3>
      ${orderId ? `<div class="summary-row"><span>訂單編號</span><span>#${orderId}</span></div>` : ''}
      ${recipientName ? `<div class="summary-row"><span>收件人</span><span>${escapeHtml(recipientName)}</span></div>` : ''}
      ${recipientAddress ? `<div class="summary-row"><span>收件地址</span><span style="text-align:right;max-width:60%;">${escapeHtml(recipientAddress)}</span></div>` : ''}
      <div class="summary-total"><span>總計</span><span>${formatCurrency(totalAmount)}</span></div>
    </aside>
  `;
}

/* ---------- 付款結果畫面 ---------- */
function renderPaymentResult({ success, title, message, transactionId, retryOrderId }) {
  const root = document.getElementById('checkout-root');
  root.innerHTML = `
    <div class="payment-result payment-result--${success ? 'success' : 'fail'}">
      <div class="payment-result-icon">${success ? Icons.checkCircle : Icons.xCircle}</div>
      <h2>${title}</h2>
      <p>${escapeHtml(message)}${transactionId ? `<br>交易編號：${escapeHtml(transactionId)}` : ''}</p>
      ${success
        ? `<a href="orders.html" class="btn btn-primary btn-lg">查看我的訂單</a>`
        : `<button type="button" class="btn btn-primary btn-lg" id="retry-payment-btn">重新付款</button>
           <a href="orders.html" class="btn btn-outline btn-lg" style="margin-left:12px;">先去看訂單</a>`
      }
    </div>
  `;

  if (success) {
    setTimeout(() => { location.href = 'orders.html'; }, 1800);
  } else {
    document.getElementById('retry-payment-btn').addEventListener('click', () => {
      setOrderIdInUrl(retryOrderId);
      loadCheckout();
    });
  }
}

/**
 * 呼叫 /api/payments/mock 並畫出結果畫面。
 * 呼叫端要先確保 orderId 存在、卡號/持卡人已經驗證過非空。
 */
async function submitPayment(orderId, cardNumber, cardHolder) {
  try {
    const result = await api.post('/payments/mock', {
      order_id: orderId,
      card_number: cardNumber,
      card_holder: cardHolder,
    });

    if (result.payment.status === 'success') {
      renderPaymentResult({
        success: true,
        title: '付款成功',
        message: `已收到您的付款，金額 ${formatCurrency(result.payment.amount)}。`,
        transactionId: result.payment.transaction_id,
      });
    } else {
      // 200 但 payment.status === 'failed'：卡號剛好是模擬失敗卡
      renderPaymentResult({
        success: false,
        title: '付款失敗',
        message: '這張卡被銀行拒絕了（模擬餘額不足），可以換一組測試卡號再試一次。',
        retryOrderId: orderId,
      });
    }
    updateCartBadge();
  } catch (err) {
    // 4xx：訂單不存在/非本人/已付款/庫存不足，err.message 是後端的 detail
    renderPaymentResult({
      success: false,
      title: '付款失敗',
      message: err.message,
      retryOrderId: orderId,
    });
  }
}

/* ---------- 模式一：一般結帳（收件表單 + 付款表單） ---------- */
function renderNewCheckout(cart) {
  const root = document.getElementById('checkout-root');
  root.innerHTML = `
    <div class="checkout-layout">
      <div>
        <div class="checkout-form-card">
          <h3>收件資訊</h3>
          <form id="recipient-form">
            <div class="form-group">
              <label class="form-label" for="recipient-name">收件人姓名</label>
              <input type="text" id="recipient-name" class="form-input" required autocomplete="name">
            </div>
            <div class="form-group">
              <label class="form-label" for="recipient-address">收件地址</label>
              <input type="text" id="recipient-address" class="form-input" required autocomplete="street-address">
            </div>
          </form>
        </div>
        ${paymentFormHtml()}
      </div>
      ${summaryCardHtml({ totalAmount: cart.total_amount })}
    </div>
  `;

  bindCardNumberFormatting(document.getElementById('card-number'));

  const paymentForm = document.getElementById('payment-form');
  paymentForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const recipientName = document.getElementById('recipient-name').value.trim();
    const recipientAddress = document.getElementById('recipient-address').value.trim();
    const cardNumber = document.getElementById('card-number').value.trim();
    const cardHolder = document.getElementById('card-holder').value.trim();

    if (!recipientName || !recipientAddress) {
      showFormError('payment-error', '請先填寫收件人姓名與地址');
      document.getElementById('recipient-name').focus();
      return;
    }

    const submitBtn = document.getElementById('pay-submit-btn');
    submitBtn.disabled = true;
    clearFormError('payment-error');

    try {
      // 第一步：建單（此時會清空購物車）
      const order = await api.post('/orders', {
        recipient_name: recipientName,
        recipient_address: recipientAddress,
      });
      setOrderIdInUrl(order.id);
      // 第二步：付款
      await submitPayment(order.id, cardNumber, cardHolder);
    } catch (err) {
      // 建單就失敗了（購物車是空的 / 庫存不足），還沒進到付款步驟
      showFormError('payment-error', err.message);
      submitBtn.disabled = false;
    }
  });
}

/* ---------- 模式二：?order_id=N 只走付款 ---------- */
function renderRetryCheckout(order) {
  const root = document.getElementById('checkout-root');

  if (order.status === 'paid') {
    root.innerHTML = `
      <div class="payment-result payment-result--success">
        <div class="payment-result-icon">${Icons.checkCircle}</div>
        <h2>這筆訂單已經付款完成</h2>
        <p>訂單編號 #${order.id}，不用再付一次囉。</p>
        <a href="orders.html" class="btn btn-primary btn-lg">查看我的訂單</a>
      </div>
    `;
    return;
  }

  root.innerHTML = `
    <div class="checkout-layout">
      <div>
        ${paymentFormHtml()}
      </div>
      ${summaryCardHtml({
        orderId: order.id,
        recipientName: order.recipient_name,
        recipientAddress: order.recipient_address,
        totalAmount: order.total_amount,
      })}
    </div>
  `;

  bindCardNumberFormatting(document.getElementById('card-number'));

  const paymentForm = document.getElementById('payment-form');
  paymentForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const cardNumber = document.getElementById('card-number').value.trim();
    const cardHolder = document.getElementById('card-holder').value.trim();
    const submitBtn = document.getElementById('pay-submit-btn');
    submitBtn.disabled = true;
    clearFormError('payment-error');
    await submitPayment(order.id, cardNumber, cardHolder);
  });
}

/* ---------- 表單錯誤訊息小工具（跟 login.js 共用同樣的 class 命名） ---------- */
function showFormError(id, message) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = message;
  el.classList.add('show');
}
function clearFormError(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = '';
  el.classList.remove('show');
}

/* ---------- 入口：判斷是哪一種模式 ---------- */
async function loadCheckout() {
  const root = document.getElementById('checkout-root');
  const orderId = getOrderIdFromUrl();

  if (orderId) {
    try {
      const order = await api.get(`/orders/${orderId}`);
      renderRetryCheckout(order);
    } catch (err) {
      root.innerHTML = `<p class="loading-text">${escapeHtml(err.message)}</p>`;
    }
    return;
  }

  try {
    const cart = await api.get('/cart');
    if (!cart.items || cart.items.length === 0) {
      root.innerHTML = `
        <div class="empty-state">
          <p>購物車是空的，先去挑選商品吧。</p>
          <a href="products.html" class="btn btn-primary" style="margin-top:14px;">去逛逛</a>
        </div>
      `;
      return;
    }
    renderNewCheckout(cart);
  } catch (err) {
    root.innerHTML = `<p class="loading-text">${escapeHtml(err.message)}</p>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (!Auth.requireLogin()) return;
  renderWarningBar();
  loadCheckout();
});
