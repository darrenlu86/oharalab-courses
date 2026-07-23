"""stage5_ml_unstructured：非結構型資料分析（AI-11）。

案例 A（文字）：天氣留言情感二元分類，`text_features.py` + `train_text.py`
+ `predict_text.py`。案例 B（影像）：sklearn `load_digits` 手寫數字辨識，
`train_digits.py`。細節見 stage5_ml_unstructured/README.md。

**重要提醒（全課程反覆強調）**：案例 A 用的留言語料是
`scripts/generate_synthetic.py`（seed 20260723）生成的合成資料，
不是真實網友留言。用合成語料訓練出來的模型效能數字必然偏樂觀——模型學到
的是生成模板的規律，不是真實語言的複雜度，不能外推到真實社群文本上的
表現。
"""
