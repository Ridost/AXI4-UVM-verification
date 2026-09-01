#!/usr/bin/env bash
# winter_props 的批次處理。
#
# --magenta 是每張圖「量出來的」底色，不是 #FF00FF——生成器每次都會漂一點，
# 用錯的 key 去做去汙染會讓邊緣泛綠。要重量的話：
#     python3 ../measure_key.py quads/*.png
#
# --shadow-tol 取「陰影帶殘差的 p99」，把生成器畫在底色上的暗洋紅橢圓
# 還原成中性的接地陰影。詳見 ../README.md。
set -euo pipefail
cd "$(dirname "$0")"

KIT=../assetkit.py
OUT=sprites

python3 "$KIT" pipeline quads/tree_pine.png  --name tree_pine  --height 300 \
    --outdir "$OUT" --magenta "#FB02FA" --shadow-tol 40
python3 "$KIT" pipeline quads/rock_mid.png   --name rock_mid   --height 70 \
    --outdir "$OUT" --magenta "#F203EA" --shadow-tol 45
python3 "$KIT" pipeline quads/snow_mound.png --name snow_mound --height 110 \
    --outdir "$OUT" --magenta "#F104EF" --shadow-tol 60

python3 "$KIT" compose layout.json
