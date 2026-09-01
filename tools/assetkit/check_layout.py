#!/usr/bin/env python3
"""
擺位驗證：檢查每個素材有沒有踩到不能站的地形區域。

用眼睛對座標很容易出錯——路是斜的、冰的邊界是彎的，差 30px 就會有一顆
石頭浮在冰面上。這支把地形依顏色分類成幾個區域，再檢查每個素材
**接地帶**（sprite 底部 12% 的範圍）落在哪裡。

在 layout.json 裡加一段 regions 就會啟用（compose 會忽略這段）：

    "regions": {
      "snow":  { "colour": "#EFE2D0", "place": true  },
      "path":  { "colour": "#EDDCC3", "place": false },
      "drift": { "colour": "#C0BFDB", "place": true  },
      "ice":   { "colour": "#BBCFD8", "place": false }
    }

colour 用 measure_key.py 或直接從地形取樣。place: false 的區域一旦佔到
接地帶就會報錯——路要留空（那是走道），冰面不能站東西。

    python3 check_layout.py winter_props/layout.json

回傳碼 1 代表有問題，可以直接接在 build.sh 裡當關卡。
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

CONTACT_BAND = 0.12      # sprite 底部這個比例算「接地帶」
OCCUPY_FAIL = 0.25       # 接地帶被禁止區域佔到這個比例就算踩到


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def check(layout_path):
    layout_path = Path(layout_path)
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    base = layout_path.parent

    regions = layout.get("regions")
    if not regions:
        print("layout 裡沒有 regions 區塊，跳過檢查")
        return 0

    names = list(regions)
    refs = np.array([_hex_to_rgb(regions[n]["colour"]) for n in names], dtype=float)
    banned = {i for i, n in enumerate(names) if not regions[n].get("place", True)}

    terrain = np.array(Image.open(base / layout["terrain"]).convert("RGB")).astype(float)
    H, W, _ = terrain.shape
    dist = np.stack([np.linalg.norm(terrain - c, axis=2) for c in refs])
    lab = np.argmin(dist, axis=0)

    print(f"{'sprite':26s} {'anchor':>12s} {'scale':>5s}   contact band")
    problems = 0
    for p in sorted(layout.get("props", []), key=lambda q: q.get("y", 0)):
        path = base / p["src"]
        if not path.exists():
            print(f"  ⚠ 找不到 {p['src']}")
            problems += 1
            continue
        s = float(p.get("scale", 1.0))
        spr = Image.open(path)
        w, h = int(spr.width * s), int(spr.height * s)
        x, y = int(p["x"]), int(p["y"])

        y0, y1 = max(0, y - int(h * CONTACT_BAND)), min(H, y + 1)
        x0, x1 = max(0, x - w // 2), min(W, x + w // 2)
        if y0 >= y1 or x0 >= x1:
            continue
        counts = np.bincount(lab[y0:y1, x0:x1].ravel(), minlength=len(names))
        share = counts / counts.sum()

        mix = "  ".join(f"{names[i]} {share[i]:.0%}" for i in np.argsort(-share) if share[i] > 0.01)
        hit = [names[i] for i in banned if share[i] > OCCUPY_FAIL]
        flag = f"   <-- 踩到 {', '.join(hit)}" if hit else ""
        if hit:
            problems += 1
        print(f"{path.name:26s} {f'({x},{y})':>12s} {s:5.2f}   {mix}{flag}")

    print(f"\n{problems} 個擺位問題" if problems else "\n擺位全部合法")
    return problems


if __name__ == "__main__":
    sys.exit(1 if check(sys.argv[1]) else 0)
