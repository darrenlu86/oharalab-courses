/*
 * include.js — 共用元件載入機制（三種做法之一：JS fetch include）
 *
 * 為什麼選這個做法：見 docs/ARCHITECTURE.md 完整比較。
 * 簡單說：比「每頁複製貼上」好維護（改 header 只要改一個檔案），
 * 又不需要引入建置工具（stage3 才需要）。
 *
 * 已知限制（這是本階段要教的重點，不是 bug）：
 * 用 file:// 直接雙擊開啟 html 檔案時，瀏覽器會因為安全限制擋掉 fetch 讀取本機檔案，
 * header/footer 會整塊消失或顯示錯誤訊息。必須在 stage2-multipage/ 目錄下執行
 * `python3 -m http.server 8082`，改用 http://localhost:8082 開啟才會正常。
 */
(function () {
  "use strict";

  function highlightCurrentNav(root) {
    var current = location.pathname.split("/").pop() || "index.html";
    var links = root.querySelectorAll(".main-nav a");
    links.forEach(function (link) {
      var href = link.getAttribute("href");
      if (href === current) {
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
    });
  }

  function loadInclude(el) {
    var file = el.getAttribute("data-include");
    return fetch(file)
      .then(function (res) {
        if (!res.ok) {
          throw new Error("讀取 " + file + " 失敗：HTTP " + res.status);
        }
        return res.text();
      })
      .then(function (html) {
        el.outerHTML = html;
      })
      .catch(function (err) {
        el.innerHTML =
          '<p style="padding:1rem;color:#a13333;">共用元件載入失敗（' +
          file +
          "）。請確認網站是用 <code>python3 -m http.server</code> 這類本地伺服器開啟，而不是直接雙擊 html 檔案。</p>";
        console.error(err);
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var targets = Array.from(document.querySelectorAll("[data-include]"));
    Promise.all(targets.map(loadInclude)).then(function () {
      highlightCurrentNav(document);
      document.dispatchEvent(new CustomEvent("partials:loaded"));
    });
  });
})();
