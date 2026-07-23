import { describe, expect, it } from 'vitest'
import { generateOrderId } from './generateOrderId'

describe('generateOrderId', () => {
  it('符合 BG-<8碼大寫英數字> 的格式', () => {
    expect(generateOrderId()).toMatch(/^BG-[A-Z0-9]{8}$/)
  })

  it('連續呼叫多次幾乎不會產生重複編號（隨機性檢查）', () => {
    const ids = new Set(Array.from({ length: 200 }, () => generateOrderId()))
    // 200 次裡如果隨機性夠好，理論上不該有重複；用 Set 去重後長度應該還是 200。
    expect(ids.size).toBe(200)
  })
})
