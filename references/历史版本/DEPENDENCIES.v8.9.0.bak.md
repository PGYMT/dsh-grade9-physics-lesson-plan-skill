# 依赖清单与自举（DEPENDENCIES.md）

> 版本：v8.9.0｜适用技能：generate-9th-grade-physics-lesson-plan
> 用途：换机器、换 DSH、或第一次运行本技能前，先读本文件并跑一次自检。
> 自检/自举脚本：`scripts/check_deps.py`（检测；`--install` 补工作区脚本；`--sync-dist` 反向同步）。

## 0. 一句话用法

```sh
python3 scripts/check_deps.py              # 看缺什么（退出码 0=必需项齐，1=有缺）
python3 scripts/check_deps.py --install    # 用 scripts/dist/ 里的副本补齐工作区脚本
python3 scripts/check_deps.py --sync-dist  # 改完工作区脚本后，同步回 scripts/dist/
```

## 1. 必需项

| 依赖 | 用途 | 检测 | 安装 / 缺失后果 |
|---|---|---|---|
| Python 3 | 全部脚本（只用标准库） | `python3 -V` | 装 3.10+；缺失则全部脚本不可用 |
| Pillow | board 围栏渲染板书 PNG | `python3 -c "import PIL"` | `pip install pillow`；若工作区 `06-工具与提示词/教程/vendor/` 有匹配当前解释器标签（cp3NN）的 `pillow-*.whl`，脚本会自动解压使用。缺失则 docx 里不会有板书图 |
| 中文字体 | 板书 PNG 上的中文 | 存在 `simkai.ttf`/`simhei.ttf` 或 Noto CJK | Windows 字体在 `/mnt/c/Windows/Fonts/`；缺失则退化为 DejaVu，中文可能显示为方框 |
| 工作区脚本 | 实际干活 | 见 `check_deps.py` 的 WS_SCRIPTS 清单 | `check_deps.py --install` 从 `scripts/dist/` 补齐；缺失则对应功能不可用 |
| SKILL.md | 版本标注（读 frontmatter） | 运行入口软链或权威源 | 读不到时 docx 写「版本未知」，不阻断生成 |

## 2. 可选项

| 依赖 | 用途 | 检测 | 安装 / 缺失后果 |
|---|---|---|---|
| ffmpeg / ffprobe | 课件视频抽帧、读取时长分辨率 | `which ffmpeg ffprobe` | `apt install ffmpeg`；缺失则视频只能用自带封面确认 |
| tesseract（含 chi_sim） | 课件截图 OCR 比对 | `tesseract --list-langs` | `apt install tesseract-ocr tesseract-ocr-chi-sim`；缺失则机器层比对不可用，改人工看截图 |

## 3. 仅 Windows（课件核对用）

| 依赖 | 用途 | 检测 | 缺失后果 |
|---|---|---|---|
| PowerShell | 运行 `enbx_verify2.ps1`（打开/跳页/截图） | `/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe` | 无法自动核对课件，改人工在希沃里看 |
| 希沃白板5 | 打开与核对 .enbx | Windows 已安装 | 无法核对 |
| Windows UI Automation | 左侧页码跳转、窗口截图 | 随 Windows 提供 | 同上 |

## 4. 交叉依赖

| 依赖 | 用途 |
|---|---|
| `auto-organize-work-files` 的 `organize.py` / `skill_link.py` / `sync_checklist.py` | 写文件前声明目的地、软链校验、联动判断清单 |
| DSH 工具 `read_image` / `web_search` / `web_fetch` | 图片识别、备课调研检索 |

## 5. 已知约束

- Pillow wheel 与 Python 解释器版本绑定（现有的是 cp314）；换 Python 版本必须重新下载对应 wheel。
- 工作区脚本的**权威位置在工作区**（`00-模板与规范/`、`06-工具与提示词/教程/`）；`scripts/dist/` 是单向同步的分发副本，改脚本请改工作区再 `--sync-dist`。
- 技能脚本运行需要工作区路径；换机器时工作区结构要一致（见 `references/04-技能维护规范.md` §1）。
