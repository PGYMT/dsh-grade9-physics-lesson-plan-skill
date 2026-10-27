#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_consistency.py — 契约与正文一致性校验（L2，写完正文后跑，纯标准库）。

用法：
  python3 scripts/check_consistency.py --contract 课时契约.json --md 详案.md
  python3 scripts/check_consistency.py --contract 课时契约.json --md 详案.md --fix

5 项（每项带连续「第N项」；一次报全，不报一处修一处）：
  1. 环节标题数：md 里「### 环节…」的条数＝契约 segments 条数；
  2. 各环节用时逐条：md 每个环节标题里的（约N分钟）＝契约里该环节的 minutes；
  3. 板书块数：md 里「## 板N」的块数＝契约 boards.count；
  4. 参考资料覆盖甲/乙级来源：契约里 level 为甲或乙的每条来源，其 url 必须出现在
     md「九、参考资料」一节（只覆盖契约里最高两级，丙级不强制）；
  5. 文件名与 id 匹配：md 文件名＝section＋title＋"-"＋version_tag。

硬规则：以契约为准改 md，不允许改契约迁就 md。

默认只读两边、不写入。加 --fix 时只做两类确定性修复：
  · 把 md 各环节标题里的（约N分钟）改成契约 minutes；
  · 文件名不符合 section+title+"-"+version_tag 时改名（目标已存在则不动，列为待判断）。
修不了的（环节条数不符、板书块数不符、来源缺链接）一律列为「还需你判断」，不猜。
输出固定两行：已自动修复 N 处 / 还需你判断 M 处。

退出码：0＝5 项全过；1＝有失败项。
"""
import argparse
import json
import os
import re
import sys

HEAD_RE = re.compile(r'^###\s*(环节[^\n]*)$', re.M)
MINUTES_RE = re.compile(r'约\s*([0-9]+)\s*分钟')
BOARD_RE = re.compile(r'^[ ]*' + chr(96) * 3 + r'board[ ]*$', re.M)
BOARD_UNIT_RE = re.compile(r'^##\s*板([0-9N]+)', re.M)
REF_HEAD_RE = re.compile(r'^##\s*九、参考资料', re.M)

NO = [0]
RESULTS = []


def item(name, ok, detail=''):
    NO[0] += 1
    RESULTS.append((name, ok))
    print('  [%s] 第%d项 %s%s' % ('PASS' if ok else 'FAIL', NO[0], name,
                                 ('  ' + detail) if detail else ''))


def apply_fixes(md_path, md, d, heads, segs):
    """确定性修复：环节用时对齐契约、文件名对齐契约。返回 (修了几处, 新md, 新路径)。"""
    fixed = 0
    lines = md.split('\n')
    start = 0
    for i, s in enumerate(segs):
        if i >= len(heads):
            break
        want = s.get('minutes')
        if want is None:
            continue
        # 找到第 i 个「### 环节」行，把其中的（约N分钟）换成契约值
        for j in range(start, len(lines)):
            if HEAD_RE.match(lines[j] + '\n') or lines[j].startswith('### 环节'):
                m = MINUTES_RE.search(lines[j])
                if m and int(m.group(1)) != int(want):
                    lines[j] = (lines[j][:m.start()] + '约%d分钟' % int(want)
                                + lines[j][m.end():])
                    fixed += 1
                    print('  [修复] 环节「%s」用时改为 %s 分钟' % (s.get('name', ''), want))
                elif not m:
                    print('  [待判断] 环节「%s」标题里没写用时，没有可替换的位置' % s.get('name', ''))
                start = j + 1
                break
    out = '\n'.join(lines)
    if out != md:
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(out)
        md = out

    sec = str(d.get('section', ''))
    title = str(d.get('title', ''))
    tag = str(d.get('version_tag', ''))
    want_name = sec + title + '-' + tag
    base = re.sub(r'\.(md|docx)$', '', os.path.basename(md_path))
    if want_name and base != want_name:
        new_path = os.path.join(os.path.dirname(os.path.abspath(md_path)), want_name + '.md')
        if os.path.exists(new_path):
            print('  [待判断] 想改名为 %s，但同名文件已存在，没敢覆盖' % os.path.basename(new_path))
        else:
            os.replace(md_path, new_path)
            fixed += 1
            print('  [修复] 文件改名为 %s' % os.path.basename(new_path))
            md_path = new_path
    return fixed, md, md_path


def brief(s, limit=80):
    s = str(s)
    return s if len(s) <= limit else s[:limit] + '…'


def md_sections(md):
    heads = [m.group(1).strip() for m in HEAD_RE.finditer(md)]
    m = REF_HEAD_RE.search(md)
    refs = md[m.end():] if m else ''
    nxt = re.search(r'^##\s', refs, re.M)
    if nxt:
        refs = refs[:nxt.start()]
    return heads, refs


def main():
    ap = argparse.ArgumentParser(
        description='契约与正文一致性校验（L2）：5 项，写完正文后跑。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''字段词表与最小示例见 check_contract.py --help；
契约完整定义见 schemas/lesson.schema.json，样例见 schemas/example.lesson.json。

对照规则：
  md「### 环节一 情境导入（约5分钟）」 ←→ segments[0].name="情境导入"、minutes=5
  md「## 板1（主板）」              ←→ boards.count
  md「## 九、参考资料」里的链接       ←→ sources 里 level 为甲/乙的 url
  md 文件名                        ←→ section+title+"-"+version_tag

硬规则：以契约为准改 md，不允许改契约迁就 md。
''')
    ap.add_argument('--contract', required=True, help='课时契约 JSON 路径')
    ap.add_argument('--md', required=True, help='详案 md 路径')
    ap.add_argument('--fix', action='store_true',
                    help='只修确定性项（环节用时、文件名），其余列为待判断')
    ns = ap.parse_args()

    try:
        with open(ns.contract, encoding='utf-8') as f:
            d = json.load(f)
    except Exception as e:
        print('  [FAIL] 契约读不了：%s（%s）' % (ns.contract, e))
        print('\n结果：5 项，失败 1 项')
        return 1
    try:
        with open(ns.md, encoding='utf-8') as f:
            md = f.read()
    except Exception as e:
        print('  [FAIL] 详案读不了：%s（%s）' % (ns.md, e))
        print('\n结果：5 项，失败 1 项')
        return 1

    segs = [s for s in d.get('segments', []) if isinstance(s, dict)]
    heads, refs = md_sections(md)

    fixed = 0
    if ns.fix:
        fixed, md, ns.md = apply_fixes(ns.md, md, d, heads, segs)
        heads, refs = md_sections(md)  # 修完重新取标题与参考资料，按修后的内容判

    print('== %s × %s ==' % (os.path.basename(ns.contract), os.path.basename(ns.md)))

    item('环节标题数', len(heads) == len(segs),
         'md 标题 %d 条，契约 %d 条%s' % (
             len(heads), len(segs),
             '' if len(heads) == len(segs) else
             '；md 侧：' + brief('｜'.join(heads))))

    bad2 = []
    for i, s in enumerate(segs):
        want = s.get('minutes')
        name = str(s.get('name', ''))
        if i >= len(heads):
            bad2.append('第%d个环节 md 里没有对应标题（契约 %s %s 分钟）' % (i + 1, name, want))
            continue
        h = heads[i]
        m = MINUTES_RE.search(h)
        got = int(m.group(1)) if m else None
        if name and name not in h:
            bad2.append('第%d个环节名对不上：契约「%s」，md「%s」' % (i + 1, name, brief(h, 40)))
        if got != want:
            bad2.append('第%d个环节用时：契约 %s 分钟，md %s' % (
                i + 1, want, ('%d 分钟' % got) if got is not None else '没写用时'))
    item('各环节用时逐条', not bad2, '；'.join(bad2[:5]) + ('…' if len(bad2) > 5 else '')
         if bad2 else '每个环节的名称与用时都对得上')

    units = [m.group(1) for m in BOARD_UNIT_RE.finditer(md)]
    fences = len(BOARD_RE.findall(md))
    want_cnt = (d.get('boards') or {}).get('count')
    ok3 = (len(units) == want_cnt) if units else (fences == want_cnt)
    item('板书块数', ok3, 'md 板N %d 个（board 围栏 %d 个），契约 count=%s'
         % (len(units), fences, want_cnt))

    srcs = [s for s in d.get('sources', []) if isinstance(s, dict)]
    must = [s for s in srcs if s.get('level') in ('甲', '乙')]
    lack = [s for s in must if str(s.get('url', '')) not in refs]
    item('参考资料覆盖甲/乙级来源', not lack,
         ('缺 %d 条：' % len(lack)) + '；'.join(brief(s.get('url')) for s in lack[:3])
         if lack else '甲/乙级 %d 条来源都在「九、参考资料」里' % len(must))

    sec = str(d.get('section', ''))
    title = str(d.get('title', ''))
    tag = str(d.get('version_tag', ''))
    want_name = sec + title + '-' + tag
    base = re.sub(r'\.(md|docx)$', '', os.path.basename(ns.md))
    item('文件名与 id 匹配', base == want_name,
         'md 文件名 %s，契约拼出 %s' % (base, want_name))

    failed = [n for n, ok in RESULTS if not ok]
    print('\n结果：%d 项，失败 %d 项' % (len(RESULTS), len(failed)))
    if ns.fix:
        print('已自动修复 %d 处 / 还需你判断 %d 处' % (fixed, len(failed)))
    if failed:
        print('以契约为准改 md，不允许改契约迁就 md。')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
