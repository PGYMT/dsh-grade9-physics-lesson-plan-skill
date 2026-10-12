#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""enbx_add_pages.py — 通用 .enbx 加页（v8.14.0；原生文字/图片 + 点击出答案动画，支持中间插页）。

与 build_enbx_native_pages.py 的分工：那个是 15.2 课件的一次性页组、且只支持**末尾追加**；
本脚本吃一份页组 JSON，支持 --after **中间插页**（Slide 重编号 + Board Item 重排），
并且对「文本字号 <28 磅」与「新增页内容高度 >540px」判 **FAIL**，不再只打告警。
只写副本，原件逐字节不动。

用法：
  python3 enbx_add_pages.py --src <原件.enbx> --out <副本.enbx> --pages <页组.json>
  python3 enbx_add_pages.py --help

页组 JSON（UTF-8）：
  {
    "template_slide": 27,
    "template_indices": [0,1,2,3,4,5,10],
    "banner_old": "课堂练习",
    "pages": [
      {"after": 0, "banner": "课前回顾", "items": [
          ["h", "32磅标题"],
          ["t", "28磅正文"],
          ["a", "答案（FadeIn，点击才出现）"],
          ["img", "/路径/图.png", 610, 150, 260]
      ]}
    ]
  }
items 元素：h=32 磅标题、t=28 磅正文、a=28 磅答案（带 FadeIn）、img=图片（路径, X, Y, 宽）。
after=0 插到最前；after=N 插在原件第 N 页之后。

退出码：0=自检全过；1=有失败项（不保留副本）。
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SLIDE_W, SLIDE_H = 960, 540
MIN_FONT = 28
USAGE = __doc__


def load_helpers():
    """载入同目录 build_enbx_native_pages.py，复用其元素/动画/幻灯片 XML 生成器。"""
    path = os.path.join(HERE, 'build_enbx_native_pages.py')
    spec = importlib.util.spec_from_file_location('bp', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def render(bp, Image, furniture, items):
    """把 items 渲染成元素列表；返回 (内容高度, 元素, 新图片资源, 最小字号)。"""
    els = list(furniture)
    y = 66
    n_anim = 0
    res = []
    min_font = 10 ** 6
    for it in items:
        kind = it[0]
        if kind == 'img':
            _, path, x, yy, w = it
            im = Image.open(path)
            pw, ph = im.size
            h = round(w * ph / pw)
            rid = bp.uid()
            res.append((rid, path))
            els.append(bp.picture_xml(rid, os.path.basename(path), os.path.getsize(path), pw, ph, x, yy, w, h))
            continue
        content = it[1]
        wid = it[2] if len(it) > 2 else 840
        lines = content if isinstance(content, list) else [content]
        size = 32 if kind == 'h' else 28
        color = bp.TEAL if kind in ('h', 'a') else bp.DARK
        anim = None
        if kind == 'a':
            n_anim += 1
            anim = n_anim
        min_font = min(min_font, size)
        h = bp.text_height(lines, wid, size)
        els.append(bp.text_xml(lines, 60, y, wid, h, size, color, bold=(kind in ('h', 'a')), anim=anim))
        if wid == 840:
            y += h + 10
    return y, els, res, (0 if min_font == 10 ** 6 else min_font)


def build(bp, Image, src, out, cfg):
    """按 cfg 生成副本；返回自检结果 [(名称, 通过, 说明)]、页数对、新增页高度表。"""
    src_hash = sha256(src)
    zin = zipfile.ZipFile(src)
    names = zin.namelist()
    pat = re.compile(r'Slides/Slide_[0-9]+\.xml')
    n_slide = len([x for x in names if pat.match(x)])
    board = zin.read('Board.xml').decode('utf-8-sig')
    orig = []
    for i in range(n_slide):
        raw = zin.read('Slides/Slide_%d.xml' % i)
        sid = re.search(r'<Id>([^<]+)</Id>', raw.decode('utf-8-sig')).group(1)
        orig.append((sid, raw))
    tpl_idx = cfg.get('template_slide', 27) - 1
    template_raw = zin.read('Slides/Slide_%d.xml' % tpl_idx).decode('utf-8-sig')

    page_heights = []
    buckets = {}
    for page in cfg['pages']:
        sid = bp.uid()
        furn = bp.make_furniture(template_raw, page.get('banner', ''))
        used, els, res, minf = render(bp, Image, furn, page['items'])
        page_heights.append((page.get('banner', ''), page.get('after', 0), used, minf))
        buckets.setdefault(page.get('after', 0), []).append([sid, bp.slide_xml(sid, els).encode('utf-8'), res])

    order = list(buckets.get(0, []))
    for i in range(1, n_slide + 1):
        order.append(orig[i - 1])
        order += buckets.get(i, [])
    new_items = [e[0] for e in order]
    new_board = re.sub(r'<Slides>.*?</Slides>',
                       '<Slides>' + ''.join('<Item>%s</Item>' % g for g in new_items) + '</Slides>',
                       board, flags=re.S)
    ref = zin.read('Reference.xml').decode('utf-8-sig')
    rels = ''.join('<Relationship><Id>%s</Id><Target>Resources\\%s.png</Target><Hash>%s</Hash></Relationship>'
                   % (rid, rid, hashlib.md5(open(p, 'rb').read()).hexdigest())
                   for e in order if len(e) > 2 and isinstance(e[2], list) for rid, p in e[2])
    if rels:
        ref = ref.replace('</Relationships>', rels + '</Relationships>')

    zout = zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED)
    for nm in names:
        if nm in ('Board.xml', 'Reference.xml') or pat.match(nm):
            continue
        zout.writestr(nm, zin.read(nm))
    for i, e in enumerate(order):
        zout.writestr('Slides/Slide_%d.xml' % i, e[1])
    zout.writestr('Board.xml', new_board.encode('utf-8'))
    zout.writestr('Reference.xml', ref.encode('utf-8'))
    for e in order:
        if len(e) > 2 and isinstance(e[2], list):
            for rid, p in e[2]:
                zout.writestr('Resources/%s.png' % rid, open(p, 'rb').read())
    zout.close()
    zin.close()

    new_idx = set()
    cursor = len(buckets.get(0, []))
    new_idx |= set(range(cursor))
    for i in range(1, n_slide + 1):
        cursor += 1
        for _ in buckets.get(i, []):
            new_idx.add(cursor)
            cursor += 1

    z = zipfile.ZipFile(out)
    nn = len([x for x in z.namelist() if pat.match(x)])
    bi = re.findall(r'<Item>([^<]+)</Item>', z.read('Board.xml').decode('utf-8-sig'))
    ref2 = z.read('Reference.xml').decode('utf-8-sig')
    all_ids, oob, small, unreg = [], [], [], []
    for i in range(nn):
        raw = z.read('Slides/Slide_%d.xml' % i).decode('utf-8-sig')
        all_ids += re.findall(r'<Id>([0-9a-f]{32})</Id>', raw)
        if i not in new_idx:
            continue
        for tag in ('Text', 'Picture'):
            for e in re.findall(r'<%s>.*?</%s>' % (tag, tag), raw, re.S):
                g = lambda p: re.search(p, e)
                mx, my = g(r'<X>([^<]+)</X>'), g(r'<Y>([^<]+)</Y>')
                mw, mh = g(r'<Width>([^<]+)</Width>'), g(r'<Height>([^<]+)</Height>')
                if mx and my:
                    try:
                        x, y2 = float(mx.group(1)), float(my.group(1))
                        w = float(mw.group(1)) if mw else 0
                        h = float(mh.group(1)) if mh else 0
                        if x + w > SLIDE_W + 0.5 or y2 + h > SLIDE_H + 0.5:
                            oob.append((i + 1, tag))
                    except ValueError:
                        pass
                fs = g(r'<FontSize>([0-9.]+)</FontSize>')
                if fs and float(fs.group(1)) < MIN_FONT:
                    small.append((i + 1, float(fs.group(1))))
        for rid in re.findall(r'<Source>id://([0-9a-f]+)</Source>', raw):
            if rid not in ref2:
                unreg.append((i + 1, rid))

    over = [(b, hv) for b, aft, hv, mf in page_heights if hv > SLIDE_H]
    ok_ids = all(re.search(r'<Id>([^<]+)</Id>', z.read('Slides/Slide_%d.xml' % i).decode('utf-8-sig')).group(1) == bi[i]
                 for i in range(nn))
    heights = [hv for _, _, hv, _ in page_heights] or [0]
    checks = [
        ('Board 项数 == Slide 数', len(bi) == nn, 'Board %d / Slide %d' % (len(bi), nn)),
        ('第 i 项 GUID == Slide_i 的 Id', ok_ids, '逐页比对'),
        ('元素 Id 唯一', len(all_ids) == len(set(all_ids)), '%d/%d' % (len(set(all_ids)), len(all_ids))),
        ('新增页元素不越界', not oob, '越界 %d 个' % len(oob)),
        ('新增页文本字号 >=%d 磅' % MIN_FONT, not small, '偏小 %d 处' % len(small)),
        ('新增页内容高度 <=%dpx' % SLIDE_H, not over,
         '／'.join('%s=%dpx（建议拆页）' % (b, hv) for b, hv in over) if over else '最高 %dpx' % max(heights)),
        ('新增页资源已在 Reference.xml 登记', not unreg, '未登记 %d 个' % len(unreg)),
        ('原件逐字节未变', sha256(src) == src_hash, src_hash[:16]),
    ]
    return checks, (n_slide, nn), page_heights


def main():
    if len(sys.argv) == 1 or '--help' in sys.argv or '-h' in sys.argv:
        print(USAGE)
        return 0
    ap = argparse.ArgumentParser(description='通用 .enbx 加页（支持中间插页）')
    ap.add_argument('--src', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--pages', required=True, help='页组 JSON 路径')
    a = ap.parse_args()
    if not os.path.isfile(a.src):
        print('错误：源课件不存在 %s' % a.src)
        return 2
    if not os.path.isfile(a.pages):
        print('错误：页组 JSON 不存在 %s' % a.pages)
        return 2
    cfg = json.load(open(a.pages, encoding='utf-8'))
    bp = load_helpers()
    bp.TEMPLATE_INDICES = cfg.get('template_indices', bp.TEMPLATE_INDICES)
    bp.BANNER_OLD = cfg.get('banner_old', bp.BANNER_OLD)
    Image = bp._pillow()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    checks, (n0, n1), heights = build(bp, Image, a.src, a.out, cfg)
    print('源课件: %s | 新增 %d 页 | 页数 %d -> %d' % (os.path.basename(a.src), len(cfg['pages']), n0, n1))
    for b, aft, hv, mf in heights:
        print('   [%s] 插在第 %s 页后 | 内容高 %dpx | 最小字号 %d' % (b, aft, hv, mf))
    bad = 0
    for name, ok, detail in checks:
        print('   [%s] %s  %s' % ('PASS' if ok else 'FAIL', name, detail))
        if not ok:
            bad += 1
    print('结果：%d 项，失败 %d 项' % (len(checks), bad))
    if bad:
        try:
            os.remove(a.out)
        except OSError:
            pass
        print('（自检未过，已删除副本 %s）' % a.out)
        return 1
    print('OK ->', a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
