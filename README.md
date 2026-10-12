# dsh-grade9-physics-lesson-plan-skill

> 版本：v8.14.0

九年级物理教案生成 Skill，基于希沃白板 `.enbx` 或类似课件生成/修改教案。本仓库是技能文件的**权威源**（`SKILL.md` + `references/01–07` + 本说明）；运行入口 `~/.dsh/skills/generate-9th-grade-physics-lesson-plan` 是指向本仓库本地克隆的软链。

## 功能特点

- 只出详案/逐字稿（1 份 Markdown 工作稿＋1 份 Word 上课稿），默认每课时 40 分钟。
- 备课调研必做：先查本地存档与《备课缺口表》，按《教学资源取件手册》九章顺序自己抓，按《网络资源参考价值评价维度》逐份过门槛＋打分（甲/乙/丙），有效数不足才出《人工取件清单》；摘要先给用户确认，可用内容落地 08-网络资源/；跑 scripts/check_research.py 才进写稿。
- 板书成品化：最多 2 块、每块 ≤8 行、每行 ≤14 字；md 用 board 围栏，docx 插入渲染好的板书图。
- 教学目标按核心素养四维度、学生视角、可测可评；重难点就地写；过渡语服务真实逻辑关系。
- 可对 .enbx 副本加原生页（答案点击出现），原件逐字节不动；可修订已有教案。
- 外部校验：scripts/check_research.py 判调研完成度、scripts/check_lesson.py 判板书规格（v9 生成 docx 时自动调用），负样本自检 scripts/tests/run_tests.py。
- 依赖自举：换机器先跑 scripts/check_deps.py。

详细口径以 SKILL.md 与 references/01–07 为准：内容见 01，教学设计细则见 02，文献见 03，维护见 04，资源取件见 05，课件修改见 06，备课调研判定见 07。

## 使用方法

1. 克隆到 `/root/skill-repos/g9-physics`，再用整理技能的 `scripts/skill_link.py link` 把 `~/.dsh/skills/generate-9th-grade-physics-lesson-plan` 建成指向它的软链（不要再放项目级副本，项目级会抢优先级）。
2. 向 Agent 提供 `.enbx` 课件路径或说明课时信息。
3. Agent 加载 `SKILL.md`（入口），按其索引按需读取 `references/`，默认输出详案 Word + Markdown。

## 目录结构

```text
.
├── SKILL.md                    # 入口：触发 / 确认 / 流程 / 硬约束 / 索引
├── references/
│   ├── 01-教案生成要求.md       # 教学内容主体（角色、交付形式、教案结构、需求 1–9、备课调研）
│   ├── 02-教学设计细则.md       # 教学语言红线、板书规格、标注体系、目标精简、教案自检清单
│   ├── 03-教学研究参考.md       # 关键观点与文献（按需求号）+ 分时段附录
│   ├── 04-技能维护规范.md       # 文件构成、命名、同步、版本、脚本、变更记录
│   ├── 05-教学资源网站.md       # 教学资源取件手册（9 章，站点唯一权威）
│   ├── 06-课件修改与排版.md     # 课件（.enbx）修改与排版的执行口径
│   └── 07-网络资源参考价值评价维度.md # 备课调研判定口径（门槛＋有效性打分）
├── DEPENDENCIES.md             # 依赖清单与自举说明
├── scripts/                    # check_deps/check_structure/check_research/check_lesson + tests/ 负样本 + dist/ 分发副本
└── README.md                   # 本说明
```

## 维护

- 只改本仓库；改前备份到 `references/历史版本/`，改后跑：
  - `python3 /root/.dsh/skills/auto-organize-work-files/scripts/skill_link.py verify`
  - `python3 /root/.dsh/skills/auto-organize-work-files/scripts/sync_checklist.py --apply`
  - 重新生成工作区生成物：`python3 "/root/dsh-workspace/工作文件/06-工具与提示词/教程/build_lesson_prompt.py"`
  - 课件修改脚本在 `06-工具与提示词/教程/`（build_enbx_native_pages.py、enbx_verify2.ps1、enbx_shot_ocr.py、expected_pages.json、extract_video_frames.py）
  - 依赖自检与分发同步：`python3 scripts/check_deps.py --sync-dist`
- 详细流程见 `references/04-技能维护规范.md`；与整理技能的分工见其中的第 5 节。

## 版本记录

完整变更记录见 references/04-技能维护规范.md §6。高层里程碑：

- v8.14.0：修复备课调研溯源误判（章节目录名含空格必被截断）、存量摘要迁移缺步骤、「声明目的地」口径与失效交叉引用；新增通用加页脚本 enbx_add_pages.py（支持中间插页，字号 <28 磅与内容 >540px 判 FAIL）。
- v8.13.0：修 6 遍审查发现的缺陷——check_lesson.py 改按「## 板N」计板书行数（不再把一围栏两块合起来误判）、两个校验脚本输出带项号、练习课命名与校验正则统一、07 补关键维 0 分的等级兜底，并同步各文件版本与口径。

- v8.12.0：采纳《网络资源参考价值评价维度》（新增 references/07）——可用性门槛＋分类型有效性打分（甲/乙/丙），中断改按有效数（甲＋乙）；check_research.py 增「逐份判定」块与有效数校验。

- v8.11.0：check_research.py 增第 7 失败项——摘要「可用」数不得超过实际正文达标文件数，某类可用不足时须已出《人工取件清单》；正文达标底线机械化；05 删去实测不可用的 3 个站。

- v8.10.0：references/05 重写为 9 章《教学资源取件手册》；备课调研改为取件手册驱动并加 check_research.py；新增 check_lesson.py（板书规格，v9 生成时自动调用）与负样本自检。

- v8.7.0：备课调研七维度与分课时安排表、视频抽帧；docx 生成信息块与待查/过渡样式；新增 DEPENDENCIES.md 与 scripts/。
- v8.5.0：课件修改与排版纳入技能（references/06）。
- v8.4.0：教学目标对齐课标（四维度、条件/标准、单元定位、评价证据）。
- v8.1.0–v8.3.0：板书成品化、重难点精简、反重复红线、先声明后落地、权威源独立仓库＋软链。
- v8.0.0：备课调研、.enbx 动画还原、板书卡、标注体系、05 资源网站。
