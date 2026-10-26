#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_structure.py — 教案技能结构一致性校验（v1.0，2026-09-30）。

校验七类：
  1. 版本号一致：SKILL.md frontmatter、SKILL.md 正文首行、references/01–07 文件头、README.md、DEPENDENCIES.md。
  2. 脚本名单三处一致：check_deps.py 的 WS_SCRIPTS、references/04 的脚本表与校验清单、scripts/dist/ 文件。
  3. SKILL.md §5 索引表指向的文件都存在。
  4. 正文与工作区生成物一致：教案生成要求提示词.md 含 01/02/06 正文；教学研究参考.md＝03；
     教学资源取件手册.md＝05、网络资源参考价值评价维度.md＝07。
  5. scripts/dist/ 各副本与工作区脚本逐字节一致。
  6. 技能根两个新脚本（check_research.py、check_lesson.py）存在，且在 04 与 DEPENDENCIES 有登记。
  7. 正文中的「文件 §节号」交叉引用目标存在；跳过 04 变更记录与 README 版本记录。

用法：
  python3 scripts/check_structure.py [--workspace DIR]
退出码：0＝全绿；1＝有失败项。
"""
import argparse
import importlib.util
import os
import re
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_WS = '/root/dsh-workspace/工作文件'
REFS = ['01-教案生成要求.md', '02-教学设计细则.md', '03-教学研究参考.md',
        '04-技能维护规范.md', '05-教学资源网站.md', '06-课件修改与排版.md',
        '07-网络资源参考价值评价维度.md']

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, ok, detail))
    print('  [%s] %s%s' % ('OK' if ok else 'FAIL', name, ('  ' + detail) if detail else ''))


def rd(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def version_places():
    v = {}
    sk = rd(os.path.join(SKILL_DIR, 'SKILL.md'))
    m = re.search(r'^version:\s*([0-9][^\s]*)\s*$', sk, re.M)
    v['SKILL.frontmatter'] = m.group(1) if m else None
    m = re.search(r'^>\s*版本：v([0-9][^\s｜]*)', sk, re.M)
    v['SKILL.body'] = m.group(1) if m else None
    for r in REFS:
        m = re.search(r'^>\s*版本：v([0-9][^\s｜]*)', rd(os.path.join(SKILL_DIR, 'references', r)), re.M)
        v[r] = m.group(1) if m else None
    m = re.search(r'^>\s*版本：v([0-9][^\s｜]*)', rd(os.path.join(SKILL_DIR, 'README.md')), re.M)
    v['README'] = m.group(1) if m else None
    m = re.search(r'^>\s*版本：v([0-9][^\s｜]*)', rd(os.path.join(SKILL_DIR, 'DEPENDENCIES.md')), re.M)
    v['DEPENDENCIES'] = m.group(1) if m else None
    return v


def ws_scripts():
    spec = importlib.util.spec_from_file_location('cd', os.path.join(SKILL_DIR, 'scripts', 'check_deps.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(mod.WS_SCRIPTS)


def body(rel):
    lines = rd(os.path.join(SKILL_DIR, rel)).rstrip().split('\n')
    out = []
    for i, ln in enumerate(lines):
        if ln.startswith('> 版本：'):
            continue
        if i == 0 and ln.startswith('# '):
            continue
        out.append(ln)
    while out and out[0] == '':
        out.pop(0)
    return '\n'.join(out)


CROSS_FILES = {
    'SKILL': 'SKILL.md',
    '01': 'references/01-教案生成要求.md',
    '02': 'references/02-教学设计细则.md',
    '03': 'references/03-教学研究参考.md',
    '04': 'references/04-技能维护规范.md',
    '05': 'references/05-教学资源网站.md',
    '06': 'references/06-课件修改与排版.md',
    '07': 'references/07-网络资源参考价值评价维度.md',
    'README': 'README.md',
    'DEPENDENCIES': 'DEPENDENCIES.md',
}
CROSS_STOPS = {
    '04': r'^## 6\. 变更记录\s*$',
    'README': r'^## 版本记录\s*$',
}
CROSS_RE = re.compile(r'(?<![A-Za-z0-9])(SKILL|0[1-7]|README|DEPENDENCIES)\s*§\s*([0-9]+(?:\.[0-9]+)*)')
HEAD_RE = re.compile(r'^#{2,5}\s+(?:需求\s*)?([0-9]+(?:\.[0-9]+)*)(?=[\s.、:：]|$)')
FENCE = chr(96) * 3


def live_lines(text, stop_re=None):
    stop = re.compile(stop_re) if stop_re else None
    off = False
    for no, line in enumerate(text.splitlines(), 1):
        if stop and stop.match(line):
            off = True
        if not off:
            yield no, line


def section_numbers(rel, stop_re=None):
    secs = set()
    for _, line in live_lines(rd(os.path.join(SKILL_DIR, rel)), stop_re):
        m = HEAD_RE.match(line)
        if m:
            secs.add(m.group(1))
    return secs


def cross_references():
    secs = {k: section_numbers(rel, CROSS_STOPS.get(k)) for k, rel in CROSS_FILES.items()}
    bad = []
    for key, rel in CROSS_FILES.items():
        fence = False
        for no, line in live_lines(rd(os.path.join(SKILL_DIR, rel)), CROSS_STOPS.get(key)):
            if line.lstrip().startswith(FENCE):
                fence = not fence
                continue
            if fence:
                continue
            for m in CROSS_RE.finditer(line):
                target, num = m.group(1), m.group(2)
                if target not in secs or num not in secs[target]:
                    bad.append('%s:%d %s §%s' % (rel, no, target, num))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace', default=DEFAULT_WS)
    a = ap.parse_args()
    ws = a.workspace

    print('== 1. 版本号一致 ==')
    v = version_places()
    vals = {x for x in v.values() if x}
    check('版本号一致', len(vals) == 1 and None not in v.values(),
          '; '.join('%s=v%s' % (k, v[k]) for k in sorted(v)))

    print('== 2. 脚本名单三处一致 ==')
    scripts = ws_scripts()
    t04 = rd(os.path.join(SKILL_DIR, 'references', '04-技能维护规范.md'))
    check('04 正文列出全部工作区脚本', all(os.path.basename(k) in t04 for k in scripts))
    dist = os.path.join(SKILL_DIR, 'scripts', 'dist')
    dist_files = set(os.listdir(dist)) if os.path.isdir(dist) else set()
    want = {k.replace('/', '__') for k in scripts}
    check('scripts/dist 与 WS_SCRIPTS 一一对应', dist_files == want,
          'dist=%d want=%d' % (len(dist_files), len(want)))

    print('== 3. SKILL 索引目标存在 ==')
    sk = rd(os.path.join(SKILL_DIR, 'SKILL.md'))
    targets = set(re.findall(r'references/[0-9]{2}-[^\s|）]+\.md', sk)) | set(re.findall(r'DEPENDENCIES\.md', sk))
    missing = [t for t in targets if not os.path.exists(os.path.join(SKILL_DIR, t))]
    check('SKILL 索引目标都存在', not missing, ','.join(missing))

    print('== 4. 正文与工作区生成物一致 ==')
    prompt_p = os.path.join(ws, '06-工具与提示词/提示词/md文件/教案生成要求提示词.md')
    ref_p = os.path.join(ws, '06-工具与提示词/提示词/md文件/教学研究参考.md')
    idx_p = os.path.join(ws, '08-网络资源/教学资源取件手册.md')
    if os.path.isfile(prompt_p):
        pt = rd(prompt_p)
        check('提示词含 01/02/06 正文',
              all(body('references/' + r) in pt for r in ['01-教案生成要求.md', '02-教学设计细则.md', '06-课件修改与排版.md']))
    else:
        check('提示词生成物存在', False, prompt_p)
    check('教学研究参考.md＝03',
          os.path.isfile(ref_p) and rd(ref_p).rstrip() == rd(os.path.join(SKILL_DIR, 'references/03-教学研究参考.md')).rstrip())
    check('教学资源取件手册.md＝05',
          os.path.isfile(idx_p) and rd(idx_p).rstrip() == rd(os.path.join(SKILL_DIR, 'references/05-教学资源网站.md')).rstrip())
    dim_p = os.path.join(ws, '08-网络资源/网络资源参考价值评价维度.md')
    check('网络资源参考价值评价维度.md＝07',
          os.path.isfile(dim_p) and rd(dim_p).rstrip() == rd(os.path.join(SKILL_DIR, 'references/07-网络资源参考价值评价维度.md')).rstrip())

    print('== 5. dist 副本与工作区脚本逐字节一致 ==')
    for rel in scripts:
        src = os.path.join(ws, rel)
        dst = os.path.join(dist, rel.replace('/', '__'))
        if not os.path.isfile(src):
            check('工作区脚本存在 ' + rel, False, '缺失')
            continue
        if not os.path.isfile(dst):
            check('dist 副本存在 ' + rel, False, '缺失')
            continue
        check('dist 一致 ' + os.path.basename(rel), rd(src) == rd(dst))

    print('== 6. 技能新脚本存在与登记 ==')
    tdep = rd(os.path.join(SKILL_DIR, 'DEPENDENCIES.md'))
    for s in ['check_research.py', 'check_lesson.py']:
        check('scripts/%s 存在' % s, os.path.isfile(os.path.join(SKILL_DIR, 'scripts', s)))
        check('%s 已在 04/DEPENDENCIES 登记' % s, s in t04 and s in tdep)

    print('== 7. 交叉引用目标存在 ==')
    miss = cross_references()
    check('正文「文件 §节号」引用均存在', not miss, '; '.join(miss))

    bad = [n for n, ok, _ in RESULTS if not ok]
    print('')
    print('结果：%d 项，失败 %d 项' % (len(RESULTS), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
