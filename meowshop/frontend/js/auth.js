/**
 * auth.js — 登入狀態管理
 *
 * 用途：
 *   把「有沒有登入」「登入的人是誰」這件事集中在這裡管理。token 跟 user 資料
 *   都存在 localStorage，其他頁面只透過 Auth.xxx() 存取，不要直接操作 localStorage，
 *   之後要換成別的儲存方式（例如 sessionStorage）只需要改這一個檔案。
 *
 * 為什麼存 localStorage 而不是 cookie？
 *   教學簡化：localStorage 讀寫簡單、不用處理 cookie 的 domain/SameSite 設定，
 *   純前端 fetch 帶 Authorization header 也不用煩惱 CORS + credentials。
 *   但要跟學員說清楚 trade-off：localStorage 能被同頁面任何 JS 讀到，
 *   如果網站被 XSS 注入惡意 script，token 就會被偷走；正式產品比較安全的做法
 *   是後端發 httpOnly cookie（JS 完全讀不到），這裡沒有做，PRD 的「已知簡化」也有寫。
 */

const Auth = {
  getToken() {
    return localStorage.getItem(window.MeowShopStorageKeys.TOKEN_KEY);
  },

  getUser() {
    const raw = localStorage.getItem(window.MeowShopStorageKeys.USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  },

  isLoggedIn() {
    return !!this.getToken();
  },

  /** 登入成功後呼叫：把後端回傳的 access_token 跟 user 存起來 */
  login(token, user) {
    localStorage.setItem(window.MeowShopStorageKeys.TOKEN_KEY, token);
    localStorage.setItem(window.MeowShopStorageKeys.USER_KEY, JSON.stringify(user));
  },

  /** 登出：清掉本機資料，導回首頁 */
  logout() {
    localStorage.removeItem(window.MeowShopStorageKeys.TOKEN_KEY);
    localStorage.removeItem(window.MeowShopStorageKeys.USER_KEY);
    location.href = 'index.html';
  },

  /**
   * 頁面守門用：這頁需要登入才能看，沒登入就導去登入頁。
   * 回傳 boolean 方便呼叫端 `if (!Auth.requireLogin()) return;`
   */
  requireLogin() {
    if (!this.isLoggedIn()) {
      location.href = 'login.html';
      return false;
    }
    return true;
  },
};
