#!/usr/bin/env python3
"""Draw the language-selection button texture for FarsiMod2 (label: فارسی)."""
import os

from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, '..', '..'))
FONT = os.path.join(HERE, 'fonts', 'Vazirmatn-Regular.ttf')
OUT = os.path.join(PROJECT, 'FarsiMod2', 'assets', 'language-button.png')

text = get_display(arabic_reshaper.reshape('فارسی'))
font = ImageFont.truetype(FONT, 26)
W, H = 174, 78

img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
for y in range(H):
    if y < H // 2:
        t = y / (H // 2 - 1)
        col = (40 + int(22 * t), 104 + int(18 * t), 78 + int(16 * t), 255)
    else:
        col = (54, 144, 108, 255)
    d.line([(0, y), (W, y)], fill=col)

bbox = d.textbbox((0, 0), text, font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
for top in (0, H // 2):
    d.text(((W - tw) / 2 - bbox[0], top + (H // 2 - th) / 2 - bbox[1]), text, font=font, fill=(255, 255, 255, 255))

mask = Image.new('L', (W, H), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], 12, fill=255)
img.putalpha(mask)
img.save(OUT)
print('button:', OUT, img.size)
