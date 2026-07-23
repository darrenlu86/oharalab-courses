/**
 * login.js — 登入 / 註冊頁
 *
 * 用途：處理雙 tab 切換 + 兩個表單的送出邏輯。
 * 註冊 API（/api/auth/register）只回傳使用者資料、不會給 token（見 SPEC §4 #1），
 * 所以註冊成功後不能直接當作已登入，而是切回登入 tab、把 email 帶過去，
 * 請使用者自己輸入密碼再登入一次——這也比較符合真實世界「註冊完通常還要再登入」的習慣。
 */

function switchTab(tabName) {
  document.querySelectorAll('.auth-tab').forEach((el) => {
    el.classList.toggle('active', el.dataset.tab === tabName);
  });
  document.getElementById('panel-login').classList.toggle('active', tabName === 'login');
  document.getElementById('panel-register').classList.toggle('active', tabName === 'register');
}

function showFormError(id, message) {
  const el = document.getElementById(id);
  el.textContent = message;
  el.classList.add('show');
}

function clearFormError(id) {
  const el = document.getElementById(id);
  el.textContent = '';
  el.classList.remove('show');
}

function bindTabs() {
  document.querySelectorAll('.auth-tab').forEach((btn) => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });
}

function bindLoginForm() {
  const form = document.getElementById('login-form');
  const submitBtn = document.getElementById('login-submit');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearFormError('login-error');
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;

    submitBtn.disabled = true;
    try {
      const data = await api.post('/auth/login', { email, password });
      Auth.login(data.access_token, data.user);
      showToast(`歡迎回來，${data.user.name}`, 'success');
      location.href = 'index.html';
    } catch (err) {
      showFormError('login-error', err.message);
    } finally {
      submitBtn.disabled = false;
    }
  });
}

function bindRegisterForm() {
  const form = document.getElementById('register-form');
  const submitBtn = document.getElementById('register-submit');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearFormError('register-error');
    const name = document.getElementById('register-name').value.trim();
    const email = document.getElementById('register-email').value.trim();
    const password = document.getElementById('register-password').value;

    submitBtn.disabled = true;
    try {
      await api.post('/auth/register', { email, password, name });
      showToast('註冊成功，請登入', 'success');
      switchTab('login');
      document.getElementById('login-email').value = email;
      document.getElementById('login-password').focus();
      form.reset();
    } catch (err) {
      showFormError('register-error', err.message);
    } finally {
      submitBtn.disabled = false;
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  // 已經登入的人跑來登入頁通常是點錯，直接送回首頁
  if (Auth.isLoggedIn()) {
    location.href = 'index.html';
    return;
  }
  bindTabs();
  bindLoginForm();
  bindRegisterForm();
});
