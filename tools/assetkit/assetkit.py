#!/usr/bin/env python3
"""
素材處理管線 — 切分 / 去背 / 縮放 / 合成

四個子指令，對應 Phase 0 之後的四個步驟：

    python assetkit.py split   四宮格 → 四張
    python assetkit.py dekey   洋紅去背（含邊緣淨化）
    python assetkit.py scale   縮放到顯示尺寸
    python assetkit.py compose 手拼測試圖

需要：pillow、numpy
    pip install pillow numpy --break-system-packages
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# ---------------------------------------------------------------- split

def cmd_split(args):
    """2048×2048 四宮格 → 四張 1024×1024，命名 a/b/c/d"""
    src = Path(args.input)
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    hw, hh = w // 2, h // 2

    out_dir = Path(args.outdir or src.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.name or src.stem

    quads = {
        "a": (0, 0, hw, hh),
        "b": (hw, 0, w, hh),
        "c": (0, hh, hw, h),
        "d": (hw, hh, w, h),
    }

    for letter, box in quads.items():
        piece = img.crop(box)
        if args.trim:
            piece = _trim_to_content(piece, args.magenta, args.tolerance)
        path = out_dir / f"{stem}_{letter}.png"
        piece.save(path)
        print(f"  {path.name}  {piece.size[0]}×{piece.size[1]}")

    print(f"切分完成：4 張 → {out_dir}")


def _trim_to_content(img, magenta_hex, tol):
    """裁掉四周的純底色，只留物件的外接矩形（含少量留白）"""
    key = _hex_to_rgb(magenta_hex)
    arr = np.array(img.convert("RGB")).astype(np.int16)
    dist = np.abs(arr - np.array(key)).sum(axis=2)
    content = dist > tol * 3
    if not content.any():
        return img
    ys, xs = np.where(content)
    pad = 8
    box = (
        max(int(xs.min()) - pad, 0),
        max(int(ys.min()) - pad, 0),
        min(int(xs.max()) + pad + 1, img.width),
        min(int(ys.max()) + pad + 1, img.height),
    )
    return img.crop(box)


# ---------------------------------------------------------------- dekey

def cmd_dekey(args):
    """
    洋紅去背。

    這不是單純的「顏色相符就設為透明」——那樣會在抗鋸齒的邊緣留下紫邊。
    做法分兩步：
      1. 依「與底色的距離」算出連續的 alpha，不是 0/1
      2. 對半透明像素做**去汙染**：把混進去的底色成分減掉，還原真實色
    """
    src = Path(args.input)
    img = Image.open(src).convert("RGBA")
    rgb = np.array(img)[:, :, :3].astype(np.float32)
    key = np.array(_hex_to_rgb(args.magenta), dtype=np.float32)

    clean, alpha = _unmix(rgb, key, float(args.threshold),
                          shadow_tol=0.0 if args.keep_shadow_colour else args.shadow_tol)

    out = np.dstack([clean, alpha * 255.0]).astype(np.uint8)
    result = Image.fromarray(out, "RGBA")

    if args.despill:
        result = _despill(result, key)

    dst = Path(args.output) if args.output else src.with_name(src.stem + "_cut.png")
    result.save(dst)

    opaque = int((alpha > 0.99).sum())
    partial = int(((alpha > 0.01) & (alpha <= 0.99)).sum())
    print(f"去背完成 → {dst.name}")
    print(f"  不透明 {opaque:,} px｜半透明邊緣 {partial:,} px")
    if partial == 0:
        print("  ⚠ 沒有半透明邊緣——原圖可能沒有抗鋸齒，或容差設太窄")


def _unmix(rgb, key, threshold, shadow_tol=40.0):
    """
    差值鍵 + 去汙染的核心，回傳 (clean_rgb, alpha)。

    1. 差值鍵求 alpha
       洋紅的特徵是「R 與 B 都高、G 低」。
       magentaness = min(R,B) − G：純洋紅為 +255，一般顏色為負值。
       用距離法會把半透明像素誤判成不透明，導致去汙染除以錯的 alpha，留下紫邊。

    2. 去汙染：C_true = (C_obs − (1−α)·key) / α

    3. 底色陰影中性化（見 _backdrop_shadow_weight）
    """
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    magentaness = np.minimum(r, b) - g
    alpha = np.clip(1.0 - magentaness / threshold, 0.0, 1.0)

    a3 = alpha[:, :, None]
    clean = (rgb - (1.0 - a3) * key) / np.maximum(a3, 1e-2)
    clean = np.clip(clean, 0, 255)

    if shadow_tol > 0:
        w = _backdrop_shadow_weight(rgb, key, alpha, shadow_tol)
        clean = clean * (1.0 - w)

    clean = np.where(a3 < 0.02, rgb, clean)
    return clean, alpha


def _backdrop_shadow_weight(rgb, key, alpha, tol):
    """
    生成器很常把接地陰影畫成「比底色更暗的洋紅橢圓」。

    那不是半透明的物件邊緣——它是**被壓暗的底色**，本身沒有顏色。
    去汙染硬要把顏色還原出來時，R 與 B 會被減到 0、而底色幾乎不含的 G
    被除以很小的 alpha 放大，結果就除出一片螢光綠。

    判準：這種像素落在「黑 → 底色」這條線上，把它投影到該線的殘差很小；
    真正的物件邊緣（物件色與底色相混）殘差則大得多。實測洋紅底的雪石素材：

                      陰影帶 p99    畫面 p01
        tree_pine        37.5         38.1
        rock_mid         40.4         53.4
        snow_mound       58.5         74.7

    兩者之間有明顯的間隔，所以 tol 取「陰影帶的 p99」即可。

    命中的像素改成中性黑，alpha 保持差值鍵算出來的值——也就是還原成
    一層柔和的接地陰影。殘差 ≤ tol 完全中性化，到 2·tol 線性收斂回 0，
    避免在陰影邊界留下硬邊。
    """
    s = (rgb * key).sum(axis=2) / (key * key).sum()
    resid = np.linalg.norm(rgb - s[..., None] * key, axis=2)
    w = np.clip((2.0 * tol - resid) / tol, 0.0, 1.0)
    w = np.where(alpha < 0.9, w, 0.0)      # 不透明區域是真的畫面，不能動
    return w[:, :, None]


def _despill(img, key):
    """
    殘留洋紅抑制。

    只作用在半透明的邊緣像素——不透明區域的紫紅色是真的顏色，不能動。
    判準：R 與 B 同時高於 G 才算殘留（單獨偏紅或偏藍是正常的顏色）。
    """
    arr = np.array(img).astype(np.float32)
    r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]

    edge = (a > 4) & (a < 250)          # 只處理邊緣
    spill = np.minimum(r - g, b - g)     # 同時偏 R 與 B 的量
    spill = np.clip(spill, 0, None)
    spill = np.where(edge, spill, 0.0)

    r = r - spill
    b = b - spill

    arr[..., 0] = np.clip(r, 0, 255)
    arr[..., 2] = np.clip(b, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


# ---------------------------------------------------------------- scale

def cmd_scale(args):
    """依目標顯示高度縮放（Lanczos）"""
    src = Path(args.input)
    img = Image.open(src).convert("RGBA")
    target_h = int(args.height)
    ratio = target_h / img.height
    target_w = max(1, round(img.width * ratio))
    out = img.resize((target_w, target_h), Image.LANCZOS)

    dst = Path(args.output) if args.output else src.with_name(f"{src.stem}@{target_h}.png")
    out.save(dst)
    print(f"縮放完成 → {dst.name}  {img.size[0]}×{img.size[1]} → {target_w}×{target_h}"
          f"  (×{ratio:.3f})")
    if ratio > 1.0:
        print("  ⚠ 這是放大。生成尺寸應該大於顯示尺寸")


# ---------------------------------------------------------------- compose

def cmd_compose(args):
    """
    依 JSON 佈局把素材合成到地形上。

    佈局檔格式：
    {
      "terrain": "micro_terrain.png",
      "output":  "test_slice.png",
      "props": [
        { "src": "tree_pine_a@400.png", "x": 620, "y": 540, "scale": 1.0, "flip": false },
        { "src": "rock_mid_b@85.png",   "x": 300, "y": 820 }
      ]
    }

    x, y 是**素材底部中央**要落在的位置（anchor = 底部中央）。
    合成順序自動依 y 排序 —— 越下面的越前面。
    """
    layout = json.loads(Path(args.layout).read_text(encoding="utf-8"))
    base_dir = Path(args.layout).parent

    terrain_path = base_dir / layout["terrain"]
    canvas = Image.open(terrain_path).convert("RGBA")

    props = sorted(layout.get("props", []), key=lambda p: p.get("y", 0))

    for p in props:
        path = base_dir / p["src"]
        if not path.exists():
            print(f"  ⚠ 找不到 {p['src']}，跳過")
            continue
        sprite = Image.open(path).convert("RGBA")

        s = float(p.get("scale", 1.0))
        if s != 1.0:
            sprite = sprite.resize(
                (max(1, round(sprite.width * s)), max(1, round(sprite.height * s))),
                Image.LANCZOS,
            )
        if p.get("flip"):
            sprite = sprite.transpose(Image.FLIP_LEFT_RIGHT)

        # anchor = 底部中央
        px = int(p["x"] - sprite.width / 2)
        py = int(p["y"] - sprite.height)
        canvas.alpha_composite(sprite, (px, py))
        print(f"  放置 {path.name} @ ({p['x']}, {p['y']}) scale={s}")

    out_path = base_dir / layout.get("output", "composed.png")
    canvas.convert("RGB").save(out_path, quality=95)
    print(f"合成完成 → {out_path.name}  {canvas.size[0]}×{canvas.size[1]}")


# ---------------------------------------------------------------- pipeline

def cmd_pipeline(args):
    """
    一條龍：四宮格 → 切分 → 去背 → 縮放。

        python assetkit.py pipeline tree_pine_quad.png --name tree_pine --height 400

    產出 tree_pine_a@400.png ~ tree_pine_d@400.png
    """
    src = Path(args.input)
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    hw, hh = w // 2, h // 2

    out_dir = Path(args.outdir or src.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.name or src.stem
    key = np.array(_hex_to_rgb(args.magenta), dtype=np.float32)

    quads = {"a": (0, 0, hw, hh), "b": (hw, 0, w, hh),
             "c": (0, hh, hw, h), "d": (hw, hh, w, h)}

    made = []
    for letter, box in quads.items():
        piece = img.crop(box)
        piece = _trim_to_content(piece, args.magenta, 30)
        piece = _dekey_image(piece, key, args.threshold,
                             0.0 if args.keep_shadow_colour else args.shadow_tol)
        if args.height:
            ratio = args.height / piece.height
            piece = piece.resize(
                (max(1, round(piece.width * ratio)), args.height), Image.LANCZOS)
        suffix = f"@{args.height}" if args.height else ""
        path = out_dir / f"{stem}_{letter}{suffix}.png"
        piece.save(path)
        made.append((path.name, piece.size))

    print(f"一條龍完成 → {out_dir}")
    for name, size in made:
        print(f"  {name}  {size[0]}×{size[1]}")

    if args.meta:
        meta = {
            "id": stem,
            "kind": "prop",
            "style": "snowbell-ogu",
            "placement": {
                "anchor": {"x": 0.5, "y": 1.0},
                "baselineOffset": 0,
                "defaultScale": 1.0,
            },
            "variants": ["a", "b", "c", "d"],
            "displayHeight": args.height,
        }
        mp = out_dir / f"{stem}.meta.json"
        mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {mp.name}  ← 記得手填 footprint 與 baselineOffset")


def _dekey_image(img, key, threshold, shadow_tol=40.0):
    """dekey 的核心，供 pipeline 內部呼叫"""
    rgb = np.array(img)[:, :, :3].astype(np.float32)
    clean, alpha = _unmix(rgb, key, threshold, shadow_tol)
    out = Image.fromarray(
        np.dstack([clean, alpha * 255.0]).astype(np.uint8), "RGBA")
    return _despill(out, key)


# ---------------------------------------------------------------- util

def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def main():
    ap = argparse.ArgumentParser(description="素材處理管線")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("split", help="四宮格切成四張")
    s.add_argument("input")
    s.add_argument("--outdir")
    s.add_argument("--name", help="輸出檔名前綴，預設用輸入檔名")
    s.add_argument("--trim", action="store_true", help="裁掉四周純底色")
    s.add_argument("--magenta", default="#FF00FF")
    s.add_argument("--tolerance", type=int, default=30)
    s.set_defaults(func=cmd_split)

    d = sub.add_parser("dekey", help="洋紅去背")
    d.add_argument("input")
    d.add_argument("-o", "--output")
    d.add_argument("--magenta", default="#FF00FF")
    d.add_argument("--threshold", type=float, default=200,
                   help="差值鍵門檻，預設 200。邊緣還有紫邊就調低（150），"
                        "物件被吃掉就調高（240）")
    d.add_argument("--despill", action="store_true", default=True,
                   help="抑制殘留紫邊（預設開）")
    d.add_argument("--shadow-tol", type=float, default=40.0,
                   help="底色陰影中性化的殘差容差，預設 40。"
                        "陰影還帶綠就調高（60）；素材本身有暗紫色被壓成黑就調低（25）")
    d.add_argument("--keep-shadow-colour", action="store_true",
                   help="關掉陰影中性化，保留舊行為")
    d.set_defaults(func=cmd_dekey)

    c = sub.add_parser("scale", help="縮放到顯示高度")
    c.add_argument("input")
    c.add_argument("height", type=int, help="目標高度（px）")
    c.add_argument("-o", "--output")
    c.set_defaults(func=cmd_scale)

    p = sub.add_parser("pipeline", help="一條龍：切分＋去背＋縮放")
    p.add_argument("input", help="四宮格 PNG")
    p.add_argument("--name", required=True, help="素材名，例 tree_pine")
    p.add_argument("--height", type=int, help="目標顯示高度（px）")
    p.add_argument("--outdir")
    p.add_argument("--magenta", default="#FF00FF")
    p.add_argument("--threshold", type=float, default=200)
    p.add_argument("--shadow-tol", type=float, default=40.0,
                   help="底色陰影中性化的殘差容差，預設 40")
    p.add_argument("--keep-shadow-colour", action="store_true",
                   help="關掉陰影中性化，保留舊行為")
    p.add_argument("--meta", action="store_true", default=True,
                   help="順便產生 meta.json 骨架")
    p.set_defaults(func=cmd_pipeline)

    m = sub.add_parser("compose", help="依 JSON 佈局合成")
    m.add_argument("layout", help="佈局 JSON 路徑")
    m.set_defaults(func=cmd_compose)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
