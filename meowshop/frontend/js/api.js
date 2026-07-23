/**
 * api.js — 前端唯一的 API 溝通層
 *
 * 用途：
 *   所有頁面呼叫後端 /api/* 一律透過這裡的 api.get / api.post / api.patch / api.del，
 *   不要在各頁面自己寫 fetch()。這樣「baseURL 怎麼設」「token 怎麼帶」「錯誤怎麼處理」
 *   只需要改這一個檔案，全站行為就一致（教學點：重複的 fetch 邏輯就該抽出來）。
 *
 * 關鍵設計：
 *   1. 同源 /api 當 baseURL —— 因為後端會把前端一起 serve（見後端 main.py 的 StaticFiles mount），
 *      本機開發跟正式上線都不用改網址，也不會遇到 CORS。
 *   2. 401 其實有三種情況，不能全部套同一招「清 token + 導頁」：
 *      - 呼叫「登入 / 註冊」本來就沒帶 token，401 代表「帳號密碼錯」，這是使用者輸入問題，
 *        要把 detail 丟回給呼叫端顯示，不能自動跳轉，否則使用者永遠看不到錯誤訊息。
 *      - 呼叫「需要登入」的端點，是使用者主動觸發的操作（例如按下「加入購物車」、
 *        打開「我的訂單」），收到 401 代表 token 不存在或已過期，這時候要自動清掉
 *        localStorage 並導去登入頁——這是規格要求的「401 時導向登入」。
 *      - 但如果是「背景/選配性查詢」——例如每個頁面載入時 navbar 都會偷偷打一次
 *        GET /api/cart 來更新右上角購物車數量 badge——使用者根本沒有主動要求要做
 *        任何需要登入的事，只是單純逛首頁/商品頁。這種查詢收到 401（token 過期）
 *        如果也強制導頁，等於「純瀏覽也會被踢出」，體驗上非常粗暴，也會讓學員誤以為
 *        「401 一律導頁」是正確做法。這裡用呼叫端傳入的 `{ silent401: true }` 選項
 *        來分辨：silent401 時只清掉失效的 token，不導頁，讓呼叫端自己決定畫面怎麼
 *        更新（例如把 badge 藏起來、navbar 改畫成未登入狀態）。
 *   3. 錯誤一律丟成 Error 物件，訊息取後端回傳的 detail（FastAPI 慣例）；
 *      但 detail 的形狀不是永遠都是字串——422 驗證錯誤時 detail 是「錯誤物件陣列」
 *      （見下面 apiFetch 內的說明），這裡會先轉成人看得懂的字串再包成 Error，
 *      頁面 catch 到之後可以直接 err.message 顯示給使用者，不用重複解析 response。
 */

// 兩個 localStorage key 集中定義在這裡（api.js 是第一個載入的 script），
// auth.js 之後會透過 window.MeowShopStorageKeys 取用，避免兩個檔案各寫一次字串、改字串時漏改。
window.MeowShopStorageKeys = {
  TOKEN_KEY: 'meowshop_token',
  USER_KEY: 'meowshop_user',
};

const API_BASE = '/api';

// 這兩支端點本來就不需要登入，呼叫時不用帶 token，
// 而且它們回傳的 401/409 是「使用者輸入錯誤」，不是「登入失效」，不能觸發自動導頁。
const PUBLIC_NO_REDIRECT_PATHS = ['/auth/login', '/auth/register'];

function isPublicNoRedirectPath(path) {
  return PUBLIC_NO_REDIRECT_PATHS.some((p) => path === p);
}

/**
 * 核心 fetch 封裝。
 * @param {string} path - 例如 '/products' 或 '/cart/items/3'（不含 /api 前綴）
 * @param {object} options - fetch 的 options（method/body/headers...）
 * @param {object} meta - 呼叫端額外指定的行為選項（不會傳給 fetch）：
 *   - silent401：這支請求是「背景/選配性查詢」，401 時只清 token、不導頁
 *     （見上面 docstring 第 2 點）。預設 false＝維持原本「導去登入頁」的行為。
 */
async function apiFetch(path, options = {}, meta = {}) {
  const { silent401 = false } = meta;
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  const skipAuthRedirect = isPublicNoRedirectPath(path);
  const token = localStorage.getItem(window.MeowShopStorageKeys.TOKEN_KEY);

  if (token && !skipAuthRedirect) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch (networkErr) {
    // fetch 本身丟出例外＝連線失敗（伺服器沒開、斷網…），跟後端回傳的錯誤格式不同，
    // 這裡包裝成同樣「有 message 可以顯示」的 Error，頁面不用分兩種 catch。
    throw new Error('連線失敗，請確認網路狀態或稍後再試');
  }

  // 需要登入的端點收到 401 ⇒ token 已經失效，先把本機憑證清掉（不管是不是 silent 都要清，
  // 免得後面又拿失效的 token 繼續打其他 API）。
  if (res.status === 401 && !skipAuthRedirect) {
    localStorage.removeItem(window.MeowShopStorageKeys.TOKEN_KEY);
    localStorage.removeItem(window.MeowShopStorageKeys.USER_KEY);

    // silent401＝true（背景/選配性查詢，例如 navbar 的購物車數量 badge）：
    // 使用者根本沒有主動要求做需要登入的事，這裡只清 token，不導頁，
    // 讓呼叫端自己決定怎麼更新畫面（例如把 badge 藏起來）。
    // silent401＝false（使用者主動觸發的操作，預設值）：才走原本「導去登入頁」的邏輯。
    if (!silent401) {
      const onLoginPage = location.pathname.endsWith('login.html');
      if (!onLoginPage) {
        location.href = 'login.html';
      }
    }
  }

  // 204 No Content 或空 body 的情況不用硬解 JSON
  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (e) {
      data = null;
    }
  }

  if (!res.ok) {
    // FastAPI/Pydantic 的 422（Unprocessable Entity，通常是欄位驗證失敗）跟其他錯誤
    // 長得不一樣：detail 不是字串，而是「錯誤物件陣列」，長相像這樣：
    //   { "detail": [ { "type": "value_error", "loc": ["body", "card_number"],
    //                    "msg": "Value error, 卡號必須是 16 碼數字" } ] }
    // 如果直接 new Error(detail)，JS 會把陣列轉成 "[object Object]" 這種看不懂的字串，
    // 所以這裡先判斷是不是陣列，是的話取每一項的 msg 合併成一句話；
    // 其他狀態碼（401/404/409...）維持原本「detail 就是一句繁中字串」的假設。
    const detail = data && data.detail;
    let message;
    if (Array.isArray(detail)) {
      message = detail.map((item) => (item && item.msg) ? item.msg : JSON.stringify(item)).join('；');
    } else if (detail) {
      message = detail;
    } else {
      message = `發生錯誤（狀態碼 ${res.status}）`;
    }
    const err = new Error(message);
    err.status = res.status;
    err.detail = message;
    throw err;
  }

  return data;
}

const api = {
  get(path, meta) {
    return apiFetch(path, { method: 'GET' }, meta);
  },
  post(path, body, meta) {
    return apiFetch(path, { method: 'POST', body: JSON.stringify(body ?? {}) }, meta);
  },
  patch(path, body, meta) {
    return apiFetch(path, { method: 'PATCH', body: JSON.stringify(body ?? {}) }, meta);
  },
  del(path, meta) {
    return apiFetch(path, { method: 'DELETE' }, meta);
  },
};
