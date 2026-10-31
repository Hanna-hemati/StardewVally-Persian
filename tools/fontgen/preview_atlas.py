#!/usr/bin/env python3
"""Render a sample of the baked (visual-order) translation strings exactly the
way the game's SpriteFont will draw them: glyph-by-glyph from the bitmap atlas,
advancing left to right. Lets us eyeball the RTL order without launching the game."""
import json, os, random
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, '..', '..'))
FONTS = os.path.join(PROJECT, 'FarsiMod2', 'assets', 'fonts')
TRANS = os.path.join(PROJECT, 'FarsiMod2', 'assets', 'translations')
OUT = os.path.join(PROJECT, 'preview.png')

meta = json.load(open(os.path.join(FONTS, 'dialogue.json'), encoding='utf-8'))
atlas = Image.open(os.path.join(FONTS, 'dialogue.png')).convert('RGBA')
glyphs = {g['char']: g for g in meta['glyphs']}
LINE = meta['lineSpacing']

SAMPLES = [
    'Strings__UI',
    'Strings__1_6_Strings',
    'Characters__Dialogue__Abigail',
    'Characters__Dialogue__Penny',
    'Data__mail',
]

def render(lines, width=900, pad=24):
    img = Image.new('RGBA', (width, pad * 2 + len(lines) * LINE), (24, 28, 30, 255))
    y = pad
    for text in lines:
        x = 8
        for ch in text:
            if ch == ' ':
                x += round(glyphs[' ']['xadvance'])
                continue
            g = glyphs.get(ch)
            if g is None:
                x += 12
                continue
            if g['w'] <= 1 and g['h'] <= 1:
                x += round(g['xadvance'])
                continue
            tile = atlas.crop((g['x'], g['y'], g['x'] + g['w'], g['y'] + g['h']))
            img.alpha_composite(tile, (x, y + g['yoffset']))
            x += round(g['xadvance'])
            if x > width - 32:
                break
        y += LINE
    return img

def sample_strings():
    shown = []
    for stem in SAMPLES:
        path = os.path.join(TRANS, stem + '.json')
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding='utf-8'))
        entries = list(data['entries'].items())
        for _, v in random.sample(entries, min(5, len(entries))):
            if isinstance(v, str) and '\u0600' in v + v:
                pass
            for line in v.split('\n')[:2]:
                if any('\u0600' <= c <= '\u06FF' for c in line):
                    shown.append(line.replace('^', '  ·  '))
    # dedupe, cap 16 lines
    seen, out = set(), []
    for s in shown:
        if s not in seen:
            seen.add(s); out.append(s)
    return out[:16]

if __name__ == '__main__':
    lines = sample_strings()
    img = render(lines)
    img.save(OUT)
    for l in lines:
        print(l)
    print('saved', OUT)
