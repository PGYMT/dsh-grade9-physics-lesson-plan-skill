#!/usr/bin/env python3
# 从技能 references 的 01/02 拼装工作区可复制提示词（唯一生成物，勿手工改）。
# 版本：v2.3（2026-09-30）  用法：python3 build_lesson_prompt.py
# 技能版本号从 SKILL.md frontmatter 自动读取，禁止在本脚本内写死。
import os, re
NL = chr(10)
SKILL = '/root/skill-repos/g9-physics'
OUT = '/root/dsh-workspace/工作文件/06-工具与提示词/提示词/md文件/教案生成要求提示词.md'
OUT_REF = '/root/dsh-workspace/工作文件/06-工具与提示词/提示词/md文件/教学研究参考.md'
OUT_IDX = '/root/dsh-workspace/工作文件/08-网络资源/教学资源网站索引.md'
def rd(p): return open(p, encoding="utf-8").read().rstrip()
def skill_version():
    m = re.search(r"^version:\s*([0-9][^\s]*)\s*$", rd(os.path.join(SKILL, "SKILL.md")), re.M)
    return m.group(1) if m else "unknown"
def copy_verbatim(rel, out):
    data = rd(os.path.join(SKILL, rel)) + NL
    open(out, 'w', encoding='utf-8').write(data)
    return out

def body(rel):
    lines = rd(os.path.join(SKILL, rel)).split(NL)
    out = []
    for i, ln in enumerate(lines):
        if ln.startswith("> 版本："):
            continue
        if i == 0 and ln.startswith("# "):
            continue
        out.append(ln)
    while out and out[0] == "":
        out.pop(0)
    return NL.join(out)
ver = skill_version()
head = [
    "# 教案生成要求提示词（通用版·九年级任意课时）",
    "",
    "> 用途：作为后续生成任意九年级物理课时教案的可复用提示词。",
    "> 版本：v" + ver + "（本文件由 build_lesson_prompt.py 自动生成，请勿手工修改）",
    "> 源文件：技能 references/01-教案生成要求.md ＋ 02-教学设计细则.md ＋ 06-课件修改与排版.md",
    "> 状态：与本文件冲突时，以技能 SKILL.md 与 references 为准。",
    "",
]
body_txt = body("references/01-教案生成要求.md") + NL + NL + body("references/02-教学设计细则.md") + NL + NL + "## 附录：课件修改与排版要求" + NL + NL + body("references/06-课件修改与排版.md")
open(OUT, "w", encoding="utf-8").write(NL.join(head) + NL + body_txt + NL)
print("OK", OUT, os.path.getsize(OUT), "skill v" + ver)
for rel, out in [("references/03-教学研究参考.md", OUT_REF),
                 ("references/05-教学资源网站.md", OUT_IDX)]:
    copy_verbatim(rel, out)
    print("OK", out, os.path.getsize(out))
