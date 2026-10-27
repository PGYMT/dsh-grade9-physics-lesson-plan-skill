#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_portability.py — 硬编码路径越线检查（v1.0，2026-10-27，纯标准库）。

路径的唯一真源是 references/data/paths.yaml。本脚本扫技能内所有 md，找出
/root/、/mnt/、/home/、Windows 盘符路径等与具体机器绑定的写法；
凡是规范路径（paths.yaml 里的值、以及 DEPENDENCIES.md 里反引号登记过的路径，
以及 /root/.dsh/skills/ 下的技能入口）之外的，一律报「文件:行 + 越线片段」。
排除 references/历史版本/ 与 *.local.md。

用法：
  python3 scripts/check_portability.py          # 扫描并判定，退出码 0/1
  python3 scripts/check_portability.py --list   # 只列规范路径与登记路径
越线修法：把绝对路径改成 paths.yaml 的键名说法，或在 DEPENDENCIES.md 登记一次。
"""
import argparse
import os
import re
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(SKILL_DIR, 'references', 'data', 'paths.yaml')
sys.path.insert(0, os.path.join(SKILL_DIR, 'scripts'))
import simple_yaml  # noqa: E402

STOP = r"[^\s\x60\"'）)，。；：、｜|<>\[\]]+"
TOKEN_RE = re.compile(r"(?:/root|/mnt|/home|/usr)/" + STOP
                      + r"|(?<![A-Za-z0-9])[A-Za-z]:[\\/](?![\\/])" + STOP)
REG_RE = re.compile(r"\x60([^\x60]*(?:/root|/mnt|[A-Za-z]:[\\/])[^\x60]*)\x60")
DOCS_FIXED = ['SKILL.md', 'README.md', 'DEPENDENCIES.md', 'CHANGELOG.md']


def norm(p):
    """统一路径写法：反斜杠转正斜杠、去掉尾部标点。"""
    return p.replace('\\', '/').rstrip('.,;:)')


def docs():
    """返回要扫描的 md（相对技能根）。"""
    out = [d for d in DOCS_FIXED if os.path.isfile(os.path.join(SKILL_DIR, d))]
    for sub in ('references', 'evals'):
        d = os.path.join(SKILL_DIR, sub)
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x != '历史版本']
            for n in sorted(files):
                if n.endswith('.md') and not n.endswith('.local.md'):
                    out.append(os.path.relpath(os.path.join(root, n), SKILL_DIR))
    return out


def allowed_paths():
    """规范路径：paths.yaml 的值 + DEPENDENCIES.md 里反引号登记的路径。"""
    data = simple_yaml.load(DATA)
    canon = []
    for _, v in data.items():
        if isinstance(v, str) and ('/' in v or '\\' in v or re.match(r'^[A-Za-z]:', v)):
            canon.append(norm(v))
    dep = os.path.join(SKILL_DIR, 'DEPENDENCIES.md')
    if os.path.isfile(dep):
        with open(dep, encoding='utf-8') as f:
            for m in REG_RE.finditer(f.read()):
                canon.append(norm(m.group(1).strip()))
    return canon


def is_allowed(tok, canon):
    """规范路径本身、子路径、或它的上级目录（如 /mnt/c）都放行。"""
    t = norm(tok)
    for c in canon:
        c2 = norm(c)
        if not c2:
            continue
        if t == c2 or t.startswith(c2.rstrip('/') + '/'):
            return True
        if c2.startswith(t.rstrip('/') + '/'):
            return True
    return t.startswith('/root/.dsh/skills/')


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='硬编码路径越线检查（v1.0）：路径唯一真源是 references/data/paths.yaml。',
        epilog='越线修法：把绝对路径改成 paths.yaml 的键名说法，或在 DEPENDENCIES.md 登记一次。',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--list', action='store_true', help='只列规范路径与登记路径')
    a = ap.parse_args(argv)

    canon = allowed_paths()
    if a.list:
        for c in canon:
            print('  ' + c)
        return 0

    bad = 0
    scanned = 0
    for rel in docs():
        scanned += 1
        with open(os.path.join(SKILL_DIR, rel), encoding='utf-8') as f:
            for i, line in enumerate(f.read().splitlines(), 1):
                for m in TOKEN_RE.finditer(line):
                    if not is_allowed(m.group(0), canon):
                        bad += 1
                        print('  [FAIL] %s:%d  %s' % (rel, i, m.group(0)))
    print('\n结果：扫描 %d 份 md，越线 %d 处（规范路径 %d 条）' % (scanned, bad, len(canon)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
