// 跟 frontend/src/utils/formatCurrency.js 同一套規則：金額一律整數 NT$，理由見
// 該檔案的註解，這裡不重複展開。
export function formatCurrency(amount) {
  const rounded = Math.round(Number(amount))
  return `NT$${rounded.toLocaleString('zh-TW')}`
}
