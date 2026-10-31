#!/usr/bin/env python3
"""Machine-translation helper for the Persian Valley project.

Uses the public Google Translate web endpoint in batches, protects game tokens,
caches results, and writes logical (unshaped) Persian translation files.
"""
import json, os, re, sys, time, urllib.parse, urllib.request, hashlib, random

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(ROOT, '..', '..'))
DUMP = os.path.join(PROJ, 'dump')
OUT = os.path.join(PROJ, 'translations', 'fa')
CACHE = os.path.join(PROJ, 'translations', '.mt-cache.json')
os.makedirs(OUT, exist_ok=True)
STATE = {'cache': {}, 'dirty': 0}

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
ENDPOINT = 'https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=en&tl=fa'

# Tokens which must survive translation verbatim. Order matters.
TOKEN_PATTERNS = [
    re.compile(r'%item[^\^\[\n]*'),
    re.compile(r'(?:\{[0-9]+\}|\d[\d,]*)\s?g\b'),
    re.compile(r'#\$[A-Za-z0-9_]+#'),
    re.compile(r'\$[A-Za-z0-9_]+'),
    re.compile(r'%revealtaste:[^%\^\n]+'),
    re.compile(r'%[A-Za-z0-9_]+'),
    re.compile(r'\[[0-9A-Za-z_#:\\/ .\-]{1,100}\]'),
    re.compile(r'\(break\)'),
    re.compile(r'%%'),
    re.compile(r'@'),
    re.compile(r'_[A-Za-z0-9]+_'),
    re.compile(r'\{[0-9]+\}'),
]

ALWAYS_SKIP = re.compile(r'^[\s0-9\W_]+$', re.UNICODE)
PERSIAN_RE = re.compile(r'[\u0600-\u06FF]')

def load_cache():
    if os.path.exists(CACHE):
        try:
            STATE['cache'] = json.load(open(CACHE, encoding='utf-8'))
        except Exception:
            STATE['cache'] = {}
    print(f'cache: {len(STATE["cache"])} entries', file=sys.stderr)

def save_cache(force=False):
    if not force and STATE['dirty'] < 25:
        return
    tmp = CACHE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(STATE['cache'], f, ensure_ascii=False)
    os.replace(tmp, CACHE)
    STATE['dirty'] = 0

def normalize_fa(s):
    # Prefer Persian letter forms over Arabic look-alikes.
    s = s.replace('\u064a', '\u06cc').replace('\u0649', '\u06cc')
    s = s.replace('\u0643', '\u06a9')
    s = s.replace('\u0629', '\u0647')
    # Arabic-Indic and extended Arabic-Indic digits -> ASCII digits.
    for a, b in zip('٠١٢٣٤٥٦٧٨٩', '0123456789'):
        s = s.replace(a, b)
    for a, b in zip('۰۱۲۳۴۵۶۷۸۹', '0123456789'):
        s = s.replace(a, b)
    # Remove stray bidi controls.
    s = re.sub('[\u200b\u00ad\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]', '', s)
    return s

def mask_tokens(text):
    tokens = []
    def repl(m):
        tokens.append(m.group(0))
        return f'ZXQPV{len(tokens)-1}QXZ'
    masked = text
    for pat in TOKEN_PATTERNS:
        masked = pat.sub(repl, masked)
    return masked, tokens

def restore_tokens(text, tokens):
    def repl(m):
        i = int(m.group(1))
        return tokens[i] if 0 <= i < len(tokens) else m.group(0)
    return re.sub(r'Z\s*X\s*Q\s*P\s*V\s*([0-9]+)\s*Q\s*X\s*Z', repl, text, flags=re.IGNORECASE)

def has_letters(s):
    return bool(re.search(r'[A-Za-z]', s))

def translate_one(text):
    if not text or not text.strip() or ALWAYS_SKIP.match(text) or not has_letters(text):
        return text
    if text in STATE['cache']:
        return STATE['cache'][text]
    return None

def fetch_batch(batch):
    # batch: list of masked strings
    data = [('client', 'dict-chrome-ex'), ('sl', 'en'), ('tl', 'fa')]
    for q in batch:
        data.append(('q', q))
    body = urllib.parse.urlencode(data).encode('utf-8')
    req = urllib.request.Request(ENDPOINT, data=body, headers={
        'User-Agent': UA,
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'Accept': 'application/json,text/plain,*/*',
    })
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                raw = r.read().decode('utf-8', 'replace')
            parsed = json.loads(raw)
            if isinstance(parsed, list) and len(parsed) == len(batch) and all(isinstance(x, str) for x in parsed):
                return parsed
        except Exception as e:
            print(f'  request failed ({attempt+1}): {e}', file=sys.stderr)
        time.sleep(1.5 * (attempt + 1) + random.random())
    return None

def translate_many(texts, progress=None):
    """Translate a list of logical strings, preserving tokens and caching results."""
    unique = []
    seen = set()
    for t in texts:
        if t not in seen and translate_one(t) is None:
            seen.add(t); unique.append(t)
    if unique:
        pending = []
        for t in unique:
            masked, tokens = mask_tokens(t)
            pending.append((t, masked, tokens))
        batch_size = 80
        for i in range(0, len(pending), batch_size):
            chunk = pending[i:i+batch_size]
            # keep request body under ~25k characters
            while len(chunk) > 1 and sum(len(x[1]) for x in chunk) > 45000:
                chunk = chunk[:-1]
            out = fetch_batch([x[1] for x in chunk])
            if out is None:
                # retry one by one
                for t, masked, tokens in chunk:
                    single = fetch_batch([masked])
                    if single:
                        res = normalize_fa(restore_tokens(single[0], tokens)).replace('"', "'")
                        STATE['cache'][t] = res
                        STATE['dirty'] += 1
                    else:
                        STATE['cache'][t] = t
                        STATE['dirty'] += 1
            else:
                for (t, masked, tokens), res in zip(chunk, out):
                    res = normalize_fa(restore_tokens(res, tokens)).replace('"', "'")
                    # if a token disappeared, keep the original rather than a broken string
                    if any(tok not in res for tok in tokens):
                        res = t
                    STATE['cache'][t] = res
                    STATE['dirty'] += 1
            save_cache()
            if progress:
                progress(min(i + len(chunk), len(pending)), len(pending))
    return [STATE['cache'].get(t, t) for t in texts]

def split_translate(text, split_re, join):
    parts = re.split(split_re, text)
    out = []
    for part in parts:
        if part in ('\n', '^') or split_re.match(part or '') and part in ('\n','^'):
            out.append(part)
        else:
            out.append(translate_many([part])[0])
    return join.join(out)

def translate_plain_text(text):
    if not text:
        return text
    # Translate text runs between game control tokens, preserving the tokens verbatim.
    parts = re.split(r'(\^|\n|%revealtaste:[^%\^\n]+|#\$[A-Za-z0-9_]+#|\$[A-Za-z0-9_]+)', text)
    out = []
    for part in parts:
        if part in ('^', '\n') or re.fullmatch(r'%revealtaste:[^%\^\n]+|#\$[A-Za-z0-9_]+#|\$[A-Za-z0-9_]+', part or ''):
            out.append(part)
        else:
            out.append(translate_many([part])[0])
    return ''.join(out)


DIALOGUE_STRING_ASSETS = {'Strings/Characters','Strings/1_6_Strings','Strings/Locations','Strings/StringsFromMaps','Strings/Notes','Strings/SpeechBubbles','Strings/SimpleNonVillagerDialogues','Strings/StringsFromCSFiles','Strings/animationDescriptions'}
EVENT_TEXT_COMMANDS = {'speak', 'message', 'end', 'question', 'quickquestion', 'textabovehead', 'splitSpeak', 'splitSpeak'.lower(), 'spriteText'.lower(), 'spriteText', 'spriteText'.lower()}
DIALOGUE_STRING_ASSETS = {'Strings/Characters','Strings/1_6_Strings','Strings/Locations','Strings/StringsFromMaps','Strings/Notes','Strings/SpeechBubbles','Strings/SimpleNonVillagerDialogues','Strings/StringsFromCSFiles','Strings/animationDescriptions'}
EVENT_TEXT_COMMANDS = {'speak', 'message', 'end', 'question', 'textabovehead', 'splitspeak', 'spritetext'}

def split_event_commands(script):
    out = []
    cur = []
    quoted = False
    for ch in script:
        if ch == '"':
            quoted = not quoted
            cur.append(ch)
        elif ch == '/' and not quoted:
            out.append(''.join(cur)); cur = []
        else:
            cur.append(ch)
    out.append(''.join(cur))
    return out

def translate_quoted_parts(cmd):
    # Translate every quoted segment, leaving command syntax intact.
    parts = re.split(r'(")', cmd)
    out = []
    inside = False
    for part in parts:
        if part == '"':
            inside = not inside
            out.append(part)
        elif inside and part:
            out.append(translate_dialogue_string(part).replace('"', "'"))
        else:
            out.append(part)
    return ''.join(out)

def translate_dialogue_string(text):
    """Translate only display text in a dialogue string, leaving $ commands and their args intact."""
    if not isinstance(text, str) or not text:
        return text
    parts = re.split(r'(#)', text)
    out = []
    for part in parts:
        if part == '#':
            out.append(part)
        elif part.startswith('$'):
            if part.startswith('$y'):
                out.append(translate_y_choice(part))
            else:
                out.append(part)
        else:
            out.append(translate_plain_text(part))
    return ''.join(out)

def translate_y_choice(part):
    m = re.match(r"^(\$y\s*)(['\"])(.*)\2$", part, re.S)
    if not m:
        return part
    prefix, quote, content = m.group(1), m.group(2), m.group(3)
    pieces = re.split(r'(_[A-Za-z0-9]+_)', content)
    out = []
    for piece in pieces:
        if re.fullmatch(r'_[A-Za-z0-9]+_', piece or ''):
            out.append(piece)
        elif piece:
            out.append(translate_plain_text(piece))
        else:
            out.append(piece)
    return prefix + quote + ''.join(out) + quote

def collect_dialogue_segments(text):
    if not isinstance(text, str): return []
    out = []
    for part in re.split(r'(#)', text):
        if part == '#' or not part: continue
        if part.startswith('$'):
            if part.startswith('$y'):
                m = re.match(r"^(\$y\s*)(['\"])(.*)\2$", part, re.S)
                if m:
                    for piece in re.split(r'(_[A-Za-z0-9]+_)', m.group(3)):
                        if piece and not re.fullmatch(r'_[A-Za-z0-9]+_', piece):
                            out += text_runs(piece)
            continue
        out += text_runs(part)
    return out

def translate_hashed_text(text):
    # Preserve choice separators used by the game (#, ~) while translating each segment.
    if '#' in text or '~' in text:
        parts = re.split(r'([#~])', text)
        out = []
        for part in parts:
            if part in ('#', '~') or not part:
                out.append(part)
            else:
                out.append(translate_plain_text(part))
        return ''.join(out)
    return translate_plain_text(text)

def split_backslash_commands(script):
    out = []; cur = []; quoted = False
    for ch in script:
        if ch == '"':
            quoted = not quoted; cur.append(ch)
        elif ch == '\\' and not quoted:
            out.append(''.join(cur)); cur = []
        else:
            cur.append(ch)
    out.append(''.join(cur))
    return out

def translate_quick_question(cmd):
    m = re.match(r'^(\s*[Qq]uick[Qq]uestion)(.*)$', cmd, re.S)
    if not m:
        return cmd
    prefix, rest = m.group(1), m.group(2)
    if '(break)' not in rest:
        # No branch payload; only the answer choices need translation.
        return prefix + translate_quick_answers(rest)
    head, tail = rest.split('(break)', 1)
    head = translate_quick_answers(head)
    cmds = split_backslash_commands(tail)
    out = []
    for c in cmds:
        name = c.lstrip().split(' ', 1)[0].lower()
        if name in EVENT_TEXT_COMMANDS:
            c = translate_quoted_parts(c)
        out.append(c)
    return prefix + head + '(break)' + '\\'.join(out)

def translate_quick_answers(head):
    if '#' not in head:
        return head
    parts = head.split('#')
    out = []
    for part in parts:
        if part == '':
            out.append(part)
        else:
            out.append(translate_plain_text(part))
    return '#'.join(out)

def collect_quick_question_segments(cmd):
    m = re.match(r'^(\s*[Qq]uick[Qq]uestion)(.*)$', cmd, re.S)
    if not m: return []
    rest = m.group(2)
    out = []
    if '(break)' in rest:
        head, tail = rest.split('(break)', 1)
        for part in head.split('#'):
            out += text_runs(part)
        for c in split_backslash_commands(tail):
            name = c.lstrip().split(' ', 1)[0].lower()
            if name in EVENT_TEXT_COMMANDS:
                inside = False
                for part in re.split(r'(")', c):
                    if part == '"': inside = not inside
                    elif inside and part: out += collect_dialogue_segments(part)
    else:
        for part in rest.split('#'):
            out += text_runs(part)
    return out

def looks_like_event_script(text):
    if not isinstance(text, str) or '/' not in text:
        return False
    return bool(re.search(r'(?:^|/)(?:farmer|speak|pause|move|viewport|end|message|emote|warp|faceDirection|animate|playSound|playMusic|question|quickQuestion|textAboveHead|splitSpeak|spriteText) ', text))

def translate_event_script(script):
    out = []
    for cmd in split_event_commands(script):
        stripped = cmd.lstrip()
        name = stripped.split(' ', 1)[0].lower()
        if name == 'quickquestion':
            cmd = translate_quick_question(cmd)
        elif name in EVENT_TEXT_COMMANDS:
            cmd = translate_quoted_parts(cmd)
        out.append(cmd)
    return '/'.join(out)

def load_source(asset):
    fn = asset.replace('/', '__') + '.json'
    with open(os.path.join(DUMP, fn), encoding='utf-8') as f:
        return json.load(f)

MANUAL = os.path.join(PROJ, 'translations', 'manual')

def load_manual(asset):
    fn = asset.replace('/', '__') + '.json'
    p = os.path.join(MANUAL, fn)
    if not os.path.exists(p): return {}
    try:
        d = json.load(open(p, encoding='utf-8'))
        return d.get('entries', {})
    except Exception:
        return {}

def save_asset(asset, entries):
    fn = asset.replace('/', '__') + '.json'
    with open(os.path.join(OUT, fn), 'w', encoding='utf-8') as f:
        json.dump({'asset': asset, 'entries': entries}, f, ensure_ascii=False, indent=2)


def text_runs(text):
    return [p for p in re.split(r'(\^|\n|#\$[A-Za-z0-9_]+#|\$[A-Za-z0-9_]+)', text)
            if p and p not in ('^', '\n') and not re.fullmatch(r'#\$[A-Za-z0-9_]+#|\$[A-Za-z0-9_]+', p) and has_letters(p)]

def collect_plain_segments(text):
    if not isinstance(text, str): return []
    return text_runs(text)

def collect_event_segments(script):
    if not isinstance(script, str): return []
    segs = []
    for cmd in split_event_commands(script):
        stripped = cmd.lstrip(); name = stripped.split(' ', 1)[0].lower()
        if name == 'quickquestion':
            segs += collect_quick_question_segments(cmd)
        elif name in EVENT_TEXT_COMMANDS:
            parts = re.split(r'(")', cmd)
            inside = False
            for part in parts:
                if part == '"': inside = not inside
                elif inside and part:
                    for sub in re.split(r'[#~]', part):
                        segs += collect_dialogue_segments(sub)
    return segs

def collect_asset_segments(asset, source):
    segs = []
    if asset.startswith('Data/Events/'):
        for v in source.values():
            if isinstance(v, str) and looks_like_event_script(v): segs += collect_event_segments(v)
            elif isinstance(v, str): segs += collect_plain_segments(v)
    elif asset.startswith('Data/Festivals/'):
        for k, v in source.items():
            if not isinstance(v, str): continue
            if k == 'conditions': continue
            if looks_like_event_script(v): segs += collect_event_segments(v)
            else:
                segs += collect_plain_segments(v)
                segs += collect_dialogue_segments(v)
    elif asset == 'Data/mail':
        for v in source.values():
            if not isinstance(v, str): continue
            body, sep, tail = v.partition('%%')
            m = re.search(r'%item', body)
            text = body[:m.start()] if m else body
            segs += collect_plain_segments(text)
            if tail.startswith('[#]'):
                segs += collect_plain_segments(tail[3:])
    elif asset == 'Data/Quests':
        for v in source.values():
            if not isinstance(v, str): continue
            parts = v.split('/')
            for i in (1,2,3):
                if i < len(parts): segs += collect_plain_segments(parts[i])
    elif asset == 'Data/NPCGiftTastes':
        for v in source.values():
            if isinstance(v, str):
                for i, part in enumerate(v.split('/')):
                    if i % 2 == 0: segs += collect_plain_segments(part)
    elif asset in ('Data/Bundles','Data/hats','Data/Boots','Data/Fish','Data/Monsters'):
        for v in source.values():
            if isinstance(v, str): segs += collect_plain_segments(v)
    else:
        use_dialogue = asset.startswith('Characters/Dialogue/') or asset in DIALOGUE_STRING_ASSETS or asset in ('Data/ExtraDialogue','Data/EngagementDialogue','Data/NPCGiftTastes')
        for v in source.values():
            if isinstance(v, str):
                segs += collect_plain_segments(v)
                if use_dialogue: segs += collect_dialogue_segments(v)
    return list(dict.fromkeys(segs))

def translate_dict_asset(asset, force=False):
    source = load_source(asset)
    manual = {} if force else load_manual(asset)
    keys = list(source.keys())
    texts = []
    for k in keys:
        if k in manual: continue
        v = source[k]
        if isinstance(v, str):
            texts.append(v)
    print(f'{asset}: {len(keys)} keys, prefetching segments', file=sys.stderr)
    segs = collect_asset_segments(asset, source)
    print(f'  {len(segs)} segments', file=sys.stderr)
    if segs:
        translate_many(segs, progress=lambda a,b: print(f'  {a}/{b}', file=sys.stderr) if a==b else None)
    entries = {}
    for k in keys:
        if k in manual:
            entries[k] = manual[k]
        else:
            v = source[k]
            if isinstance(v, str):
                if looks_like_event_script(v):
                    entries[k] = translate_event_script(v)
                elif asset.startswith('Characters/Dialogue/') or asset in DIALOGUE_STRING_ASSETS:
                    entries[k] = translate_dialogue_string(v)
                else:
                    entries[k] = translate_plain_text(v)
            else:
                entries[k] = v
    save_asset(asset, entries)
    return entries

if __name__ == '__main__':
    load_cache()
    if len(sys.argv) < 2:
        print('usage: mt.py <asset> [asset...] | --list <file>')
        sys.exit(1)
    if sys.argv[1] == '--list':
        assets = [line.strip() for line in open(sys.argv[2], encoding='utf-8') if line.strip()]
    else:
        assets = sys.argv[1:]
    for asset in assets:
        translate_dict_asset(asset)
    save_cache(force=True)
    print('done', file=sys.stderr)
