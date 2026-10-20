# 模块四 · 查询与统计 · 交接说明

> 分支：`feat/query-statistics`（基于骨架 `cf69fa5`，已同步 `main` `27ffd5b`）
> 代码提交：`7e4a89a8a37b6d23c6495e994e636acf3ecccb85`（短 SHA `7e4a89a`）
> 基线骨架：`cf69fa5 chore(基础): 建立共享内存骨架`

## 1. 交付内容

```text
campusApp\queries\
  __init__.py            模块说明
  QueryRepository.py     只读仓储（筛选、计数、拼 Row、区间汇总）
  QueryService.py        四个公开方法 + 参数校验 + 错误映射
  QueryView.py           四个页签的 Tk 界面
tests\queries\
  __init__.py
  conftest.py            FixedClock / 造数工具 / 独立 MemoryStore 夹具
  testQueryRepository.py 仓储单元测试
  testQueryService.py    Service 单元测试（普通 + 健壮边界 + 异常 + 一致读）
  testQueryView.py       界面行为测试（取值、文案、刷新、时间兜底）
docs\modules\queries\
  design.md              设计与口径说明
  test-cases.md          用例表（含真实结果与代码 SHA）
  defects.md             8 个缺陷的复现、修复与回归
  handoff.md             本文件
  change-requests.md     对公共契约的请求
  evidence\              8 张界面截图 + test-results.json
```

## 2. 实现的公开接口

严格按规格 4.5，签名未做任何改动：

```python
QueryService(store, repository, clock)

listPersonalRegistrations(studentId, page, pageSize)   -> Result[Page[RegistrationRow]]
listActivityRegistrations(activityId, status, page, pageSize)
                                                       -> Result[Page[RegistrationRow]]
getActivityStats(activityId)                           -> Result[ActivityStats]
getOverviewStats(startDate, days)                      -> Result[OverviewStats]
```

界面按规格 4.6：

```python
QueryView(parent, studentService, activityService, queryService)
QueryView.refresh()   # 无参数，重载两个下拉列表
```

本模块**不写**任何集合、不申请编号；`QueryRepository` 的所有方法只接收
`state`（`StoreSnapshot`），不持有 Store 引用，符合规格 4.3
「Repository 构造函数无参数、只通过方法参数接收本次 state」。

依赖的外部接口（由 A、B 提供，本模块只调用）：

- `studentService.listStudents()` —— 按 `studentId` 升序（**A 尚未提交，见第 6 节**）
- `activityService.listActivities()` —— 按 `startAt, activityId` 升序（B 已提交，已实测可用）

## 3. 如何运行

### 3.1 依赖

- Python 3.12（实测 3.12.4）
- 开发依赖按 `requirements-dev.txt`：`pytest==8.4.2`、`pytest-cov==6.3.0`
- 运行时仅标准库：`tkinter`、`dataclasses`、`threading`、`types`、`datetime`

### 3.2 测试命令

```powershell
git clone https://github.com/Bobxianyu/stusent-event.git campus-query
cd campus-query
git switch feat/query-statistics

python -m pytest tests/queries -q    # 本模块
python -m pytest -q                  # 全仓库
```

`pyproject.toml` 已固定 `testpaths = ["tests"]`、`python_files = ["test*.py"]`、
`python_functions = ["test*"]`，不需要额外的 `-o` 覆盖。

### 3.3 覆盖率

```powershell
python -m pytest tests/queries --cov=campusApp.queries --cov-fail-under=80
```

本机 `pip install` 被系统权限拒绝（`Errno 13 Permission denied`），装不上
`pytest-cov`，因此用等价口径的自建脚本（`sys.settrace` + `code.co_lines()`，
统计「有字节码的行」）。脚本在工作区 `cq-tools\coverageTrace.py`，**不随模块提交**：

```powershell
python cq-tools\coverageTrace.py E:\campus-query
```

最近一次结果（真实骨架）：

```text
131 passed
QueryRepository.py      90/90  = 100.0%
QueryService.py         92/92  = 100.0%
TOTAL 182/182 = 100.0%
```

规格要求核心业务 ≥80%，实测 100%。`QueryView.py` 不计入语句覆盖率，
另用 18 条界面测试 + 8 张截图佐证。

### 3.4 打开界面

模块尚未挂载进 `campusApp/app.py`（该文件由 A 维护，见 `change-requests.md` CR-07）。
在此之前可用证据脚本单独打开：

```powershell
python cq-tools\evidenceShots.py E:\campus-query
```

## 4. 测试结果

最近一次完整运行（`evidence/test-results.json`）：

```text
collected 131 items
131 passed
pytestExit = 0
```

| 文件 | 条数 | 覆盖内容 |
| --- | --- | --- |
| `testQueryRepository.py` | 9 | 存在性、三类计数、区间汇总、悬空引用、未知状态 |
| `testQueryService.py` | 104 | 分页/状态/日期/天数/区间/去重/一致读/内部错误 |
| `testQueryView.py` | 18 | 选项映射、刷新保留、提示文案、时间兜底、五个交互入口 |

全仓库一次运行：`190 passed, 2 skipped`（2 个 skip 来自 A、B 的既有用例，与本模块无关）。

## 5. 与真实骨架的对齐记录

本模块最初在没有 `campusApp/core/` 的目录里开发，接入真实骨架后做了三处适配
（均已含在 `7e4a89a` 中）：

| 项目 | 本地早期版本 | 真实骨架 | 处理 |
| --- | --- | --- | --- |
| 状态常量 | `CONFIRMED` / `WAITLISTED` / `CANCELLED` | `STATUS_CONFIRMED` / `STATUS_WAITLISTED` / `STATUS_CANCELLED` | 改用骨架常量 |
| 错误码 | 字符串字面量 | `ERROR_VALIDATION` / `ERROR_STUDENT_NOT_FOUND` 等 | 改用骨架常量 |
| 缩进 | 4 空格 | 2 空格（AGENTS.md） | 全量改为 2 空格 |

另外发现并修复了一个只有接上真实骨架才暴露的缺陷（D-8）：
真实 `formatDateTime` 会校验业务时间范围并抛 `DomainError`，
界面渲染越界时间戳时会让整页崩溃，现已改为显示占位符 `—`。

`getDateRange` 在真实骨架中用正则严格校验 `YYYY-MM-DD`，与本模块用例的严格期望一致，
因此 `change-requests.md` 的 CR-02 已闭环。

## 6. 尚未完成的部分

### 6.1 学生服务不存在（阻塞下拉框的真实数据）

仓库当前**没有** `campusApp/students/`，A 只提交了公共骨架和活动模块。
`QueryView` 需要 `studentService.listStudents()` 才能填充「学生」下拉框。

- 本模块测试用 `FakeStudentService` 覆盖该依赖（`tests/queries/testQueryView.py`）；
- 证据截图用只读适配器从 `MemoryStore` 快照取学生（`cq-tools/evidenceShots.py`），
  该适配器**不在交付代码里**；
- A 提交学生模块后，只需确认其 `listStudents()` 按 `studentId` 升序，界面即可直接使用。

### 6.2 未挂载进主程序

`campusApp/app.py` 目前只自动挂载活动页，其余三个页签显示「本模块尚未接入」。
按规格 4.6 与 `docs/foundation.md`，挂载由 A 在集成时统一完成，
所需代码片段已写进 `change-requests.md` CR-07。

### 6.3 pytest-cov 未安装

见第 3.3 节。装上之后建议用官方命令复核一次覆盖率数字。

## 7. Git 状态

| 项目 | 状态 |
| --- | --- |
| 远程仓库 | `https://github.com/Bobxianyu/stusent-event` |
| 基线骨架 | `cf69fa5`（`chore(基础): 建立共享内存骨架`） |
| 功能分支 | `feat/query-statistics` |
| 已同步 | `main` 的 `27ffd5b`（合并提交 `9bb543b`） |
| 模块提交 | `7e4a89a` `feat(查询): 实现查询与统计模块` |
| 文档提交 | ef15bf docs(查询): 补充需求、用例表、缺陷与交接文档 |
| 推送 | 失败（403）：当前凭据账号 GQ-33550336 对仓库无写权限，见 7.1 |

提交时按白名单逐个暂存，未使用 `git add .`：

```powershell
git add -- campusApp/queries tests/queries docs/modules/queries
git diff --cached --name-only
git diff --cached --check
```

### 7.1 推送受阻（需要人配合）

推送命令与返回（真实输出）：

`	ext
$ git push -u origin feat/query-statistics
remote: Permission to Bobxianyu/stusent-event.git denied to GQ-33550336.
fatal: unable to access 'https://github.com/Bobxianyu/stusent-event.git/':
The requested URL returned error: 403
`

原因：本机 Git 凭据管理器缓存的账号是 GQ-33550336，
该账号不是 Bobxianyu/stusent-event 的协作者，只能读取、不能推送。
这不是网络问题——读操作全部正常（git ls-remote、git clone、git fetch 均成功）。

两条可行路径（任选一条）：

1. 加协作者：请仓库负责人把 GQ-33550336 加为 collaborator（Write 权限），
   之后在本目录执行 git push -u origin feat/query-statistics 即可。
2. Fork + PR：在 GitHub 上 fork 该仓库，再把本地分支推到自己的 fork：

   `powershell
   git remote add mine https://github.com/GQ-33550336/stusent-event.git
   git push -u mine feat/query-statistics
   `

   推完后在 GitHub 上从 GQ-33550336:feat/query-statistics
   向上游 Bobxianyu:main 发起 Pull Request。

本地分支与提交都已就绪，推送成功前不影响代码本身。

### 本机环境备注（不影响仓库内容）

- `github.com` 在 `hosts` 中被指向 `127.0.0.1`，由 Steam++（Watt Toolkit）
  的 Accelerator 在 80/443 端口反代，因此 `git` 可用、但 `curl.exe` 不走代理；
- `E:` 是 exFAT，不记录文件属主，git 会报 `dubious ownership`，
  已用 `git config --global --add safe.directory` 登记。

## 8. 已知限制

1. **学生模块未接入**：见 6.1，页面下拉框的数据来源仍是适配器。
2. **未做跨模块端到端验收**：规格 9.4 的 7 个场景由 A 在集成阶段执行，
   本模块只保证只读查询在真实 `MemoryStore` 上正确。
3. **覆盖率工具自建**：`pytest-cov` 装不上，数字来自等价口径脚本。
4. **界面测试依赖图形环境**：无显示环境时 `testQueryView.py` 会 `skip`
   （本机 1707×960，实测未 skip）。
5. **不实现写操作**：本模块任何情况下都不修改共享状态。

## 9. 交接清单

- [x] 三层实现（Repository / Service / View）
- [x] 单元测试与界面测试，全部通过（131 条）
- [x] 语句覆盖率 ≥80%（实测 100%）
- [x] 需求与设计说明 `design.md`
- [x] 用例表 `test-cases.md`（普通 + 健壮边界，实际结果来自真实运行）
- [x] 缺陷记录 `defects.md`（8 个，均含复现与回归）
- [x] 变更请求 `change-requests.md`
- [x] 界面截图 `evidence/`（8 张，真实骨架下生成）
- [x] 分支 `feat/query-statistics` 与模块提交
- [ ] 推送并开 PR（见第 7 节）
- [ ] 挂载进 `app.py`（A 负责，CR-07）
