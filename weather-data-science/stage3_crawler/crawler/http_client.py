"""爬蟲共用的 HTTP 用戶端：表明身分的 User-Agent、可設定的禮貌延遲、逾時、重試。

這支模組刻意抽出來獨立,是因為「怎麼有禮貌地打一個網站」跟「怎麼解析
這個網站的 HTML」是兩個不同的關注點——五支關卡爬蟲都共用同一份禮貌延遲
與重試邏輯,不要各自重寫一份（也不會有些關卡忘記加延遲）。

真實網站的爬蟲禮儀最低限度要做到：
1. User-Agent 表明自己是爬蟲、附聯絡方式（方便對方在你造成問題時聯絡你）。
2. 檢查並遵守 robots.txt（見 `check_robots_allowed`）。
3. 請求之間加延遲,不要對伺服器造成瞬間高流量。
4. 逾時與重試要有上限,不要無限重試造成對方負擔。

本課程的沙盒站（sandbox_site）本身不會因為爬得快而抗議,但這裡的禮貌延遲
是刻意示範給「以後要爬真實網站」的你看的,不要因為練習對象是自己人就
養成省略這一步的習慣。
"""

from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urljoin

import requests

USER_AGENT = "weather-course-crawler/1.0 (+teaching sandbox crawler; contact: kevin868686@gmail.com)"

DEFAULT_TIMEOUT = 10.0
DEFAULT_DELAY_SECONDS = 0.2
MAX_RETRIES = 2


class PoliteSession:
    """包住 `requests.Session`，每次 GET 之後 sleep 一段禮貌延遲，
    帶自我表明身分的 User-Agent，失敗時重試（逾時/連線錯誤/5xx）。
    """

    def __init__(
        self,
        base_url: str,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        self.base_url = base_url.rstrip("/")
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.request_count = 0

    def get(self, path: str, params: dict | None = None) -> requests.Response:
        """GET `base_url + path`，失敗重試最多 max_retries 次，成功後 sleep
        `delay_seconds` 再回傳（禮貌延遲放在回傳前，確保呼叫端拿到結果和
        「已經等過一輪」是同一時間點,呼叫端不需要自己再插入 sleep)。
        """
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                self.request_count += 1
                resp.raise_for_status()
                if self.delay_seconds > 0:
                    time.sleep(self.delay_seconds)
                return resp
            except (requests.RequestException,) as exc:
                last_error = exc
                if attempt <= self.max_retries:
                    time.sleep(0.5)
        raise RuntimeError(f"GET {url} 失敗，已重試 {self.max_retries} 次：{last_error}")

    def close(self) -> None:
        self.session.close()


def check_robots_allowed(base_url: str, paths: list[str], user_agent: str = USER_AGENT) -> dict[str, bool]:
    """抓 base_url/robots.txt，回傳 {path: 是否允許爬取} 的字典。

    示範「爬之前先檢查 robots.txt」這個禮儀——沙盒站的 robots.txt 允許
    全部路徑（`Allow: /`），真實網站通常會限制更多,爬蟲上線前都應該過
    這一關,不能因為練習對象寬鬆就跳過這個檢查步驟。
    """
    parser = urllib.robotparser.RobotFileParser()
    robots_url = urljoin(base_url.rstrip("/") + "/", "robots.txt")
    parser.set_url(robots_url)
    parser.read()
    return {path: parser.can_fetch(user_agent, path) for path in paths}


def parse_robots_txt(text: str, paths: list[str], user_agent: str = USER_AGENT) -> dict[str, bool]:
    """跟 check_robots_allowed 一樣的判斷邏輯，但直接吃 robots.txt 內容字串
    （不連網路），給測試用固定樣本驗證解析邏輯是否正確。
    """
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(text.splitlines())
    return {path: parser.can_fetch(user_agent, path) for path in paths}
