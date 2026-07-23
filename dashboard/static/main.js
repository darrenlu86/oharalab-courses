"use strict";

/**
 * dashboard/static/main.js — 唯讀 Dashboard 前端邏輯。
 *
 * 做什麼：
 *     頁面載入後平行呼叫四支 API（/api/summary、/api/prices、/api/news、
 *     /api/supply-chain），把回傳的 JSON 組成畫面：版頭股價摘要、收盤價
 *     折線圖、成交量長條圖、新聞列表、供應鏈三欄卡片、頁尾資料狀態。
 *
 * 為什麼四支 API 各自獨立 try/catch、互不影響：
 *     其中一支 API 失敗（例如新聞爬蟲還沒跑過、/api/news 回傳空清單，
 *     或極端情況下網路請求失敗），不該讓整頁「當機」看不到任何東西——
 *     股價圖表、資料狀態應該照樣顯示。這是唯讀 Dashboard 的基本原則：
 *     單一資料來源的問題，不該擴散成整頁故障。
 *
 * 注意（初學者常見誤解）：
 *     `fetch()` 只有在「網路層級」失敗（例如伺服器完全連不上）才會讓
 *     `.catch()` 接到；HTTP 4xx/5xx 不會自動變成例外，`response.ok` 才是
 *     要自己檢查的地方——這就是為什麼下面的 fetchJSON() 要手動判斷
 *     `response.ok` 再決定要不要丟出錯誤。
 */

// 查詢參數固定指向台積電（2330），呼應版頭「台積電（2330）」——
// 本教學專案資料庫目前只收錄這一檔股票。
const DEFAULT_SYMBOL = "2330";
const DEFAULT_DAYS = 90;
const DEFAULT_NEWS_LIMIT = 30;

// 圖表顏色：直接照抄 dataviz skill palette.md 的 light-mode 已驗證值，
// 不自創色。slot 1（blue）給收盤價折線圖，slot 2（orange）給成交量長條圖——
// 兩張圖是分開顯示的獨立圖表，不是同一張圖裡的兩個系列疊在一起比較。
const COLOR_SERIES_PRICE = "#2a78d6";
const COLOR_SERIES_VOLUME = "#eb6834";
const COLOR_GRID = "#e1e0d9"; // gridline（hairline，recessive，不搶眼）
const COLOR_AXIS = "#c3c2b7"; // baseline / axis
const COLOR_TEXT_PRIMARY = "#0b0b0b";
const COLOR_TEXT_MUTED = "#898781";

document.addEventListener("DOMContentLoaded", () => {
  // 四個區塊各自獨立載入，任何一個失敗都不影響其他三個。
  loadSummary();
  loadPrices();
  loadNews();
  loadSupplyChain();
});

/**
 * 對指定 URL 發 GET 請求並解析成 JSON；HTTP 非 2xx 時主動丟出錯誤，
 * 讓呼叫端的 try/catch 可以統一處理「這支 API 讀取失敗」的情況。
 */
async function fetchJSON(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`API 回應異常：${url}（狀態碼 ${response.status}）`);
  }
  return response.json();
}

// ---------------------------------------------------------------------------
// 頁尾「資料狀態」小字 ＋ 版頭最後更新時間
//
// 為什麼原本的四張統計卡片改成頁尾一行文字：這是「股票評價網」改版的一部分
// ——投資人打開頁面第一眼該看到的是股價（見版頭 .price-summary），各表筆數
// 只是教學專案想留給學員確認「爬蟲到底寫進了多少筆」的除錯資訊，不該佔用
// 版面最顯眼的位置，所以降級成頁尾小字。
// ---------------------------------------------------------------------------
async function loadSummary() {
  const lastUpdatedEl = document.getElementById("last-updated");
  try {
    const summary = await fetchJSON("/api/summary");
    renderDataStatus(summary);
    lastUpdatedEl.textContent = formatLastUpdated(summary);
  } catch (err) {
    console.error("讀取 /api/summary 失敗：", err);
    lastUpdatedEl.textContent = "讀取失敗，請確認 Dashboard 伺服器是否正常。";
    const statusEl = document.getElementById("data-status");
    statusEl.textContent = "資料狀態讀取失敗，請確認 Dashboard 伺服器是否正常。";
  }
}

/** 把 /api/summary 的四個表筆數組成頁尾一行文字，例如：
 *  「資料狀態：股票 1 筆・每日股價 56 筆・新聞 12 筆・供應鏈公司 84 筆」。
 *  純數字組字串，不含任何來自外部資料源的自由文字，不需要 escapeHtml。 */
function renderDataStatus(summary) {
  const parts = [
    `股票 ${summary.stocks} 筆`,
    `每日股價 ${summary.daily_prices} 筆`,
    `新聞 ${summary.news} 筆`,
    `供應鏈公司 ${summary.supply_chain} 筆`,
  ];
  const statusEl = document.getElementById("data-status");
  statusEl.textContent = `資料狀態：${parts.join("・")}`;
}

/**
 * 把 UTC ISO8601 時間字串（如 "2026-07-22T13:00:03Z"，格式見
 * crawlers/news_crawler.py 的 _to_iso_utc()）轉成「台北時間」友善格式
 * （YYYY-MM-DD HH:mm 台北時間）。
 *
 * 為什麼要在顯示層做時區轉換，而不是資料庫存的時候就先轉好：
 *     資料庫（news.published_at 欄位）一律存 UTC，這是後端資料儲存的通用
 *     慣例——不管以後有誰、從哪個時區打開這個 Dashboard，資料庫裡存的都是
 *     同一個絕對時間點，不會因為「存的當下是哪個時區」而有兩種答案。
 *     「要用哪個時區顯示給人看」屬於顯示層的責任，所以轉換動作放在前端，
 *     而且明確指定 `timeZone: "Asia/Taipei"`，不依賴瀏覽器的預設時區——
 *     本教學專案的目標使用者（台股投資人）固定用台北時間思考，不該因為
 *     使用者電腦設定的時區不同，就看到不同的顯示時間。
 */
function formatTaipeiDateTime(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return isoString;
  }
  const parts = new Intl.DateTimeFormat("zh-TW", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const get = (type) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")} 台北時間`;
}

/**
 * 版頭要顯示「最後更新時間」，但 /api/summary 回傳的是兩個獨立欄位
 * （latest_trade_date 股價、latest_news_at 新聞），基準不一樣：
 *     - latest_trade_date 只是「交易日期」（如 "2026-07-02"），本身沒有
 *       時分秒，代表的是台灣證交所的某個交易日，不是一個精確時間點——
 *       所以這裡不對它做時區轉換（沒有時間可轉），直接顯示日期字串即可，
 *       避免 `new Date("2026-07-02")` 被當成「當天 UTC 00:00」，
 *       多轉出一段本來不存在的時間。
 *     - latest_news_at 是完整 UTC 時間戳，用 formatTaipeiDateTime() 轉成
 *       台北時間顯示，不然學員直接看 UTC 字串容易誤判新聞發布的時段。
 *
 * 做法：兩者都存在時，比較兩者代表的時間點，取「比較新」的那一個顯示，
 * 並標註是哪一種資料的更新時間，避免把不同精度的字串混在一起顯示造成誤解。
 * 兩者都沒有（資料庫全空）時，顯示提示訊息而不是空白或 "null"。
 */
function formatLastUpdated(summary) {
  const candidates = [];
  if (summary.latest_trade_date) {
    candidates.push({
      display: `${summary.latest_trade_date}（股價）`,
      // sortKey 只用來跟 latest_news_at 比較新舊，不會拿去顯示。
      sortKey: new Date(`${summary.latest_trade_date}T00:00:00Z`),
    });
  }
  if (summary.latest_news_at) {
    candidates.push({
      display: `${formatTaipeiDateTime(summary.latest_news_at)}（新聞）`,
      sortKey: new Date(summary.latest_news_at),
    });
  }

  if (candidates.length === 0) {
    return "尚無資料，請先執行爬蟲（venv/bin/python scripts/run_all_crawlers.py）。";
  }

  candidates.sort((a, b) => b.sortKey - a.sortKey);
  return `最後更新：${candidates[0].display}`;
}

// ---------------------------------------------------------------------------
// 股價：版頭股價摘要 ＋ 收盤價折線圖 ＋ 成交量長條圖（分開兩張，單軸，
// 不做雙軸疊圖）。版頭摘要與兩張圖表共用同一支 /api/prices 回應，不另外
// 多發一次請求——最新收盤價與漲跌幅本來就在這份資料的最後一筆裡。
// ---------------------------------------------------------------------------
async function loadPrices() {
  const emptyEl = document.getElementById("prices-empty");
  const chartsEl = document.getElementById("prices-charts");
  try {
    const body = await fetchJSON(`/api/prices?symbol=${DEFAULT_SYMBOL}&days=${DEFAULT_DAYS}`);
    const prices = body.prices || [];

    if (prices.length === 0) {
      emptyEl.classList.remove("hidden");
      chartsEl.classList.add("hidden");
      renderHeaderPriceEmpty();
      return;
    }

    emptyEl.classList.add("hidden");
    chartsEl.classList.remove("hidden");
    renderPriceChart(prices);
    renderVolumeChart(prices);
    // /api/prices 已依 trade_date 遞增排序（見 app.py 的 docstring），
    // 所以陣列最後一筆就是「最新一個交易日」，不需要再自己找最大日期。
    renderHeaderPrice(prices[prices.length - 1]);
  } catch (err) {
    console.error("讀取 /api/prices 失敗：", err);
    emptyEl.textContent = "股價資料讀取失敗，請確認 Dashboard 伺服器是否正常。";
    emptyEl.classList.remove("hidden");
    chartsEl.classList.add("hidden");
    renderHeaderPriceEmpty();
  }
}

/**
 * 把「最新一筆股價」渲染成版頭的大字收盤價＋漲跌額／漲跌幅。
 *
 * 漲跌幅怎麼算：daily_prices.change 欄位的定義是「今日收盤 - 前一交易日
 * 收盤」（見 db/schema_sqlite.sql），所以反推 `close - change` 就能還原
 * 前一交易日收盤價，不需要 API 另外回傳這個欄位或前端自己再查一次前一筆。
 *
 * 顏色（台股慣例「紅漲綠跌」）：見 style.css :root 的 --price-up /
 * --price-down 註解，這裡只負責依漲跌方向套用對應的 class，不在 JS 裡
 * 寫死顏色值——顏色定義集中在 CSS，才不會出現「JS 一份色碼、CSS 一份
 * 色碼」兩邊各自維護、日後改色漏改一邊的情況。
 */
function renderHeaderPrice(latestRow) {
  const priceValueEl = document.getElementById("price-value");
  const priceChangeEl = document.getElementById("price-change");

  const close = latestRow.close;
  if (typeof close !== "number" || Number.isNaN(close)) {
    renderHeaderPriceEmpty();
    return;
  }
  priceValueEl.textContent = formatPrice(close);

  const change = latestRow.change;
  if (typeof change !== "number" || Number.isNaN(change)) {
    // 理論上只有資料庫裡「這檔股票的第一筆交易日」會沒有 change（沒有
    // 前一天可比較），教學專案資料量小，這種情況不算罕見，用中性文字
    // 說明，而不是顯示 "NaN%" 這種對使用者沒意義的訊息。
    priceChangeEl.textContent = "無前一交易日資料可比較";
    priceChangeEl.className = "price-change flat";
    return;
  }

  const previousClose = close - change;
  const percent = previousClose !== 0 ? (change / previousClose) * 100 : null;

  const direction = change > 0 ? "up" : change < 0 ? "down" : "flat";
  const arrow = change > 0 ? "▲" : change < 0 ? "▼" : "－";
  const sign = change > 0 ? "+" : ""; // 負值 toFixed() 本身就會帶「-」，不用再補
  const changeText = `${sign}${change.toFixed(2)}`;
  const percentText =
    percent === null ? "" : ` (${percent > 0 ? "+" : ""}${percent.toFixed(2)}%)`;

  priceChangeEl.textContent = `${arrow} ${changeText}${percentText}`;
  priceChangeEl.className = `price-change ${direction}`;
}

/** 股價資料讀取失敗或資料庫尚無資料時，版頭改顯示中性的預留文字，
 *  不留下「載入中…」卡住不動、或空白看起來像壞掉的畫面。 */
function renderHeaderPriceEmpty() {
  document.getElementById("price-value").textContent = "－－";
  const priceChangeEl = document.getElementById("price-change");
  priceChangeEl.textContent = "尚無股價資料";
  priceChangeEl.className = "price-change flat";
}

/** 股價數字統一格式化成固定兩位小數（如 1015.00），方便跟其他數字對齊。 */
function formatPrice(value) {
  return value.toLocaleString("zh-TW", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function renderPriceChart(prices) {
  const ctx = document.getElementById("price-chart").getContext("2d");
  new Chart(ctx, {
    type: "line",
    data: {
      labels: prices.map((row) => row.trade_date),
      datasets: [
        {
          label: "收盤價",
          data: prices.map((row) => row.close),
          borderColor: COLOR_SERIES_PRICE,
          backgroundColor: COLOR_SERIES_PRICE,
          borderWidth: 2, // 規範：line 2px
          pointRadius: 0, // thin marks：預設不畫資料點，只留線本身
          pointHoverRadius: 3,
          tension: 0.15,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        // 單一系列不放 legend：圖表標題本身就是這個系列的名稱，
        // 再放一次 legend 是重複資訊。
        legend: { display: false },
        title: {
          display: true,
          text: "收盤價（元）",
          color: COLOR_TEXT_PRIMARY,
          font: { size: 14, weight: "600" },
        },
        // tooltip 用 Chart.js 內建行為即可，不客製樣式。
        tooltip: { enabled: true },
      },
      scales: {
        x: {
          ticks: { color: COLOR_TEXT_MUTED, maxTicksLimit: 8 },
          grid: { color: COLOR_GRID }, // 淺色 recessive grid，不搶過資料線
          border: { color: COLOR_AXIS },
        },
        y: {
          ticks: { color: COLOR_TEXT_MUTED },
          grid: { color: COLOR_GRID },
          border: { color: COLOR_AXIS },
        },
      },
    },
  });
}

function renderVolumeChart(prices) {
  const ctx = document.getElementById("volume-chart").getContext("2d");
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: prices.map((row) => row.trade_date),
      datasets: [
        {
          label: "成交量",
          data: prices.map((row) => row.volume),
          backgroundColor: COLOR_SERIES_VOLUME,
          borderWidth: 0,
          barPercentage: 0.6, // thin marks：長條不整條塞滿類別寬度
          categoryPercentage: 0.7,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: {
          display: true,
          text: "成交量（股）",
          color: COLOR_TEXT_PRIMARY,
          font: { size: 14, weight: "600" },
        },
        tooltip: { enabled: true },
      },
      scales: {
        x: {
          ticks: { color: COLOR_TEXT_MUTED, maxTicksLimit: 8 },
          grid: { display: false }, // 長條圖 x 軸格線容易與長條互相干擾，關閉
          border: { color: COLOR_AXIS },
        },
        y: {
          ticks: { color: COLOR_TEXT_MUTED },
          grid: { color: COLOR_GRID },
          border: { color: COLOR_AXIS },
        },
      },
    },
  });
}

// ---------------------------------------------------------------------------
// 新聞列表
// ---------------------------------------------------------------------------
async function loadNews() {
  const emptyEl = document.getElementById("news-empty");
  const listEl = document.getElementById("news-list");
  try {
    const body = await fetchJSON(`/api/news?symbol=${DEFAULT_SYMBOL}&limit=${DEFAULT_NEWS_LIMIT}`);
    const news = body.news || [];

    if (news.length === 0) {
      emptyEl.classList.remove("hidden");
      listEl.innerHTML = "";
      return;
    }

    emptyEl.classList.add("hidden");
    renderNewsList(news);
  } catch (err) {
    console.error("讀取 /api/news 失敗：", err);
    emptyEl.textContent = "新聞資料讀取失敗，請確認 Dashboard 伺服器是否正常。";
    emptyEl.classList.remove("hidden");
    listEl.innerHTML = "";
  }
}

function renderNewsList(news) {
  const listEl = document.getElementById("news-list");
  listEl.innerHTML = "";
  for (const item of news) {
    const li = document.createElement("li");
    li.className = "news-item";
    const title = item.title || "（無標題）";
    const url = item.url || "#";
    const source = item.source || "未知來源";
    const publishedAt = formatDateTime(item.published_at);
    li.innerHTML = `
      <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(title)}</a>
      <div class="news-meta">${escapeHtml(source)} ・ ${escapeHtml(publishedAt)}</div>
    `;
    listEl.appendChild(li);
  }
}

// ---------------------------------------------------------------------------
// 供應鏈：上／中／下游三欄卡片
// ---------------------------------------------------------------------------
async function loadSupplyChain() {
  const emptyEl = document.getElementById("supply-chain-empty");
  const gridEl = document.getElementById("supply-chain-grid");
  try {
    const body = await fetchJSON(`/api/supply-chain?symbol=${DEFAULT_SYMBOL}`);
    const upstream = body.upstream || [];
    const midstream = body.midstream || [];
    const downstream = body.downstream || [];

    if (upstream.length === 0 && midstream.length === 0 && downstream.length === 0) {
      emptyEl.classList.remove("hidden");
      gridEl.classList.add("hidden");
      return;
    }

    emptyEl.classList.add("hidden");
    gridEl.classList.remove("hidden");
    // 欄標題「上游 150 家」的數字直接取自 API 回傳陣列的長度，不寫死——
    // 供應鏈公司數量會隨爬蟲重新執行而變動，寫死的數字很快就會跟畫面
    // 顯示的實際卡片數量對不上。
    setColumnHeading("upstream-heading", "上游", upstream.length);
    setColumnHeading("midstream-heading", "中游", midstream.length);
    setColumnHeading("downstream-heading", "下游", downstream.length);
    renderCompanyCards("upstream-cards", upstream);
    renderCompanyCards("midstream-cards", midstream);
    renderCompanyCards("downstream-cards", downstream);
  } catch (err) {
    console.error("讀取 /api/supply-chain 失敗：", err);
    emptyEl.textContent = "供應鏈資料讀取失敗，請確認 Dashboard 伺服器是否正常。";
    emptyEl.classList.remove("hidden");
    gridEl.classList.add("hidden");
  }
}

/** 更新供應鏈欄標題文字為「{label} {count} 家」，找不到對應元素時安靜跳過。 */
function setColumnHeading(headingId, label, count) {
  const headingEl = document.getElementById(headingId);
  if (headingEl) {
    headingEl.textContent = `${label} ${count} 家`;
  }
}

function renderCompanyCards(containerId, companies) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";

  if (companies.length === 0) {
    const p = document.createElement("p");
    p.className = "empty-state";
    p.textContent = "此環節尚無資料。";
    container.appendChild(p);
    return;
  }

  for (const company of companies) {
    const div = document.createElement("div");
    div.className = "company-card";
    const name = company.company_name || "（未命名公司）";
    const symbol = company.company_symbol; // 可為 None：未上市公司沒有代號
    const segment = company.segment || "";
    div.innerHTML = `
      <div class="company-name">${escapeHtml(name)}</div>
      <div class="company-meta">${symbol ? escapeHtml(symbol) : "無代號（未上市）"}${segment ? " ・ " + escapeHtml(segment) : ""}</div>
    `;
    container.appendChild(div);
  }
}

// ---------------------------------------------------------------------------
// 共用小工具
// ---------------------------------------------------------------------------

/**
 * 把 ISO8601 時間字串轉成適合閱讀的在地化格式；若字串格式異常（無法被
 * Date 解析），退回顯示原始字串——寧可顯示「看起來怪怪的原始值」，
 * 也不要顯示 "Invalid Date" 這種對使用者沒有意義的訊息。
 */
function formatDateTime(isoString) {
  if (!isoString) {
    return "時間未知";
  }
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return isoString;
  }
  return date.toLocaleString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * 簡易 HTML escape：新聞標題／公司名稱／URL 等文字來自資料庫（最終來自
 * 外部網站），直接用 innerHTML 拼字串前一定要跳脫，避免萬一爬到含有
 * `<script>` 之類字元的內容時被瀏覽器當成 HTML 執行（XSS 風險）。
 *
 * 為什麼還要額外跳脫 `"` 與 `'`（`div.textContent → innerHTML` 這招本身
 * 不會處理引號）：
 *     `div.textContent = value` 再讀 `div.innerHTML` 只會跳脫 `&`、`<`、`>`
 *     這三個在「文字節點內容」裡才有特殊意義的字元。但這個函式的輸出不是
 *     只用在文字節點（如 `<div>${escapeHtml(x)}</div>`），也用在 HTML
 *     屬性值裡（如 `href="${escapeHtml(url)}"`）——雙引號在「屬性值」的
 *     上下文才有特殊意義（用來界定屬性值從哪裡結束），如果不跳脫，一個
 *     含有 `"` 的字串接進 `href="..."` 就能提前結束屬性、注入新的屬性
 *     （例如 `onerror=...`）。目前的資料流（news url 已經過全字串 regex
 *     驗證）走不到這條攻擊路徑，但這是共用工具函式，之後很可能被複製去
 *     處理「沒有經過同樣驗證」的字串，所以在這裡就先補齊，不留這個坑給
 *     未來的自己或其他學員。
 */
function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = String(value);
  return div.innerHTML.replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}
