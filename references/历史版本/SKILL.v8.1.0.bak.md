---
name: generate-9th-grade-physics-lesson-plan
version: 8.1.0
description: Use when the user asks to generate or revise a Grade 9 physics lesson plan from a Seewo EasiNote .enbx or similar whiteboard courseware, or references the saved 教案生成要求/通用版教案生成要求. Defaults to 40 minutes per period, confirms the number of periods, outputs only the 详案/逐字稿 (a full Markdown working copy and a clean Word teaching copy), and covers new-lesson and practice/review-lesson structures. It researches excellent lesson plans and courseware first, unpacks .enbx animations and images, writes board design as a finished two-board picture in five parallel knowledge blocks (keywords only, underline blanks instead of boxes, no safety icons), prints board reminders in red, and keeps the Word copy free of working notes. Triggers include 九年级物理教案、希沃白板、.enbx 课件、核心素养目标、问题链/逻辑链、易混概念辨析、详案/逐字稿、40分钟课时教案、练习课详案、讲评课详案、板书设计、同步优学.
---

# 九年级物理教案生成技能

> 版本：v8.1.0
> 本文件只是入口：触发、确认、流程、硬约束、索引。详细要求按第 5 节读取 references/，不要凭记忆生成。

## 1. 何时触发

满足任一条件才执行：
- 用户明确要求“生成/修改/重写一份九年级物理教案”；
- 用户提供 .enbx / 希沃白板课件路径，并希望基于它写教案；
- 用户明确提到“按教案生成要求/提示词/规范来做”。

不触发（按普通问题回答）：只讨论物理概念、只写普通文档；没有课件也没有课时信息；只是询问本技能怎么用。

## 2. 执行前必须确认（读下面的用户档案，只问与档案不同的项）

用户档案（默认值）：
- 教材：人教版（2024）九年级物理全一册；课时：每课时 40 分钟
- 实验条件：默认“仅多媒体”；不出“学生分组实验”版
- 稿型：只出详案/逐字稿（1 份 md＋1 份 docx）
- 板书：最多 2 块小黑板，每块 ≤8 行、每行 ≤14 字
- 落位：docx 放章节根级、md 放 md文件/；文件名“<节号><节名>-<N课时>-<版本>-详案”
- 联网调研：默认允许，资料存 08-网络资源/

缺哪项问哪项，其余不重复问：
1. 源课件路径（.enbx）
2. 教材版本/章节
3. 课时数
4. 实验条件
5. 学生用件：有没有导学案/观察记录表？几页？谁印发？
6. 输出形式（默认 1 md＋1 docx）
7. 是否还要练习课/讲评课详案
8. 是否允许联网检索

信息齐了就执行。

## 3. 执行流程（线性，每步只做一次）

0. **备课调研**：按 05 检索 2—3 份优秀教案、2—3 份优秀课件，提炼板书/重点/难点/易错/过渡语五维度借鉴清单，存 08-网络资源/；摘要先给用户确认。
1. **解包 .enbx**：读 Slides/Slide_*.xml 的文字、表格、数据、例题，并读每个元素的 <Animations> 还原“点第几下出现什么”；导出图片/视频到 05-课件与文本/<章节>/课件素材/，图片用 read_image 识别（量大用一个子代理，只回短描述）。
2. **查重与确认**：检查目标目录是否已有同名课时的 详案.md/docx，沿用既有命名与层级。
3. **写 详案.md**：按 01 的结构与需求 1–9 一次写全（逐字稿＋就地标注＋板书 ```board 源码）；写完不整篇重写。
4. **一键生成 docx＋板书图**：运行工作区 00-模板与规范/教案docx生成脚本-v9.py，把 ```board 渲染成 PNG 插入 docx；板书旁批标红。
5. **自检**：按 02 §7 跑一遍（脚本机械项＋人工清单）。
6. **汇报**：文件路径、改动点、可继续调整处。

## 4. 硬约束（不可偏离；细节见 references）

1. 只出详案/逐字稿（md＋docx），两套结构（新授课/练习课）不混用；先调研后生成。
2. docx 必须是真 OOXML：标题层级可导航；旁批 `〔…〕` 与正文样式可分；`〔板书｜…〕` 用红色样式。
3. 教学目标按核心素养四维度分写；科学思维必须落在模型建构/科学推理/科学论证/质疑创新中至少两类；单句精简。
4. 重难点、易混、板书动作、用时一律**就地**写在教学过程对应位置；“四、教学重难点”只写重点 1 条＋难点 ≤2 条。
5. 板书写成成品：md 用 ```board 围栏，最多 2 块、每块 ≤8 行、每行 ≤14 字；填空用下划线留空、不用 □；板上不出现安全符号；docx 里插入渲染好的板书图。
6. 过渡只为真实逻辑关系服务：导入/过渡/首问不得三连重复；弱联系只报下一步。
7. 学生用件（导学案/记录表等）必须在“五、教学准备”写清名称、栏目、印发方式。
8. 备查/过程内容（调研流水、课件补白汇总、板书时机汇总）一律不进教案，不单独成节。

## 5. 详细要求在哪（按需读取）

| 要做的事 | 读哪里 |
|---|---|
| 内容主体：结构、两稿分工、需求 1–9 | references/01-教案生成要求.md |
| 教学语言红线、板书规格、标注体系、目标精简、唯一自检清单 | references/02-教学设计细则.md |
| 关键观点与文献 | references/03-教学研究参考.md |
| 资源网站索引与检索技巧 | references/05-教学资源网站.md |
| 目录结构、命名、同步、脚本、变更记录 | references/04-技能维护规范.md |

## 6. 交付前自检

见 references/02-教学设计细则.md §7。这是本技能**唯一**一份自检清单，不要另立第二份。

## 7. 维护本技能

改动前先读 references/04-技能维护规范.md。技能目录在工作区外，写入需要一次放行；建议先在 工作区/99-待处理/skill-new/ 暂存核对，再一次性复制到仓库副本与用户级副本，最后按 04 校验。
