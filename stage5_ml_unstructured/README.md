# stage5_ml_unstructured — 非結構型資料分析（AI-11）

## 這一關在教什麼

前面 stage4 處理的是「本來就是表格」的結構化資料，這一關要處理「一段文字」
「一張圖片」這種本身沒有固定欄位的非結構化資料——怎麼把它們變成模型看得懂
的數值向量，以及傳統機器學習（TF-IDF + LogisticRegression）跟神經網路
（MLPClassifier）在小規模資料上到底差多少。

## 你會學到

- 中文斷詞（jieba）+ TF-IDF 怎麼把一句話變成一個數值向量。
- **合成語料的隱藏陷阱**：同一份資料如果訓練/測試集切分不當（沒有先去
  重），分數會嚴重虛高——本階段開發時真的踩到這個坑（見「注意」）。
- 神經網路（MLPClassifier）跟傳統模型（LogisticRegression）不是「神經
  網路一定比較強」——本階段兩個案例都出現簡單模型打平或小贏神經網路的
  真實結果，這是誠實的資料，不是特例。
- 手寫數字辨識：8x8 灰階圖像怎麼被攤平成 64 維向量（影像→向量的最簡單
  示範，沒有用到卷積）。
- 為什麼真實專案通常不會像本階段這樣從零訓練，而是用預訓練模型（文件
  指路 HuggingFace，本課程不實際下載）。

## 完成後產出對照表

| 專案卡要求 | 本階段交付 |
|---|---|
| 完整的訓練與推論程式碼 | `text_features.py`/`train_text.py`/`predict_text.py`（案例 A）+ `train_digits.py`（案例 B） |
| 模型效能評估報告 | `report.md`（兩案例實測指標＋混淆矩陣＋錯誤案例分析） |
| 含欄位定義與來源說明的應用情境 Demo 簡報 | `slides.md` |

## 前置需求

- repo 根 `venv/` 已安裝 `requirements.txt`（含 `jieba`、`scikit-learn`）。
- `data/synthetic/comments.csv` 已存在（案例 A 用）。
- 案例 B 的 `load_digits()` 是 sklearn 內建資料集，不需要任何額外檔案或
  網路下載。

## 快速開始

**案例 A（文字情感分類）**：

```
venv/bin/python -m stage5_ml_unstructured.train_text
```

預期輸出結構（實測數字，完整見 `report.md`）：

```
原始資料：2040 筆，其中 916 筆內容跟別筆完全重複；去重後：1523 筆
訓練集：1218 筆／測試集：305 筆
模型                      accuracy  precision   recall      f1
logistic_regression        1.000      1.000    1.000   1.000
mlp_neural_network         0.993      0.991    1.000   0.995
MLP 誤判案例（共 2 筆，列出前 2 筆）：
  ...
```

單句推論：

```
venv/bin/python -m stage5_ml_unstructured.predict_text --text "今天下雨超級討厭"
```

**案例 B（手寫數字辨識）**：

```
venv/bin/python -m stage5_ml_unstructured.train_digits
```

預期輸出（實測）：

```
總樣本數：1797　訓練：1437　測試：360
模型                      accuracy  f1_macro
logistic_regression        0.972     0.972
mlp_neural_network         0.964     0.963
MLP 誤判樣本數：13 / 360
```

## 逐步教學

### 第一步：文字→向量的兩層轉換

打開 `text_features.py` 的 `tokenize()`——中文沒有空格分詞，jieba 先把
一句話切成詞（例如「雨下不停」→「雨下 / 不停」），這一步之後才輪到
`train_text.py` 裡的 `TfidfVectorizer` 把詞彙轉成數值（每個詞在整個
語料庫裡出現得越稀有、在這句話裡出現得越多次，權重越高）。這是兩個
獨立的步驟：斷詞決定「有哪些詞可以被計數」，TF-IDF 決定「這些詞的權重
怎麼算」。

### 第二步：親手驗證合成語料的重複問題

跑一次 `venv/bin/python -c "from stage5_ml_unstructured.text_features
import load_labeled_comments; df = load_labeled_comments();
print(df.duplicated(subset='content', keep=False).sum())"`——你會看到
916（滿 2040 筆的將近一半！）。這是 `scripts/generate_synthetic.py`
的模板生成機制帶來的副作用（同一內容最多重複 3 次，但當總筆數變多、
天氣分類權重集中時，重複率比想像中高）。`train_text.py` 已經處理這個
問題（先去重再切分），但你應該親手驗證過這件事，才會理解為什麼這一步
不能省。

### 第三步：讀錯誤案例分析，體會「合成語料的天花板」

打開 `report.md` 的錯誤案例小節。MLP 在去重後的測試集上只誤判 2 筆
——這不是模型很聰明，是**合成語料的模板本身區分度就很高**（負面模板
充滿「崩潰」「倒楣」「爛透了」這類強烈負面詞，正面模板充滿「開心」
「珍惜」「舒服」），TF-IDF 幾乎可以直接靠關鍵字比對就分類正確。這跟
真實社群留言（用詞模糊、反諷、多義)的難度天差地遠——`predict_text.py`
對一句真實網路用語（「靠北喔今天是怎樣 熱到快中暑了吧」，明顯負面）
的推論結果印證了這個落差（見 `report.md`）。

### 第四步：手寫數字——非結構化資料的最單純案例

`train_digits.py` 完全不用 jieba 或斷詞，因為圖像資料本身已經是數值
（每個像素的灰階值 0~16），只需要把 8x8 的二維陣列攤平成 64 維向量
（`digits.data`，sklearn 已經幫你做好這一步）。這是本課程裡「非結構化
→特徵向量」最簡單的示範，讓你在不用碰卷積神經網路的前提下，理解影像
辨識的基本框架。

## 為什麼這樣設計

**為什麼案例 A 要同時跑 LogisticRegression 跟 MLPClassifier？** 因為
「神經網路一定比傳統模型強」是常見的迷思——本階段的實測結果剛好推翻
這個迷思兩次（案例 A 兩者打平甚至 LogisticRegression 略勝，案例 B
LogisticRegression 0.972 > MLP 0.964）。在資料量小、任務簡單（TF-IDF
關鍵字區分度高、8x8 像素維度低）的情境下，簡單模型往往夠用，複雜模型
的容量優勢發揮不出來，甚至因為沒有仔細調參而略輸——這是真實的機器學習
經驗，不是本課程刻意設計的反差。

**為什麼案例 B 要加一個 LogisticRegression 基準線，SPEC 沒有要求？**
因為「為什麼要用神經網路」這個問題，沒有一個對照組就沒辦法回答——多花
幾行程式碼換來一個具體數字對比，值得做。

**為什麼合成語料的侷限要用真實推論案例（而不是只用文字描述）來說明？**
因為「效能數字會偏樂觀」這句話本身很抽象，`predict_text.py` 對一句
真實網路用語給出錯誤預測，是具體、可重現的證據——文件裡的警語配上一個
真的會失敗的例子，比空講「這是合成資料」有說服力得多。

## 注意（常見錯誤 / 踩坑紀錄）

- **不去重直接切分會製造完美但虛假的分數**：開發過程中第一版
  `train_text.py` 沒有去重，`train_test_split` 直接對全部 2040 筆隨機
  切分，兩個模型的 accuracy/precision/recall/f1 全部是 1.000，MLP 誤判
  0 筆。追查後發現訓練集與測試集之間有大量內容完全重複的列（模板生成
  機制導致)，模型不需要泛化，靠背答案就能拿到滿分。已修正為先按內容
  去重再切分（`train_and_evaluate()` 的 `drop_duplicates(subset=
  "content")`），去重後 MLP 仍有 99.3% accuracy——證明語料本身確實很
  容易分類，不完全是虛假分數，但去重是必要的方法論修正，兩件事要分開
  講清楚。
- **誤判案例可能真的湊不到 5~10 筆**：SPEC 要求列 5~10 筆誤判案例逐筆
  討論，但去重後 MLP 只誤判 2 筆——本課程沒有為了湊數字而人為製造更多
  錯誤（例如故意用更小的訓練集、更差的超參數），而是誠實列出這 2 筆，
  並補上「模型猶豫得最厲害但答對」的案例一起討論，說明數量不足的原因
  就是「這份語料真的很容易分類」，不是隱藏了什麼問題。
- **合成語料效能數字不可外推到真實文本**：見 `report.md`「合成語料的
  侷限」一節，`predict_text.py` 對真實網路用語的錯誤預測是具體證據。

## 延伸挑戰

1. 把 `TfidfVectorizer` 換成 jieba 斷詞後再手動實作簡單的詞頻向量
   （bag-of-words，不用 TF-IDF 加權），比較兩者在測試集上的表現差異。
2. 找 10~20 句真實的（非本課程生成的）台灣網路天氣相關留言（例如翻
   PTT 或社群媒體公開貼文，注意不要用於任何商業用途），跑
   `predict_text.py`，統計真實準確率，跟 `report.md` 裡的合成語料
   準確率做對比，寫一段「真實 vs 合成」落差的分析。
3. 對手寫數字案例試著把 `MLPClassifier` 的 `hidden_layer_sizes` 從
   `(100,)` 改成 `(100, 50)`（兩層），比較 accuracy 有沒有進步，並記錄
   訓練時間的變化。

## 驗收 checklist

- [x] `venv/bin/python -m pytest tests/test_stage5_ml_unstructured.py -v`
      全綠（17 個測試)。
- [x] `train_text.py`／`train_digits.py` 都實際執行過，指標與 report.md
      一致。
- [x] `predict_text.py` 對正面/負面模板句子與一句真實網路用語都跑過，
      印出的結果與 report.md 一致。
- [x] 三張圖表都存在 `figures/` 且非空圖。
- [x] 合成語料的侷限有具體案例佐證，不是只有一句空泛警語。
