"""沙盒站的資料載入層：啟動時把 CSV 讀進記憶體,之後每個請求都直接查記憶體。

規模只有幾千列（天氣）加幾千則留言,沒有大到需要資料庫或分頁查詢下推,
啟動時全部讀進來最單純,也最貼近「這是教學工具不是正式服務」的定位。
天氣資料一律讀 `data/raw/*.csv`（真實資料），留言/公告一律讀
`data/synthetic/*.csv`（合成資料）——這條界線刻意保持清楚，不要混著讀。
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.paths import RAW_DIR, SYNTHETIC_DIR  # noqa: E402
from scripts.init_db import DEFAULT_STATIONS  # noqa: E402

# 沙盒站與 scripts/init_db.py 共用同一份測站清單（city, name_zh, lat, lon），
# 避免兩邊各寫一份、以後改一邊忘了改另一邊。
CITY_NAME_ZH: dict[str, str] = {city: name_zh for city, name_zh, _, _ in DEFAULT_STATIONS}
KNOWN_CITIES: list[str] = [city for city, _, _, _ in DEFAULT_STATIONS]

PAGE_SIZE = 50

# 天氣 CSV 的欄位順序（含 date），records 頁表格的欄位順序照這個走，
# 跟 data/raw/*.csv 的 header 一模一樣，方便 stage3 爬蟲直接對應欄位。
WEATHER_COLUMNS = [
    "date",
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "rain_sum",
    "precipitation_hours",
    "windspeed_10m_max",
    "windgusts_10m_max",
    "winddirection_10m_dominant",
    "shortwave_radiation_sum",
]


def _load_stations() -> list[dict]:
    return [
        {"city": city, "name_zh": name_zh, "latitude": lat, "longitude": lon}
        for city, name_zh, lat, lon in DEFAULT_STATIONS
    ]


def _load_weather(raw_dir: Path) -> dict[str, list[dict]]:
    weather: dict[str, list[dict]] = {}
    for city in KNOWN_CITIES:
        csv_path = raw_dir / f"{city}.csv"
        with csv_path.open(newline="", encoding="utf-8") as f:
            weather[city] = list(csv.DictReader(f))
    return weather


def _load_comments(synthetic_dir: Path) -> list[dict]:
    csv_path = synthetic_dir / "comments.csv"
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["rating"] = int(row["rating"])
    return rows


def _load_announcements(synthetic_dir: Path) -> list[dict]:
    csv_path = synthetic_dir / "announcements.csv"
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class SandboxData:
    """把四份 CSV 讀進記憶體的容器,app.py 在啟動時建立一個全域實例。

    做成 class 而不是模組級變數,是為了讓測試可以在需要時建立指向
    tests/fixtures 的獨立實例,不會互相污染（目前測試直接用真實 data/
    目錄即可,但保留這個彈性）。
    """

    def __init__(self, raw_dir: Path = RAW_DIR, synthetic_dir: Path = SYNTHETIC_DIR):
        self.stations = _load_stations()
        self.weather = _load_weather(raw_dir)
        self.comments = _load_comments(synthetic_dir)
        self.announcements = _load_announcements(synthetic_dir)
        self.announcements_by_id = {a["ann_id"]: a for a in self.announcements}

    def weather_for_city(self, city: str) -> list[dict]:
        return self.weather.get(city, [])

    def comments_for_city(self, city: str | None) -> list[dict]:
        if city is None:
            return self.comments
        return [c for c in self.comments if c["city"] == city]


def paginate(items: list, page: int, page_size: int = PAGE_SIZE) -> tuple[list, int]:
    """回傳 (該頁的項目, 總頁數)。page 超出範圍（<1 或 > 總頁數）回傳空清單。

    總頁數至少為 1（即使 items 是空清單，也顯示「第 1 頁 / 共 1 頁」，
    比顯示「共 0 頁」更容易懂）。
    """
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page < 1 or page > total_pages:
        return [], total_pages
    start = (page - 1) * page_size
    return items[start : start + page_size], total_pages
