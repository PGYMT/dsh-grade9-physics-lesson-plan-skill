#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inject_version.py — 技能版本号单源注入与校验（v1.0，2026-10-27）。

唯一真源：SKILL.md frontmatter 的 version 行。
其余位置的文件头都写 `> 版本：v{{VERSION}}`，由本脚本注入：
  1. SKILL.md 正文首行
  2. README.md、DEPENDENCIES.md
  3. references/ 下自动发现的 00–08 各文件头
历史记录（references/04 §6 变更记录、README 版本记录）不参与注入。

用法：
  python3 scripts/inject_version.py            # 只校验：全部一致退出 0，否则报文件与行并退出 1
  python3 scripts/inject_version.py --write    # 把 frontmatter 版本注入其余各处的占位符
  python3 scripts/inject_version.py --template # 反向：把已注入的具体版本改回占位符（准备下一次升版）
退出码：0＝一致或写入成功；1＝有残留占位符或版本不一致。
"""
import argparse
import os
import re
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = '{{VERSION}}'
HEADER_RE = re.compile(r'^(>[ \t]*版本：v)(\S+?)(｜.*)?$', re.M)
REF_NAME_RE = re.compile(r'^[0-9]{2}-.+\.md$')


def targets():
    """返回参与版本号注入的文件（相对技能根）。"""
    out = ['SKILL.md', 'README.md', 'DEPENDENCIES.md']
    d = os.path.join(SKILL_DIR, 'references')
    if os.path.isdir(d):
        for n in sorted(os.listdir(d)):
            if REF_NAME_RE.match(n) and not n.endswith('.local.md'):
                out.append(os.path.join('references', n))
    return out


def read_frontmatter():
    """从 SKILL.md frontmatter 取版本号；取不到返回 None。"""
    p = os.path.join(SKILL_DIR, 'SKILL.md')
    if not os.path.isfile(p):
        return None
    head = open(p, encoding='utf-8').read().splitlines()[:20]
    for i, line in enumerate(head):
        m = re.match(r'^version:\s*(\S+)\s*$', line)
        if m:
            return m.group(1)
        if i > 0 and line.strip() == '---':
            break
    return None


def scan():
    """逐个文件找出所有版本头，返回 [(相对路径, 行号, 当前值)]。"""
    rows = []
    for rel in targets():
        p = os.path.join(SKILL_DIR, rel)
        if not os.path.isfile(p):
            continue
        for i, line in enumerate(open(p, encoding='utf-8').read().splitlines(), 1):
            m = HEADER_RE.match(line)
            if m:
                rows.append((rel, i, m.group(2)))
    return rows


def write(version):
    """把各文件头的版本值替换成 frontmatter 版本；返回替换处数。"""
    n = 0
    for rel in targets():
        p = os.path.join(SKILL_DIR, rel)
        if not os.path.isfile(p):
            continue
        s = open(p, encoding='utf-8').read()
        s2, k = HEADER_RE.subn(lambda m: m.group(1) + version + (m.group(3) or ''), s)
        if k:
            open(p, 'w', encoding='utf-8').write(s2)
            n += k
    return n


def write_template():
    """把各文件头的具体版本改回占位符；返回替换处数。"""
    n = 0
    for rel in targets():
        p = os.path.join(SKILL_DIR, rel)
        if not os.path.isfile(p):
            continue
        s = open(p, encoding='utf-8').read()
        s2, k = HEADER_RE.subn(lambda m: m.group(1) + TOKEN + (m.group(3) or ''), s)
        if k:
            open(p, 'w', encoding='utf-8').write(s2)
            n += k
    return n


def check():
    """校验：无占位符残留、无缺头、全部等于 frontmatter；返回 (失败列表, 处数, 版本)。"""
    ver = read_frontmatter()
    rows = scan()
    bad = []
    if not ver:
        bad.append(('SKILL.md', 0, 'frontmatter 里找不到 version'))
    for rel, line, val in rows:
        if val == TOKEN:
            bad.append((rel, line, '残留占位符 ' + TOKEN + '，跑 --write 注入'))
        elif val != ver:
            bad.append((rel, line, '当前 v%s，应为 v%s' % (val, ver)))
    return bad, len(rows), ver


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='技能版本号单源注入与校验（v1.0）：唯一真源是 SKILL.md frontmatter 的 version。',
        epilog='版本头格式：> 版本：v%s（可跟｜备注）\n'
               '例：python3 scripts/inject_version.py --template && 改 SKILL.md frontmatter && python3 scripts/inject_version.py --write',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--write', action='store_true', help='把 frontmatter 版本注入其余各处的占位符')
    g.add_argument('--template', action='store_true', help='反向：把各处具体版本改回占位符')
    a = ap.parse_args(argv)

    if a.template:
        n = write_template()
        print('已改回占位符 %d 处' % n)
        return 0
    ver = read_frontmatter()
    if a.write:
        if not ver:
            print('[FAIL] SKILL.md frontmatter 里找不到 version')
            return 1
        n = write(ver)
        print('已注入 v%s 共 %d 处' % (ver, n))
        return 0

    bad, total, ver = check()
    if bad:
        for rel, line, msg in bad:
            print('[FAIL] %s:%d  %s' % (rel, line, msg))
        print('结果：%d 处版本头，失败 %d 处（真源 v%s）' % (total, len(bad), ver))
        return 1
    print('结果：%d 处版本头，全部一致（v%s）' % (total, ver))
    return 0


if __name__ == '__main__':
    sys.exit(main())
