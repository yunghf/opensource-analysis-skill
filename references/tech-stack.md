# 技术栈拆解（Tech Stack Breakdown）

> 目标：把仓库的"技术选型现状"变成一张可对比的矩阵，并回答两个业务问题：**这套栈还健康吗？我如果要基于它做二开，成本在哪？**

## 1. 技术栈矩阵（七维度）

必须七行齐全，缺失项写"无"并说明（例如纯库项目无部署维度）。

| 维度 | 内容 | 评价角度 |
|------|------|---------|
| ① 语言构成 | 主语言 / 次语言 + 各自代码行占比 | 是否单一语言、是否需要多语言心智负担 |
| ② 运行时与版本要求 | Python / Node / JDK / Go 版本下限（读 CI、`pyproject.toml`、`engines`、`pom.xml`） | 是否已 EOL、是否卡住用户环境 |
| ③ 框架与核心库 | Web 框架、CLI 框架、序列化、异步运行时、测试框架 | 是否主流、社区活跃度 |
| ④ 数据与存储 | 关系库、KV、缓存、搜索引擎、消息队列、对象存储 | 是否引入运维负担 |
| ⑤ 基础设施 | 容器 / 编排 / 云服务 / 网关 / 监控 / 配置中心 | 部署复杂度、可移植性 |
| ⑥ 构建与交付 | 构建工具、打包方式、CI/CD、制品形态 | 是否为现代标准（如 hatch/uv、pnpm、Bazel） |
| ⑦ 质量与工程化 | linter、formatter、类型检查、覆盖率、pre-commit | 工程成熟度信号 |

## 2. 依赖清单提取

```bash
# Python
cat pyproject.toml requirements*.txt            # 声明
pip list --format=freeze                        # 已安装（有环境时）
pipdeptree                                      # 依赖树
poetry show --tree  /  uv tree                  # 若用 Poetry / uv

# Node
cat package.json | jq '{dependencies,devDependencies,engines}'
npm ls --all --depth=1
pnpm why <pkg>

# Java
mvn dependency:tree -DoutputFile=deps.txt
gradle dependencies

# Go
go list -m all
go mod graph | wc -l

# Rust
cargo tree --depth 2
```

产出：**直接依赖表** + **间接依赖规模**（间接依赖数 > 200 时标注"依赖膨胀"）。

## 3. 依赖健康度评估

| 检查项 | 方法 | 判定 |
|--------|------|------|
| 是否有维护 | 看依赖仓库最近发布/提交时间 | 两年无更新且非"完成态"库 → 关注 |
| 版本是否过时 | 见下方命令 | 落后主版本 ≥ 2 → 关注 |
| 已知漏洞 | `npm audit` / `pip-audit` / `osv-scanner` / `govulncheck` / `mvn org.owasp:dependency-check-maven:check` | high/critical > 0 → P0 |
| 许可证兼容 | 见 §4 | 出现 GPL/AGPL 而本项目为 MIT/Apache 的**分发型**项目 → P0 风险 |
| 依赖数量 | 见 §2 | 直接依赖 > 40 或间接 > 300 → P2 关注 |
| 锁定文件 | 是否存在 `package-lock.json` / `poetry.lock` / `uv.lock` / `go.sum` | 缺失 → 构建不可复现 |

版本过时检查：

```bash
npx npm-check-updates --format group      # Node
pip list --outdated                       # Python（近似；以 pyproject 声明为准）
mvn versions:display-dependency-updates   # Java
go list -m -u all                         # Go
```

## 4. 许可证识别

```bash
# 本项目
head -20 LICENSE 2>/dev/null || grep -i "license" README.md pyproject.toml package.json

# 依赖侧（Node 生态最方便）
npx license-checker --summary
# Python
pip install pip-licenses && pip-licenses --format=markdown
```

评价口径：注意区分**库（被链接）**与**分发型产品**——GPL/AGPL 依赖对前者通常可接受，对后者可能触发传染性义务。不确定时只说风险方向，不给法律结论。

## 5. 选型评价写法

对每个关键选型写三句话，不要写空泛的"很流行"：

1. **它是当前最佳实践吗**：与同类对比（如 uv vs pip+virtualenv、pnpm vs npm、Pydantic v2 vs v1）。
2. **它处于什么生命周期**：活跃维护 / 稳定成熟 / 维护期 / 已弃用（给信号：最近发布会、issue 响应、是否有官方替代建议）。
3. **替换/迁移成本**：影响面（涉及多少文件、有无 API 兼容层）。

## 6. 报告结构（技术栈拆解报告）

1. **结论先行**：一句话定性（如"主流且现代的 Python 栈，唯一风险是 2021 年后停更的 X 库"）。
2. **技术栈矩阵**：§1 的七维度表。
3. **依赖清单**：直接依赖表 + 间接依赖规模。
4. **依赖健康度**：§3 表格 + 漏洞与过时清单。
5. **许可证合规**：本项目 + 关键依赖的许可证。
6. **选型评价与二开成本**：§5 写法，逐关键项。
7. **升级/替换建议**：按 P0/P1/P2。

## 7. 诚实边界

- 版本与漏洞信息**有时效性**：必须记录采集日期，并说明"数据截至 <日期>"。
- 无法访问依赖仓库（离线）时，标注"未验证维护状态"，不臆断"这个库应该还在维护"。
