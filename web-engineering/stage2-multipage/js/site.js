/*
 * site.js — 行動選單、商品分類篩選、聯絡表單前端驗證
 * 不用任何框架或函式庫，全部原生 DOM API。
 */
(function () {
  "use strict";

  // ---------- 行動選單（掛在 header partial 載入完成後）----------
  function initMobileNav() {
    var toggle = document.querySelector(".nav-toggle");
    var nav = document.getElementById("main-nav");
    if (!toggle || !nav) return;
    toggle.addEventListener("click", function () {
      var isOpen = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(isOpen));
    });
  }

  // ---------- 商品分類篩選（products.html）----------
  // 這裡刻意不用「複製一份商品資料到 JS 陣列再 render」的做法：
  // 12 筆商品卡片本來就寫在 HTML 裡（好處：view-source 看得到內容、SEO 友善、
  // 沒有 JS 也能看到全部商品），JS 只負責「依 data-category 顯示/隱藏」。
  function initCategoryFilter() {
    var tabGroup = document.querySelector("[data-tab-group]");
    if (!tabGroup) return;
    var tabs = Array.from(tabGroup.querySelectorAll(".tab"));
    var cards = Array.from(document.querySelectorAll("[data-category]"));

    function applyFilter(category) {
      cards.forEach(function (card) {
        var match = category === "all" || card.getAttribute("data-category") === category;
        card.hidden = !match;
      });
      tabs.forEach(function (tab) {
        var active = tab.getAttribute("data-category") === category;
        tab.classList.toggle("active", active);
        tab.setAttribute("aria-pressed", String(active));
      });
    }

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        var category = tab.getAttribute("data-category");
        applyFilter(category);
        // 篩選狀態反映到網址上，這樣「首頁分類入口」的連結
        // （例如 products.html?category=beans）可以直接對到正確的分類。
        var url = new URL(location.href);
        if (category === "all") {
          url.searchParams.delete("category");
        } else {
          url.searchParams.set("category", category);
        }
        history.replaceState(null, "", url);
      });
    });

    var categories = tabs.map(function (t) {
      return t.getAttribute("data-category");
    });
    var requested = new URLSearchParams(location.search).get("category");
    applyFilter(categories.indexOf(requested) > -1 ? requested : "all");
  }

  // ---------- 聯絡表單驗證（contact.html）----------
  // 誠實聲明：這是 mock 表單，前端驗證通過後只會顯示「已送出」的成功訊息，
  // 沒有任何後端接收或儲存資料。真正能寄出/儲存的表單要等 stage4 接後端 API 之後才有。
  function initContactForm() {
    var form = document.getElementById("contact-form");
    if (!form) return;
    var successBox = document.querySelector(".form-success");
    var emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    function setFieldError(field, message) {
      var wrapper = field.closest(".form-field");
      if (!wrapper) return;
      var errorEl = wrapper.querySelector(".error-message");
      if (message) {
        wrapper.classList.add("has-error");
        if (errorEl) errorEl.textContent = message;
        field.setAttribute("aria-invalid", "true");
      } else {
        wrapper.classList.remove("has-error");
        if (errorEl) errorEl.textContent = "";
        field.removeAttribute("aria-invalid");
      }
    }

    function validate() {
      var valid = true;
      var name = form.querySelector("#field-name");
      var email = form.querySelector("#field-email");
      var topic = form.querySelector("#field-topic");
      var message = form.querySelector("#field-message");
      var agree = form.querySelector("#field-agree");

      if (!name.value.trim()) {
        setFieldError(name, "請填寫姓名");
        valid = false;
      } else {
        setFieldError(name, "");
      }

      if (!email.value.trim()) {
        setFieldError(email, "請填寫 email");
        valid = false;
      } else if (!emailPattern.test(email.value.trim())) {
        setFieldError(email, "email 格式看起來不對，請確認（例如 name@example.com）");
        valid = false;
      } else {
        setFieldError(email, "");
      }

      if (!topic.value) {
        setFieldError(topic, "請選擇聯絡主題");
        valid = false;
      } else {
        setFieldError(topic, "");
      }

      if (!message.value.trim()) {
        setFieldError(message, "請填寫訊息內容");
        valid = false;
      } else if (message.value.trim().length < 10) {
        setFieldError(message, "訊息內容至少需要 10 個字，方便我們理解你的問題");
        valid = false;
      } else {
        setFieldError(message, "");
      }

      if (!agree.checked) {
        setFieldError(agree, "請先勾選同意條款才能送出");
        valid = false;
      } else {
        setFieldError(agree, "");
      }

      return valid;
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (successBox) successBox.classList.remove("is-visible");

      if (!validate()) {
        var firstError = form.querySelector(
          ".has-error input, .has-error select, .has-error textarea"
        );
        if (firstError) firstError.focus();
        return;
      }

      form.reset();
      if (successBox) {
        successBox.classList.add("is-visible");
        successBox.focus();
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initCategoryFilter();
    initContactForm();
  });
  document.addEventListener("partials:loaded", initMobileNav);
})();
