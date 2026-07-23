// 分類代碼 -> 中文顯示名稱。集中放這裡，元件不用各自寫死對照表。
export const CATEGORY_LABELS = {
  beans: '咖啡豆',
  drip: '掛耳包',
  gear: '沖煮器具',
  cups: '杯具',
  gift: '禮盒',
}

export const CATEGORY_ORDER = ['beans', 'drip', 'gear', 'cups', 'gift']

export function categoryLabel(code) {
  return CATEGORY_LABELS[code] ?? code
}
