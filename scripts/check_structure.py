#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_structure.py — 教案技能结构一致性校验（v1.0，2026-09-30）。

校验五类：
  1. 版本号五处一致：SKILL.md frontmatter、SKILL.md 正文首行、01–06 文件头、README.md、DEPENDENCIES.md。
  2. 脚本名单三处一致：check_deps.py 的 WS_SCRIPTS、references/04 的脚本表与校验清单、scripts/dist/ 文件。
  3. SKILL.md §5 索引表指向的文件都存在。
  4. 正文与工作区生成物一致：教案生成要求提示词.md 含 01/02/06 正文；教学研究参考.md＝03；
     教学资源网站索引.md＝05。
  5. scripts/dist/ 各副本与工作区脚本逐字节一致。

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
        '04-技能维护规范.md', '05-教学资源网站.md', '06-课件修改与排版.md']

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace', default=DEFAULT_WS)
    a = ap.parse_args()
    ws = a.workspace

    print('== 1. 版本号五处一致 ==')
    v = version_places()
    vals = {x for x in v.values() if x}
    check('版本号五处一致', len(vals) == 1 and None not in v.values(),
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
    idx_p = os.path.join(ws, '08-网络资源/教学资源网站索引.md')
    if os.path.isfile(prompt_p):
        pt = rd(prompt_p)
        check('提示词含 01/02/06 正文',
              all(body('references/' + r) in pt for r in ['01-教案生成要求.md', '02-教学设计细则.md', '06-课件修改与排版.md']))
    else:
        check('提示词生成物存在', False, prompt_p)
    check('教学研究参考.md＝03',
          os.path.isfile(ref_p) and rd(ref_p).rstrip() == rd(os.path.join(SKILL_DIR, 'references/03-教学研究参考.md')).rstrip())
    check('教学资源网站索引.md＝05',
          os.path.isfile(idx_p) and rd(idx_p).rstrip() == rd(os.path.join(SKILL_DIR, 'references/05-教学资源网站.md')).rstrip())

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

    bad = [n for n, ok, _ in RESULTS if not ok]
    print('')
    print('结果：%d 项，失败 %d 项' % (len(RESULTS), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
