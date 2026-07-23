"""
客服助理串流回覆——`GET /api/support/stream?question=...`。本階段新增，
stage5 完全沒有客服功能。

**誠實聲明：這不是真的 AI 客服**。回覆內容是本檔案內寫死的規則式 FAQ 比對
（關鍵字命中哪一條，就逐字吐出對應的固定回覆），完全沒有呼叫任何外部服務、
沒有任何語言模型——master spec 規定本課程「全本地端，不得呼叫任何需要帳號/
金鑰的雲端服務」。真實產品這裡通常會接 LLM streaming（例如 OpenAI/Anthropic
的 `stream=True` 或 Server-Sent Events 版的 chat completion），**介面（SSE
逐字送出文字）長得完全一樣**——這正是這一課要教的重點：先看懂「串流回覆」
這個 UX 模式本身怎麼做，之後要換成真的接 LLM，前端程式碼一行都不用改，
只需要把後端這支函式裡「規則比對 → 固定字串」換成「呼叫 LLM API → 逐 token
yield」。

## 為什麼用 SSE（Server-Sent Events）不是 WebSocket

這支端點跟 `/ws/*` 系列刻意選了不同的技術，用意是讓學員實際比較兩者：

| | WebSocket | SSE |
|---|---|---|
| 資料流向 | 雙向（伺服器 ↔ 瀏覽器都能主動送） | 單向（只有伺服器 → 瀏覽器） |
| 協定 | 獨立協定，需要 handshake upgrade | 就是一個普通的 HTTP GET，`Content-Type: text/event-stream` |
| 瀏覽器 API | `WebSocket`，需要自己處理重連 | `EventSource`，瀏覽器原生支援自動重連 |
| 穿透代理/防火牆 | 部分環境會擋（企業防火牆常擋非 80/443 的協定升級） | 就是 HTTP，幾乎不會被擋 |
| 本專案用途 | 訂單事件推播（雙向的「連線」概念，需要知道誰連上了） | 客服逐字回覆（單次請求、單次回覆流，回完就結束） |

**這一課的教學判斷準則**：如果你的需求是「伺服器主動、持續推播多筆不同事件
給一個保持開啟的連線」（例如訂單狀態），選 WebSocket；如果是「針對這一次的
請求，把原本會一次回傳的內容改成分批慢慢吐出來」（例如聊天回覆、進度條），
SSE 通常更簡單、更輕量，不需要處理連線生命週期。完整比較與循序圖見
docs/REALTIME.md。
"""

import asyncio
import json
import re
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/support", tags=["support"])

# 規則式 FAQ 資料庫——(比對用的關鍵字 tuple, 回覆全文)。比對時由上到下找第一個
# 「question 裡有出現任一關鍵字」的條目；都沒命中就回預設的「轉真人客服」訊息。
# 這份清單刻意簡短（5 條），教學重點不是做出一個聰明的客服，而是示範串流機制本身。
FAQ_RULES: list[tuple[tuple[str, ...], str]] = [
    (
        ("出貨", "多久到", "配送", "運送"),
        "訂單付款成功後，我們通常會在 1 到 2 個工作天內出貨，出貨後依配送地區約 1 到 3 天送達。"
        "你可以在「我的訂單」頁面即時看到出貨狀態，出貨後也會透過即時通知提醒你。",
    ),
    (
        ("退貨", "退款", "取消訂單"),
        "訂單狀態還是「待付款」的時候，可以自行在訂單頁按「取消訂單」。"
        "已經付款的訂單目前需要由店家後台協助取消，退款流程本課程沒有實作，"
        "真實產品這裡通常會串金流服務商的退款 API。",
    ),
    (
        ("庫存", "補貨", "沒貨", "缺貨"),
        "商品頁如果顯示「補貨中」代表目前庫存是 0，我們沒有提供到貨通知訂閱功能，"
        "建議你過幾天再回來看看，或是先選購其他有現貨的商品。",
    ),
    (
        ("付款", "付款失敗", "刷卡", "信用卡"),
        "結帳頁面使用的是模擬付款，測試卡號 4000 0000 0000 0002 會固定模擬付款失敗，"
        "其餘卡號一律視為成功。如果你的訂單顯示「付款失敗」，可以在訂單頁重新嘗試付款。",
    ),
    (
        ("咖啡豆", "豆子", "淺焙", "深焙", "中焙"),
        "淺焙保留較多果酸與花果香、中焙有明顯的堅果與焦糖甜感、深焙走煙燻可可與厚實醇度，"
        "如果不確定怎麼選，「沖沖經典綜合豆」是店內招牌配方，適合每天手沖不挑豆。",
    ),
]

FALLBACK_REPLY = "不好意思，這個問題我還沒學會回答。你可以換個方式描述，或是透過頁尾的聯絡方式找真人客服協助。"


def _match_reply(question: str) -> str:
    for keywords, reply in FAQ_RULES:
        if any(keyword in question for keyword in keywords):
            return reply
    return FALLBACK_REPLY


def _split_into_chunks(text: str) -> list[str]:
    """把回覆文字切成一小段一小段，模擬「逐字／逐詞吐出」的打字機效果。

    用中文標點（，。！？、）當斷點切成短句，而不是逐字元切——逐字元對中文來說
    切得太細碎（每個字都要一次網路事件，SSE 事件數量會多到沒有必要），照標點
    切出來的短句長度剛好能在前端做出流暢的打字機動畫，同時事件數量合理。
    """
    pieces = re.split(r"(?<=[，。！？、])", text)
    return [piece for piece in pieces if piece]


async def _stream_reply(question: str) -> AsyncGenerator[str, None]:
    reply = _match_reply(question)
    chunks = _split_into_chunks(reply)
    for chunk in chunks:
        yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
        # 教學用的人工延遲，模擬「逐字生成」的節奏感——真的接 LLM streaming 時，
        # 這個延遲會被「等待下一個 token 從模型吐出來」的真實延遲取代，不需要
        # 自己手動 sleep。120ms 是刻意調過、在課堂 demo 看起來夠像打字、又不會
        # 讓一則幾句話的回覆等超過兩三秒的數字，沒有更嚴謹的來源。
        await asyncio.sleep(0.12)
    # 用一個獨立的 `[DONE]` 事件標記整段回覆結束，前端看到這個字串就知道可以
    # 停止「顯示輸入中...」的動畫了，不用去猜測「網路只是暫時卡頓」還是
    # 「後端真的講完了」。這是仿照多數 LLM streaming API（例如 OpenAI）的慣例。
    yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"


@router.get("/stream")
async def support_stream(question: str = Query(min_length=1, max_length=200)) -> StreamingResponse:
    return StreamingResponse(
        _stream_reply(question),
        media_type="text/event-stream",
        headers={
            # SSE 回應不應該被任何中間層（反向代理、瀏覽器）快取或緩衝——
            # 沒有這個 header，某些代理伺服器會把整個回應緩衝完才一次送出，
            # 前端就完全看不到「逐字」的效果，整段話會一次全部跳出來。
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
