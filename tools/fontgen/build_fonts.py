#!/usr/bin/env python3
"""Build the Persian font atlases for the FarsiMod2 Stardew Valley mod.

Outputs three bitmap fonts under FarsiMod2/assets/fonts (all rendered from
Vazirmatn, with symbols taken from Noto Sans Symbols 2):

- dialogue.json / dialogue.png   -> SpriteFont replacement for Fonts/SpriteFont1
- small.json / small.png         -> SpriteFont replacement for Fonts/SmallFont
- fa2.fnt / fa2_0.png            -> BMFont used by SpriteText for the custom language

The charset covers ASCII, Latin-1, the Arabic block, the Arabic Presentation
Forms (contextual shapes produced by the translation pipeline and the runtime
shaper), plus a generous set of commonly used symbols and arrows.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(PROJECT, 'FarsiMod2', 'assets', 'fonts')
os.makedirs(OUT, exist_ok=True)

VAZIR = os.path.join(HERE, 'fonts', 'Vazirmatn-Regular.ttf')
SYMBOLS = os.path.join(HERE, 'fonts', 'NotoSansSymbols2-Regular.ttf')
vazir_cmap = TTFont(VAZIR, lazy=True).getBestCmap()
symbols_cmap = TTFont(SYMBOLS, lazy=True).getBestCmap()

# Formatting characters that must never make it into the atlas.
EXCLUDE = {0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x00AD, 0xFEFF, 0x061C,
           0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069}

RANGES = [
    (0x0020, 0x007E),   # ASCII
    (0x00A0, 0x00FF),   # Latin-1 supplement
    (0x0100, 0x024F),   # extended Latin
    (0x02B0, 0x02FF),   # spacing modifiers
    (0x0370, 0x052F),   # Greek/Cyrillic
    (0x0590, 0x05FF),   # Hebrew (kept for completeness)
    (0x0600, 0x06FF),   # Arabic (incl. Persian letters)
    (0x0750, 0x077F),   # Arabic supplement
    (0x2000, 0x206F),   # general punctuation
    (0x2070, 0x209F),
    (0x20A0, 0x20CF),   # currency
    (0x2100, 0x27BF),   # letterlike, arrows, misc technical/symbols
    (0xFB50, 0xFDFF),   # Arabic presentation forms A (Persian letters)
    (0xFE70, 0xFEFF),   # Arabic presentation forms B (contextual shapes)
]

GAME_EXTRAS = '♥♡★☆♪→←↑↓•…؛،؟\u0640'


def build_charset():
    chars = set()
    for a, b in RANGES:
        for cp in range(a, b + 1):
            if cp in EXCLUDE:
                continue
            if cp in vazir_cmap or cp in symbols_cmap:
                chars.add(chr(cp))
    chars.update(chr(c) for c in range(0x20, 0x7F))
    chars.update(GAME_EXTRAS)
    return ''.join(sorted(chars))


def choose_font(ch):
    cp = ord(ch)
    if cp in vazir_cmap:
        return VAZIR
    if cp in symbols_cmap:
        return SYMBOLS
    return None


class Glyph:
    __slots__ = ('ch', 'w', 'h', 'xoff', 'yoff', 'adv', 'mask', 'page', 'ax', 'ay')

    def __init__(self, ch, w, h, xoff, yoff, adv, mask):
        self.ch, self.w, self.h = ch, w, h
        self.xoff, self.yoff, self.adv = xoff, yoff, adv
        self.mask, self.page, self.ax, self.ay = mask, -1, 0, 0


def render(ch, size):
    path = choose_font(ch)
    if path is None:
        return None
    font = ImageFont.truetype(path, size)
    if ch in (' ', '\u00a0'):
        adv = max(1, round(font.getlength(ch)))
        g = Glyph(ch, 1, 1, 0, 0, adv, Image.new('L', (1, 1), 0))
        return g
    try:
        x0, y0, x1, y1 = font.getbbox(ch, anchor='ls')
    except Exception:
        x0, y0, x1, y1 = font.getbbox(ch)
    if x1 - x0 <= 0 or y1 - y0 <= 0:
        g = Glyph(ch, 1, 1, 0, 0, max(0, round(font.getlength(ch))), Image.new('L', (1, 1), 0))
        return g
    w, h = x1 - x0, y1 - y0
    canvas = Image.new('L', (w + 8, h + 8), 0)
    d = ImageDraw.Draw(canvas)
    d.text((4 - x0, 4 - y0), ch, font=font, fill=255, anchor='ls')
    canvas = canvas.crop((4, 4, 4 + w, 4 + h))
    g = Glyph(ch, w, h, x0, y0, max(1, round(font.getlength(ch))), canvas)
    return g


def pack(glyphs, atlas=2048, pad=2):
    pages, cur = [], []
    x, y, rowh = pad, pad, 0
    last = None
    for g in sorted(glyphs, key=lambda g: (-g.h, -g.w)):
        if g.w + 2 * pad > atlas:
            raise ValueError(f'glyph {g.ch!r} is wider than the atlas')
        if x + g.w + pad > atlas:
            x, y, rowh = pad, y + rowh + pad, 0
            if y + g.h + pad > atlas:
                last = None
                pages.append(cur)
                cur = []
                x, y, rowh = pad, pad, 0
        g.page = len(pages)
        g.ax, g.ay = x, y
        x += g.w + pad
        rowh = max(rowh, g.h)
        cur.append(g)
    pages.append(cur)
    return pages


def write_single_page(page_glyphs, atlas, out_name):
    img = Image.new('RGBA', (atlas, atlas), (255, 255, 255, 0))
    for g in page_glyphs:
        if g.w == 1 and g.h == 1:
            continue
        white = Image.new('RGBA', g.mask.size, (255, 255, 255, 0))
        white.putalpha(g.mask)
        img.alpha_composite(white, (g.ax, g.ay))
    img.save(os.path.join(OUT, out_name))
    return out_name


def write_pages(pages, atlas, stem):
    out = []
    for i, page_glyphs in enumerate(pages):
        name = f'{stem}.png' if len(pages) == 1 else f'{stem}_{i}.png'
        write_single_page(page_glyphs, atlas, name)
        out.append(name)
    return out


def spritefont_pointer(name, size, line_spacing, baseline, atlas=2048, spacing=0.0):
    glyphs = []
    for ch in CHARSET:
        g = render(ch, size)
        if g is not None:
            glyphs.append(g)
    pages = pack(glyphs, atlas)
    if len(pages) != 1:
        raise ValueError(f'{name}: SpriteFont needs one atlas page, got {len(pages)}')
    files = write_pages(pages, atlas, name)
    print(f'{name}: {len(glyphs)} glyphs, pages={len(pages)}, file={files}')
    records = []
    for g in glyphs:
        records.append({
            'char': g.ch, 'page': g.page,
            'x': g.ax, 'y': g.ay, 'w': g.w, 'h': g.h,
            'xoffset': g.xoff, 'yoffset': baseline + g.yoff,
            'xadvance': g.adv, 'sprite_crop_y': baseline + g.yoff,
        })
    meta = {'name': name, 'size': size, 'lineSpacing': line_spacing,
            'spacing': spacing, 'atlas': atlas, 'glyphs': records}
    with open(os.path.join(OUT, f'{name}.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def bmfont_pointer(name, size, line_spacing, baseline, atlas=2048):
    glyphs = []
    for ch in CHARSET:
        g = render(ch, size)
        if g is not None:
            glyphs.append(g)
    pages = pack(glyphs, atlas)
    # The runtime loads page textures as "Fonts/<file>" straight from the
    # .fnt <page file> attribute, so the on-disk name must match exactly.
    files = []
    for i, page_glyphs in enumerate(pages):
        png = f'{name}_{i}.png'
        write_single_page(page_glyphs, atlas, png)
        files.append(png)
    print(f'{name}: {len(glyphs)} glyphs, pages={len(pages)}, files={files}')
    lines = ['<?xml version="1.0"?>', '<font>',
             f'  <info face="Vazirmatn" size="{size}" bold="0" italic="0" charset="" unicode="1" '
             f'stretchH="100" smooth="1" aa="1" padding="0,0,0,0" spacing="1,1" outline="0"/>',
             f'  <common lineHeight="{line_spacing}" base="{baseline}" scaleW="{atlas}" '
             f'scaleH="{atlas}" pages="{len(pages)}" packed="0" alphaChnl="0" redChnl="4" '
             f'greenChnl="4" blueChnl="4"/>',
             '  <pages>']
    for i in range(len(pages)):
        lines.append(f'    <page id="{i}" file="{"fa2" if len(pages) == 1 else name}_{i}" />')
    lines.append('  </pages>')
    lines.append(f'  <chars count="{len(glyphs)}">')
    for g in glyphs:
        lines.append(
            f'    <char id="{ord(g.ch)}" x="{g.ax}" y="{g.ay}" width="{g.w}" height="{g.h}" '
            f'xoffset="{g.xoff}" yoffset="{baseline + g.yoff}" xadvance="{g.adv}" '
            f'page="{g.page}" chnl="15" />')
    lines.append('  </chars>')
    lines.append('</font>')
    with open(os.path.join(OUT, f'{name}.fnt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    CHARSET = build_charset()
    print('charset size:', len(CHARS_ET := CHARSET))
    spritefont_pointer('dialogue', 30, 42, 27)
    spritefont_pointer('small', 18, 28, 18)
    bmfont_pointer('fa2', 38, 48, 34)
    print('fonts built into', OUT)
