#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os, re, glob, sys
ROOT=os.path.dirname(os.path.abspath(__file__)); PROJ=os.path.abspath(os.path.join(ROOT,'..','..'))
DUMP=os.path.join(PROJ,'dump'); FA=os.path.join(PROJ,'translations','fa')
TOK=re.compile(r'(\{[0-9]+\}|#\$[A-Za-z0-9_]+#|\$[A-Za-z0-9_]+|%[A-Za-z0-9_]+|@|_[A-Za-z0-9]+_|\[[A-Z][A-Z0-9_]*\])')
LETTER=re.compile(r'[A-Za-z]')
def split_cmds(s):
    out=[];cur=[];q=False
    for ch in s:
        if ch=='"': q=not q; cur.append(ch)
        elif ch=='/' and not q: out.append(''.join(cur)); cur=[]
        else: cur.append(ch)
    out.append(''.join(cur)); return out
def source(asset):
    p=os.path.join(DUMP,asset.replace('/','__')+'.json')
    return json.load(open(p,encoding='utf-8')) if os.path.exists(p) else None
bad=0; missing_keys=0; untranslated=0; tokenbad=0
for p in sorted(glob.glob(os.path.join(FA,'*.json'))):
    d=json.load(open(p,encoding='utf-8')); asset=d['asset']; src=source(asset)
    if src is None: continue
    ent=d['entries']
    miss=set(src)-set(ent)
    if miss: missing_keys+=len(miss); print('MISSING KEYS',asset,len(miss),list(miss)[:3])
    for k,v in ent.items():
        if k not in src: continue
        s=src[k]
        if not isinstance(s,str) or not isinstance(v,str): continue
        if TOK.findall(s)!=TOK.findall(v):
            tokenbad+=1
            if tokenbad<=15: print('TOKENS',asset,k,TOK.findall(s),TOK.findall(v))
        if LETTER.search(s) and v.strip()==s.strip():
            untranslated+=1
            if untranslated<=15: print('UNTRANSLATED',asset,k,repr(s[:100]))
        if s and '/' in s and re.search(r'(?:^|/)(?:farmer|speak|pause|move|viewport|end|message|emote|warp|faceDirection|animate|playSound|playMusic|question|quickQuestion|textAboveHead|splitSpeak|spriteText) ',s):
            a=split_cmds(s); b=split_cmds(v)
            if len(a)!=len(b): print('EVENT CMD COUNT',asset,k,len(a),len(b)); bad+=1
            if s.count('"')!=v.count('"'): print('QUOTE COUNT',asset,k,s.count('"'),v.count('"')); bad+=1
print('files',len(glob.glob(os.path.join(FA,'*.json'))))
print('missing_keys',missing_keys,'untranslated',untranslated,'tokenbad',tokenbad,'eventbad',bad)
