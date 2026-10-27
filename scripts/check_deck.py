#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""课件逐页清单校验（L1'）：6 项，写教案与改课件之前跑。

用法：
    python3 scripts/check_deck.py 某个课件清单.deck.json
    python3 scripts/check_deck.py 某个课件清单.deck.json --contract 课程契约.json

6 项分别是：
    1 页号从 1 连续
    2 每页有 shot 且文件存在
    3 animations 与 reveal_order 长度一致
    4 knowledge 非空
    5 总页数至少 1
    6 id 与课程契约的 section 一致（没给 --contract 时跳过）

退出码：0 全过；1 有失败项。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)

EPILOG = """字段词表（详见 schemas/deck.schema.json）：
  id            节号，如 15.2；必须与课程契约的 section 一致
  file          课件文件名，如 15.2第2节  电流和电路.enbx
  pages         页清单，至少 1 页
    no          页号，从 1 连续
    title       页标题（与课件上一致）
    knowledge   本页知识点，至少 1 条
    animations  本页点击出现次数
    reveal_order 点击后依次出现什么，条数必须等于 animations
    shot        本页截图路径，相对本清单所在目录

最小示例（也可直接看 schemas/example.deck.json）：
{
  "id": "15.2",
  "file": "15.2第2节  电流和电路.enbx",
  "pages": [
    {"no": 1, "title": "封面", "knowledge": ["章节课名"],
     "animations": 0, "reveal_order": [], "shot": "shots/p01.png"}
  ]
}
"""


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="课件逐页清单校验：6 项，写教案与改课件之前跑。",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("deck", help="课件逐页清单 json 路径")
    ap.add_argument("--contract", default="", help="可选的课程契约 json；给了就校验第 6 项（id 与 section 一致）")
    a = ap.parse_args(argv)

    results = []

    def item(n, name, ok, detail=""):
        results.append((n, name, ok))
        print("  [%s] 第%d项 %s%s" % ("PASS" if ok else "FAIL", n, name, ("  " + detail) if detail else ""))

    deck_path = os.path.abspath(a.deck)
    deck_dir = os.path.dirname(deck_path)
    print("== 课件逐页清单校验（L1'）==  %s" % deck_path)

    try:
        with open(deck_path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError) as e:
        item(1, "清单可读", False, "读不出或不是合法 JSON：%s" % e)
        print("\n结果：1 项，失败 1 项")
        return 1

    pages = d.get("pages")
    if not isinstance(pages, list):
        pages = []
        item(1, "清单有 pages 数组", False, "当前 pages=%r" % d.get("pages"))
    else:
        nos = [p.get("no") for p in pages if isinstance(p, dict)]
        want = list(range(1, len(nos) + 1))
        item(1, "页号从 1 连续", nos == want,
             "当前页号 %s；应为 %s" % (nos, want) if nos != want else "%d 页，页号连续" % len(nos))

    missing = []
    no_shot = []
    for p in pages:
        if not isinstance(p, dict):
            continue
        shot = p.get("shot") or ""
        if not shot:
            no_shot.append(p.get("no"))
        elif not os.path.isfile(os.path.join(deck_dir, shot)):
            missing.append("第%s页 %s" % (p.get("no"), shot))
    ok2 = bool(pages) and not missing and not no_shot
    item(2, "每页有 shot 且文件存在", ok2,
         ("缺截图文件：%s" % "; ".join(missing)) if missing else
         ("这些页没写 shot：%s" % no_shot) if no_shot else
         "%d 页截图都在" % len(pages))

    bad3 = []
    for p in pages:
        if not isinstance(p, dict):
            continue
        anim = p.get("animations")
        n = len(p.get("reveal_order") or [])
        if not isinstance(anim, int) or anim != n:
            bad3.append("第%s页 animations=%r，reveal_order=%d 条" % (p.get("no"), anim, n))
    item(3, "animations 与 reveal_order 长度一致", not bad3, "; ".join(bad3))

    bad4 = [str(p.get("no")) for p in pages if isinstance(p, dict) and not (p.get("knowledge") or [])]
    item(4, "knowledge 非空", not bad4, ("这些页 knowledge 为空：%s" % "、".join(bad4)) if bad4 else "")

    item(5, "总页数至少 1", len(pages) >= 1, "当前 %d 页" % len(pages))

    if not a.contract:
        item(6, "id 与课程契约一致", True, "没给 --contract，跳过")
        results[-1] = (6, "id 与课程契约一致", True)
        print("  [SKIP] 第6项 id 与课程契约一致  没给 --contract")
        results.pop()
    else:
        try:
            with open(a.contract, encoding="utf-8") as f:
                c = json.load(f)
        except (OSError, ValueError) as e:
            item(6, "id 与课程契约一致", False, "契约读不出：%s" % e)
        else:
            sec = str(c.get("section") or "")
            item(6, "id 与课程契约一致", str(d.get("id")) == sec,
                 "清单 id=%r，契约 section=%r" % (d.get("id"), sec))

    bad = [n for n, _, ok in results if not ok]
    print("\n结果：%d 项，失败 %d 项" % (len(results), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
