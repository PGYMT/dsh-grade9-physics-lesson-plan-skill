#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评测集跑分：三套基准的判定器（v1.0）

只在发版前跑。流程：L1 课程安排表 → L2 正文一致 → L3 成品检查 → 对照 expected.yaml → 出 pass 表。
模型判断项（提问三检、过渡三连、术语时机、学生预设这类）脚本判不了，读 verdicts.yaml 里人给的结论；
没判的列「未判」，不计入通过率分母。

用法：
  python3 scripts/run_evals.py                 # 三套全跑
  python3 scripts/run_evals.py --only base-01  # 只跑一套
  python3 scripts/run_evals.py --json /tmp/r.json
  python3 scripts/run_evals.py --baseline evals/baseline/result.json   # 与不带技能的对照组比

对照组怎么来：同一个 input.contract.json，另起一个不加载技能的会话跑一遍，产物照同一目录结构放，
用 --json 记下结果，再用 --baseline 比两组通过率；差值是「技能贡献了几个百分点」。差值 <10 提示。
退出码：0 全过；1 有退化项；2 环境/基准缺失。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import simple_yaml  # noqa: E402

EVALS = os.path.join(SKILL_DIR, 'evals')
SCRIPTS = HERE
FENCE = chr(96) * 3
KNOWN, UNJUDGED = 'known', '未判'


def rd(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True,
                       cwd=SKILL_DIR, timeout=600)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def pick(pat, items):
    for it in items:
        if re.search(pat, os.path.basename(it)):
            return it
    return None


def base_files(bdir):
    ref = os.path.join(bdir, 'reference')
    files = [os.path.join(ref, x) for x in sorted(os.listdir(ref))] if os.path.isdir(ref) else []
    md = pick(r'\.md$', files)
    docx = pick(r'\.docx$', files)
    contract = os.path.join(bdir, 'input.contract.json')
    return md, docx, contract if os.path.isfile(contract) else None


PUNCT = set('，。、；：！？（）【】「」《》〈〉'
            '“”‘’·—…→←↔=+*/|_[]{}<>~!@#$%^&*()"\',.:;?')


def actual_chars(s):
    """与 check_lesson 同口径：去掉空白与标点后数可见字。"""
    return sum(1 for ch in s if not ch.isspace() and ch not in PUNCT)


def parse_boards(md):
    """返回 [(板名, [行...]), ...]；board 围栏里的 ## 板N 段。"""
    out, cur, fence = [], None, False
    for ln in rd(md).split('\n'):
        if ln.strip().startswith(FENCE):
            fence = not fence
            continue
        if not fence:
            continue
        m = re.match(r'^##\s*板(\d)', ln.strip())
        if m:
            cur = ('板' + m.group(1), [])
            out.append(cur)
            continue
        if ln.startswith('## '):
            cur = None
            continue
        if cur is not None and ln.strip():
            cur[1].append(ln.strip())
    return out


def caps(md, contract):
    bad = []
    boards = parse_boards(md)
    if len(boards) > contract['boards']['count']:
        bad.append('板数 %d > 契约 %d' % (len(boards), contract['boards']['count']))
    for name, rows in boards:
        if len(rows) > contract['boards']['max_lines']:
            bad.append('%s 有 %d 行 > %d' % (name, len(rows), contract['boards']['max_lines']))
        for r in rows:
            if actual_chars(r) > contract['boards']['max_chars']:
                bad.append('%s 有一行 %d 字 > %d（%s）'
                           % (name, actual_chars(r), contract['boards']['max_chars'], r))
                break
    return (not bad), '; '.join(bad) if bad else '板数 %d 块、行数与字数都在限内' % len(boards)


def board_fences(md):
    """board 围栏个数：一个围栏渲染一张 PNG，围栏里可以写两块板。"""
    return sum(1 for ln in rd(md).split('\n') if ln.strip() == FENCE + 'board')


def docx_media(docx, md):
    with zipfile.ZipFile(docx) as z:
        imgs = [n for n in z.namelist() if re.search(r'word/media/board-\d+\.png$', n)]
    n = board_fences(md)
    ok = len(imgs) == n
    return ok, '内嵌板书图 %d 张，board 围栏 %d 个' % (len(imgs), n)


def sources_cover(md, contract):
    text = rd(md)
    need = [s['url'] for s in contract['sources'] if s['level'] in ('甲', '乙')]
    miss = [u for u in need if u not in text]
    kinds = sorted({s['type'] for s in contract['sources']})
    ok = not miss and len(contract['sources']) >= 3
    return ok, ('缺 %d 条甲/乙级来源' % len(miss)) if miss else '来源 %d 条，类型 %s' % (len(contract['sources']), '/'.join(kinds))


def practice_structure(md):
    text = rd(md)
    need = ['当堂检测', '分层']
    miss = [k for k in need if k not in text]
    return (not miss), ('缺环节：' + '、'.join(miss)) if miss else '有当堂检测与分层任务'


MACHINE = {}


def machine(how):
    def deco(fn):
        MACHINE[how] = fn
        return fn
    return deco


@machine('contract')
def _contract(bdir, md, docx, contract):
    return run([sys.executable, os.path.join(SCRIPTS, 'check_contract.py'),
                contract, '--strict', '--md', md])


@machine('consistency')
def _consistency(bdir, md, docx, contract):
    return run([sys.executable, os.path.join(SCRIPTS, 'check_consistency.py'),
                '--contract', contract, '--md', md])


@machine('lesson')
def _lesson(bdir, md, docx, contract):
    return run([sys.executable, os.path.join(SCRIPTS, 'check_lesson.py'),
                '--docx', docx, '--md', md, '--skill', SKILL_DIR])


@machine('boards')
def _boards(bdir, md, docx, contract):
    c = json.load(open(contract, encoding='utf-8'))
    ok, detail = caps(md, c)
    return (0 if ok else 1), detail


@machine('docx_media')
def _docx_media(bdir, md, docx, contract):
    ok, detail = docx_media(docx, md)
    return (0 if ok else 1), detail


@machine('sources')
def _sources(bdir, md, docx, contract):
    c = json.load(open(contract, encoding='utf-8'))
    ok, detail = sources_cover(md, c)
    return (0 if ok else 1), detail


@machine('practice')
def _practice(bdir, md, docx, contract):
    ok, detail = practice_structure(md)
    return (0 if ok else 1), detail



@machine('minutes')
def _minutes(bdir, md, docx, contract):
    c = json.load(open(contract, encoding='utf-8'))
    total = sum(int(s['minutes']) for s in c['segments'])
    ok = total == int(c['duration_min'])
    return (0 if ok else 1), '环节合计 %d 分钟，课时 %d 分钟' % (total, c['duration_min'])


CJK_RE = re.compile(r'[一-鿿]')


@machine('files')
def _files(bdir, md, docx, contract):
    """成品齐全：md 与 docx 都在，且正文是逐字稿体量（≥4000 汉字）。"""
    miss = [x for x in (md, docx) if not x or not os.path.isfile(x)]
    if miss:
        return 1, '缺参考成品'
    n = len(CJK_RE.findall(rd(md)))
    ok = n >= 4000
    return (0 if ok else 1), '汉字 %d 个（逐字稿线 4000）/ docx %dB' % (n, os.path.getsize(docx))


def tail(text, n=3):
    lines = [x for x in text.strip().splitlines() if x.strip()]
    bad = [x.strip() for x in lines if 'FAIL' in x]
    if bad:
        return bad[0][:90]
    return (lines[-1][:90] if lines else '')


def run_base(bdir):
    name = os.path.basename(bdir)
    exp_path = os.path.join(bdir, 'expected.yaml')
    if not os.path.isfile(exp_path):
        return None
    exp = simple_yaml.load(exp_path)
    md, docx, contract = base_files(bdir)
    ver = os.path.join(bdir, 'verdicts.yaml')
    verdicts = simple_yaml.load(ver) if os.path.isfile(ver) else {}
    rows = []
    for c in exp['checks']:
        cid, kind, how, expect = c['id'], c['kind'], c.get('how'), c.get('expect', 'pass')
        if kind == 'model':
            v = (verdicts or {}).get(cid)
            state = 'pass' if v == 'pass' else ('fail' if v == 'fail' else UNJUDGED)
            rows.append((cid, c['name'][:26], '模型', state, '', expect))
            continue
        fn = MACHINE.get(how)
        if not fn:
            rows.append((cid, c['name'][:26], '机器', 'ERROR', '未知判定器 ' + str(how), expect))
            continue
        rc, out = fn(bdir, md, docx, contract)
        ok = (rc == 0)
        if ok:
            state = 'pass'
        elif expect == 'known':
            state = KNOWN
        else:
            state = 'fail'
        rows.append((cid, c['name'][:26], '机器', state, tail(out), expect))
    total = len(rows)
    known = sum(1 for r in rows if r[3] == KNOWN)
    unjudged = sum(1 for r in rows if r[3] == UNJUDGED)
    passed = sum(1 for r in rows if r[3] == 'pass')
    failed = sum(1 for r in rows if r[3] in ('fail', 'ERROR'))
    denom = total - known - unjudged
    rate = (passed / denom) if denom else 0.0
    return {'base': name, 'title': exp.get('title', ''), 'rows': rows, 'total': total,
            'passed': passed, 'failed': failed, 'known': known,
            'unjudged': unjudged, 'rate': round(rate, 4)}


def show(res):
    print('== %s  %s ==' % (res['base'], res['title']))
    for cid, nm, kind, state, detail, expect in res['rows']:
        mark = {'pass': '[PASS]', 'fail': '[FAIL]', KNOWN: '[已知]', UNJUDGED: '[未判]'}.get(state, '[错误]')
        extra = ('  ' + detail) if detail else ''
        print('  %-4s %-26s %-4s %s%s' % (cid, nm, kind, mark, extra))
    print('  合计 %d 条：通过 %d，退化 %d，已知 %d，未判 %d；通过率 %.0f%%'
          % (res['total'], res['passed'], res['failed'], res['known'], res['unjudged'], res['rate'] * 100))


def compare(cur, base):
    print('== 与对照组比（同一套基准，不带技能跑一遍）==')
    worse = 0
    for name, r in cur.items():
        b = base.get(name)
        if not b:
            print('  %s 对照组缺数据' % name)
            continue
        d = (r['rate'] - b['rate']) * 100
        flag = '达标（>=10）' if d >= 10 else '不足 10 个百分点'
        if d < 10:
            worse += 1
        print('  %s 带技能 %.0f%% / 不带 %.0f%% → 差 %+.0f 个百分点  %s'
              % (name, r['rate'] * 100, b['rate'] * 100, d, flag))
    return worse


def main():
    ap = argparse.ArgumentParser(description='评测集跑分（三套基准，发版前跑）',
                                 epilog='例：python3 scripts/run_evals.py --only base-01')
    ap.add_argument('--only', help='只跑一套，如 base-01')
    ap.add_argument('--json', help='把结果写到这个 json，供 --baseline 比对')
    ap.add_argument('--baseline', help='对照组结果 json（不带技能跑出来的）')
    ap.add_argument('--evals-dir', help='评测集根目录，缺省用技能自带的 evals/（判对照组结果时指向临时目录）')
    a = ap.parse_args()

    root = os.path.abspath(a.evals_dir) if a.evals_dir else EVALS
    if not os.path.isdir(root):
        print('[缺基准] 找不到评测集目录：' + root)
        return 2
    bases = sorted(d for d in os.listdir(root)
                   if d.startswith('base-') and os.path.isdir(os.path.join(root, d)))
    if a.only:
        bases = [b for b in bases if b == a.only]
    if not bases:
        print('[缺基准] 没有可跑的 base-*')
        return 2

    cur = {}
    bad = 0
    for b in bases:
        res = run_base(os.path.join(root, b))
        if res is None:
            print('[跳过] %s 缺 expected.yaml' % b)
            continue
        show(res)
        cur[b] = res
        bad += res['failed']
    print()

    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump({k: {kk: vv for kk, vv in v.items() if kk != 'rows'} for k, v in cur.items()},
                      f, ensure_ascii=False, indent=2)
        print('结果已写入 ' + a.json)

    if a.baseline:
        if not os.path.isfile(a.baseline):
            print('[缺对照组] ' + a.baseline)
            return 2
        with open(a.baseline, encoding='utf-8') as f:
            base = json.load(f)
        bad += compare(cur, base)

    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
