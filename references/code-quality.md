# 代码质量评估（Code Quality Assessment）

> 目标：把"这代码好不好"变成**可复现的数字 + 可定位文件 + 可排序的改造清单**。所有指标必须来自实际执行，不允许估算。

## 1. 指标定义与阈值

| 维度 | 指标 | 良好 | 警戒 | 高风险 |
|------|------|------|------|--------|
| 复杂度 | 函数圈复杂度（CC） | ≤ 10 | 11–20 | > 20 |
| 复杂度 | 函数认知复杂度 | ≤ 15 | 16–25 | > 25 |
| 规模 | 单函数行数 | ≤ 50 | 51–100 | > 100 |
| 规模 | 单文件行数 | ≤ 400 | 401–800 | > 800 |
| 规模 | 单类行数 / 方法数 | ≤ 300 / ≤ 20 | 301–600 / 21–35 | > 600 / > 35 |
| 重复 | 重复代码率 | ≤ 5% | 5–10% | > 10% |
| 测试 | 行覆盖率 | ≥ 70% | 40–70% | < 40% |
| 依赖 | 循环依赖数 | 0 | 1–5 | > 5 |
| 静态 | 高危告警（error 级） | 0 | 1–10 | > 10 |
| 依赖 | 已知漏洞（high/critical） | 0 | 1–3 | > 3 |

> 阈值来源：业界通行经验值（Sonar / Radon / ESLint 默认档）。阈值只用于**分档**，结论必须结合项目性质：生成代码、协议绑定层、vendor 目录应排除在统计外。

## 2. 通用规模统计（先用它建立全局图景）

```bash
# 可选工具：cloc（推荐）/ scc（更快）/ tokei
cloc . --exclude-dir=.git,node_modules,vendor,dist,build,third_party
scc --exclude-dir .git,node_modules,vendor

# 无工具时的兜底
find . -path ./.git -prune -o -name "*.py" -print | xargs wc -l | tail -5
```

产出：语言构成表（语言 / 文件数 / 代码行 / 占比 / 一句话用途）。

## 3. 分语言工具链

### Python

```bash
pip install radon pylint ruff mypy vulture bandit pip-audit pytest pytest-cov

radon cc -s -a -nb src/            # 圈复杂度（-s 显示分数，-a 平均，-nb 不显示等级明细）
radon mi -s src/                   # 可维护性指数（MI < 20 表示难维护）
ruff check . --statistics          # 快速静态检查
pylint --disable=all --enable=R,C  # 仅看重构与约定类问题（噪音更低）
vulture . --min-confidence 80      # 死代码
bandit -r src/ -ll                 # 安全问题（-ll 只报 medium 以上）
pip-audit                          # 依赖漏洞
pytest --cov=src --cov-report=term-missing -q
```

### JavaScript / TypeScript

```bash
npx eslint . --ext .js,.jsx,.ts,.tsx -f json      # 告警分布
npx tsc --noEmit                                   # 类型健康度
npx madge --circular --extensions ts,js src/       # 循环依赖
npx jscpd src/ --min-lines 10 --min-tokens 70      # 重复代码
npx vitest run --coverage   # 或 npx jest --coverage
npm audit --json
```

### Java / Kotlin

```bash
mvn dependency:tree                                # 依赖树（找冲突与膨胀）
mvn -q test                                        # 跑测试
mvn org.jacoco:jacoco-maven-plugin:prepare-agent test   # + report 生成覆盖率
mvn com.github.spotbugs:spotbugs-maven-plugin:check     # 缺陷扫描
mvn versions:display-dependency-updates                  # 可升级依赖
```

### Go

```bash
golangci-lint run --out-format=tab       # 聚合 linter
go vet ./...
go test ./... -coverprofile=cover.out && go tool cover -func=cover.out | tail -1
govulncheck ./...
```

### 其他语言

用 `lizard` 兜底（支持 C/C++/C#/Java/JS/Python/Ruby/Swift 等 20+ 语言）：

```bash
pip install lizard
lizard . -x "./node_modules/*" -x "./vendor/*" -w 10    # -w 只显示 CC>10 的函数
```

## 4. 热点定位：复杂度 × 变更频率

单看复杂度会把"稳定但复杂"的代码误判为靶点。真正的重构靶点是**又复杂又常改**：

```bash
# 统计近 1 年每个文件被修改的次数
git log --since="1 year ago" --numstat --format="" | awk 'NF==3{print $3}' | sort | uniq -c | sort -rn | head -30
```

交叉表（Top-N 热点）：

| 文件 | CC（max/avg） | 行数 | 近一年变更次数 | 覆盖 | 判定 |
|------|--------------|------|--------------|------|------|
| `src/core/router.py` | 34 / 12 | 820 | 47 | 22% | **P0**（高风险 × 高频变更） |
| `src/legacy/parser.py` | 28 / 15 | 610 | 2 | 5% | P1（复杂但冻结，可延后） |

## 5. 改造优先级分级

| 级别 | 判定标准 | 典型动作 |
|------|---------|---------|
| **P0** | 影响正确性/安全性：高危漏洞、无测试覆盖的核心链路、高频变更且高复杂度的核心文件、并发/事务缺陷 | 立即修，给最小可行修补方案 |
| **P1** | 阻塞可维护性：循环依赖、超大文件/类、重复率 > 10%、缺失关键测试、错误处理缺失 | 排入迭代，给拆分方案与边界 |
| **P2** | 整洁度与体验：命名、死代码、注释、格式、非核心路径重复 | 有机会顺手做 |

每条建议必须写成：`[级别] 文件路径 → 问题（指标数字）→ 影响面 → 建议动作`。

## 6. 报告结构（代码质量评估报告）

1. **结论先行**：整体质量分档（好/中/差）+ 三个最该动的地方。
2. **指标总览表**：第 1 节全部维度 × 实测值 × 档位。
3. **规模与构成**：语言构成、目录规模 Top-10。
4. **复杂度热点 Top-10**：含 §4 的交叉表。
5. **重复与依赖**：重复率、重复块示例、循环依赖环。
6. **测试与安全**：覆盖率、未覆盖的关键模块、漏洞清单。
7. **改造清单**：P0/P1/P2 分级的表格。

## 7. 诚实边界

- 工具无法安装（离线/无权限）时，写"未采集"并给出采集命令，**不猜数值**。
- 覆盖率与复杂度只对**被统计的代码**负责：必须先声明排除目录（生成代码、第三方、测试夹具）。
- 不要用代码行数做"质量"结论（行的多少不是好坏）；它只用于规模与占比。
