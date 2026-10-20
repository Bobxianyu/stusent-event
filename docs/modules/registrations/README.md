# 模块三：报名与取消

## 功能与入口

本模块负责提交报名、判定正式与候补、取消报名、自动递补以及展示当前学生的报名历史。

桌面入口是 `python -m campusApp.app` 中的“报名与取消”页。该页由集成人按第 4.6 节统一挂载，构造签名为
`RegistrationView(parent, studentService, activityService, registrationService, queryService)`；查询服务缺省时只停用历史区，报名与取消不受影响。

`RegistrationService` 的公开方法（签名由公共骨架固定，不擅自改动）：

| 方法 | 功能 | 主要失败情况 |
| --- | --- | --- |
| `registerStudent(studentId, activityId)` | 提交报名，返回正式或候补结果及剩余名额 | 编号非法、学生不存在、活动不存在、未开放/已关闭/已截止、重复报名、有效报名已达 3 条 |
| `cancelRegistration(studentId, registrationId)` | 取消本人报名，并递补最早的候补 | 编号非法、记录不存在、非本人记录、已取消、活动已开始 |

两个方法都返回公共 `Result`：成功时 `ok=True`，失败时 `error.code` 为 `campusApp.core.constants` 中的报名错误码，`error.message` 为中文说明。

辅助方法 `describeStatus(registration)` 把状态码转成界面使用的中文说明，不参与业务判定。

## 规则与边界

- **报名窗口左闭右开**：`openAt <= now < closeAt` 且活动未被手动关闭。手动关闭标记、未开放、已截止统一返回 `ACTIVITY_NOT_OPEN`。
- **重复报名**：同一学生对同一活动最多一条未取消记录，候补也算未取消；取消后可再次申请，生成新记录并排在候补队尾。
- **个人额度**：有效报名上限 3 条，按“活动 `endAt > now`”统计，跨活动累计；已取消记录不占用；活动恰好结束时不再占用。
- **容量判定**：`countConfirmed < capacity` 时正式报名，否则进入候补；正式人数不允许超过容量，由 `MemoryStore` 草稿校验兜底。
- **取消条件**：只要求 `now < startAt`，与报名窗口无关；因此报名截止后、活动开始前仍可取消并递补。
- **递补规则**：取消正式名额时，在同一次写事务中把该活动 `registrationId` 最小的候补转为正式；一次最多递补一条；递补不再检查个人额度（该候补已占用一条）。
- **原子性**：报名、取消、递补都在一个 `store.runWrite` 内完成，任何异常或校验失败都会丢弃整份草稿，不留下“已取消但未递补”的中间态；失败的申请不消耗报名编号。
- **状态唯一**：报名状态只由 `Registration.status` 表达，不另写第二份状态字段。
- **读写隔离**：跨模块读取使用当前写回调持有的同一份 `StoreDraft`，不另建 Store、不读取旧快照。

## 数据结构与依赖

| 类型 | 来源 | 说明 |
| --- | --- | --- |
| `Registration` | `core.contracts` | 报名实体，含状态与取消时间 |
| `RegistrationReceipt` | `core.contracts` | 报名结果与剩余名额 |
| `CancellationReceipt` | `core.contracts` | 取消结果与被递补编号 |
| `RegistrationRow` | `core.contracts` | 报名历史行，由模块四组装 |
| `StoreSnapshot` / `StoreDraft` | `core.contracts` | 只读快照与写草稿，草稿含 `nextRegistrationId` |
| `StudentReader` / `ActivityReader` | `core.contracts` | 跨模块只读协议，构造时注入 |

构造方式：`RegistrationService(store, repository, studentReader, activityReader, clock)`。

- `studentReader` 由模块一的 `StudentRepository` 实现；本模块不导入其他模块的 Service 或 View。
- `activityReader` 复用模块二的 `ActivityRepository`。
- 本模块只独占 `state.registrations` 与 `nextRegistrationId` 的写入。

## 用例表（含前置内存状态）

下表的“已有报名”为用例开始前该学生的有效报名条数，时间均相对固定基准 `now`。用例名对应 `tests/registrations` 中的测试函数。

| 用例 | 已有报名 | 容量 | 当前时间 | 预期 |
| --- | --- | --- | --- | --- |
| 首个申请人 | 0 | 2 | 窗口内 | 正式报名，剩余名额 1 |
| 名额已满 | 0（他人 1 条正式） | 1 | 窗口内 | 候补，剩余名额 0 |
| 开始前 1 秒 | 0 | 5 | `openAt - 1` | 拒绝，`ACTIVITY_NOT_OPEN` |
| 恰好开始 | 0 | 5 | `openAt` | 允许 |
| 截止前 1 秒 | 0 | 5 | `closeAt - 1` | 允许 |
| 恰好截止 | 0 | 5 | `closeAt` | 拒绝，`ACTIVITY_NOT_OPEN` |
| 截止后 1 秒 | 0 | 5 | `closeAt + 1` | 拒绝，`ACTIVITY_NOT_OPEN` |
| 手动关闭 | 0 | 5 | 窗口内，`isClosed=True` | 拒绝，`ACTIVITY_NOT_OPEN` |
| 额度 0/1/2 条 | 0、1、2 | 10 | 窗口内 | 允许 |
| 额度第 4 条 | 3 | 10 | 窗口内 | 拒绝，`ACTIVE_LIMIT_REACHED` |
| 活动结束前 1 秒仍占额度 | 3（其一 `endAt = now + 1`） | 10 | 窗口内 | 拒绝，`ACTIVE_LIMIT_REACHED` |
| 活动恰好结束不占额度 | 3（其一 `endAt = now`） | 10 | 窗口内 | 允许 |
| 已取消不占额度 | 2 条有效 + 1 条已取消 | 10 | 窗口内 | 允许 |
| 重复报名 | 1（同活动） | 5 | 窗口内 | 拒绝，`DUPLICATE_REGISTRATION` |
| 取消后重报 | 0 | 1 | 窗口内 | 新记录排在候补队尾 |
| 开始前 1 秒取消 | 1 | 5 | `startAt - 1` | 成功 |
| 恰好开始取消 | 1 | 5 | `startAt` | 拒绝，`CANCELLATION_CLOSED` |
| 截止后取消 | 1 | 1 | `closeAt + 1`，早于 `startAt` | 成功并递补 |
| 取消正式递补 | 1 正式 + 2 候补 | 1 | 窗口内 | 递补编号最小的候补 |
| 取消候补 | 1 正式 + 1 候补 | 1 | 窗口内 | 不触发递补 |
| 递补者已满 3 条 | 候补者另有 3 条有效 | 1 | 窗口内 | 仍递补为正式 |
| 最后名额竞争 | 0 | 1 | 窗口内 | 两个线程并发，恰一条正式、一条候补 |

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests/registrations -q
.\.venv\Scripts\python.exe -m pytest tests/registrations `
  --cov=campusApp.registrations --cov-report=term-missing --cov-fail-under=80
```

最近一次执行结果：全量 `122 passed, 1 skipped`；本模块覆盖率为
`RegistrationRepository` 100%、`RegistrationService` 98%、`RegistrationView` 86%，合计 92%。

界面测试需要可用的 Tk 环境；Tcl 初始化失败时用例标记为跳过。

## 运行环境（与编辑器无关）

本模块的代码与测试都是普通 Python 文件，不绑定任何 IDE，也不绑定 VS Code 的 Jupyter 插件。

| 内容 | 依赖 | 在别处怎么用 |
| --- | --- | --- |
| `campusApp/registrations/*.py` | 仅标准库（`tkinter`、`logging`、`dataclasses`、`typing`）与本项目 `campusApp.core` | 任意 Python 3.12 解释器、任意编辑器或命令行 |
| `tests/registrations/*.py` | `pytest`（`requirements-dev.txt` 锁定 8.4.2）与 `pytest-cov` | `python -m pytest tests/registrations` |
| `registrationDemo.ipynb` | 仅用于演示，需要带 `ipykernel` 的内核 | VS Code、PyCharm、JupyterLab、Jupyter Notebook、浏览器均可 |

注意事项：

- **Notebook 是可选件**。业务验收只看 `pytest` 结果，不装 Jupyter 也能完整验证本模块。
- **`ipykernel` 不是运行依赖**，也没有写进 `requirements-dev.txt`（该文件只锁定测试依赖）。
  需要跑 Notebook 时单独安装：`pip install ipykernel`。
- `.ipynb` 是开放的 JSON 格式，本 Notebook 内只有普通 Python 代码，没有 `%magic`、`!shell`
  或 VS Code 专有语法；内核声明为通用的 `python3`，任何 Jupyter 前端都能打开并运行。
- Notebook 第一个单元格会用 `pyproject.toml` 自动定位仓库根目录并加入 `sys.path`，
  因此在 `docs/modules/registrations/` 里直接打开也能 `import campusApp`。
- PyCharm 打不开 Notebook 时（例如版本较低或使用 Community 版），可以：直接忽略该文件、
  用 `pip install jupyterlab` 后在浏览器打开，或用 `jupyter nbconvert --to html` 导出成静态页面阅读。
- 仓库里的 `.venv` 只在生成它的机器上有效，并且已被 `.gitignore` 忽略，不会进入版本库；
  换机器请按根目录 `README.md` 重新创建虚拟环境。

## 后续接入

1. **学生读取（模块一）**：需要 `StudentRepository.findById(state, studentId)` 满足 `StudentReader` 协议，
   用于报名前的学生存在性检查，以及界面下拉框依赖的 `listStudents`。
2. **报名历史（模块四）**：`RegistrationView` 调用
   `QueryService.listPersonalRegistrations(studentId, page, pageSize)`；
   模块四交付前传入 `None`，历史区显示“查询模块尚未接入”。
3. **页签挂载（集成人）**：在 `app.py` 中按 Store、Repository、Service、View 顺序构造并挂到“报名与取消”页；不得重建 Store，也不得在切换页签时重置数据。

缺少的公共项已记录在 [change-requests.md](change-requests.md)。

## 已知限制

- 本期不支持修改容量、禁用学生或删除记录，因此合法数据中出现候补时活动应当已满。
- 只保证同一进程内的数据一致性；多个独立运行的程序不共享内存与名额。
- 程序关闭后报名数据与编号重置，不使用数据库，也不写入业务数据文件。
- 报名历史的分页、状态筛选与统计口径由模块四负责，本模块只提交查询请求。
