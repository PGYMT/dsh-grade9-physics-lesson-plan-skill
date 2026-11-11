#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""enbx_shot_ocr.py -- enbx screenshot MACHINE layer (tesseract).

Reads the PNGs produced by enbx_verify2.ps1, OCRs each with tesseract
(chi_sim+eng), normalises the text, and checks expected_pages.json:
  must / must_not        checked on the "before click" shot (p N _0.png)
  after_click.steps      checked on the "after K clicks" shots (p N _aK.png)
  same_page_required     page number must not change between before/after

Because a PrintWindow shot contains the whole EasiNote window (toolbar,
slide list, inspector panel), the full image confuses tesseract.  By
default --crop auto OCRs a few candidate crops of the slide canvas and
keeps the one with the best score (CJK char count minus app-chrome hits).

Severity (two-layer design):
  FAIL = hard machine failure: missing shot, forbidden word present, or the
         page number changed on click.  These drive a non-zero exit code.
  MISS = tesseract did not find a "must" word.  Small text, white-on-colour
         banners and rotated (vertical) text are exactly what tesseract
         cannot read, so a MISS is handed to the VISUAL layer (read_image)
         and only fails the run when --strict is given.

Exit code: 0 = no hard failures (and no MISS in --strict), else 1.
"""
import argparse
import difflib
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata

TAB = "\t"
CHROME = ["希沃白板", "文件", "同步", "撤消", "撤销", "恢复", "文本", "形状", "多媒体", "表格",
          "课堂活动", "思维导图", "学科工具", "布局与背景", "属性", "新建页面", "分享",
          "动画", "关联", "更多背景", "更改布局", "应用主题", "本地图片"]
CANDS = {
    "edit": (0.10, 0.18, 0.78, 0.85),     # edit mode: slide canvas between panels
    "present": (0.0, 0.0, 1.0, 0.94),       # presentation mode: drop the bottom toolbar
    "full": (0.0, 0.0, 1.0, 1.0),
}


def get_pil():
    try:
        from PIL import Image
        return Image
    except Exception:
        libs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "_libs")
        if os.path.isdir(libs):
            sys.path.insert(0, libs)
        try:
            from PIL import Image
            return Image
        except Exception:
            return None


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("\u3000", " ")
    s = re.sub(r"\s+", "", s)
    return s.lower()


def ocr_path(png: str, lang: str, psm: str, tesseract: str = "tesseract") -> str:
    cmd = [tesseract, png, "stdout", "-l", lang, "--psm", str(psm)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError:
        sys.stderr.write("tesseract not found on PATH: " + tesseract + "\n")
        sys.exit(2)
    return r.stdout or ""


def score_text(t: str) -> int:
    cjk = sum(1 for ch in t if "\u4e00" <= ch <= "\u9fff")
    chrome = sum(t.count(w) for w in CHROME)
    return cjk - 4 * chrome


def ocr_image(png: str, lang: str, psm: str, tesseract: str, tmpdir: str, crop: str):
    """Return (text, crop_used).  crop = 'auto' | 'none' | 'L,T,R,B'."""
    key = crop.lower()
    if key == "none":
        return ocr_path(png, lang, psm, tesseract), None
    Image = get_pil()
    if Image is None:
        sys.stderr.write("Pillow unavailable; OCR on the uncropped image\n")
        return ocr_path(png, lang, psm, tesseract), None
    im = Image.open(png).convert("RGB")
    W, H = im.size
    named = {"edit": CANDS["edit"], "present": CANDS["present"], "full": CANDS["full"]}
    if key in named:
        cands = [named[key]]
    elif key == "auto":
        cands = [CANDS["edit"], CANDS["present"], CANDS["full"]]
    else:
        cands = [tuple(float(x) for x in crop.split(","))]
    best = None
    for (l, t, r, b) in cands:
        box = (int(l * W), int(t * H), int(r * W), int(b * H))
        c = im.crop(box)
        if c.width < 20 or c.height < 20:
            continue
        if key == "present":
            # a 4K fullscreen shot must be downscaled, not upscaled, for tesseract
            if c.width > 1920:
                c = c.resize((1920, int(c.height * 1920.0 / c.width)), Image.LANCZOS)
        else:
            c = c.resize((int(c.width * 1.5), int(c.height * 1.5)), Image.LANCZOS)
        cp = os.path.join(tmpdir, os.path.basename(png) + ("_%.2f_%.2f.png" % (l, t)))
        c.save(cp)
        txt = ocr_path(cp, lang, psm, tesseract)
        sc = score_text(txt)
        if best is None or sc > best[0]:
            best = (sc, txt, (l, t, r, b))
    if best is None:
        return ocr_path(png, lang, psm, tesseract), None
    return best[1], best[2]


def hit(text_n: str, phrase: str, min_sim: float):
    p = norm(phrase)
    if not p:
        return True, 1.0, "empty"
    if p in text_n:
        return True, 1.0, "substr"
    if len(p) <= 2:
        return False, 0.0, "short-no-fuzzy"
    L = len(p)
    best = 0.0
    if len(text_n) < L:
        best = difflib.SequenceMatcher(None, p, text_n).ratio()
    else:
        for i in range(0, len(text_n) - L + 1):
            r = difflib.SequenceMatcher(None, p, text_n[i:i + L]).ratio()
            if r > best:
                best = r
                if best >= 0.995:
                    break
    return (best >= min_sim), best, "fuzzy"


def load_shots(shots_dir: str):
    info = {}
    p = os.path.join(shots_dir, "shots.txt")
    if not os.path.exists(p):
        return info
    with open(p, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line or line.startswith("page" + TAB):
                continue
            parts = line.split(TAB)
            if len(parts) < 5:
                continue
            fname = os.path.basename(parts[2])
            try:
                at = int(parts[3])
            except Exception:
                at = None
            try:
                clicks = int(parts[4])
            except Exception:
                clicks = 0
            info[fname] = {"page": int(parts[0]), "phase": parts[1],
                           "page_at_shot": at, "clicks": clicks}
    return info


def discover(shots_dir: str):
    pages = {}
    for path in sorted(glob.glob(os.path.join(shots_dir, "p*_*.png"))):
        name = os.path.basename(path)
        m = re.match(r"^p(\d+)_0\.png$", name)
        if m:
            pages.setdefault(int(m.group(1)), {})["before"] = path
            continue
        m = re.match(r"^p(\d+)_a(\d+)\.png$", name)
        if m:
            pages.setdefault(int(m.group(1)), {}).setdefault("after", {})[int(m.group(2))] = path
    return pages


def main():
    ap = argparse.ArgumentParser(description="enbx screenshot machine-layer OCR checks")
    ap.add_argument("--shots-dir", required=True)
    ap.add_argument("--expected", required=True)
    ap.add_argument("--pages", default="", help="comma list, empty = all pages found")
    ap.add_argument("--lang", default="chi_sim+eng")
    ap.add_argument("--psm", default="3")
    ap.add_argument("--minsim", type=float, default=0.80)
    ap.add_argument("--crop", default="edit",
                    help="edit (default, canvas crop for the editor window) | present (presentation mode) | "
                         "auto | none | L,T,R,B (fractions of the image)")
    ap.add_argument("--tesseract", default="tesseract")
    ap.add_argument("--no-anim-checks", action="store_true",
                    help="editor-mode shots: skip must_not and after_click checks "
                         "(edit mode shows animated elements, so answers are always visible)")
    ap.add_argument("--strict", action="store_true",
                    help="treat a tesseract MISS as failure (default: MISS goes to the visual layer)")
    ap.add_argument("--dump-text", action="store_true", help="print raw OCR text")
    ap.add_argument("--report-dir", default="",
                    help="where to write ocr_report.md/.json; default "
                         "<expected-dir>/ocr_reports/<shots-basename> (/mnt/c is read-only)")
    ap.add_argument("--compare-dir", default="",
                    help="reference shots dir; when set, only the OCR text similarity of matching "
                         "pN_0.png files is computed (T15 original-vs-copy check)")
    ap.add_argument("--compare-minsim", type=float, default=0.90,
                    help="minimum difflib similarity for --compare-dir (default 0.90)")
    args = ap.parse_args()

    with open(args.expected, encoding="utf-8") as fh:
        exp_all = json.load(fh)
    exp_pages = exp_all.get("pages", {})

    shots_dir = os.path.abspath(args.shots_dir)
    if not os.path.isdir(shots_dir):
        sys.stderr.write("shots dir not found: " + shots_dir + "\n")
        sys.exit(2)

    want = [int(x) for x in args.pages.split(",") if x.strip()] if args.pages.strip() else []
    found = discover(shots_dir)
    targets = want if want else sorted(found.keys())
    shots_info = load_shots(shots_dir)
    tmpdir = tempfile.mkdtemp(prefix="enbx_ocr_")

    texts = {}
    crops = {}
    rows = []
    hard = []
    miss = []

    def get_text(png):
        if png not in texts:
            txt, cr = ocr_image(png, args.lang, args.psm, args.tesseract, tmpdir, args.crop)
            texts[png] = txt
            crops[png] = cr
            if args.dump_text:
                print("=" * 70)
                print("OCR " + os.path.basename(png) + "  crop=" + str(cr))
                print(txt.strip())
        return texts[png]

    def snippet(png):
        return get_text(png).replace("\n", " ").strip()[:150]

    if args.compare_dir:
        ref_dir = os.path.abspath(args.compare_dir)
        h2 = ["页号", "相似度", "判定", "说明"]
        rows2 = []
        bad2 = []
        for pg in targets:
            a = os.path.join(shots_dir, "p%d_0.png" % pg)
            b = os.path.join(ref_dir, "p%d_0.png" % pg)
            if not os.path.exists(a) or not os.path.exists(b):
                rows2.append([str(pg), "-", "FAIL",
                              "缺截图 本目录=" + str(os.path.exists(a)) + " 对比目录=" + str(os.path.exists(b))])
                bad2.append("p%d missing screenshot" % pg)
                continue
            ta = norm(get_text(a))
            tb = norm(get_text(b))
            ratio = difflib.SequenceMatcher(None, ta, tb).ratio()
            ok = ratio >= args.compare_minsim
            rows2.append([str(pg), "%.3f" % ratio, "PASS" if ok else "FAIL",
                          "OCR文本相似度(阈值%.2f)" % args.compare_minsim])
            if not ok:
                bad2.append("p%d similarity %.3f (threshold %.2f)" % (pg, ratio, args.compare_minsim))
        print("")
        print("T15 原件 vs 副本 同页 OCR 文本相似度")
        print("副本: " + shots_dir)
        print("原件: " + ref_dir)
        w2 = [min(max([len(str(r[i])) for r in ([h2] + rows2)]), 46) for i in range(len(h2))]
        def fmt2(r):
            return " | ".join(str(r[i])[:w2[i]].ljust(w2[i]) for i in range(len(h2)))
        print(fmt2(h2))
        print("-+-".join("-" * x for x in w2))
        for r in rows2:
            print(fmt2(r))
        rep_dir = (args.report_dir or "").strip()
        if not rep_dir:
            rep_dir = os.path.join(os.path.dirname(os.path.abspath(args.expected)), "ocr_reports",
                                   "compare-" + os.path.basename(shots_dir.rstrip("/" + os.sep)))
        try:
            os.makedirs(rep_dir, exist_ok=True)
        except OSError:
            rep_dir = shots_dir
        rep = {"mode": "compare", "shots_dir": shots_dir, "reference_dir": ref_dir,
               "compare_minsim": args.compare_minsim, "rows": [dict(zip(h2, r)) for r in rows2],
               "failures": bad2, "pass": not bad2, "report_dir": rep_dir}
        jp = os.path.join(rep_dir, "compare_report.json")
        with open(jp, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, ensure_ascii=False, indent=2)
        mp = os.path.join(rep_dir, "compare_report.md")
        with open(mp, "w", encoding="utf-8") as fh:
            fh.write("# T15 原件 vs 副本 同页 OCR 文本相似度\n\n")
            fh.write("- 副本: " + shots_dir + "\n- 原件: " + ref_dir + "\n")
            fh.write("- 阈值: %.2f\n\n" % args.compare_minsim)
            fh.write("| " + " | ".join(h2) + " |\n")
            fh.write("|" + "|".join(["---"] * len(h2)) + "|\n")
            for r in rows2:
                fh.write("| " + " | ".join(str(x) for x in r) + " |\n")
            if bad2:
                fh.write("\n## 失败\n\n")
                for x in bad2:
                    fh.write("- " + x + "\n")
        print("")
        print("T15 结论: " + ("全部通过" if not bad2 else "有 " + str(len(bad2)) + " 页未达标"))
        print("报告: " + mp)
        sys.exit(1 if bad2 else 0)

    for pg in targets:
        key = str(pg)
        exp = exp_pages.get(key)
        if exp is None:
            rows.append([key, "-", "SKIP", "预期清单无此页", "待视觉层", "skip"])
            continue
        imgs = found.get(pg, {})
        if not imgs:
            msg = "没有截图（脚本未跑，或该页未命中）"
            rows.append([key, "-", "FAIL", msg, "待视觉层", "机器失败"])
            hard.append("p" + str(pg) + " " + msg)
            continue

        png0 = imgs.get("before")
        if png0:
            t = norm(get_text(png0))
            missed = [p for p in exp.get("must", []) if not hit(t, p, args.minsim)[0]]
            forbidden = [] if args.no_anim_checks else [p for p in exp.get("must_not", []) if hit(t, p, args.minsim)[0]]
            if forbidden:
                detail = "禁止词误现:" + "/".join(forbidden) + " | OCR:" + snippet(png0)
                rows.append([key, os.path.basename(png0), "FAIL", detail, "待视觉层", "机器失败"])
                hard.append("p" + str(pg) + " before 误现: " + "/".join(forbidden))
            elif missed:
                detail = "未命中:" + "/".join(missed) + " | OCR:" + snippet(png0)
                rows.append([key, os.path.basename(png0), "MISS", detail, "待视觉层",
                             "机器未命中(交视觉层)"])
                miss.append("p" + str(pg) + " before 未命中: " + "/".join(missed))
            else:
                rows.append([key, os.path.basename(png0), "PASS", "必现词全中", "待视觉层", "机器通过"])
        else:
            rows.append([key, "-", "FAIL", "无点击前截图", "待视觉层", "机器失败"])
            hard.append("p" + str(pg) + " missing before shot")

        ac = exp.get("after_click") or {}
        if args.no_anim_checks:
            ac = {}
        for st in ac.get("steps") or []:
            k = int(st.get("clicks", 1))
            fa = (imgs.get("after") or {}).get(k)
            tag = key + " +" + str(k) + "click"
            if not fa:
                rows.append([tag, "-", "FAIL", "无第" + str(k) + "次点击后截图", "待视觉层", "机器失败"])
                hard.append("p" + str(pg) + " missing after" + str(k))
                continue
            t = norm(get_text(fa))
            missed = [p for p in st.get("must", []) if not hit(t, p, args.minsim)[0]]
            forbidden = [p for p in st.get("must_not", []) if hit(t, p, args.minsim)[0]]
            if forbidden:
                detail = "禁止词误现:" + "/".join(forbidden) + " | OCR:" + snippet(fa)
                rows.append([tag, os.path.basename(fa), "FAIL", detail, "待视觉层", "机器失败"])
                hard.append("p" + str(pg) + " after" + str(k) + " 误现: " + "/".join(forbidden))
            elif missed:
                detail = "未命中:" + "/".join(missed) + " | OCR:" + snippet(fa)
                rows.append([tag, os.path.basename(fa), "MISS", detail, "待视觉层",
                             "机器未命中(交视觉层)"])
                miss.append("p" + str(pg) + " after" + str(k) + " 未命中: " + "/".join(missed))
            else:
                rows.append([tag, os.path.basename(fa), "PASS", "点击后必现词全中", "待视觉层", "机器通过"])

        if (not args.no_anim_checks) and ac.get("same_page_required") and (imgs.get("after") or {}):
            before_at = (shots_info.get(os.path.basename(png0), {}) or {}).get("page_at_shot") if png0 else None
            bad = []
            for k, fa in sorted((imgs.get("after") or {}).items()):
                aat = (shots_info.get(os.path.basename(fa), {}) or {}).get("page_at_shot")
                if before_at is not None and aat is not None and before_at != aat:
                    bad.append((k, before_at, aat))
            if bad:
                detail = "点击后页码变化 " + str(bad) + "（做成了新页，不是页内动画）"
                rows.append([key, "-", "FAIL", detail, "待视觉层", "机器失败"])
                hard.append("p" + str(pg) + " page changed: " + str(bad))
            else:
                rows.append([key, "-", "PASS", "点击前后页码未变(" + str(before_at) + ")",
                             "待视觉层", "机器通过"])

        for v in exp.get("visual", []):
            rows.append([key, "-", "-", v, "待视觉层", "待判"])

    header = ["页号", "截图", "机器判定", "说明", "视觉判定", "结论"]
    print("")
    print("机器层判读表（tesseract " + args.lang + " / psm " + str(args.psm) + " / minsim " + str(args.minsim) +
          " / crop " + args.crop + (" / strict" if args.strict else "") + "）")
    print("shots dir: " + shots_dir)
    print("裁剪方式: " + ", ".join(os.path.basename(k) + "=" + str(v) for k, v in crops.items()))
    widths = [min(max([len(str(r[i])) for r in ([header] + rows)]), 46) for i in range(len(header))]
    def fmt(r):
        return " | ".join(str(r[i])[:widths[i]].ljust(widths[i]) for i in range(len(header)))
    print(fmt(header))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(fmt(r))

    verdict = "全部通过" if not hard and not miss else (
        "硬失败 " + str(len(hard)) + " 项" + ("；未命中 " + str(len(miss)) + " 项(交视觉层)" if miss else ""))
    report = {
        "shots_dir": shots_dir, "expected": os.path.abspath(args.expected),
        "lang": args.lang, "psm": args.psm, "minsim": args.minsim, "crop": args.crop,
        "strict": bool(args.strict), "targets": targets,
        "crops_used": {os.path.basename(k): v for k, v in crops.items()},
        "rows": [dict(zip(header, r)) for r in rows],
        "hard_failures": hard, "machine_misses": miss, "machine_verdict": verdict,
    }
    rep_dir = (args.report_dir or "").strip()
    if not rep_dir:
        rep_dir = os.path.join(os.path.dirname(os.path.abspath(args.expected)), "ocr_reports",
                               os.path.basename(shots_dir.rstrip("/" + os.sep)))
    try:
        os.makedirs(rep_dir, exist_ok=True)
    except OSError:
        rep_dir = shots_dir
    report["report_dir"] = rep_dir
    json_path = os.path.join(rep_dir, "ocr_report.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    md_path = os.path.join(rep_dir, "ocr_report.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("# OCR 机器层判读表\n\n")
        fh.write("- shots dir: " + shots_dir + "\n")
        fh.write("- lang/psm/minsim/crop: " + args.lang + " / " + str(args.psm) + " / " +
                 str(args.minsim) + " / " + args.crop + (" / strict" if args.strict else "") + "\n")
        fh.write("- 机器层结论: **" + verdict + "**\n\n")
        fh.write("> PASS=机器通过；MISS=tesseract 未命中，交视觉层判定；FAIL=硬失败。\n\n")
        fh.write("| " + " | ".join(header) + " |\n")
        fh.write("|" + "|".join(["---"] * len(header)) + "|\n")
        for r in rows:
            fh.write("| " + " | ".join(str(x) for x in r) + " |\n")
        if hard:
            fh.write("\n## 硬失败\n\n")
            for x in hard:
                fh.write("- " + x + "\n")
        if miss:
            fh.write("\n## 未命中（交视觉层）\n\n")
            for x in miss:
                fh.write("- " + x + "\n")
    print("")
    print("机器层结论: " + verdict)
    print("报告: " + md_path)
    print("报告: " + json_path)
    sys.exit(1 if (hard or (args.strict and miss)) else 0)


if __name__ == "__main__":
    main()
