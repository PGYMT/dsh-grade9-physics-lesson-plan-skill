#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_structure.py — 教案技能结构一致性校验（v1.2，2026-10-27）。

校验八类：
  1. 版本号一致：SKILL.md frontmatter、SKILL.md 正文首行、references/ 下自动发现的 00–09 各文件头、README.md、DEPENDENCIES.md。
  2. 脚本名单三处一致：check_deps.py 的 WS_SCRIPTS＋SKILL_SCRIPTS、references/04 的脚本表与校验清单、scripts/dist/ 文件。
  3. SKILL.md §5 索引表指向的文件都存在。
  4. 正文与工作区生成物一致：教案生成要求提示词.md 含 01/02/06 正文；教学研究参考.md＝03；
     教学资源取件手册.md＝05、网络资源参考价值评价维度.md＝07。
  5. scripts/dist/ 各副本与源文件逐字节一致（工作区脚本、技能内脚本）；板书脚本的工作区投影与技能内一致。
  6. 技能根两个新脚本（check_research.py、check_lesson.py）存在，且在 04 与 DEPENDENCIES 有登记。
  7. 正文中的「文件 §节号」交叉引用目标存在；跳过 04 变更记录与 README 版本记录。
  8. references/04 §1 配套脚本表与实际脚本文件一一对应（不多列、不漏列）。

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
# references/ 下按「两位数字-名字.md」自动发现，新增 00、08、09 时无需改脚本。
# 排除 *.local.md（本地私人清单，不入库）与历史版本/（旧档）。
REF_NAME_RE = re.compile(r'^[0-9]{2}-[^/]+\.md$')


def discover_refs():
    d = os.path.join(SKILL_DIR, 'references')
    if not os.path.isdir(d):
        return []
    return [n for n in sorted(os.listdir(d))
            if REF_NAME_RE.match(n) and not n.endswith('.local.md')
            and os.path.isfile(os.path.join(d, n))]


REFS = discover_refs()

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


def skill_scripts():
    spec = importlib.util.spec_from_file_location('cd', os.path.join(SKILL_DIR, 'scripts', 'check_deps.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(mod.SKILL_SCRIPTS)


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


def cross_files():
    """SKILL + references/ 自动发现的各文件 + README/DEPENDENCIES；键为 00–09 等短名。"""
    d = {'SKILL': 'SKILL.md'}
    for n in REFS:
        d[n[:2]] = 'references/' + n
    d['README'] = 'README.md'
    d['DEPENDENCIES'] = 'DEPENDENCIES.md'
    return d


CROSS_FILES = cross_files()
CROSS_STOPS = {
    '04': r'^## 6\. 变更记录\s*$',
    'README': r'^## 版本记录\s*$',
}
CROSS_RE = re.compile(
    r'(?<![A-Za-z0-9])(SKILL|0[0-9]|README|DEPENDENCIES)\s*§\s*([0-9]+(?:\.[0-9]+)*)')
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


TABLE_EXT = ('.py', '.ps1', '.json')


def script_rows():
    """解析 04 §1 配套脚本表：返回 [(位置, 脚本名)]，只收脚本格里的文件名。"""
    t = rd(os.path.join(SKILL_DIR, 'references', '04-技能维护规范.md'))
    rows = []
    for line in t.splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip().strip('`') for c in line.strip().strip('|').split('|')]
        if len(cells) != 3:
            continue
        pos, name = cells[0], cells[1]
        if not name.endswith(TABLE_EXT) or '/' in name or ' ' in name:
            continue
        rows.append((pos, name))
    return rows


def table_targets(ws):
    """把脚本表的「位置＋脚本名」解析成实际路径。"""
    out = {}
    for pos, name in script_rows():
        if '技能根' in pos:
            base = os.path.join(SKILL_DIR, 'scripts')
            if 'tests' in pos:
                base = os.path.join(base, 'tests')
            out[name] = os.path.join(base, name)
        else:
            out[name] = os.path.join(ws, pos, name)
    return out


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
    own = skill_scripts()
    t04 = rd(os.path.join(SKILL_DIR, 'references', '04-技能维护规范.md'))
    check('04 正文列出全部工作区脚本', all(os.path.basename(k) in t04 for k in scripts))
    check('04 正文列出全部技能内脚本', all(s in t04 for s in own))
    dist = os.path.join(SKILL_DIR, 'scripts', 'dist')
    dist_files = set(os.listdir(dist)) if os.path.isdir(dist) else set()
    want = {k.replace('/', '__') for k in scripts} | set(own)
    check('scripts/dist 与「工作区脚本＋技能内脚本」一一对应', dist_files == want,
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
        check('提示词含 00/01/02/06 正文',
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

    print('== 5. dist 副本与源文件逐字节一致 ==')
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
    for s in own:
        src = os.path.join(SKILL_DIR, 'scripts', s)
        dst = os.path.join(dist, s)
        if not os.path.isfile(src):
            check('技能内脚本存在 ' + s, False, '缺失')
        elif not os.path.isfile(dst):
            check('dist 副本存在 ' + s, False, '缺失')
        else:
            check('dist 一致（技能内） ' + s, rd(src) == rd(dst))
    proj = os.path.join(ws, '06-工具与提示词/教程/build_board_png.py')
    mine = os.path.join(SKILL_DIR, 'scripts', 'build_board_png.py')
    check('build_board_png.py 工作区投影与技能内一致',
          os.path.isfile(proj) and os.path.isfile(mine) and rd(proj) == rd(mine),
          '工作区那份须是技能内副本的逐字投影')

    print('== 6. 技能新脚本存在与登记 ==')
    tdep = rd(os.path.join(SKILL_DIR, 'DEPENDENCIES.md'))
    for s in ['check_research.py', 'check_lesson.py']:
        check('scripts/%s 存在' % s, os.path.isfile(os.path.join(SKILL_DIR, 'scripts', s)))
        check('%s 已在 04/DEPENDENCIES 登记' % s, s in t04 and s in tdep)

    print('== 7. 交叉引用目标存在 ==')
    miss = cross_references()
    check('正文「文件 §节号」引用均存在', not miss, '; '.join(miss))

    print('== 8. 04 §1 脚本表与实际文件一一对应 ==')
    listed = table_targets(ws)
    live = {os.path.basename(k): os.path.join(ws, k) for k in scripts}
    live.update({s: os.path.join(SKILL_DIR, 'scripts', s) for s in own})
    for s in ['check_structure.py', 'check_deps.py', 'check_research.py', 'check_lesson.py']:
        live[s] = os.path.join(SKILL_DIR, 'scripts', s)
    rt = os.path.join(SKILL_DIR, 'scripts', 'tests', 'run_tests.py')
    if os.path.isfile(rt):
        live['run_tests.py'] = rt
    ghost = sorted(n for n, p in listed.items() if not os.path.isfile(p))
    check('脚本表每行都指向真实文件', not ghost, '; '.join(ghost))
    unlisted = sorted(n for n in live if n not in listed)
    check('每个实际脚本都在脚本表里', not unlisted, '; '.join(unlisted))

    bad = [n for n, ok, _ in RESULTS if not ok]
    print('')
    print('结果：%d 项，失败 %d 项' % (len(RESULTS), len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
