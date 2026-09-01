#!/usr/bin/env python3
"""
量出四宮格實際的底色（key）。

生成器輸出的「洋紅」幾乎不會剛好是 #FF00FF，而且**每張圖都不一樣**。
拿 #FF00FF 去做去汙染會多減紅、多減藍、少減綠，邊緣就會泛綠。
跑管線前先用這支量一次，把結果餵給 --magenta。

    python measure_key.py quads/*.png
"""
import sys
import numpy as np
from PIL import Image


def measure(path):
    a = np.array(Image.open(path).convert("RGB"))
    flat = a.reshape(-1, 3).astype(np.int32)
    packed = (flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2]
    vals, counts = np.unique(packed, return_counts=True)
    v = int(vals[counts.argmax()])
    r, g, b = (v >> 16) & 255, (v >> 8) & 255, v & 255
    share = counts.max() / len(flat)
    return (r, g, b), share


if __name__ == "__main__":
    for p in sys.argv[1:]:
        (r, g, b), share = measure(p)
        print(f"{p:40s}  --magenta \"#{r:02X}{g:02X}{b:02X}\"   ({r},{g},{b})  佔 {share:.1%}")
