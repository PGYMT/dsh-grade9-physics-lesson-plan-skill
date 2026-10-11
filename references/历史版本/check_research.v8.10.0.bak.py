#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_research.py — 备课调研完成度外部校验（v8.10.0，纯标准库）。

用法：
  python3 scripts/check_research.py --workspace DIR --chapter 章节 --section 节号节名 --summary 摘要.md
  python3 scripts/check_research.py --workspace DIR --chapter 章节 --section 节号节名 --lesson 详案.md

失败项 6 项（影响退出码）：
  1. 摘要文件存在，且七维度逐条出现；
  2. 七维度每条都带 http(s) 链接与抓取日期（标「在线来源，未落盘」也照样要链接与日期）；
  3. 摘要含「哈希清单」块；
  4. 教案/课件/练习/导学案/板书参考五类去重后达标，且每类来源类型为「官方」或「精品」；
  5. 摘要「已落盘」数与 08-网络资源/ 实际文件对账（实际少于摘要才 FAIL）；
  6. 传了 --lesson 时，教案「九、参考资料」的每个来源都能在「来源映射」里落到本地文件或标「在线来源，未落盘」。
提示项 3 项（不影响退出码）：失败站点条数、缺口表是否已更新、各类可用率。
退出码：0=全绿；1=有失败项。
"""
import argparse
import os
import re
import sys

DIMENSIONS = ['板书设计', '重点突破', '难点突破', '易错纠正', '过渡语', '讲授思路', '讲授顺序']
COUNT_TYPES = ['教案', '课件', '练习', '导学案', '板书参考']
LOWER = {'教案': 3, '课件': 3, '练习': 3, '导学案': 2, '板书参考': 2}
UPPER = {'教案': 5, '课件': 5, '练习': 5, '导学案': None, '板书参考': None}
RES_EXT = ('.md', '.docx', '.pdf', '.pptx', '.ppt', '.doc', '.txt')
EXCLUDE = ('调研记录', '调研摘要', '人工取件清单', '检索记录', '抓取记录')
URL_RE = re.compile(r'https?://[^\s)）>」]+')
DATE_RE = re.compile(r'20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]')

RESULTS = []


def item(name, ok, detail=''):
    RESULTS.append((name, ok, detail))
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name, ('  ' + detail) if detail else ''))


def warn(name, detail=''):
    print('  [WARN] %s%s' % (name, ('  ' + detail) if detail else ''))


def skip(name, detail=''):
    print('  [SKIP] %s%s' % (name, ('  ' + detail) if detail else ''))


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def split_blocks(text):
    blocks = {}
    cur = None
    buf = []
    for ln in text.splitlines():
        if ln.startswith('## '):
            if cur is not None:
                blocks[cur] = buf
            cur = ln[3:].strip()
            buf = []
        elif cur is not None:
            buf.append(ln)
    if cur is not None:
        blocks[cur] = buf
    return blocks


def find_block(blocks, key):
    for k, v in blocks.items():
        if key in k:
            return v
    return None


def parse_counts(lines):
    rows = {}
    for ln in lines:
        s = ln.strip().lstrip('-').lstrip('*').strip()
        if '=' not in s:
            continue
        k, v = s.split('=', 1)
        rows[k.strip()] = [p.strip() for p in v.split('/')]
    return rows


def auto_summary(ws, chapter, section):
    d = os.path.join(ws, '08-网络资源', '优秀教案', chapter, 'md文件')
    if not os.path.isdir(d):
        return None, []
    pat = re.compile(re.escape(section) + r'-调研摘要-([0-9]{8})\.md$')
    hits = []
    for n in os.listdir(d):
        m = pat.search(n)
        if m:
            hits.append((m.group(1), os.path.join(d, n)))
    hits.sort(reverse=True)
    return (hits[0][1] if hits else None), hits


def walk_files(root):
    out = []
    if not os.path.isdir(root):
        return out
    for dp, dn, fn in os.walk(root):
        for f in fn:
            out.append(os.path.join(dp, f))
    return out


def count_resources(root, sec_no, kind=None):
    fs = set()
    for p in walk_files(root):
        b = os.path.basename(p)
        if sec_no and not b.startswith(sec_no):
            continue
        if not b.lower().endswith(RES_EXT):
            continue
        if any(k in b for k in EXCLUDE):
            continue
        if kind == '教案' and '学案' in b:
            continue
        if kind == '导学案' and '学案' not in b:
            continue
        fs.add(os.path.splitext(b)[0])
    return len(fs)


def actual_counts(ws, chapter, sec_no):
    return {
        '教案': count_resources(os.path.join(ws, '08-网络资源', '优秀教案', chapter), sec_no, '教案'),
        '课件': count_resources(os.path.join(ws, '08-网络资源', '优秀课件PPT', chapter), sec_no, '课件'),
        '练习': count_resources(os.path.join(ws, '08-网络资源', '同步优学', '九年级上册', chapter), sec_no),
        '导学案': count_resources(os.path.join(ws, '08-网络资源', '优秀教案', chapter), sec_no, '导学案'),
        '板书参考': count_resources(os.path.join(ws, '08-网络资源', '板书设计参考'), sec_no),
    }


def parse_mapping(lines):
    m = {}
    for ln in lines:
        s = ln.strip().lstrip('-').strip()
        if '->' in s:
            k, v = s.split('->', 1)
            m[k.strip()] = v.strip()
    return m


def main():
    ap = argparse.ArgumentParser(description='备课调研完成度校验')
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--chapter', required=True)
    ap.add_argument('--section', required=True)
    ap.add_argument('--summary', default='')
    ap.add_argument('--lesson', default='')
    a = ap.parse_args()
    ws = a.workspace

    print('== 定位摘要 ==')
    summary = a.summary
    if not summary:
        summary, hits = auto_summary(ws, a.chapter, a.section)
        if summary:
            print('  自动选用：%s（同节 %d 份）' % (summary, len(hits)))
    if not summary or not os.path.isfile(summary):
        item('摘要文件存在', False, summary or '未找到')
        return finish()
    item('摘要文件存在', True, summary)
    text = read(summary)
    blocks = split_blocks(text)

    print('== 1. 七维度逐条 ==')
    dim_lines = find_block(blocks, '七维度')
    dims = {}
    if dim_lines:
        for ln in dim_lines:
            s = ln.strip().lstrip('-').lstrip('*').strip()
            for d in DIMENSIONS:
                if s.startswith(d) and d not in dims:
                    dims[d] = s
                    break
    missing = [d for d in DIMENSIONS if d not in dims]
    item('七维度逐条出现', not missing, '缺：' + '／'.join(missing) if missing else '七条齐全')

    print('== 2. 每条带链接与日期 ==')
    bad2 = []
    for d in DIMENSIONS:
        s = dims.get(d, '')
        if not s:
            bad2.append(d + '(缺条目)')
        elif not URL_RE.search(s) or not DATE_RE.search(s):
            bad2.append(d + '(缺链接或日期)')
    item('七维度每条带链接与日期', not bad2, '／'.join(bad2))

    print('== 3. 哈希清单 ==')
    hashes = find_block(blocks, '哈希清单')
    ok3 = hashes is not None and any(ln.strip().lstrip('-').strip() for ln in hashes)
    item('摘要含哈希清单', ok3, '块缺失' if hashes is None else '块为空' if not ok3 else '')

    print('== 4. 份数达标 + 来源类型 ==')
    stat = find_block(blocks, '份数统计')
    rows = parse_counts(stat) if stat else {}
    bad4 = []
    for t in COUNT_TYPES:
        parts = rows.get(t)
        if not parts or len(parts) < 6:
            bad4.append(t + '(缺行/字段)')
            continue
        if parts[5] == '不适用':
            continue
        try:
            got = int(re.sub(r'[^0-9]', '', parts[0]) or '0')
        except ValueError:
            got = 0
        if got < LOWER[t]:
            bad4.append('%s(%d<%d)' % (t, got, LOWER[t]))
        if parts[4] not in ('官方', '精品'):
            bad4.append('%s(来源类型=%s)' % (t, parts[4]))
    item('五类份数达标且含官方/精品', not bad4, '／'.join(bad4))

    print('== 5. 与实际文件对账 ==')
    m = re.match(r'[0-9]+\.[0-9]+', a.section)
    sec_no = m.group(0) if m else ''
    actual = actual_counts(ws, a.chapter, sec_no)
    bad5 = []
    for t in COUNT_TYPES:
        parts = rows.get(t)
        if not parts or len(parts) < 6 or parts[5] == '不适用':
            continue
        try:
            claimed = int(re.sub(r'[^0-9]', '', parts[0]) or '0')
        except ValueError:
            claimed = 0
        if actual.get(t, 0) < claimed:
            bad5.append('%s(摘要%d>实际%d)' % (t, claimed, actual.get(t, 0)))
    item('已落盘与 08-网络资源/ 对账', not bad5, '／'.join(bad5))

    print('== 6. 教案来源可溯源 ==')
    if not a.lesson or not os.path.isfile(a.lesson):
        skip('教案来源可溯源', '未传 --lesson' if not a.lesson else '教案不存在：' + a.lesson)
    else:
        mapping = parse_mapping(find_block(blocks, '来源映射') or [])
        lt = read(a.lesson)
        idx = lt.find('九、参考资料')
        refs = lt[idx:] if idx >= 0 else ''
        bad6 = []
        for u in URL_RE.findall(refs):
            if u in mapping:
                continue
            if any(k == u and '未落盘' in v for k, v in mapping.items()):
                continue
            bad6.append(u)
        for lp in re.findall(r'08-网络资源/[^\s)）>」|]+', refs):
            if os.path.exists(os.path.join(ws, lp)):
                continue
            if os.path.basename(lp) in ' '.join(mapping.values()):
                continue
            bad6.append(lp)
        item('教案来源可溯源', not bad6, '／'.join(sorted(set(bad6))))

    print('== 提示项（不影响退出码）==')
    fails = find_block(blocks, '失败站点')
    warn('失败站点条数', str(len([ln for ln in (fails or []) if ln.strip().startswith('-')])))
    usable = []
    for t in COUNT_TYPES:
        parts = rows.get(t)
        if parts and len(parts) >= 4:
            usable.append('%s=%s/%s' % (t, parts[2], parts[3]))
    warn('各类候选/可用', '，'.join(usable) if usable else '无')
    gap = os.path.join(ws, '08-网络资源', '备课缺口表.md')
    if os.path.isfile(gap):
        mdate = a.section
        sd = ''
        for d in DATE_RE.findall(os.path.basename(summary)):
            sd = d
        found = '—'
        for ln in read(gap).splitlines():
            if a.section in ln:
                cells = [c.strip() for c in ln.strip().strip('|').split('|')]
                if cells:
                    found = cells[-1]
                break
        if sd and found != '—' and found >= sd:
            warn('缺口表已更新', found)
        else:
            warn('缺口表已更新', '本节最近更新=%s，摘要日期=%s' % (found, sd or '未知'))
    else:
        warn('缺口表已更新', '未找到 ' + gap)
    return finish()


def finish():
    bad = [n for n, ok, _ in RESULTS if not ok]
    print('')
    print('结果：%d 项，失败 %d 项' % (len(RESULTS), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
