#!/usr/bin/env python3
"""Translate the non-dialogue data assets (events, mail, quests, festivals, ...)."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mt

def has_text(s):
    return isinstance(s, str) and bool(re.search(r'[A-Za-z]', s))

def tr(s):
    if not has_text(s): return s
    return mt.translate_plain_text(s)

def tr_dialogue(s):
    if not has_text(s): return s
    return mt.translate_dialogue_string(s)

def tr_event(s):
    if not has_text(s): return s
    return mt.translate_event_script(s)

def tr_mail(v):
    if not isinstance(v, str): return v
    body, sep, tail = v.partition('%%')
    title = None
    if tail.startswith('[#]'):
        title = tail[3:]; tail = '[#]'
    # keep the %item command and everything after it untouched
    m = re.search(r'%item', body)
    if m:
        text, rest = body[:m.start()], body[m.start():]
    else:
        text, rest = body, ''
    text = tr(text)
    if title is not None:
        tail += tr(title)
    return text + rest + sep + tail

def fields_translate(v, indexes, skip_values=()):
    if not isinstance(v, str): return v
    parts = v.split('/')
    for i in indexes:
        if i < len(parts) and parts[i] not in skip_values:
            parts[i] = tr(parts[i])
    return '/'.join(parts)

def tr_gift(v):
    parts = v.split('/')
    for i in range(0, len(parts), 2):
        parts[i] = tr_dialogue(parts[i])
    return '/'.join(parts)

def tr_festival(v):
    if not isinstance(v, str): return v
    d = json.loads(v) if False else None

def translate_festival_dict(d):
    out = {}
    for k, v in d.items():
        if not isinstance(v, str):
            out[k] = v; continue
        if k == 'name':
            out[k] = tr(v)
        elif k == 'conditions':
            out[k] = v
        elif mt.looks_like_event_script(v):
            out[k] = tr_event(v)
        else:
            out[k] = tr(v)
    return out

def translate_quest(v):
    if not isinstance(v, str): return v
    parts = v.split('/')
    for i in (1, 2, 3):
        if i < len(parts) and parts[i] not in ('null', '', '-1'):
            parts[i] = tr(parts[i])
    return '/'.join(parts)

def translate_bundle(v):
    if not isinstance(v, str): return v
    parts = v.split('/')
    if parts: parts[0] = tr(parts[0])
    if len(parts) > 1: parts[-1] = tr(parts[-1])
    return '/'.join(parts)

def translate_hat(v):
    if not isinstance(v, str): return v
    parts = v.split('/')
    for i in (0, 1, len(parts)-1):
        if 0 <= i < len(parts): parts[i] = tr(parts[i])
    return '/'.join(parts)

def translate_boot(v):
    return translate_hat(v)

def translate_fish(v):
    if not isinstance(v, str): return v
    parts = v.split('/')
    if parts: parts[0] = tr(parts[0])
    return '/'.join(parts)

def translate_monster(v):
    if not isinstance(v, str): return v
    parts = v.split('/')
    if parts: parts[-1] = tr(parts[-1])
    return '/'.join(parts)

def translate_asset(asset):
    source = mt.load_source(asset)
    manual = mt.load_manual(asset)
    segs = mt.collect_asset_segments(asset, source)
    print(f'{asset}: prefetching {len(segs)} segments', file=sys.stderr)
    if segs:
        mt.translate_many(segs, progress=lambda a,b: print(f'  {a}/{b}', file=sys.stderr) if a==b else None)
    out = {}
    if asset.startswith('Data/Events/'):
        for k, v in source.items():
            out[k] = manual.get(k, tr_event(v) if isinstance(v, str) else v)
    elif asset.startswith('Data/Festivals/'):
        for k, v in source.items():
            if k in manual: out[k] = manual[k]
            elif not isinstance(v, str): out[k] = v
            elif k == 'name': out[k] = tr(v)
            elif k == 'conditions': out[k] = v
            else: out[k] = tr_event(v) if mt.looks_like_event_script(v) else tr(v)
    elif asset == 'Data/mail':
        for k, v in source.items():
            out[k] = manual.get(k, tr_mail(v))
    elif asset == 'Data/NPCGiftTastes':
        for k, v in source.items():
            out[k] = manual.get(k, tr_gift(v))
    elif asset == 'Data/Quests':
        for k, v in source.items():
            out[k] = manual.get(k, translate_quest(v))
    elif asset == 'Data/Bundles':
        for k, v in source.items():
            out[k] = manual.get(k, translate_bundle(v))
    elif asset == 'Data/hats':
        for k, v in source.items():
            out[k] = manual.get(k, translate_hat(v))
    elif asset == 'Data/Boots':
        for k, v in source.items():
            out[k] = manual.get(k, translate_boot(v))
    elif asset == 'Data/Fish':
        for k, v in source.items():
            out[k] = manual.get(k, translate_fish(v))
    elif asset == 'Data/Monsters':
        for k, v in source.items():
            out[k] = manual.get(k, translate_monster(v))
    elif asset.startswith('Characters/Dialogue/'):
        for k, v in source.items():
            out[k] = manual.get(k, tr_dialogue(v) if isinstance(v, str) else v)
    elif asset in ('Data/ExtraDialogue', 'Data/EngagementDialogue'):
        for k, v in source.items():
            if k in manual: out[k] = manual[k]
            elif isinstance(v, str) and mt.looks_like_event_script(v): out[k] = tr_event(v)
            elif isinstance(v, str): out[k] = tr_dialogue(v)
            else: out[k] = v
    elif asset.startswith('Data/TV/'):
        for k, v in source.items():
            out[k] = manual.get(k, tr(v) if isinstance(v, str) else v)
    else:
        # default: translate every string value as plain text
        for k, v in source.items():
            out[k] = manual.get(k, mt.translate_plain_text(v) if isinstance(v, str) else v)
    mt.save_asset(asset, out)
    print(f'{asset}: {len(out)} entries', file=sys.stderr)
    return out

if __name__ == '__main__':
    mt.load_cache()
    args = sys.argv[1:]
    if not args:
        print('usage: translate_data.py <asset>... | --list <file>', file=sys.stderr); sys.exit(1)
    if args[0] == '--list':
        assets = [line.strip() for line in open(args[1], encoding='utf-8') if line.strip()]
    else:
        assets = args
    for a in assets:
        translate_asset(a)
    mt.save_cache(force=True)
