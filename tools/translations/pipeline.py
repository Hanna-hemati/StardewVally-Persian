#!/usr/bin/env python3
import json, os, re, sys
import arabic_reshaper
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(ROOT, '..', '..'))
SRC = os.path.join(PROJ, 'translations', 'fa')
OUT = os.path.join(PROJ, 'FarsiMod2', 'assets', 'translations')
SOURCE_DUMP = os.path.join(PROJ, 'dump')
FONT_JSON = os.path.join(PROJ, 'FarsiMod2', 'assets', 'fonts', 'dialogue.json')
os.makedirs(OUT, exist_ok=True)

TOKEN_RE = re.compile(r'(\$[A-Za-z0-9_]+|#\$[A-Za-z0-9_]+#|%[A-Za-z0-9_]+|\{[0-9]+\}|@|\[[A-Z_]+\])')
# characters that should be preserved as a single unit
PUA_BASE = 0xE000

POST_REPLACE = {}

def normalize_fa(text: str) -> str:
    text = text.replace('\u064a','\u06cc').replace('\u0649','\u06cc').replace('\u0643','\u06a9').replace('\u0629','\u0647')
    for a,b in zip('٠١٢٣٤٥٦٧٨٩','0123456789'): text = text.replace(a,b)
    for a,b in zip('۰۱۲۳۴۵۶۷۸۹','0123456789'): text = text.replace(a,b)
    return text

def post_replace(text: str) -> str:
    for a,b in POST_REPLACE.items():
        text = text.replace(a,b)
    return normalize_fa(text)

def shape(text: str) -> str:
    text = post_replace(text).replace('\t', '    ')
    # split on newlines, shape each line separately
    parts = re.split(r'(\^|\n)', text)
    out = []
    tokens = []
    for part in parts:
        if part in ('^', '\n'):
            out.append(part); continue
        def repl(m):
            tokens.append(m.group(0))
            return chr(PUA_BASE + len(tokens) - 1)
        masked = TOKEN_RE.sub(repl, part)
        shaped = arabic_reshaper.reshape(masked)
        # remove zero-width non-joiners now that shaping has used them
        shaped = shaped.replace('\u200c', '').replace('\u200d', '').replace('\u200b', '').replace('\u00ad', '')
        # restore tokens
        res = []
        for ch in shaped:
            o = ord(ch)
            if PUA_BASE <= o < PUA_BASE + len(tokens):
                res.append(tokens[o - PUA_BASE])
            else:
                res.append(ch)
        out.append(''.join(res))
    return ''.join(out)

def tokens(text: str):
    return sorted(TOKEN_RE.findall(text))

def load_source(asset):
    fn = asset.replace('/', '__') + '.json'
    with open(os.path.join(SOURCE_DUMP, fn), encoding='utf-8') as f:
        return json.load(f)

def build():
    font = TTFont(os.path.join(PROJ,'tools','fontgen','fonts','Vazirmatn-Regular.ttf'), lazy=True)
    cmap = font.getBestCmap()
    glyph_data = json.load(open(FONT_JSON, encoding='utf-8'))
    glyph_chars = {g['char'] for g in glyph_data['glyphs']}
    report = []
    total = 0
    for old in os.listdir(OUT):
        if old.endswith('.json'):
            os.remove(os.path.join(OUT, old))
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith('.json'): continue
        with open(os.path.join(SRC, fn), encoding='utf-8') as f:
            data = json.load(f)
        asset = data['asset']
        source = load_source(asset)
        entries = dict(data['entries'])
        manual_path = os.path.join(PROJ, 'translations', 'manual', fn)
        if os.path.exists(manual_path):
            try:
                manual = json.load(open(manual_path, encoding='utf-8'))
                entries.update(manual.get('entries', {}))
            except Exception:
                pass
        shaped_entries = {}
        for key, val in entries.items():
            if key not in source:
                print(f'WARN {asset}: unknown key {key!r}')
                continue
            src = source[key]
            st, tt = tokens(src), tokens(val)
            if st != tt:
                print(f'WARN {asset}:{key}: token mismatch {st} != {tt}')
            shaped = shape(val)
            missing = sorted({c for c in shaped if c not in glyph_chars and c not in ' \n^'})
            if missing:
                print(f'WARN {asset}:{key}: missing glyphs {missing}')
            shaped_entries[key] = shaped
            total += 1
        outdata = {'asset': asset, 'entries': shaped_entries}
        with open(os.path.join(OUT, asset.replace('/', '__') + '.json'), 'w', encoding='utf-8') as f:
            json.dump(outdata, f, ensure_ascii=False, indent=2)
        report.append((asset, len(shaped_entries)))
    print(f'built {len(report)} assets, {total} entries')
    for a,n in report: print(f'  {n:>5} {a}')

if __name__ == '__main__':
    build()
