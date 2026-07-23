# 離線樣本

這裡的三份 `forecast_{city}.json` 是**真實** Open-Meteo forecast API 回應
的原始存檔（未經任何修改），用於 `--offline` 模式與 pytest（測試不連外網，
SPEC §7）。`demo_output.txt` 是 CLI 實際執行一次的完整終端機輸出原文。

## 擷取時間戳

實際執行下列指令取得（`date` 指令輸出，非估計值）：

```
2026-07-24 00:26:51 CST (UTC+0800)
```

取得方式：

```
curl -s "https://api.open-meteo.com/v1/forecast?latitude=25.0330&longitude=121.5654&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,windspeed_10m_max&timezone=Asia/Taipei&forecast_days=2" -o forecast_taipei.json
```

台中、高雄同一批次擷取（座標見 `stage1_api_app/weather_brief.py` 的
`CITY_INFO`），時間戳相同（同一分鐘內連續執行三次 curl）。

## 注意：這是「某一天的預報」快照

`forecast_*.json` 裡的日期是擷取當下的今天/明天（2026-07-24/25），**不會
隨你執行 `--offline` 的時間改變**——這是離線樣本的本質限制：它凍結在
擷取那一刻，不是即時預報。教學上這樣完全足夠（練的是「怎麼解析與呈現
預報資料」，不是「今天到底會不會下雨」），但如果你拿這份樣本的日期去對
現在的真實天氣，兩者當然對不上，這是預期行為不是 bug。

`demo_output.txt` 的擷取時間戳同理：那是「執行 CLI 那一刻」的輸出，往後
重跑 `--offline` 會得到完全相同的文字（因為讀的是同一份 JSON），這也是
`--offline` 模式故意追求的決定性（deterministic）——方便寫測試斷言輸出
內容，不用每次重新產生預期值。
