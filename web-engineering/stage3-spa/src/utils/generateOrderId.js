// 訂單編號規則：BG-<8碼大寫英數字>，例如 BG-7K2QX9F1。
// 這是「純前端 mock 訂單」的編號產生器，教學重點：
// 為什麼不用遞增序號（1, 2, 3...）？因為訂單存在使用者自己瀏覽器的 localStorage，
// 不同人的瀏覽器互相看不到彼此的資料，遞增序號在單一裝置上不會撞號，
// 但拿掉「這是本機 mock」的前提就會出錯 —— 真實後端（stage4 起）才會由資料庫保證全域唯一性。
const CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

export function generateOrderId() {
  let suffix = ''
  for (let i = 0; i < 8; i += 1) {
    suffix += CHARS[Math.floor(Math.random() * CHARS.length)]
  }
  return `BG-${suffix}`
}
