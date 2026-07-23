"""本地 mock AI 服務：OpenAI Chat Completions 相容格式，規則式回覆生成。

這不是真的大型語言模型——`weather_brief.py` 把天氣預報寫成一段固定格式的
文字丟進來，這支服務用正規表示式把數字（溫度/降雨機率/風速）抽出來，
套進一組 if/else 規則產生穿搭與出行建議。之所以叫它「AI API」而不是直接
叫「規則引擎」，是因為它刻意模仿 OpenAI 的請求/回應格式（`POST
/v1/chat/completions`、`Authorization: Bearer`、`choices[0].message.content`
的回應結構），讓你在完全不用申請帳號、不用付費的情況下，練習「串接一個
OpenAI 相容 API」該長什麼樣子——換成真正的 OpenAI 或任何相容服務（例如
本機跑的 Ollama），理論上只需要換 `base_url` 和 `api_key`，不用改
`weather_brief.py` 呼叫端的程式碼結構。**本課程沒有實際串接任何付費 AI
服務**，這裡的「AI」全部是規則式邏輯。

啟動：
    venv/bin/python -m uvicorn stage1_api_app.mock_ai_server:app --port 8331

驗證 API 金鑰用環境變數 MOCK_AI_API_KEY（未設定時用下面的預設值）。這是
教學用的假金鑰，不是任何真實服務的憑證，可以安全地寫進版控——正式專案的
API 金鑰應該一律走環境變數，絕對不要複製這個模式去存真的金鑰。
"""

from __future__ import annotations

import os
import re
import time
import uuid

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Mock AI Server（OpenAI Chat Completions 相容格式）")

# 教學用假金鑰，不是任何真實服務的憑證。正式專案請改讀 .env 且不要 commit 真金鑰。
DEFAULT_API_KEY = "mock-weather-advisor-demo-key"


def _expected_api_key() -> str:
    return os.environ.get("MOCK_AI_API_KEY", DEFAULT_API_KEY)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]


# --- 規則式回覆邏輯 ---------------------------------------------------------

TODAY_PATTERN = re.compile(
    r"今天.*?最高溫\s*([\-\d.]+)\s*度.*?最低溫\s*([\-\d.]+)\s*度"
    r".*?降雨機率\s*(\d+)%.*?最大風速\s*([\d.]+)\s*km/h"
)
TOMORROW_PATTERN = re.compile(
    r"明天.*?最高溫\s*([\-\d.]+)\s*度.*?最低溫\s*([\-\d.]+)\s*度"
    r".*?降雨機率\s*(\d+)%.*?最大風速\s*([\d.]+)\s*km/h"
)


def _rain_advice(pop: int) -> str:
    if pop >= 60:
        return f"降雨機率高達 {pop}%，出門務必攜帶雨具，安排戶外行程建議改期或準備備案。"
    if pop >= 30:
        return f"降雨機率中等（{pop}%），建議隨身帶一把折疊傘備用，不用取消戶外計畫。"
    return f"降雨機率偏低（{pop}%），基本上不需要特別準備雨具。"


def _clothing_advice(tmax: float, tmin: float) -> str:
    if tmax >= 32:
        return f"最高溫達 {tmax:.1f} 度，天氣炎熱，建議穿著透氣輕便衣物，注意防曬與補充水分。"
    if tmax <= 18:
        return f"最高溫僅 {tmax:.1f} 度，天氣偏冷，建議加件保暖外套，早晚溫差大（最低溫 {tmin:.1f} 度）要留意。"
    return f"氣溫落在舒適範圍（{tmin:.1f}~{tmax:.1f} 度），一般春秋裝即可，不需要特別加減衣物。"


def _wind_advice(wind: float) -> str:
    if wind >= 30:
        return f"風勢偏大（最大陣風 {wind:.1f} km/h），機車族請留意側風，戶外請小心招牌與盆栽掉落。"
    return ""


def generate_advice(user_message: str) -> str:
    """從固定格式的天氣描述文字裡抽數字、套規則，回傳一段建議文字。

    如果收到的文字不是預期格式（正規表示式抽不到今天的數據），回傳一段
    誠實說明「看不懂格式」的訊息，而不是假裝理解後亂回答——這是刻意的
    教學設計：mock 服務的能力邊界要對學員可見，不要用看起來合理的
    萬用回覆掩蓋掉「其實沒讀懂輸入」這件事。
    """
    today_match = TODAY_PATTERN.search(user_message)
    if today_match is None:
        return (
            "看起來這則訊息不是本服務認得的天氣預報格式（需包含「今天」"
            "「最高溫」「最低溫」「降雨機率」「最大風速」等欄位），"
            "無法生成具體建議。這是規則式 mock 服務的已知限制，不是真正的語言模型。"
        )

    tmax, tmin, pop, wind = today_match.groups()
    tmax, tmin, wind = float(tmax), float(tmin), float(wind)
    pop = int(pop)

    parts = [_rain_advice(pop), _clothing_advice(tmax, tmin)]
    wind_note = _wind_advice(wind)
    if wind_note:
        parts.append(wind_note)

    tomorrow_match = TOMORROW_PATTERN.search(user_message)
    if tomorrow_match is not None:
        t_tmax, _, t_pop, _ = tomorrow_match.groups()
        t_tmax, t_pop = float(t_tmax), int(t_pop)
        delta = t_tmax - tmax
        if abs(delta) >= 3:
            direction = "明顯回暖" if delta > 0 else "明顯轉涼"
            parts.append(f"提醒一下，明天最高溫會{direction}（{tmax:.1f} → {t_tmax:.1f} 度），提前準備衣物。")
        if t_pop >= 60 and pop < 60:
            parts.append(f"另外明天降雨機率會跳到 {t_pop}%，記得帶傘出門備用。")

    return " ".join(parts)


@app.post("/v1/chat/completions")
def chat_completions(
    body: ChatCompletionRequest,
    authorization: str | None = Header(default=None),
):
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 Authorization: Bearer <api_key> 標頭")

    provided_key = authorization.removeprefix("Bearer ").strip()
    if provided_key != _expected_api_key():
        raise HTTPException(status_code=401, detail="API 金鑰不正確")

    user_messages = [m for m in body.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="messages 裡至少要有一則 role=user 的訊息")

    advice = generate_advice(user_messages[-1].content)

    # 回應結構照抄 OpenAI Chat Completions API：id/object/created/model/choices/usage。
    return {
        "id": f"chatcmpl-mock-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": advice},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(user_messages[-1].content),
            "completion_tokens": len(advice),
            "total_tokens": len(user_messages[-1].content) + len(advice),
        },
    }
