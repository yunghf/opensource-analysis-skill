# 仓库获取与源码阅读通路（Repo Acquisition）

> 本文件是 `SKILL.md` Step 0 的执行细则。目标：**即使在无 git、不允许 clone 的环境里，也能通过 URL 读到 GitHub / Gitee 源码并完成解构**，并在做不到时给出诚实的降级声明。
> 本文所有成功率与耗时均为 **2026-09-18 本机实测**，不是估计值。

## 1. 四条通路的能力矩阵

| 通路 | 调用方式 | 适合 | 实测表现 |
|------|---------|------|---------|
| **A. 内置 WebFetch** | `WebFetch <url>` | 单文件、元数据、README、release/tag 列表——**需要 AI 当场理解内容**的场合 | raw 单文件精确回传 ✅；`git/trees?recursive=1` 的 153 条目 JSON 完整回传 ✅（不自动摘要，但输出格式不完全受 prompt 控制） |
| **B. 批量拉取脚本** | `scripts/fetch_repo.py` | 一次拉几十~几百个文件、要**落盘**做统计（行数/复杂度/依赖解析） | `psf/requests` **103 文件 / 13.2s / 零失败**，与上游**逐字节一致**（sha256 抽验通过） |
| **C. git 克隆** | `git clone` | **需要提交历史**（角度二演化分析）、需要精确 diff | git 2.54 可用，`--depth 1` 秒级 |
| **D. 内置 WebSearch** | `WebSearch <query>` | 项目背景、社区评价、issue 讨论、许可证与合规解读、竞品对比 | 不在源码通路上，但**非代码类结论必须靠它交叉验证** |

### A 与 B 的分工（别混用）

- **A（WebFetch）＝ 少量、单点、要理解**：读 README 提炼定位、读 API 确认默认分支与许可证、读某关键文件判断入口。
- **B（脚本）＝ 批量、完整、要落盘**：凡是要"读完再统计"的（行数、复杂度、目录测绘、依赖清单），一律用 B —— **WebFetch 的结果只在你的上下文里，不在磁盘上**，后续工具链用不了。

## 2. 决策树：先定要不要 git

```
需要角度二（git 演化分析）吗？
├─ 需要 → 必须用 C：git clone --filter=blob:none <url>
│          （GitHub API 不提供提交历史；浅克隆需 git fetch --unshallow 补历史）
└─ 不需要 → 用 B 直拉：快、不依赖 git、不受 API 提交限额影响
           ├─ 只要总览/文件树 → --meta-only（约 1 秒）
           ├─ 只要某模块     → 用带子目录的 URL
           └─ 全量分析       → 默认参数
```

**混合策略（推荐）**：`B 拉工作树 + C 补历史` —— 用 B 快速拿到源码，仅在需要角度二时补一次 `git clone --filter=blob:none`（该模式不下载历史文件内容，体积远小于全量）。

## 3. 脚本用法（通路 B）

```bash
# 路径解析：fetch_repo.py 位于本 skill 的 scripts/ 目录下，以 skill 根目录为基准
SC="<本 skill 根目录>/scripts"    # 例如 ~/.workbuddy/skills/opensource-x/scripts
command -v cygpath >/dev/null && SC=$(cygpath -m "$SC")     # Git Bash: /c/... → C:/...

python "$SC/fetch_repo.py" https://github.com/psf/requests                 # 全量
python "$SC/fetch_repo.py" psf/requests --meta-only                        # 只要元数据 + 文件树
python "$SC/fetch_repo.py" psf/requests/src/requests --max-files 40        # 只要子目录
python "$SC/fetch_repo.py" https://github.com/pandas-dev/pandas --include "*.py,*.toml" --max-files 150
python "$SC/fetch_repo.py" https://gitee.com/oschina/git-osc --out ./git-osc
python "$SC/fetch_repo.py" owner/repo --ref v2.31.0                        # 指定 tag/分支/commit
```

支持的目标写法：`https://github.com/o/r` · `https://github.com/o/r/tree/<ref>/<sub/dir>` · `git@github.com:o/r.git` · `o/r`（简写，默认 GitHub） · `https://gitee.com/o/r`。

### 产物

```
<out>/
├── <原仓库目录结构>/...          # 源码文件，与上游逐字节一致
└── _fetch/
    ├── meta.json                 # stars/forks/license/pushed_at/archived/language…（填报告开头）
    ├── tree.json                 # 完整文件树（含 size；目录测绘直接用它，无需再请求 API）
    └── summary.md                # 获取报告：语言构成、跳过明细、失败清单、后续步骤
```

### 选文件的默认规则（要向用户解释，别默默丢文件）

- **跳过**：二进制/图片/字体/音视频/归档/凭据证书/数据集（`.png .zip .pem .db .pt .whl …`）、vendored 目录（`node_modules/ vendor/ dist/ build/ __pycache__/ site-packages/ target/`）、`.lock`。
- **优先级排序**（`max-files` 截断时优先保留）：README → 依赖与构建清单 → 入口文件（`main/app/index/__init__/__main__`）→ 架构文档 → 源码 → 配置 → 其他文档。
- 默认 `max-files=300`、单文件上限 400 KB、并发 8。
- **截断与跳过一定会在 `summary.md` 记明**，报告中必须如实声明"未下载 N 个文件"。

## 4. 克隆策略（通路 C，需要历史时用）

| 目标 | 命令 | 说明 |
|------|------|------|
| 只看现状（架构 / 质量 / 技术栈） | `git clone --depth 1 <url> <dir>` | 最快，历史不可用 |
| 需要演化分析（推荐） | `git clone --filter=blob:none <url> <dir>` | 保留完整提交历史，文件内容按需拉取 |
| 需要精确 diff / 逐文件重构分析 | `git clone <url> <dir>` | 全量；大仓库慎用 |
| 只要某个 tag / 版本 | `git clone --depth 1 --branch <tag> <url> <dir>` | |

判断克隆是否保留了历史：

```bash
git rev-parse --is-shallow-repository      # true = 浅克隆，演化分析不可用
git log --oneline --all | wc -l            # 提交总数
git log --format="%h %ad %s" --date=format:"%Y-%m-%d" --all   # 演化分析原料
```

**要求角度二却拿到浅克隆时，必须先补历史**：`git fetch --unshallow`（大仓库耗时长）或 `git fetch --deepen=500`。

## 5. 网络降级链（本机实测踩坑，必须按此实现）

**核心事实：原始内容域名稳定性随时间波动，不能依赖任何单一镜像。**

实测（同一台机器、同一天、两轮独立探测）：

| 原始内容镜像 | 轮次 1 | 轮次 2 | 平均耗时 | 结论 |
|---|---|---|---|---|
| `github.com/<o>/<r>/raw/<ref>/<path>` | 4/4 | 4/4 | 0.87s | **最稳，首选** |
| `raw.githubusercontent.com/...` | 1/3 | 4/4 | 0.55s | 最快，但历史上有 1/3 崩率 |
| `raw.githack.com/<o>/<r>/<ref>/<path>` | 4/4 | 4/4 | 0.89s | 可用备选 |
| `cdn.statically.io/gh/<o>/<r>/<ref>/<path>` | 4/4 | 1/4 | 24.25s | 慢且不稳，仅兜底 |
| `cdn.jsdelivr.net/gh/...` | 0/4 | 2/4 | — | 本机不可用，**不纳入** |

脚本已内置 **4 源轮询 + 自适应偏好**（某镜像成功一次后，后续文件优先命中它）。改顺序前请自己先测一轮，不要照抄本表。

其他真实约束：

1. **API 限流**：GitHub 未认证 **60 次/小时**。脚本只调 1 次元数据 + 1 次文件树，其余走 raw（**raw CDN 不计入 API 限流**），正常分析几乎不会撞限额。撞了返回 403，脚本提示设置 `GITHUB_TOKEN`（提到 5000/h）。
2. **`truncated: true`**：文件树超过约 10 万条目时 API 会截断 —— 此时必须改用 git 克隆，并在报告中声明树不完整。
3. **raw 偶发 `SSL: UNEXPECTED_EOF_WHILE_READING`**：不代表文件不可得，重试即可。脚本默认每镜像重试 2 次 × 4 个镜像。**注意本机 `curl` 走 Schannel，HTTPS 握手有失败历史，优先用脚本（urllib）而非 curl。**
4. **私有无凭据**：401/404 一律**如实告知用户**，不尝试绕过。
5. **超大仓库**：先 `--meta-only` 看 blob 数与总体积，再与用户确认范围，不要无边界开跑。

### 超大仓库的分片策略

触发条件：> 500 MB，或 blob 数极大，或单次获取超过约 3 分钟。

1. **只分析子目录**：`--include <subdir>/*`（脚本）或 `git sparse-checkout set <subdir>`（git）。
2. **只做架构层**：跳过角度二与角度四的细粒度部分，报告中写明"因规模受限未覆盖"。
3. **演化分析只取近 N 次**：`git log --oneline -n 2000`，并标注采样范围。

## 6. 接不到源码时的诚实降级

按顺序尝试，并把**实际用了哪条通路写进报告开头的"数据来源"**：

1. 脚本直拉（B）
2. 换镜像 / 加大重试 / 加 token
3. git 克隆（C）
4. 仅元数据 + WebSearch 公开资料 → 报告降级为**"外部资料综述"**，且必须声明"未读取源码，结论为二手信息"，**不得出现任何代码级结论**
5. 请用户提供本地路径或压缩包

降级声明模板（写入报告"分析对象"一节）：

> **数据来源**：GitHub REST API + raw CDN 拉取的源码树（未获取 git 历史）
> **未覆盖角度**：角度二 git 演化分析（无 `.git`）
> **建议**：如需演化分析，请在有网络环境执行 `git clone --filter=blob:none <url>`

> 铁律：**未读到源码，就不许写"这个类怎么设计""这个函数怎么实现"。宁缺勿编。** 不允许用"通常这类项目会……"补足结论。
