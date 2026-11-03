---
name: opensource-analysis
agent_created: true
display_name: 开源项目深度解构
display_name_en: OpenSource-analysis
description: 本 skill 应在用户给出 GitHub/Gitee 仓库链接（或本地仓库路径）并要求"分析 / 读懂 / 拆解 / 解构 / 审计 / 评审某个项目"时使用；也适用于"写分析报告、做架构评审、代码审计、技术尽调、评估代码质量、拆解技术栈、二开调研、面试前建立项目认知"等场景。它对任意代码仓库执行六角度深度分析（架构实现 / git 演化 / 第一性原理 / 设计巧思 / 代码质量 / 技术栈拆解），无需 git clone 即可经 URL 直连读取源码树，全程先读懂"怎么组织"、再讲清"为什么这么组织"、最后回答"值不值得用、从哪下手改"，产出 HTML / Markdown / SVG 形态的证据链报告与项目全景思维导图。
description_en: This skill should be used when the user provides a GitHub/Gitee repo URL (or a local repo path) and asks to analyze, review, audit, deconstruct, or understand a codebase. It runs six analysis lenses (architecture implementation, git evolution, first-principles reasoning, design-wisdom mining, code quality assessment, tech-stack breakdown) over any repository, reads the source tree directly over the network without git clone, and delivers evidence-backed reports (HTML / Markdown / SVG) plus a project-wide mind map.
version: 1.0.0
source: "Packaged from expert loongwoong/OpenSource-X (2026-11)"
---

# OpenSource-Analysis — 开源项目深度解构

对任意代码仓库做一次完整的深度解构：**先读懂它怎么组织，再讲清它为什么这么组织，最后回答它值不值得用、从哪下手改。** 每份结论都有代码证据（文件路径 + 行号或片段），每个分析角度都有对应报告。

## 触发场景

- 用户给出 **GitHub / Gitee 仓库链接**（或本地仓库路径），要求"分析 / 读懂 / 拆解 / 解构某个项目"
- 用户要求"写分析报告"、"做架构评审"、"代码审计"、"技术尽调"、"评估代码质量"、"拆解技术栈"
- 学习明星项目源码、二次开发前置调研、面试前建立项目全局认知、新接手代码库并沉淀文档
- 对已有分析补充"演化历史 / 第一性原理 / 设计巧思"等更深角度

## 按用户身份切换侧重

| 用户是谁 | 用户要什么 | 分析侧重 |
|----------|-----------|---------|
| 学习者 | 读懂明星项目的设计精髓 | 架构实现 + 设计巧思深挖（重点讲"为什么必然"） |
| 二次开发 / 选型者 | 判断能不能改、要不要用 | 代码质量 + 技术栈拆解 + 依赖健康度与许可证风险 |
| 面试者 | 面试前快速建立全局认知 | 架构全景 + 关键链路 + 可复述的思维导图 |
| 尽调 / 调研者 | 一份能交给别人的报告 | 六角度全覆盖 + HTML 报告 + 证据链完整 |

## 工作流总览

```
输入：GitHub/Gitee 仓库链接，或本地仓库路径
  Phase 0  接入门（G2 阻塞）→ 获取源码 → 摸底通报（G1）
  Phase 1  四角度分析：架构实现 / git 演化 / 第一性原理 / 设计巧思（静默连跑，G0）
  Phase 2  代码质量评估（量化指标 + P0/P1/P2 改造清单）
  Phase 3  技术栈拆解（七维度矩阵 + 依赖健康度 + 许可证合规）
  Phase 4  产物生成（形态由接入门选定：HTML / Markdown / SVG）
  Phase 5  校验与交付（校验脚本必须全过 + present_files 呈现 + 三句话汇报）
```

**主流程 Step 0~8 的完整执行规范见 `references/main-workflow.md`，开始分析前必须先加载并遵循它**，不要凭直觉自创流程。

## 交互门位（必读，优先级高于一切流程细节）

详细规范见 `references/interaction-gates.md`。三条硬规则：

1. **拿到链接先开门，一次问完 4 项**：分析目标 / 深度档 / 产物形态 / 数据通路。用宿主原生候选项机制一次发出（最多 4 题），不要拆成多轮。每项描述必须写"选了会怎样"。
2. **全程只有 1 个阻塞门**：接入门之后一律静默连跑，只在摸底完成（G1 通报）与交付（G1 通报）时给结论，不逐阶段问"继续吗"。
3. **只有人能回答的问题才停下来**——且仅限三种：范围超预期（blob > 5,000 / 树被截断 / 预计 > 3 分钟）、数据不可得（私有、限流、404）、目标变更。

- 用户说「你定 / 都行 / 先跑一版」→ 切 `autopilot` 并一句话确认；交付时**必须声明哪些门未经确认**。
- 用户订正时**只重跑受影响的下游**：改产物形态 = 只重跑产物生成步骤，绝不整体重开。
- **自检口诀**：把问题里的专业术语删掉，剩下的句子还成立吗？不成立 → 那是专业判断，登记告知，不要问。

## 宿主能力映射（用对工具，别重复造）

以下按宿主环境常见的工具能力做映射；宿主缺少某能力时，用等效手段替代并在报告中声明。

| 宿主能力 | 用来做什么 | 不要用来做 |
|----------|-----------|-----------|
| 原生候选项问答 / 结构化提问 | 接入门的 4 项选择（目标/深度/形态/通路） | 逐阶段问"继续吗"；问专业判断 |
| 拉取脚本 `scripts/fetch_repo.py`（Python 3 标准库，无第三方依赖） | 批量拉源码树、落盘做统计。`--meta-only` 约 1 秒拿元数据与文件树 | 少量单文件读取（杀鸡用牛刀） |
| 网页读取（WebFetch / curl） | 少量单点读取：README、元数据、某关键文件、release 列表 | 批量拉取（结果只在上下文，不落盘） |
| 网页搜索 | 项目背景、社区评价、issue 讨论、许可证与合规解读、竞品对比 | 代替读源码（二手信息不能当代码结论） |
| Shell + git | 需要提交历史（角度二）、精确 diff | 只看现状时（直连更快） |
| 内联可视化（若有） | 分析中即时渲染总览卡、架构图、导图骨架（进度可见） | 替代产物文件 |
| 文件呈现工具（如 present_files / 打开文件） | 交付时呈现产物 | 呈现中间态 |

## 输出规范

- **结论先行**：每份报告开头一段"结论"，先给判断再给证据。
- **一切有据**：每个结论必须能落到"文件路径（+ 行号或代码片段）"。写不出出处的结论不要写。
- **表格优先**：职责表、指标表、对照表、映射表。禁止大段散文式描述代码。
- **量化**：代码质量部分必须给数字与阈值对照（如"CC=23 > 20，属必拆区间"），不接受"有点复杂"这类表述。
- **优先级**：改造建议按 P0/P1/P2 分层，每条含文件路径与影响面。
- **可复述性**：思维导图必须能让人在 3 分钟内讲清项目"是什么、怎么分层、核心链路在哪"。
- **声明数据来源**：报告开头必须写明走了哪条通路（直连拉取 / git 克隆 / 本地路径）以及未覆盖的角度。
- **语言**：跟随用户语言，默认中文。

## 边界与铁律

1. **不编造**：没有实际读到的文件、没有跑出来的指标，一律不写。工具不可用时说明"未采集"并给出采集命令，而不是猜一个数字。**未读到源码时不得出现任何代码级结论**（只能降级为"外部资料综述"并显式声明）。
2. **不越权**：只读分析，不修改目标仓库；需要执行构建或测试时，先告知命令与资源开销，得到同意再执行。
3. **私有仓库**：无凭据时如实告知并停止；不尝试绕过鉴权。
4. **交互克制**：一次只开一个阻塞门；通报卡 ≤60 行；不问专业判断；已确认的不复查。
5. **订正只重跑下游**：改形态只重出产物，改范围只重跑受影响角度。**绝不整体重开**。
6. **大仓库策略**：blob > 5,000 或树被截断时先确认范围（只分析某模块 / 只做架构层 / 跳过演化），避免无边界耗时。
7. **区分事实与评价**：架构"事实描述"与"优劣评价"必须分开表述，评价要给出判断依据。
8. **产物落盘**：所有产物写入 `analysis/`（项目已有 `docs/` 约定时写 `docs/analysis/`），文件名用项目名做前缀。
9. **引用代码前必须先读当前文件内容**，不允许凭记忆或训练数据编造代码。

## 资源清单

| 资源 | 用途 |
|------|------|
| `references/main-workflow.md` | **主流程 Step 0~8 完整规范（必读）** |
| `references/interaction-gates.md` | 交互门位规范（G0/G1/G2 分档、接入门 4 项问法、通报卡、autopilot、增量重跑） |
| `references/output-formats.md` | 产物形态规范（HTML / Markdown / SVG 能力边界、选择矩阵、规格、问法） |
| `references/repo-acquisition.md` | 仓库获取与源码阅读通路（四条通路实测矩阵、决策树、多源降级链） |
| `references/architecture-analysis.md` | 角度一：架构实现分析详细方法 |
| `references/evolution-analysis.md` | 角度二：git 演化分析详细方法 |
| `references/first-principles.md` | 角度三：第一性原理分析详细方法 |
| `references/design-wisdom.md` | 角度四：设计巧思深挖 + 检查清单 |
| `references/code-quality.md` | 代码质量指标、阈值、工具链与改造分级 |
| `references/tech-stack.md` | 技术栈矩阵、依赖健康度、许可证合规 |
| `references/mindmap-spec.md` | 思维导图产物规范（Mermaid + 离线 SVG） |
| `references/html-report-spec.md` | HTML 报告规格（设计语言、组件、校验） |
| `scripts/fetch_repo.py` | 不依赖 git 的源码拉取器（Python 3 标准库实现） |
| `assets/report-template.html` | 可复用 HTML 报告骨架（复制后替换内容区块） |
