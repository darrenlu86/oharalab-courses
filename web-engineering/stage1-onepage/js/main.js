/*
 * 沖沖咖啡 BrewGo — 開幕倒數活動頁
 * 純原生 JavaScript，不依賴任何框架或函式庫。
 * 分成四個功能區塊：導覽列漢堡選單、開幕倒數計時、FAQ 手風琴、訂閱表單驗證。
 * 每個區塊都包成一個函式，在檔案最下面統一呼叫初始化——這樣即使某個區塊
 * 需要的 DOM 元素不存在（例如你複製這支檔案去別的頁面），也不會讓其他區塊跟著壞掉。
 */

(function () {
  "use strict";

  /* ------------------------------------------------------------------
   * 1. 導覽列漢堡選單（行動版收合）
   * ------------------------------------------------------------------ */
  function initNavToggle() {
    var toggle = document.querySelector(".navbar__toggle");
    var menu = document.querySelector(".navbar__menu");
    if (!toggle || !menu) return;

    toggle.addEventListener("click", function () {
      var isOpen = menu.classList.toggle("is-open");
      // aria-expanded 讓螢幕閱讀器知道選單目前是展開還是收合，
      // 這是純 CSS 做不到的部分，一定要靠 JS 同步更新。
      toggle.setAttribute("aria-expanded", String(isOpen));
    });

    // 點擊選單內的連結後自動收合，行動版點完錨點選單還開著會擋住內容。
    menu.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        menu.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  /* ------------------------------------------------------------------
   * 2. 開幕倒數計時
   * ------------------------------------------------------------------
   * 邊界處理（教學重點）：如果現在時間已經超過 OPENING_DATE，不能讓倒數
   * 變成負數（會出現「-3 天」這種對使用者沒有意義的畫面），要換成
   * 「已盛大開幕」的訊息。這是每個做倒數計時功能都會踩到的坑，
   * 必須在寫程式的當下就決定「過期之後要顯示什麼」，而不是等使用者回報才修。
   */
  var OPENING_DATE = new Date("2026-09-01T10:00:00+08:00");

  function initCountdown() {
    var wrapper = document.querySelector("[data-countdown]");
    if (!wrapper) return;

    var daysEl = wrapper.querySelector("[data-days]");
    var hoursEl = wrapper.querySelector("[data-hours]");
    var minutesEl = wrapper.querySelector("[data-minutes]");
    var secondsEl = wrapper.querySelector("[data-seconds]");
    var doneEl = document.querySelector("[data-countdown-done]");

    function tick() {
      var now = new Date();
      var diffMs = OPENING_DATE.getTime() - now.getTime();

      if (diffMs <= 0) {
        // 已過開幕時間：隱藏倒數格子，顯示「已盛大開幕」，並停止計時器。
        wrapper.classList.add("hidden");
        if (doneEl) doneEl.classList.remove("hidden");
        clearInterval(timerId);
        return;
      }

      var totalSeconds = Math.floor(diffMs / 1000);
      var days = Math.floor(totalSeconds / 86400);
      var hours = Math.floor((totalSeconds % 86400) / 3600);
      var minutes = Math.floor((totalSeconds % 3600) / 60);
      var seconds = totalSeconds % 60;

      daysEl.textContent = String(days);
      hoursEl.textContent = String(hours).padStart(2, "0");
      minutesEl.textContent = String(minutes).padStart(2, "0");
      secondsEl.textContent = String(seconds).padStart(2, "0");
    }

    tick();
    var timerId = setInterval(tick, 1000);
  }

  /* ------------------------------------------------------------------
   * 3. FAQ 手風琴（accordion）
   * ------------------------------------------------------------------
   * 用 aria-expanded 當「單一事實來源」：CSS 靠這個屬性決定要不要展開
   * （見 css/style.css 的 [aria-expanded="true"] 選擇器），JS 只負責切換
   * 這個屬性，不用另外維護一份 class 清單，兩邊才不會兜不起來。
   */
  function initAccordion() {
    var triggers = document.querySelectorAll(".accordion__trigger");
    if (!triggers.length) return;

    triggers.forEach(function (trigger) {
      var panel = document.getElementById(trigger.getAttribute("aria-controls"));
      if (!panel) return;

      trigger.addEventListener("click", function () {
        var isExpanded = trigger.getAttribute("aria-expanded") === "true";
        var nextState = !isExpanded;

        // aria-expanded 與 panel.hidden 是同一件事的兩種表達方式：
        // 前者告訴螢幕閱讀器目前狀態，後者實際控制視覺上看不看得到，
        // 兩個一起改，才不會出現「畫面上看不到，但螢幕閱讀器以為是展開的」這種不一致。
        trigger.setAttribute("aria-expanded", String(nextState));
        panel.hidden = !nextState;
      });
    });
  }

  /* ------------------------------------------------------------------
   * 4. 訂閱表單前端驗證（純前端 mock，沒有任何後端接收資料）
   * ------------------------------------------------------------------
   * 誠實聲明：這裡「送出」只是把表單藏起來、換成成功訊息，資料不會被存到
   * 任何地方、也不會離開瀏覽器。真的要收集 email 名單，需要一支後端 API
   * 把資料寫進資料庫（或串第三方電子報服務），這是後面階段（stage4 起）
   * 才會補上的東西。
   */
  function initSubscribeForm() {
    var form = document.querySelector("[data-subscribe-form]");
    if (!form) return;

    var nameInput = form.querySelector("#subscribe-name");
    var emailInput = form.querySelector("#subscribe-email");
    var nameError = form.querySelector("[data-error-for='name']");
    var emailError = form.querySelector("[data-error-for='email']");
    var successBox = document.querySelector("[data-subscribe-success]");

    // 簡化版 email 格式檢查：只要求「有 @、@ 前後都有字元、結尾有網域」，
    // 不追求完全符合 RFC 5322（那份規格連很多正式產品都做不到 100% 正確），
    // 教學上這樣的寬鬆規則已經足夠擋掉「忘記打 @」這類最常見的手誤。
    var EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    function validateName() {
      var value = nameInput.value.trim();
      if (!value) {
        nameError.textContent = "請填寫姓名。";
        return false;
      }
      nameError.textContent = "";
      return true;
    }

    function validateEmail() {
      var value = emailInput.value.trim();
      if (!value) {
        emailError.textContent = "請填寫 email。";
        return false;
      }
      if (!EMAIL_PATTERN.test(value)) {
        emailError.textContent = "email 格式看起來不對，請確認有沒有打錯（例如缺少 @ 或網域）。";
        return false;
      }
      emailError.textContent = "";
      return true;
    }

    nameInput.addEventListener("blur", function () {
      nameInput.dataset.touched = "true";
      validateName();
    });

    emailInput.addEventListener("blur", function () {
      emailInput.dataset.touched = "true";
      validateEmail();
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault(); // 阻止瀏覽器真的把表單送到某個網址去（本來就沒有後端可以收）

      nameInput.dataset.touched = "true";
      emailInput.dataset.touched = "true";

      var isNameValid = validateName();
      var isEmailValid = validateEmail();

      if (!isNameValid || !isEmailValid) {
        // 驗證沒過：把焦點移到第一個有問題的欄位，方便鍵盤與螢幕閱讀器使用者。
        (isNameValid ? emailInput : nameInput).focus();
        return;
      }

      form.classList.add("hidden");
      if (successBox) successBox.classList.add("is-visible");
    });
  }

  /* ------------------------------------------------------------------
   * 初始化
   * ------------------------------------------------------------------ */
  document.addEventListener("DOMContentLoaded", function () {
    initNavToggle();
    initCountdown();
    initAccordion();
    initSubscribeForm();
  });
})();
