# HTML 报告规格（产物要求）

每份分析报告必须有自包含 HTML 版本。规格如下，推荐直接复制 `assets/report-template.html` 再替换内容。

## 硬性要求

1. **零外部依赖**：无 CDN、无外链字体/图标库、无外部 JS。双击 `file://` 必须可用。
2. **单文件**：CSS/JS 全部内嵌；图片用内联 SVG/CSS 绘制，不用 `<img src="...">` 外链。
3. **中文字符集**：`<meta charset="utf-8">`，`lang="zh-CN"`。
4. **可校验**：内嵌 `<script>` 必须通过 `node --check`；doctype/`</html>`/script 配对正确（校验命令见 SKILL.md Step 6）。

## 设计语言（沿用 UOM 分析报告风格）

```
--bg:#f3f5f4; --surface:#ffffff; --ink:#17201c; --muted:#68736d;
--line:#dfe4e1; --line-strong:#cbd3ce;
--green:#156b4a; --green-dark:#0e5238; --green-soft:#e7f2ec;     主色（绿色，来自 OMS 工作台）
--red:#b83b35; --red-soft:#f8e9e7;                                 警示/代价
--amber:#9a6418; --amber-soft:#f8eedc;                             注意/中间态
--blue:#356a91; --blue-soft:#e7eff5;                               信息/协议层
--code-bg:#0f1a16; --code-ink:#d9e6df;                             深色代码块
--mono:ui-monospace,SFMono-Regular,"Cascadia Code",Menlo,Consolas,monospace;
字体: Inter, ui-sans-serif, system-ui, "PingFang SC", "Microsoft YaHei"
```

布局：`grid-template-columns:250px minmax(0,1fr)`——左侧固定 TOC（深色 `#17231e`），右侧内容（最大宽 ~940px）。

## 必备组件（模板中已实现，替换内容即可）

| 组件 | 说明 |
| --- | --- |
| Hero 区 | 渐变深绿背景、kicker、标题、meta chips、结论先行框 |
| 侧边 TOC + scrollspy | JS 从 h2/h3 自动生成目录，滚动高亮当前节 |
| 代码框 | 深色背景 + mac 三圆点 + 文件名栏；内嵌轻量高亮（Python 关键字/字符串/注释/数字/YAML 键） |
| 表格 | 职责表/对照表/映射表（th 浅绿底） |
| 卡片 grid | `.grid2` 双栏/多栏卡片 |
| Callout | info/warn/ok/red 四色，带标题 |
| 分层图 | `.layers`（层块 + 文件标签 chips） |
| 流程图 | `.flow`（步骤行：序号方块 + 标题 + 描述 + 层标注） |
| 时间线 | `.master-tl`（竖线 + 圆点 + 阶段徽章） |
| 巧思可折叠卡 | `.cv`（点标题展开/收起，含"为什么必然"高亮框） |
| 双栏对照 | `.dual`（优势 vs 代价等） |
| 页脚 | 报告名 + 互链其他报告 |

## 组件 CSS/JS 复用

模板 `assets/report-template.html` 已包含全部组件 CSS 与三个 JS 块（TOC/scrollspy、可折叠卡、代码高亮）。复制模板时：
1. 保留 `<style>` 与 `<script>` 原样；
2. 只替换 `<header class="hero">` 与 `<div class="content">` 内的内容；
3. 报告三（巧思卡）额外需要 `.cv` 组件与折叠 JS——模板已含。

## 内容映射（三份报告的 HTML 章节）

| 报告 | HTML 章节 |
| --- | --- |
| 架构实现分析 | 仓库总览/分层图 → 各层职责 → 结合机制 → 数据流 → 校验体系 → 评估 → 结论 |
| 演化分析 | 时间线总览 → 阶段卡片 A~N → 决定性重构（迁移对照表）→ 演化规律 |
| 第一性原理与巧思 | 基本事实卡片 → 巧思全景（按层可折叠卡）→ 映射表 → 综合结论 |

## 校验命令

见 SKILL.md Step 6（python 结构断言 + `node --check` 内嵌 JS）。校验失败必须修复后交付。
