# 模块四 · 查询与统计 · 缺陷记录

> 原则：先保留可复现的原版本与失败证据，再修复并复测。
> 本次所有缺陷都在同一个未提交工作区内发现与修复，「修复前版本」用代码片段与
> 失败命令记录；提交 Git 后会在 `handoff.md` 补上修复前后的提交 SHA。

## 汇总

| 编号 | 严重程度 | 一句话 | 状态 |
| --- | --- | --- | --- |
| D-1 | 中（测试缺陷） | 自带用例用非法前置状态造数，被存储层拒绝 | 已修复 |
| D-2 | 中 | 总览统计对未知报名状态静默跳过，总数悄悄变少 | 已修复 |
| D-3 | 高 | 界面用下拉索引定位实体，选项顺序变化后查错学生 | 已修复 |
| D-4 | 中 | 规格要求的「刷新」按钮缺失 | 已修复 |
| D-5 | 中 | 下拉选项加载失败被静默吞掉，界面只剩空框 | 已修复 |
| D-6 | 低 | 结果表列宽写死，中文时间列被截断 | 已修复 |
| D-7 | 低 | 取消时间用真假值判断，`0` 会被当成空 | 已修复 |
| D-8 | 高 | 接入真实骨架后，界面渲染越界时间戳会整页崩溃 | 已修复 |

---

## D-1 自带用例使用非法前置状态造数

**发现方式**：运行仓库自带的 `tests/queries`，2 条用例失败。

**复现步骤**

```powershell
cd E:\campus-query
python -m pytest tests/queries -o python_files='test*.py' -q
```

**失败证据**（修复前）

```text
FAILED tests/queries/testQueryRepository.py::testCountByStatus
FAILED tests/queries/testQueryService.py::testGetActivityStatsCounts
E  ValidationFailed: 同一学生同一活动存在多条未取消记录
```

**根因**：两条用例都给同一个学生、同一个活动同时塞了 `CONFIRMED` 和
`WAITLISTED` 两条未取消记录。这违反公共约束「同一 `(studentId, activityId)` 最多
一条正式或候补记录」（规格 4.3），被存储层的发布前校验拒绝。
问题在**用例**，不在业务代码：规格 7.5 明确「不要通过制造非法内存状态来代替正常报名过程」。

**修复**：改为合法前置状态——同一学生先取消再正式报名（两条历史，其中一条已取消），
候补由另一名学生承担。同时把「混合状态」的意图写进 `conftest.py` 的造数注释。

**回归**：`testCountByStatus`、`testGetActivityStatsCounts` 现均通过，
且断言值仍覆盖「确认/候补/取消」三类各 1 条。

---

## D-2 总览统计对未知状态静默跳过

**发现方式**：代码审查。原实现是 `if/elif/elif` 链，没有 `else`。

**修复前代码**（`QueryRepository.summarizeByStartRange`）

```python
if reg.status == CONFIRMED:
    confirmedCount += 1
    distinctStudents.add(reg.studentId)
elif reg.status == WAITLISTED:
    waitlistedCount += 1
elif reg.status == CANCELLED:
    cancelledCount += 1
```

**现象**：若快照里出现第四种状态字符串，该条记录既不报错也不计入任何计数，
总览数字会**无声地小于**真实条数。使用者无法察觉。

**根因**：把「内部状态已损坏」当成「可忽略的数据」，与规格 4.3
「由公共存储层检查基础约束，失败时抛异常」的处理风格不一致。

**修复**：先做状态白名单断言，命中未知值立即抛异常，由 Service 的兜底
`except Exception` 转成 `INTERNAL_ERROR`（中文文案，不泄露内部细节）。

```python
knownStatuses = (CONFIRMED, WAITLISTED, CANCELLED)
...
if reg.status not in knownStatuses:
    raise ValueError("报名状态非法：%r" % (reg.status,))
```

**回归**

- `testSummarizeRejectsUnknownStatus`：直接调用仓储，断言抛 `ValueError`。
- `testGetOverviewUnknownStatusFailsLoudly`：从 Service 侧验证同样失败。
- 原有 21 条总览用例全部仍通过，说明正常路径未受影响。

---

## D-3 界面按下拉索引定位实体，导致查错学生（高危）

**发现方式**：审查 `QueryView` 的 `_selectedStudentId` / `_selectedActivityId`。

**修复前代码**

```python
def _selectedStudentId(self, combo):
    idx = combo.current()
    if idx < 0 or idx >= len(self.studentOptions):
        return None
    return self.studentOptions[idx][0]
```

**现象**：`refresh()` 只更新 `["values"]`，不会重置 `current()` 索引。
若两次刷新之间选项顺序发生变化（例如新增学生按 `studentId` 升序插到前面、
或有学生被移除），索引仍指向旧位置，于是**查到的是另一个学生的记录**。
界面不会有任何提示，学生看到的是别人的报名历史。

**根因**：用位置（索引）做实体标识，而位置会随数据变化；实体编号才是稳定标识。

**修复**：选项改成「显示文本 → 实体编号」的字典，按当前文本取值。

```python
def _resolveStudentId(self, combo):
    return self.studentOptions.get(combo.get())
```

`_applyOptions` 在刷新时按文本尽量保留原选择，原选择已不存在才回落到第一项。

**回归**

- `testSelectionResolvesEntityNotIndex`：把学生列表倒序后刷新，
  仍解析到 `studentId=2`（修复前会解析到另一个人）。
- `testRefreshKeepsSelectionWhenStillPresent`：选择不丢。
- `testRefreshClearsVanishedSelection`：选择失效时回落到第一项，不残留。

---

## D-4 缺少「刷新」按钮

**发现方式**：对照规格 8.2.5「提供分页、刷新和无结果提示」逐条核对界面。

**现象**：`QueryView` 只有 `refresh()` 方法，界面上没有任何控件调用它。
用户新增学生或活动后必须切换页签才可能看到新选项，纯查询场景下没有手动刷新入口。

**修复**：在视图顶部增加工具条，放「刷新」按钮并在其右侧显示选项加载错误。
`refresh()` 不改变已显示的查询结果，只重载两个下拉列表。

**回归**：`testRefreshKeepsSelectionWhenStillPresent`、
`testRefreshClearsVanishedSelection`、`testRefreshSurfacesOptionErrors`
均从按钮调用的同一入口进入。截图见 `evidence/01` 等（工具条左侧「刷新」）。

---

## D-5 选项加载失败被静默吞掉

**发现方式**：审查 `refresh()`。

**修复前代码**

```python
def _loadStudentOptions(self):
    result = self.studentService.listStudents()
    if not result.ok:
        return []
    ...
```

**现象**：学生模块尚未实现（返回 `NOT_IMPLEMENTED`）或发生内部错误时，
下拉框直接空白，界面没有任何解释，使用者以为「本来就没有学生」。

**修复**：把失败原因收集起来，在工具条以红色中文提示；
两个列表分别判断，互不掩盖。

```python
errors.append("学生列表加载失败：%s" % studentResult.error.message)
```

**回归**：`testRefreshSurfacesOptionErrors` 断言两条提示同时出现，
截图 `evidence/08-选项加载失败提示.png`。

---

## D-6 结果表列宽写死，中文时间列被截断

**发现方式**：查看第一轮界面截图，右侧「活动开始/活动结束」列不可见。

**现象**：7 列统一 130px，而 `YYYY-MM-DD HH:MM:SS` 的北京时间文本在默认字号下
约需 160px，导致表格横向溢出、右侧列被裁。

**修复**：改为按列指定宽度（`widths = (80, 200, 100, 170, 170, 170, 170)`），
活动名单表用 `(90, 150, 130, 110, 190, 190)`。

**回归**：重新生成全部截图，7 列与 6 列均可完整显示，见 `evidence/01`。

---

## D-7 取消时间用真假值判断

**发现方式**：审查 `_fillRegistrationTree`。

**修复前代码**

```python
formatDateTime(row.cancelledAt) if row.cancelledAt else ""
```

**现象**：时间字段是整数 Unix 秒，用真假值判断会把 `0`（1970-01-01T08:00:00 北京时间）
当作「没有取消时间」。虽然业务上不会产生 0，但这是错误的判空方式，
一旦将来支持历史数据导入就会显示错误。

**修复**：改为 `is not None`。

**回归**：`testPersonalQueryFillsTree` 断言未取消行的取消时间列是空串；
`testPersonalQueryShowsNoResultHint` 等其它界面用例仍通过。

---

## D-8 界面渲染越界时间戳导致整页崩溃

**发现方式**：把模块接到真实公共骨架后跑 `tests/queries`，2 条界面用例失败。

**失败证据**（接入真实骨架后的第一次运行）

```text
FAILED tests/queries/testQueryView.py::testPersonalQueryFillsTree
FAILED tests/queries/testQueryView.py::testActivityQueryStatusFilter
E  campusApp.core.contracts.DomainError: 时间超出支持的时间范围
   campusApp\core\timeUtils.py:33
```

**根因**：本地早期版本用自写的 `formatDateTime`，它对任何整数都直接格式化；
真实骨架的 `formatDateTime` 会先调用 `validateTimestamp`（业务范围 2000-01-01 至
2100-01-01），越界即抛 `DomainError`。而 `QueryView` 在渲染表格时对每一行的
`joinedAt` / `cancelledAt` / `startAt` / `endAt` 都直接调用它，
只要有一行时间异常，整个查询页就抛异常，用户看到的是崩溃而不是数据。

**为什么只有接真骨架才暴露**：本地桩为了省事没有做范围校验，
这正好说明「在桩上全绿」不能替代真实集成验证。

**修复**：新增 `_formatTime` 统一收口，空值返回空串，越界返回占位符 `—`。

```python
def _formatTime(self, timestamp):
  if timestamp is None:
    return ""
  try:
    return formatDateTime(timestamp)
  except DomainError:
    return UNKNOWN_TIME_TEXT
```

表格的 6 个时间列全部改走该函数，界面不再因为单条数据异常而整体失败。

**回归**

- `testFormatTimeFallbackForOutOfRange`：覆盖 `None`、0、1024、
  `MAX_TIMESTAMP`、`MAX_TIMESTAMP + 1` 与正常时间六种输入。
- `testOutOfRangeTimestampRendersPlaceholder`：端到端验证一条 `joinedAt=0`
  的记录仍能渲染成一行，时间列显示 `—`。
- 接入后 131 条用例全部通过。

---

## 观察项（未改）

### O-1 `_buildRows` 遇到悬空引用时跳过该行

`QueryRepository._buildRows` 在 `state.students.get(...)` 或
`state.activities.get(...)` 返回 `None` 时 `continue`，不抛异常。

**判断**：保留。该分支属于防御性代码——存储层已保证报名引用的学生与活动存在
（规格 4.3），一旦出现悬空引用说明内部状态已损坏，此时「少显示一行」比
「整个查询页崩溃」更可接受。为避免它变成第二个 D-2，用例
`testBuildRowsSkipsDanglingReference` 把该行为固定下来，
若将来策略改为抛异常，该用例会失败并提示需要同步更新。

### O-2 状态过滤下拉出现未知文本时按「全部」处理

`_statusFromLabel` 找不到对应标签时返回 `None`（即不过滤）。
由于该下拉框是 `state="readonly"`，用户无法输入自定义值，
只有代码写错才可能触发。本期不改，记录在此以便集成时复核。
