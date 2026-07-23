"""本腳本產生之留言與公告皆為合成資料，非真實網友內容。

用途：為 stage3_crawler（爬蟲教學）與 stage5_ml_unstructured（情感分類教學）
提供結構固定、規模可控的中文短文本語料，同時餵給 sandbox_site 當作展示內容。
所有留言與公告都是這支腳本用「模板 × 詞彙組合 + 雜訊」硬生生兜出來的，不是
任何人在網路上寫的真心話——這件事在 docs/DATA_SOURCES.md、sandbox_site 每頁
footer、stage5 教案裡都要重複講一次，避免學員誤把它當真實社群文本使用。

生成規則：
- 固定 `SEED = 20260723`（留言用），公告另外用 `SEED + 1` 當種子——兩者都是
  `random.Random(...)` 的獨立實例，不吃 Python 全域 `random` 模組的狀態，
  所以不管在哪台機器、哪個時間點執行，重跑都會得到逐 byte 相同的輸出。
- 留言的 city / date 一定從 `data/raw/*.csv` 裡 2023~2025 年區間的真實觀測值
  取樣，並依當天是雨天／高溫日／舒適日，用不同權重去抽對應語氣的留言
  （雨天多潮濕抱怨、高溫日多炎熱抱怨、舒適日多正面），這是本課程刻意示範
  「合成資料仍可與真實資料建立鬆散關聯」的教學點。
- 內容用「開場語助詞 + 模板 + 語尾標點/語助詞」三段拼接，模板本身依
  （天氣類型, rating）分組、每組 4~6 種寫法，加上開場與語尾各 10 種變化，
  組合空間遠大於 2,400 筆的需求量，逐字重複的內容不會超過 3 次
  （執行時會印出實測統計，不是理論保證）。
- rating 目標分布固定為 1:2:3:4:5 = 8%:12%:15%:35%:30%（2,400 筆對應
  192/288/360/840/720 筆），詳細算法見 `RATING_TARGET_COUNTS`。

執行方式：
    venv/bin/python scripts/generate_synthetic.py

會覆寫 `data/synthetic/comments.csv` 與 `data/synthetic/announcements.csv`。
因為輸出是決定性的（固定 seed），這兩個檔案本來就該是 committed 產物的
唯一來源，重跑只會得到一模一樣的內容，不需要額外備份機制。
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.paths import RAW_DIR, SYNTHETIC_DIR  # noqa: E402

# ---------------------------------------------------------------------------
# 常數
# ---------------------------------------------------------------------------

SEED = 20260723
ANNOUNCEMENT_SEED = SEED + 1  # 公告用獨立的 rng 實例，跟留言的抽樣互不影響

CITIES = ["taipei", "taichung", "kaohsiung"]
CITY_NAME_ZH = {"taipei": "台北", "taichung": "台中", "kaohsiung": "高雄"}

DATE_RANGE_START = "2023-01-01"
DATE_RANGE_END = "2025-12-31"

TOTAL_COMMENTS = 2400
# rating 目標分布 8% / 12% / 15% / 35% / 30%，總數 2400 時剛好都是整數。
RATING_TARGET_COUNTS = {
    1: 192,
    2: 288,
    3: 360,
    4: 840,
    5: 720,
}
assert sum(RATING_TARGET_COUNTS.values()) == TOTAL_COMMENTS

MAX_DUPLICATE_CONTENT = 3
CONTENT_MIN_LEN = 8
CONTENT_MAX_LEN = 60

ANNOUNCEMENT_COUNT = 30

# 天氣分類門檻：跟 stage4 的雨天定義（precipitation_sum >= 1.0mm）一致，
# 高溫/舒適是本階段自訂的教學用門檻，不是氣象局的正式分級。
RAINY_PRECIP_MM = 1.0
HOT_TEMP_C = 33.0
COMFORTABLE_TEMP_RANGE = (22.0, 29.0)

# ---------------------------------------------------------------------------
# 留言用詞彙庫：開場語助詞、語尾標點/語助詞、依（天氣類型, rating）分組的模板
# ---------------------------------------------------------------------------

OPENERS = [
    "",
    "唉,",
    "老實說,",
    "說真的,",
    "欸,",
    "跟你說,",
    "不誇張,",
    "老天鵝,",
    "講真的,",
    "先說,",
]

PARTICLES = [
    "。",
    "!",
    "喔。",
    "耶。",
    "啦。",
    "的說。",
    "……",
    "啊!",
    "唉。",
    "",
]

# 模板內可用的欄位：{city}=城市中文名、{temp}=當天最高溫（一位小數）、
# {particle}=語尾標點/語助詞。所有模板單獨看長度都落在 8~60 字之間，
# 加上開場與語尾之後仍然安全在範圍內（程式仍會逐筆檢查，不是純靠人工估算）。
TEMPLATES: dict[str, dict[int, list[str]]] = {
    "rainy": {
        1: [
            "{city}又下大雨,鞋子襪子全濕透,超級崩潰{particle}",
            "雨下不停,積水淹到小腿,今天有夠倒楣{particle}",
            "騎車滑倒在濕滑路面,痛死了,爛透了{particle}",
            "傘被強風吹爛,全身濕到不行,氣死我了{particle}",
            "{city}排水又不通,整條路都是水,超級誇張{particle}",
        ],
        2: [
            "{city}下雨天出門好麻煩,心情有點差{particle}",
            "濕度太高,衣服都曬不乾,有點煩{particle}",
            "雨勢時大時小,交通變得比較塞{particle}",
            "又忘記帶傘,被淋得有點狼狽{particle}",
        ],
        3: [
            "{city}今天下雨,出門記得帶傘{particle}",
            "雨下得不算大,天氣普普通通{particle}",
            "下雨天沒什麼特別感覺,還好而已{particle}",
        ],
        4: [
            "下雨天在家聽雨聲,感覺還蠻放鬆的{particle}",
            "雨後空氣變清新,{city}的天空滿好看{particle}",
            "難得涼爽的雨天,不用開冷氣挺舒服{particle}",
        ],
        5: [
            "超喜歡下雨天的味道,{city}這場雨舒服極了{particle}",
            "雨中散步別有一番風味,今天心情超好{particle}",
            "終於降溫了,這場雨根本是及時雨,太棒了{particle}",
        ],
    },
    "hot": {
        1: [
            "熱到快中暑,{city}簡直變成大烤箱,受不了{particle}",
            "氣溫飆破{temp}度,曬到皮膚都痛了,誇張{particle}",
            "太陽超毒辣,走五分鐘就滿身大汗,超厭世{particle}",
            "冷氣突然故障遇到這種高溫,快熱死人了{particle}",
        ],
        2: [
            "{city}今天有夠悶熱,出門就開始冒汗,有點煩{particle}",
            "熱到沒什麼胃口,整個人懶洋洋的{particle}",
            "太陽好大,撐傘還是覺得有點喘不過氣{particle}",
        ],
        3: [
            "{city}今天氣溫偏高,出門記得防曬{particle}",
            "天氣熱,不過還算可以忍受{particle}",
        ],
        4: [
            "雖然很熱,但陽光很棒,適合曬棉被{particle}",
            "大熱天正好去海邊玩水,超開心{particle}",
            "{city}豔陽高照,吃碗剉冰消暑心情就變好{particle}",
        ],
        5: [
            "熱是熱,但這種夏天的活力感我超喜歡{particle}",
            "曬得黝黑正好去衝浪,今天超級盡興{particle}",
        ],
    },
    "comfortable": {
        1: [
            "天氣是不錯,但今天諸事不順,心情很差{particle}",
            "溫度剛好,不過塞車塞了一小時,煩死了{particle}",
        ],
        2: [
            "天氣還可以,不過風有點大吹得有點煩{particle}",
            "溫度雖然剛好,紫外線還是偏強,有點在意{particle}",
        ],
        3: [
            "{city}今天天氣普通,沒什麼特別感覺{particle}",
            "氣溫適中,就是平凡的一天{particle}",
        ],
        4: [
            "今天{city}天氣舒服,微風徐徐心情不錯{particle}",
            "溫度剛剛好,適合出門走走,還蠻愉快的{particle}",
            "陽光溫和不刺眼,這種天氣算滿舒服的{particle}",
        ],
        5: [
            "{city}今天根本秋高氣爽,整個人都輕鬆起來{particle}",
            "涼爽宜人的一天,出去野餐超級開心{particle}",
            "這種完美天氣一年沒幾天,超級珍惜{particle}",
        ],
    },
    "ordinary": {
        1: [
            "{city}今天陰陰的,心情也跟著悶悶的{particle}",
            "風有點大又濕冷,出門真的很不舒服{particle}",
            "這種忽冷忽熱的天氣讓人很不耐煩{particle}",
        ],
        2: [
            "天空灰濛濛的,感覺有點提不起勁{particle}",
            "{city}早晚溫差有點大,穿搭很難抓{particle}",
        ],
        3: [
            "{city}今天天氣還好,普普通通而已{particle}",
            "沒什麼特別,平常心看待今天的天氣{particle}",
        ],
        4: [
            "天氣涼涼的很舒服,適合窩在家看書{particle}",
            "{city}今天雲層很美,拍照效果超棒{particle}",
        ],
        5: [
            "微涼的天氣讓人特別有精神,今天過得很棒{particle}",
            "{city}這種舒服的秋涼天,整天心情都很好{particle}",
        ],
    },
}

# 依 rating 決定要優先從哪種天氣類型抽 city/date：雨天/高溫日的權重在負面
# rating 較高，舒適日的權重在正面 rating 較高，體現「留言傾向跟著真實天氣
# 走」這個教學點。權重只影響抽樣機率，不代表這種天氣「只能」對應這個 rating
# ——同一天氣類型底下四種 rating 都有模板，符合「鬆散相關」而非硬規則。
SAMPLING_WEIGHTS: dict[int, dict[str, float]] = {
    1: {"rainy": 5, "hot": 4, "comfortable": 1, "ordinary": 2},
    2: {"rainy": 4, "hot": 3, "comfortable": 1, "ordinary": 2},
    3: {"rainy": 2, "hot": 2, "comfortable": 2, "ordinary": 3},
    4: {"rainy": 1, "hot": 1, "comfortable": 4, "ordinary": 2},
    5: {"rainy": 1, "hot": 1, "comfortable": 5, "ordinary": 2},
}

# ---------------------------------------------------------------------------
# 公告用詞彙庫：30 個固定主題（決定性,不吃 rng）+ 句子池（由 rng 挑選拼成內文）
# ---------------------------------------------------------------------------

ANNOUNCEMENT_TITLES = [
    "網站測試維護通知",
    "系統升級公告",
    "新增留言功能公告",
    "資料回補完成公告",
    "網站介面調整說明",
    "例行資料更新公告",
    "留言規範提醒",
    "測站清單校正公告",
    "API 服務調整公告",
    "使用者意見回饋整理",
    "網站效能優化公告",
    "資料來源說明更新",
    "分頁功能調整公告",
    "公告版面改版說明",
    "教學課程進度公告",
    "測站座標校正說明",
    "網站瀏覽人數統計",
    "資料庫遷移公告",
    "留言星等說明公告",
    "服務條款更新提醒",
    "網站假期維護公告",
    "資料回溯期間說明",
    "系統穩定性報告",
    "新增歷史資料公告",
    "網站色彩與版面微調",
    "留言分頁機制說明",
    "資料保存政策公告",
    "沙盒站教學用途重申",
    "年度資料彙整公告",
    "感謝使用者參與公告",
]
assert len(ANNOUNCEMENT_TITLES) == ANNOUNCEMENT_COUNT

ANNOUNCEMENT_SENTENCE_POOL = [
    "本站為教學示範用途的沙盒氣象站,所有資料僅供課程練習使用。",
    "近期已完成一批歷史天氣資料的校對與補齊作業。",
    "留言功能持續開放,歡迎課程學員實際操作分頁與翻頁測試。",
    "本次公告為教學情境模擬,內容不代表任何真實機關立場。",
    "測站清單維持台北、台中、高雄三個示範城市,座標資料定期核對。",
    "系統已針對頁面載入速度進行例行檢查,目前運作正常。",
    "本站不會主動聯繫留言者,任何私訊要求皆非本站發出。",
    "公告內容由課程講師團隊統一撰寫,供學員練習列表與詳情頁爬取。",
    "近期新增之留言資料為程式生成之合成內容,並非真實網友留言。",
    "本站所有頁面皆遵守 robots.txt 規範,歡迎依禮貌原則進行爬蟲練習。",
    "測試期間如發現資料顯示異常,可回報課程講師協助排查。",
    "本次資料回補涵蓋 2023 年至 2025 年區間,提供更完整的練習素材。",
    "沙盒站的星等評分僅為 1 至 5 的示範數值,不代表實際服務品質。",
    "分頁功能已確認每頁固定顯示五十筆資料,方便練習翻頁邏輯。",
    "本站資料庫定期由課程腳本重新產生,學員可放心重複練習。",
    "感謝各位學員在練習過程中提出的寶貴意見與回報。",
    "本公告列表與詳情頁面專供列表轉詳情的爬蟲教學情境使用。",
    "本站不提供任何真實交易或會員服務,純粹作為程式練習環境。",
    "歷史天氣資料來源為 Open-Meteo 公開歷史氣象 API。",
    "留言與公告皆屬課程合成資料,僅供分析與爬蟲流程練習。",
    "本次版面調整僅涉及顯示排版,資料欄位定義維持不變。",
    "若練習過程中遇到頁面錯誤,歡迎截圖回報以利課程改進。",
    "本站不會出現需要登入或付費才能瀏覽的內容。",
    "所有公告發布時間皆為課程模擬時間,非即時發布。",
    "本站資料每次重新產生時皆會保持相同的隨機種子,方便重複驗證。",
    "感謝大家共同維護良好的練習風氣,請勿將本站生成之合成資料當作真實言論外流。",
    "本站頁尾皆標示教學沙盒身分,提醒使用情境。",
    "近期已針對測站資料表的欄位命名進行文件補充說明。",
    "本次公告亦提醒學員留意合成語料與真實資料的差異。",
    "後續仍會持續依課程進度更新沙盒站內容,敬請期待。",
]

ANNOUNCEMENT_DATE_START = date(2024, 1, 1)
ANNOUNCEMENT_DATE_END = date(2025, 12, 31)


# ---------------------------------------------------------------------------
# 讀真實天氣資料，決定留言的 city/date 抽樣池
# ---------------------------------------------------------------------------


def classify_day(temp_max: float, precip: float) -> str:
    """依當天最高溫與降雨量分成四類天氣類型，決定留言語氣的抽樣權重。"""
    if precip >= RAINY_PRECIP_MM:
        return "rainy"
    if temp_max >= HOT_TEMP_C:
        return "hot"
    if COMFORTABLE_TEMP_RANGE[0] <= temp_max <= COMFORTABLE_TEMP_RANGE[1]:
        return "comfortable"
    return "ordinary"


def load_weather_pool(raw_dir: Path = RAW_DIR) -> list[dict]:
    """讀 data/raw/*.csv,篩出 2023~2025 年區間的列,附上天氣分類。

    回傳的每一筆都是留言可以掛上去的「真實存在的 city+date」,
    這是 SPEC §3.2 要求「city/date 必須真的存在於真實天氣資料」的來源。
    """
    pool: list[dict] = []
    for city in CITIES:
        csv_path = raw_dir / f"{city}.csv"
        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d = row["date"]
                if not (DATE_RANGE_START <= d <= DATE_RANGE_END):
                    continue
                temp_max = float(row["temperature_2m_max"])
                precip = float(row["precipitation_sum"])
                pool.append(
                    {
                        "city": city,
                        "name_zh": CITY_NAME_ZH[city],
                        "date": d,
                        "temp_max": temp_max,
                        "precip": precip,
                        "day_type": classify_day(temp_max, precip),
                    }
                )
    return pool


# ---------------------------------------------------------------------------
# 留言內容生成
# ---------------------------------------------------------------------------


def generate_content(
    rng: Random,
    entry: dict,
    rating: int,
    content_counts: Counter,
    max_attempts: int = 300,
) -> str:
    """依（天氣類型, rating）挑模板,拼上開場/語尾雜訊,回傳一則留言內容。

    會檢查長度落在 8~60 字、且同一字串目前出現次數 < 3 次才接受；
    模板 × 開場 × 語尾的組合空間遠大於單一 cell 的需求量，重試幾次
    內一定能找到符合條件的組合（不是靠運氣，是靠組合數夠大）。
    """
    templates = TEMPLATES[entry["day_type"]][rating]
    temp_str = f"{entry['temp_max']:.1f}"
    content = ""
    for _ in range(max_attempts):
        opener = rng.choice(OPENERS)
        template = rng.choice(templates)
        particle = rng.choice(PARTICLES)
        filled = template.format(city=entry["name_zh"], temp=temp_str, particle=particle)
        content = (opener + filled).strip()
        if (
            CONTENT_MIN_LEN <= len(content) <= CONTENT_MAX_LEN
            and content_counts[content] < MAX_DUPLICATE_CONTENT
        ):
            content_counts[content] += 1
            return content
    # 理論上不會走到這裡（模板×詞彙組合空間遠大於 2400 筆需求量）；
    # 萬一真的撞到，寧可誠實接受重複也不要無限迴圈卡死腳本。
    content_counts[content] += 1
    return content


def generate_comments(pool: list[dict]) -> list[dict]:
    """依 RATING_TARGET_COUNTS 與 SAMPLING_WEIGHTS 抽樣 city/date、生成留言內容。"""
    rng = Random(SEED)

    draws: list[tuple[int, dict]] = []
    for rating in sorted(RATING_TARGET_COUNTS):
        weights = [SAMPLING_WEIGHTS[rating][entry["day_type"]] for entry in pool]
        count = RATING_TARGET_COUNTS[rating]
        sampled = rng.choices(pool, weights=weights, k=count)
        draws.extend((rating, entry) for entry in sampled)

    # 打散順序，避免 CSV 裡整批同一個 rating 連在一起（更像真實留言板的
    # 交錯時間軸），仍然是同一個 rng 實例、決定性洗牌。
    rng.shuffle(draws)

    content_counts: Counter = Counter()
    comments = []
    for idx, (rating, entry) in enumerate(draws, start=1):
        content = generate_content(rng, entry, rating, content_counts)
        comments.append(
            {
                "comment_id": f"c{idx:04d}",
                "city": entry["city"],
                "date": entry["date"],
                "rating": rating,
                "content": content,
            }
        )
    return comments, content_counts


# ---------------------------------------------------------------------------
# 公告內容生成
# ---------------------------------------------------------------------------


def generate_announcement_body(rng: Random) -> str:
    """從句子池挑句子拼接,直到長度落在 100~300 字之間才停止。"""
    body = ""
    last = None
    for _ in range(12):  # 安全上限，避免萬一機率一直不中而卡住
        candidates = [s for s in ANNOUNCEMENT_SENTENCE_POOL if s != last]
        sentence = rng.choice(candidates)
        if len(body) + len(sentence) > 300 and len(body) >= 100:
            break
        body += sentence
        last = sentence
        if len(body) >= 100 and rng.random() < 0.3:
            break
    return body


def generate_announcements() -> list[dict]:
    rng = Random(ANNOUNCEMENT_SEED)
    total_days = (ANNOUNCEMENT_DATE_END - ANNOUNCEMENT_DATE_START).days

    announcements = []
    for idx, title in enumerate(ANNOUNCEMENT_TITLES, start=1):
        body = generate_announcement_body(rng)
        offset = rng.randint(0, total_days)
        published_at = ANNOUNCEMENT_DATE_START + timedelta(days=offset)
        announcements.append(
            {
                "ann_id": f"a{idx:02d}",
                "title": title,
                "body": body,
                "published_at": published_at.isoformat(),
            }
        )
    return announcements


# ---------------------------------------------------------------------------
# 寫檔 + 自我檢查統計
# ---------------------------------------------------------------------------


def write_comments_csv(comments: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["comment_id", "city", "date", "rating", "content"])
        writer.writeheader()
        writer.writerows(comments)


def write_announcements_csv(announcements: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ann_id", "title", "body", "published_at"])
        writer.writeheader()
        writer.writerows(announcements)


def print_self_check(comments: list[dict], content_counts: Counter) -> None:
    """印出留言的自我檢查統計：rating 分布、city 分布、重複內容上限。"""
    total = len(comments)
    print(f"留言總數：{total}")

    print("rating 分布（實測 count / 百分比 / 目標百分比）：")
    rating_counts = Counter(c["rating"] for c in comments)
    target_pct = {1: 8, 2: 12, 3: 15, 4: 35, 5: 30}
    for rating in sorted(rating_counts):
        count = rating_counts[rating]
        pct = count / total * 100
        print(f"  rating={rating}: {count} 筆（{pct:.2f}%，目標 {target_pct[rating]}%）")

    city_counts = Counter(c["city"] for c in comments)
    print("city 分布（實測 count）：")
    for city in CITIES:
        print(f"  {city}: {city_counts.get(city, 0)} 筆")

    max_dup = max(content_counts.values()) if content_counts else 0
    dup_over_limit = [content for content, n in content_counts.items() if n > MAX_DUPLICATE_CONTENT]
    unique_contents = len(content_counts)
    print(f"不重複內容數：{unique_contents}（總筆數 {total}）")
    print(f"單一內容最大重複次數：{max_dup}（上限 {MAX_DUPLICATE_CONTENT}）")
    if dup_over_limit:
        raise AssertionError(
            f"有 {len(dup_over_limit)} 則內容重複超過 {MAX_DUPLICATE_CONTENT} 次，違反 SPEC §3.2"
        )

    lengths = [len(c["content"]) for c in comments]
    print(f"內容長度範圍：{min(lengths)}~{max(lengths)} 字（要求 {CONTENT_MIN_LEN}~{CONTENT_MAX_LEN}）")
    assert min(lengths) >= CONTENT_MIN_LEN and max(lengths) <= CONTENT_MAX_LEN

    rating_values = set(c["rating"] for c in comments)
    assert rating_values <= {1, 2, 3, 4, 5}, f"rating 出現非法值：{rating_values}"


def main() -> None:
    pool = load_weather_pool()
    print(f"真實天氣資料池：{len(pool)} 筆（3 城市 × 2023~2025 年區間）")
    day_type_counts = Counter(e["day_type"] for e in pool)
    print(f"天氣分類分布：{dict(day_type_counts)}")

    comments, content_counts = generate_comments(pool)
    announcements = generate_announcements()

    write_comments_csv(comments, SYNTHETIC_DIR / "comments.csv")
    write_announcements_csv(announcements, SYNTHETIC_DIR / "announcements.csv")

    print("-" * 60)
    print_self_check(comments, content_counts)
    print("-" * 60)
    print(f"公告總數：{len(announcements)}")
    body_lengths = [len(a["body"]) for a in announcements]
    print(f"公告內文長度範圍：{min(body_lengths)}~{max(body_lengths)} 字（要求 100~300）")
    assert min(body_lengths) >= 100 and max(body_lengths) <= 300

    print("-" * 60)
    print(f"已寫入：{SYNTHETIC_DIR / 'comments.csv'}")
    print(f"已寫入：{SYNTHETIC_DIR / 'announcements.csv'}")
    print("本次執行為決定性生成（固定 seed），重跑會得到逐 byte 相同的輸出。")


if __name__ == "__main__":
    main()
