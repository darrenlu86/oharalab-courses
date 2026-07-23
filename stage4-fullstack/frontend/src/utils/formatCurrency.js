// 金額格式化：全站金額一律是整數 NT$（型錄本身沒有小數），
// 這支函式負責統一加上千分位逗號與 NT$ 前綴，教學重點是「別把格式邏輯散落在每個元件裡」。
//
// 為什麼不用 Intl.NumberFormat('zh-TW', { style: 'currency', currency: 'TWD' })：
// 這個內建格式在多數瀏覽器會把 TWD 當成一般貨幣輸出到小數點兩位（NT$520.00），
// 但我們的商品型錄金額規則是「一律整數」，用內建 currency style 還要再處理小數位數，
// 不如直接用千分位格式化＋自己接前綴字串，行為完全可控。
export function formatCurrency(amount) {
  const rounded = Math.round(Number(amount))
  return `NT$${rounded.toLocaleString('zh-TW')}`
}

// 外幣參考價：全站金額顯示規則統一「一律整數、不顯示小數」，外幣換算結果也四捨五入成整數，
// 跟 formatCurrency 的整數規則保持一致——這裡只是「參考價」，不是真的用外幣結帳，
// 顯示到個位數已經足夠讓使用者知道大概是多少錢，不需要到小數點後兩位那麼精確。
export function formatForeignCurrency(amount, currencyCode) {
  const rounded = Math.round(Number(amount))
  return `${currencyCode} ${rounded.toLocaleString('zh-TW')}`
}
