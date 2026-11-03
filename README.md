# OpenSource-analysis Skill

**把任意 GitHub / Gitee 仓库变成一张能讲课的图。** 先读懂它怎么组织，再讲清它为什么这么组织，最后回答它值不值得用、从哪下手改。

一个自包含的 Agent Skill：对任意代码仓库执行**六角度深度解构**，每条结论都带代码证据（文件路径 + 行号 / 片段），产出 HTML / Markdown / SVG 形态的报告与项目全景思维导图。

- **无需 `git clone` 即可读源码**：内置拉取脚本经 GitHub / Gitee API 直连读取源码树（实测 103 文件 / 13.2s / 零失败）
- **零外部依赖**：拉取脚本只用 Python 3 标准库；HTML 报告零 CDN、`file://` 双击可开
- **一次确认，全程静默连跑**：只在开始问 4 个问题，之后不再逐阶段打断
- **拒绝编造**：没有实际读到的文件、没有跑出来的指标，一律标注"未采集"并给出采集命令

---

## 六个分析角度

| # | 角度 | 回答的问题 | 核心产出 |
|---|------|-----------|---------|
| 1 | **架构实现** | 代码怎么组织、数据怎么流 | 分层职责表、依赖方向证据、完整数据流、校验体系、优势与代价 |
| 2 | **Git 演化** | 这套架构是怎么演化来的 | 提交时间线、决定性重构的逐文件剖析、重命名对照表、演化对比表 |
| 3 | **第一性原理** | 它在为谁解决什么不可回避的问题 | 根本问题 + 2~4 条基本事实 + 每条对应的必然设计 + 代价 |
| 4 | **设计巧思** | 哪些设计防住了不可靠性 / 支撑了可演化性 | ≥8 项巧思（覆盖 ≥3 层），每项含代码 + "为什么必然" + 映射表 |
| 5 | **代码质量** | 这代码能改吗、从哪改 | 量化指标（CC / 规模 / 重复率 / 覆盖率 / 循环依赖）、热点 Top-10、P0/P1/P2 清单 |
| 6 | **技术栈** | 这套栈还健康吗、二开成本在哪 | 七维度矩阵、依赖健康度、CVE 与许可证合规、迁移成本评价 |

## 按身份切换侧重

| 你是谁 | 分析侧重 |
|--------|---------|
| 学习者 | 架构实现 + 设计巧思深挖（重点讲"为什么必然"） |
| 二次开发 / 选型者 | 代码质量 + 技术栈拆解 + 依赖健康度与许可证风险 |
| 面试者 | 架构全景 + 关键链路 + 可复述的思维导图 |
| 尽调 / 调研者 | 六角度全覆盖 + HTML 报告 + 证据链完整 |

---

## 快速开始

本仓库根目录**就是** skill 目录，克隆或下载后放到宿主的 skills 目录即可。

```bash
git clone https://github.com/yunghf/opensource-analysis-skill.git

# 通用（任何支持 SKILL.md 约定的 Agent）
cp -R opensource-analysis-skill ~/.<your-agent>/skills/opensource-x

# WorkBuddy
cp -R opensource-analysis-skill ~/.workbuddy/skills/opensource-x

# Claude Code
cp -R opensource-analysis-skill ~/.claude/skills/opensource-x
```

**环境要求**：`python3`（拉取源码、跑校验）。可选：`node`（HTML 内嵌 JS 语法校验）、`cloc` / `scc`（规模统计）、`git`（角度二演化分析）。

## 使用示例

直接在对话里给出仓库链接和意图即可，skill 会自动触发：

```
分析这个项目：https://github.com/psf/requests
帮我看看这个仓库的架构，能不能二次开发：https://github.com/gin-gonic/gin
面试前想快速搞懂这个项目的设计：https://github.com/tiangolo/fastapi
对 gitee.com/oschina/git-osc 做一次技术尽调，要能交给别人的报告
```

首次触发时，skill 会用**一次**结构化提问确认 4 件事（分析目标 / 深度档 / 产物形态 / 数据通路），随后一路跑完：

```
输入：仓库链接或本地路径
  Phase 0  接入门 → 获取源码 → 摸底通报（仓库总览卡）
  Phase 1  四角度分析：架构 / 演化 / 第一性原理 / 设计巧思
  Phase 2  代码质量评估
  Phase 3  技术栈拆解
  Phase 4  产物生成（HTML / Markdown / SVG）
  Phase 5  校验（HTML 必须全过）+ 交付
```

## 产出物

```
analysis/
├── <项目>架构实现分析.md / .html
├── <项目>基础层与领域模型演化分析.md / .html
├── <项目>第一性原理与设计巧思分析.md / .html
├── <项目>代码质量评估.md / .html
├── <项目>技术栈拆解.md / .html
├── <项目>项目全景思维导图.md        # Mermaid + 纯文本缩进树 + 内联 SVG
└── svg/<视角>.svg                   # 选了「加出 SVG」时
```

HTML 报告零外部依赖，含侧栏 TOC + 滚动高亮 + 代码高亮 + 可折叠巧思卡，复制 `assets/report-template.html` 作骨架生成。

## 目录结构

```
opensource-analysis-skill/
├── SKILL.md                     # 入口：触发条件、工作流、“铁律”、宿主能力映射
├── references/
│   ├── main-workflow.md         # 主流程 Step 0~8 完整规范
│   ├── interaction-gates.md     # 交互门位（1 个阻塞门 / 通报卡 / autopilot / 增量重跑）
│   ├── repo-acquisition.md      # 四条源码获取通路与降级链
│   ├── architecture-analysis.md # 角度一方法
│   ├── evolution-analysis.md    # 角度二方法
│   ├── first-principles.md      # 角度三方法
│   ├── design-wisdom.md         # 角度四方法 + 巧思检查清单
│   ├── code-quality.md          # 指标阈值与工具链
│   ├── tech-stack.md            # 七维度矩阵与依赖健康度
│   ├── output-formats.md        # HTML / Markdown / SVG 形态规格
│   ├── html-report-spec.md      # HTML 设计语言与组件
│   └── mindmap-spec.md          # 思维导图规范
├── scripts/
│   └── fetch_repo.py            # 无 git 依赖的源码拉取器（纯标准库）
└── assets/
    └── report-template.html     # HTML 报告骨架
```

## 设计原则

| 原则 | 具体做法 |
|------|---------|
| **结论先行** | 每份报告开头一段判断，再给证据 |
| **一切有据** | 每个结论落到"文件路径（+ 行号或片段）"；写不出出处就不写 |
| **量化** | 质量部分必须给数字与阈值对照（如 `CC=23 > 20`），不接受"有点复杂" |
| **优先级** | 改造建议按 P0 / P1 / P2 分层，每条含文件路径与影响面 |
| **交互克制** | 全程只有 1 个阻塞门；订正时只重跑受影响的下游，绝不整体重开 |
| **诚实降级** | 拿不到 `.git` 就把角度二降级为"版本演进回顾"并声明依据，不编造提交历史 |

## 数据来源与降级

四条通路：**GitHub / Gitee API 直连拉取**（默认，无 git 依赖）→ **git 浅克隆**（仅角度二需要历史时）→ **本地路径**（用户提供）→ **外部资料综述**（源码不可得时降级，且显式声明不得出代码级结论）。每份报告开头都必须写明本次实际走了哪条通路、哪些角度未覆盖。

## 许可

[MIT](LICENSE)。可自由用于商业与非商业场景，保留版权声明即可。

> by loongwoong
