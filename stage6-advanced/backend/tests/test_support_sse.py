"""
測試 `GET /api/support/stream`——SSE 客服助理串流回覆。

`TestClient` 對串流回應（`StreamingResponse`）的處理方式是把整個回應體一次
讀完（測試環境不像真的瀏覽器會一邊收一邊畫面更新），所以這裡驗證的重點是
「整段 SSE payload 的格式對不對」（`data: ...` 開頭、逐塊都是合法 JSON、
以 `{"done": true}` 結尾），而不是真的驗證「逐字送達的節奏」——節奏（`asyncio.sleep`）
只有真的用瀏覽器 EventSource 連線才感受得到，這裡誠實標示這個測試涵蓋不到
的部分。
"""

import json

from fastapi.testclient import TestClient


def _parse_sse_events(raw_text: str) -> list[dict]:
    events = []
    for block in raw_text.strip().split("\n\n"):
        if not block.startswith("data: "):
            continue
        payload = block.removeprefix("data: ")
        events.append(json.loads(payload))
    return events


def test_support_stream_missing_question_returns_422(client: TestClient):
    resp = client.get("/api/support/stream")
    assert resp.status_code == 422


def test_support_stream_shipping_question_returns_matching_faq(client: TestClient):
    resp = client.get("/api/support/stream", params={"question": "請問多久到貨？"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse_events(resp.text)
    assert len(events) >= 2  # 至少一段內容 chunk + 結尾的 done 事件
    assert events[-1] == {"done": True}

    full_reply = "".join(event["chunk"] for event in events if "chunk" in event)
    assert "工作天" in full_reply


def test_support_stream_unmatched_question_returns_fallback(client: TestClient):
    resp = client.get("/api/support/stream", params={"question": "今天台北天氣如何"})
    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    full_reply = "".join(event["chunk"] for event in events if "chunk" in event)
    assert "還沒學會回答" in full_reply


def test_support_stream_no_login_required(client: TestClient):
    # 客服串流刻意不需要登入（訪客也可能想先問問題再決定要不要下單），
    # 這裡沒有帶任何 Authorization header 也應該正常回應 200。
    resp = client.get("/api/support/stream", params={"question": "可以退貨嗎"})
    assert resp.status_code == 200
