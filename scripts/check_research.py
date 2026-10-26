#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_research.py — 备课调研完成度外部校验（v8.18.1，纯标准库）。

用法：
  python3 scripts/check_research.py --workspace DIR --chapter 章节 --section 节号节名 --summary 摘要.md
  python3 scripts/check_research.py --workspace DIR --chapter 章节 --section 节号节名 --lesson 详案.md

失败项（影响退出码）：
  1. 摘要文件存在，且七维度逐条出现；
  2. 七维度每条都带 http(s) 链接与抓取日期（标「在线来源，未落盘」也照样要链接与日期）；
  3. 摘要含「哈希清单」块；
  4. 五类去重后达标；份数统计的来源类型只能是「官方」或「精品」（逐份判定可写更宽）；
  5. 摘要「已落盘」数与 08-网络资源/ 实际文件对账（实际少于摘要才 FAIL）；
  6. 传了 --lesson 时，教案必须有「九、参考资料」，且每个来源都能在「来源映射」里落到本地文件或标「在线来源，未落盘」；映射里的本地文件必须存在；
  7. 摘要含「逐份判定」块，覆盖全部可用件（=正文达标文件），每行 >=9 字段，等级取 甲/乙/丙/—；
  8. 「可用」数不超正文达标数；有效数（判定行中等级为甲或乙的件数）低于该类下限时，必须已出《人工取件清单》。

正文达标底线（即维度文件第 1 关第 5 条的机械线）：去掉头部引用块与首个标题后，教案/课件/练习/导学案
非空白字符 >= 400、板书参考 >= 100，且命中至少 1 个内容标记。机械线只判「有没有可读正文」，
判不了内容对应与科学性，也判不了分数打得对不对——那几项由人按 references/07 判。

提示项 5 项（不影响退出码）：失败站点条数、缺口表是否已更新、各类候选/可用、正文未达底线的文件清单、有效数。
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
DATE_ANY_RE = re.compile(r'20[0-9]{2}-?[0-9]{2}-?[0-9]{2}')
FLOOR = {'教案': 400, '课件': 400, '练习': 400, '导学案': 400, '板书参考': 100}
BODY_MARKERS = ('教学目标', '学习目标', '教学过程', '教学重点', '教学难点', '重难点',
                '板书', '导学', '预习', '答案', '解析', '例题', '练习', '探究',
                '实验', '借鉴', '采用', '设计意图')
GRADES = ('甲', '乙', '丙', '—')
EFFECTIVE = ('甲', '乙')
MANUAL_LIST = '人工取件清单'
JUDGE_BLOCK = '逐份判定'
LEGACY_JUDGE_BLOCK = '网络教案价值打分'

RESULTS = []
ITEM_NO = 0


def item(name, ok, detail=''):
    global ITEM_NO
    ITEM_NO += 1
    RESULTS.append((name, ok, detail))
    print('  [%s] 第%d项 %s%s' % ('PASS' if ok else 'FAIL', ITEM_NO, name, ('  ' + detail) if detail else ''))


def warn(name, detail=''):
    print('  [WARN] %s%s' % (name, ('  ' + detail) if detail else ''))


def skip(name, detail=''):
    global ITEM_NO
    ITEM_NO += 1
    print('  [SKIP] 第%d项 %s%s' % (ITEM_NO, name, ('  ' + detail) if detail else ''))


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


def to_int(s):
    return int(re.sub(r'[^0-9]', '', s) or '0')


def norm_section(s):
    return re.sub(r'[\s、，,。；;：:（）()【】]', '', s or '')


def parse_date(s):
    m = DATE_ANY_RE.search(s or '')
    if not m:
        return None
    d = m.group(0).replace('-', '')
    return '%s-%s-%s' % (d[:4], d[4:6], d[6:8])


def auto_summary(ws, chapter, section):
    d = os.path.join(ws, '08-网络资源', '优秀教案', chapter, 'md文件')
    if not os.path.isdir(d):
        return None, []
    target = norm_section(section)
    hits = []
    for n in os.listdir(d):
        m = re.search(r'-调研摘要-([0-9]{8})\.md$', n)
        if not m:
            continue
        if norm_section(n[:m.start()]) != target:
            continue
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


def match_kind(basename, kind):
    if kind == '教案' and '学案' in basename:
        return False
    if kind == '导学案' and '学案' not in basename:
        return False
    return True


def collect_paths(root, sec_no, kind=None):
    found = {}
    for p in walk_files(root):
        b = os.path.basename(p)
        if sec_no and not b.startswith(sec_no):
            continue
        if not b.lower().endswith(RES_EXT):
            continue
        if any(k in b for k in EXCLUDE):
            continue
        if not match_kind(b, kind):
            continue
        found[os.path.splitext(b)[0]] = p
    return found


def count_resources(root, sec_no, kind=None):
    return len(collect_paths(root, sec_no, kind))


def resource_roots(ws, chapter):
    return {
        '教案': (os.path.join(ws, '08-网络资源', '优秀教案', chapter), '教案'),
        '课件': (os.path.join(ws, '08-网络资源', '优秀课件PPT', chapter), '课件'),
        '练习': (os.path.join(ws, '08-网络资源', '同步优学', '九年级上册', chapter), None),
        '导学案': (os.path.join(ws, '08-网络资源', '优秀教案', chapter), '导学案'),
        '板书参考': (os.path.join(ws, '08-网络资源', '板书设计参考'), None),
    }


def actual_counts(ws, chapter, sec_no):
    return {t: count_resources(r, sec_no, k) for t, (r, k) in resource_roots(ws, chapter).items()}


def content_body(path):
    lines = []
    for ln in read(path).splitlines():
        if ln.startswith('>'):
            continue
        if ln.startswith('# ') and not lines:
            continue
        lines.append(ln)
    text = '\n'.join(lines)
    if '---' in text:
        text = text.split('---', 1)[1]
    return text


def body_ok(path, typ):
    text = content_body(path)
    chars = sum(1 for ch in text if not ch.isspace())
    return chars >= FLOOR.get(typ, 400) and any(m in text for m in BODY_MARKERS)


def good_files(ws, chapter, sec_no):
    """按类型返回正文达标（=可用）文件 {类型: {basename: path}}。"""
    out = {}
    for t, (root, kind) in resource_roots(ws, chapter).items():
        out[t] = {os.path.basename(p): p for p in collect_paths(root, sec_no, kind).values() if body_ok(p, t)}
    return out


def parse_judgements(lines):
    """解析「逐份判定」块，返回 (按类型的 文件名->等级, 字段不足/等级非法的问题清单)。"""
    rows = {}
    bad = []
    if not lines:
        return rows, bad
    for ln in lines:
        s = ln.strip().lstrip('-').lstrip('*').strip()
        s = s.replace('｜', '|').strip()
        if s.startswith('|'):
            s = s[1:]
        if s.endswith('|'):
            s = s[:-1]
        if '|' not in s:
            continue
        parts = [p.strip() for p in s.split('|')]
        if len(parts) < 9:
            bad.append('字段%d(%s)' % (len(parts), (parts[0] or '?')[:24]))
            continue
        typ = parts[1]
        if typ not in COUNT_TYPES:
            continue
        if parts[6] not in GRADES:
            bad.append('%s(等级=%s)' % (parts[0][:24], parts[6]))
            continue
        rows.setdefault(typ, {})[parts[0]] = parts[6]
    return rows, bad


def find_manual_list(ws, section):
    root = os.path.join(ws, '08-网络资源')
    for p in walk_files(root):
        b = os.path.basename(p)
        if MANUAL_LIST in b and norm_section(b).startswith(norm_section(section)):
            return p
    return ''


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

    print('== 七维度逐条 ==')
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

    print('== 每条带链接与日期 ==')
    bad2 = []
    for d in DIMENSIONS:
        s = dims.get(d, '')
        if not s:
            bad2.append(d + '(缺条目)')
        elif not URL_RE.search(s) or not parse_date(s):
            bad2.append(d + '(缺链接或日期)')
    item('七维度每条带链接与日期', not bad2, '／'.join(bad2))

    print('== 哈希清单 ==')
    hashes = find_block(blocks, '哈希清单')
    ok3 = hashes is not None and any(ln.strip().lstrip('-').strip() for ln in hashes)
    item('摘要含哈希清单', ok3, '块缺失' if hashes is None else '块为空' if not ok3 else '')

    print('== 份数达标 / 来源类型 ==')
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
        got = to_int(parts[0])
        if got < LOWER[t]:
            bad4.append('%s(%d<%d)' % (t, got, LOWER[t]))
        if parts[4] not in ('官方', '精品'):
            bad4.append('%s(份数统计来源类型=%s，只能官方/精品)' % (t, parts[4]))
    item('五类份数达标且含官方/精品', not bad4, '／'.join(bad4))

    print('== 与实际文件对账 ==')
    m = re.match(r'[0-9]+\.[0-9]+', a.section)
    sec_no = m.group(0) if m else ''
    actual = actual_counts(ws, a.chapter, sec_no)
    bad5 = []
    for t in COUNT_TYPES:
        parts = rows.get(t)
        if not parts or len(parts) < 6 or parts[5] == '不适用':
            continue
        claimed = to_int(parts[0])
        if actual.get(t, 0) < claimed:
            bad5.append('%s(摘要%d>实际%d)' % (t, claimed, actual.get(t, 0)))
    item('已落盘与 08-网络资源/ 对账', not bad5, '／'.join(bad5))

    print('== 教案来源可溯源 ==')
    if not a.lesson or not os.path.isfile(a.lesson):
        skip('教案来源可溯源', '未传 --lesson' if not a.lesson else '教案不存在：' + a.lesson)
    else:
        mapping = parse_mapping(find_block(blocks, '来源映射') or [])
        lt = read(a.lesson)
        idx = lt.find('九、参考资料')
        if idx < 0:
            item('教案来源可溯源', False, '未找到「九、参考资料」')
        else:
            refs = lt[idx:]
            bad6 = []
            for u in URL_RE.findall(refs):
                if u in mapping:
                    continue
                if any(k == u and '未落盘' in v for k, v in mapping.items()):
                    continue
                bad6.append(u)
            for lp in re.findall(r'08-网络资源/[^\n)）>」|]+?\.(?:md|docx|pdf|pptx|ppt|txt|doc)', refs):
                if os.path.exists(os.path.join(ws, lp)):
                    continue
                if os.path.basename(lp) in ' '.join(mapping.values()):
                    continue
                bad6.append(lp)
            res_files = []
            for rt, ds, fs in os.walk(os.path.join(ws, '08-网络资源')):
                for f in fs:
                    res_files.append(os.path.join(rt, f))
            for v in mapping.values():
                if not v or v.strip() in ('—', '-', '无') or '未落盘' in v or URL_RE.search(v):
                    continue
                for part in re.split(r'[；;、]', v):
                    part = part.strip()
                    if not part:
                        continue
                    np = part.replace('\\', '/').strip()
                    cands = [part,
                             os.path.join(os.path.dirname(summary), part),
                             os.path.join(ws, part),
                             os.path.join(ws, '08-网络资源', part)]
                    if any(os.path.exists(c) for c in cands):
                        continue
                    if any(p.replace('\\', '/').endswith('/' + np) for p in res_files):
                        continue
                    bad6.append('来源映射本地文件不存在：%s' % part)
            item('教案来源可溯源', not bad6, '／'.join(sorted(set(bad6))))

    print('== 逐份判定块与有效数 ==')
    good = good_files(ws, a.chapter, sec_no)
    manual = find_manual_list(ws, a.section)
    jrows, jbad = parse_judgements(find_block(blocks, JUDGE_BLOCK))
    bad7 = list(jbad)
    if find_block(blocks, JUDGE_BLOCK) is None:
        if find_block(blocks, LEGACY_JUDGE_BLOCK) is not None:
            bad7.append('检测到旧「%s」块，未升级为「逐份判定」；请按 07 §2.2–2.5 分类型打分、按 07 §6 九字段格式改写（迁移步骤见 references/04 §3）' % LEGACY_JUDGE_BLOCK)
        else:
            bad7.append('缺「逐份判定」块')
    for t in COUNT_TYPES:
        if not good.get(t):
            continue
        miss = set(good[t]) - set(jrows.get(t, {}))
        if miss:
            bad7.append('%s缺判定行%d条' % (t, len(miss)))
    item('逐份判定块覆盖可用件且字段等级合法', not bad7, '／'.join(bad7))

    print('== 有效数与中断阈值 ==')
    effective = {}
    bad8 = []
    for t in COUNT_TYPES:
        parts = rows.get(t)
        if not parts or len(parts) < 6 or parts[5] == '不适用':
            continue
        effective[t] = sum(1 for g in jrows.get(t, {}).values() if g in EFFECTIVE)
        claimed = to_int(parts[3])
        mech = len(good.get(t, {}))
        if claimed > mech:
            bad8.append('%s(可用%d>正文达标%d)' % (t, claimed, mech))
        if effective[t] < LOWER[t] and not manual:
            bad8.append('%s(有效%d<%d且无《人工取件清单》)' % (t, effective[t], LOWER[t]))
    item('可用数不超正文达标数且有效数达标或已出清单', not bad8, '／'.join(bad8))

    print('== 提示项（不影响退出码）==')
    fails = find_block(blocks, '失败站点')
    warn('失败站点条数', str(len([ln for ln in (fails or []) if ln.strip().startswith('-')])))
    usable = []
    for t in COUNT_TYPES:
        parts = rows.get(t)
        if parts and len(parts) >= 4:
            usable.append('%s=候选%s/可用%s(正文达标%d/有效%d)' % (t, parts[2], parts[3], len(good.get(t, {})), effective.get(t, 0)))
    warn('各类候选/可用/有效', '，'.join(usable) if usable else '无')
    shells = []
    for t, (root, kind) in resource_roots(ws, a.chapter).items():
        for p in collect_paths(root, sec_no, kind).values():
            if not body_ok(p, t):
                shells.append(os.path.basename(p))
    warn('正文未达底线的文件（按不可用计）', '，'.join(sorted(set(shells))) if shells else '无')
    if manual:
        warn('已找到《人工取件清单》', manual)
    gap = os.path.join(ws, '08-网络资源', '备课缺口表.md')
    if os.path.isfile(gap):
        sd = parse_date(os.path.basename(summary)) or ''
        found = '—'
        for ln in read(gap).splitlines():
            if norm_section(a.section) in norm_section(ln):
                cells = [c.strip() for c in ln.strip().strip('|').split('|')]
                if cells:
                    found = cells[-1]
                break
        found_d = parse_date(found) or ''
        if sd and found_d and found_d >= sd:
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
