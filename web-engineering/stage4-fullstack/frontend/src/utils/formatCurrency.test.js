import { describe, expect, it } from 'vitest'
import { formatCurrency, formatForeignCurrency } from './formatCurrency'

describe('formatCurrency', () => {
  it('三位數金額直接加上 NT$ 前綴', () => {
    expect(formatCurrency(520)).toBe('NT$520')
  })

  it('四位數以上金額會加上千分位逗號', () => {
    expect(formatCurrency(1580)).toBe('NT$1,580')
  })

  it('會四捨五入成整數（型錄金額規則：一律沒有小數）', () => {
    expect(formatCurrency(520.6)).toBe('NT$521')
  })

  it('0 元也能正確格式化', () => {
    expect(formatCurrency(0)).toBe('NT$0')
  })
})

describe('formatForeignCurrency', () => {
  it('四捨五入成整數，並附上幣別代碼（跟 formatCurrency 一樣不顯示小數）', () => {
    expect(formatForeignCurrency(16.043, 'USD')).toBe('USD 16')
  })

  it('四捨五入進位的情況也正確', () => {
    expect(formatForeignCurrency(20.6, 'JPY')).toBe('JPY 21')
  })

  it('千分位逗號在外幣參考價也生效', () => {
    expect(formatForeignCurrency(1580.2, 'JPY')).toBe('JPY 1,580')
  })
})
