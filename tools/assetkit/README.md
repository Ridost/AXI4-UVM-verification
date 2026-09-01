# assetkit — 素材處理管線

生成好的四宮格 PNG → 可以放進遊戲的素材。四個步驟全部自動化。

## 安裝

```bash
pip install pillow numpy --break-system-packages
```

只有這兩個依賴。

---

## 跑之前：先量底色

**生成器輸出的「洋紅」幾乎不會剛好是 `#FF00FF`，而且每張圖都不一樣。**
`winter_props/` 這三張實測出來是：

| 圖 | 實際底色 | 差多少 |
|---|---|---|
| `tree_pine.png`  | `#FB02FA` (251, 2,250) | −4, +2, −5 |
| `rock_mid.png`   | `#F203EA` (242, 3,234) | −13, +3, −21 |
| `snow_mound.png` | `#F104EF` (241, 4,239) | −14, +4, −16 |

拿 `#FF00FF` 去做去汙染 `(C − (1−α)·key)/α` 會**多減紅、多減藍、少減綠**，
再除以很小的 α 放大，邊緣就會鑲一圈螢光綠。這不是紫邊，調 `--threshold` 治不好。

所以每次拿到新的四宮格，先量：

```bash
python3 measure_key.py quads/*.png
```

它印出來的就是可以直接貼上去的 `--magenta "#RRGGBB"`。

---

## 最常用：一條龍

```bash
python3 assetkit.py pipeline tree_pine_quad.png --name tree_pine --height 400 \
    --magenta "#FB02FA"
```

做完四件事：切成四張 → 裁掉四周空白 → 洋紅去背 → 縮放到 400px 高。

**產出**
```
tree_pine_a@400.png
tree_pine_b@400.png
tree_pine_c@400.png
tree_pine_d@400.png
tree_pine.meta.json     ← 骨架，footprint 和 baselineOffset 要手填
```

### 批次處理

寫成一個 `.sh` 一次跑完，見 `winter_props/build.sh`。

---

## 手拼測試圖

寫一份 `layout.json`（範例見 `winter_props/layout.json`）：

```json
{
  "terrain": "terrain.png",
  "output":  "composed_reference.png",
  "props": [
    { "src": "sprites/tree_pine_a@300.png", "x": 300,  "y": 300, "scale": 0.52 },
    { "src": "sprites/rock_mid_a@70.png",   "x": 930,  "y": 505, "scale": 0.85 },
    { "src": "sprites/tree_pine_c@300.png", "x": 140,  "y": 360, "scale": 0.58, "flip": true }
  ]
}
```

```bash
python3 assetkit.py compose layout.json
```

| 欄位 | 說明 |
|---|---|
| `x`, `y` | **素材底部中央**要落在的位置 |
| `scale` | 選填，預設 1.0 |
| `flip` | 選填，水平翻轉。同一素材翻轉後就像另一個 |

**深度自動排序**——依 `y` 由小到大合成，越下面的越前面。不用自己排順序。

`scale` 除了做隨機微調（0.85–1.15）之外，也可以拿來做**遠近**：
`winter_props/layout.json` 裡遠處的樹用 0.50、近處用 1.12，同一組素材就撐出景深。

### 為什麼用 JSON 不用手拖

手拖比較快，但**位置記不下來**。用 JSON 的話：
- 改一個數字就能微調，不用整張重拼
- 這份 JSON 之後可以直接轉成地圖資料，不用在 Studio 裡重擺一次
- 每次調整都可重現

---

## 分步指令（需要細調時）

```bash
python3 assetkit.py split quad.png --name tree_pine --trim   # 只切分
python3 assetkit.py dekey tree_pine_a.png -o cut_a.png       # 只去背
python3 assetkit.py scale cut_a.png 400                      # 只縮放
```

---

## 去背的原理與調校

**沒有用「顏色相符就設為透明」的做法**——那會在抗鋸齒的邊緣留下紫邊。

用的是**差值鍵**：洋紅的特徵是「R 與 B 都高、G 低」，所以
```
magentaness = min(R, B) − G      純洋紅 = +255，一般顏色為負
alpha = 1 − magentaness / 200
```
算出連續的 alpha 之後，再對半透明像素做**去汙染**，把混進去的洋紅成分減掉：
```
真實色 = (觀測色 − (1−α)×洋紅) / α
```
最後還有一道殘留抑制，只作用在邊緣像素。

### 調校

| 症狀 | 調整 |
|---|---|
| 邊緣還有紫邊 | `--threshold 150`（調低） |
| 物件邊緣被吃掉、變透明 | `--threshold 240`（調高） |
| **邊緣鑲一圈綠** | **底色量錯了。跑 `measure_key.py`，把 `--magenta` 換成量出來的值** |
| 接地陰影變成綠色一坨 | `--shadow-tol` 調高（見下節） |
| 物件本身有洋紅或紫色被誤刪 | 換底色。用 `--magenta "#00FF00"` 綠底重生 |

**素材本身有洋紅或紫色時一定要換底色。**

---

## 接地陰影：底色陰影中性化

生成器很常把接地陰影畫成**「比底色更暗的洋紅橢圓」**。

那不是半透明的物件，是**被壓暗的底色**——它本身沒有顏色。去汙染硬要把顏色
還原出來時，R 與 B 被減到 0，而底色幾乎不含的 G 被除以很小的 α 放大：

```
觀測 (165, 24, 171)  α≈0.30
→ 解出 (−61, 75, −21)  → 截到 0 → (0, 75, 0)   一坨螢光綠
```

`_backdrop_shadow_weight()` 用一個幾何判準把它認出來：這種像素落在
**「黑 → 底色」這條線上**，投影殘差很小；真正的物件邊緣殘差則大得多。

|  | 陰影帶殘差 p99 | 不透明畫面殘差 p01 |
|---|---|---|
| `tree_pine`  | 37.5 | 38.1 |
| `rock_mid`   | 40.4 | 53.4 |
| `snow_mound` | 58.5 | 74.7 |

兩者之間有間隔，所以 `--shadow-tol` 取**陰影帶的 p99** 就對了
（預設 40；`winter_props` 用 40 / 45 / 60）。命中的像素改成中性黑、
alpha 不動，就還原成一層柔和的接地陰影。

`--keep-shadow-colour` 可以關掉這一步，回到舊行為。

---

## 擺位驗證

用眼睛對座標很容易出錯——路是斜的、冰的邊界是彎的，差 30px 就有一顆石頭浮在冰上。
在 `layout.json` 加一段 `regions`，就可以讓 `check_layout.py` 依顏色把地形分區，
再檢查每個素材的**接地帶**（底部 12%）落在哪裡：

```json
"regions": {
  "snow":  { "colour": "#EFE2D0", "place": true  },
  "path":  { "colour": "#EDDCC3", "place": false },
  "drift": { "colour": "#C0BFDB", "place": true  },
  "ice":   { "colour": "#BBCFD8", "place": false }
}
```

```bash
python3 check_layout.py winter_props/layout_v2.json
```

`place: false` 的區域被接地帶佔到 25% 以上就報錯，回傳碼 1，可以直接當 build 的關卡。
走道要留空、冰面不能站東西，這兩條靠肉眼很難守住。`compose` 會忽略 `regions` 這段。

---

## 檢查產出

```bash
python3 -c "
from PIL import Image; import numpy as np, sys
a = np.array(Image.open(sys.argv[1]))
al = a[...,3]; rgb = a[...,:3].astype(int)
edge = (al>20)&(al<235); lo = rgb[(al>10)&(al<120)]
e = rgb[edge]
spill = ((e[:,0]-e[:,1]>40)&(e[:,2]-e[:,1]>40)).mean() if edge.sum() else 0
green = ((lo[:,1]-lo[:,0]>25)&(lo[:,1]-lo[:,2]>25)).mean() if len(lo) else 0
print(f'邊緣 {edge.sum():,} px｜洋紅殘留 {spill:.2%}｜陰影泛綠 {green:.2%}')
" sprites/tree_pine_a@300.png
```

**兩個數字都應該接近 0%。**
- 洋紅殘留 > 5% → `--threshold` 調低重跑
- 陰影泛綠 > 5% → 底色量錯，或 `--shadow-tol` 太低

如果邊緣像素是 0，代表原圖沒有抗鋸齒——那通常表示生成器輸出的是硬邊，
素材貼上去會很生硬，值得重生。

---

## 常見問題

**Q：四張變體的尺寸不一樣怎麼辦？**
`--trim` 會依各自的內容裁切，所以四張的原始尺寸本來就會不同。`--height` 會把
它們統一成同樣的高度，寬度依比例。**這是對的**——四棵樹本來就不該一樣寬。

**Q：素材有一部分被裁掉了？**
`--trim` 的判準是「與底色的距離」。如果素材邊緣顏色太接近洋紅，會被誤判成背景。
改用綠底重生。

**Q：接地陰影被去背去掉了？**
先確認生成器是怎麼畫的。畫在**底色上**的暗洋紅橢圓由 `--shadow-tol` 處理（見上）。
如果是畫成不透明的黑色橢圓，去背不會刪掉它，但合成時會很明顯——重生時強調
「soft, semi-transparent contact shadow」。

**Q：可以處理不是四宮格的圖嗎？**
`split` 寫死成 2×2。單張素材直接用 `dekey` + `scale` 就好。

---

## winter_props

雪地場景的第一組素材。重跑：

```bash
cd winter_props && ./build.sh
```

產出 `sprites/`（12 張素材 + 3 份 meta 骨架）與 `composed_reference.png`。

`terrain_v2.png` + `layout_v2.json` 是第二版地形的擺位（平面化的地形、
描邊分區、可讀的雪徑），產出 `composed_v2.png`：

```bash
python3 ../check_layout.py layout_v2.json && python3 ../assetkit.py compose layout_v2.json
```
`meta.json` 裡的 `footprint` 與 `baselineOffset` 還是空的，要手填。
