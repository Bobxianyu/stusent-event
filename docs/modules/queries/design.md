# 模块四 · 查询与统计 · 设计说明

> 负责人：Agent D（分支 `feat/query-statistics`）
> 依据：《校园活动报名系统-四模块协作开发说明》v1.1 第 3、4、8 节
> 写入白名单：`campusApp/queries/`、`tests/queries/`、`docs/modules/queries/`

## 1. 模块定位

本模块是四个模块中**唯一只读**的一个：它不修改 `students`、`activities`、
`registrations` 任何一个集合，也不申请编号。全部数据来自 `MemoryStore.runRead`
交出的 `StoreSnapshot`，因此不会与 A、B、C 的写操作产生数据竞争。

对外提供四个能力：

| 需求编号 | 能力 | 公开方法 |
| --- | --- | --- |
| D-1 | 个人报名历史（含已取消、已结束） | `listPersonalRegistrations` |
| D-2 | 活动报名名单（可按状态过滤） | `listActivityRegistrations` |
| D-3 | 单活动统计 | `getActivityStats` |
| D-4 | 时间范围内总览统计 | `getOverviewStats` |

## 2. 分层与文件

```text
campusApp/queries/
  QueryRepository.py   只读仓储：在快照上筛选、计数、拼 RegistrationRow
  QueryService.py      参数校验 → runRead → 领域错误转 Result
  QueryView.py         四个页签的 Tk 界面：输入收集与结果显示
```

依赖方向：`View → Service → Repository → StoreSnapshot`，没有反向依赖，
View 不接触 `MemoryStore`，Service 不接触 Tk。

构造函数严格按规格 4.5：

```python
QueryService(store, repository, clock)
QueryView(parent, studentService, activityService, queryService)
```

## 3. 关键口径

### 3.1 剩余名额与占用率

```text
剩余名额 = capacity - 正式报名数
占用率   = round(正式报名数 / capacity * PERCENT_BASE, 2)
```

候补与已取消**不占**名额。`capacity` 下界为 1（公共常量 `MIN_CAPACITY`），
所以除法不会除零；空活动返回 `0.0` 而不是 `NaN`。百分数基数取公共常量
`PERCENT_BASE`。

### 3.2 计数三分

`countByStatus` 与 `summarizeByStartRange` 都把记录严格分成
`STATUS_CONFIRMED` / `STATUS_WAITLISTED` / `STATUS_CANCELLED` 三类。若快照中出现第四种状态字符串，
说明内部状态已损坏，仓储**立即抛异常**，由 Service 转成 `INTERNAL_ERROR`，
而不是静默跳过——静默跳过会让总数悄悄变少且无人发现（缺陷 D-2）。

### 3.3 总览区间

```text
[startDate 的北京时间午夜, startDate + days 天的北京时间午夜)
```

判定条件是 `fromAt <= activity.startAt < toAt`：**起点包含、终点排除**。
统计的是区间内活动的**当前**记录状态，不重建历史某天的状态；
因此报名时间早于区间起点的记录同样计入。

`distinctParticipantCount` 只对 `CONFIRMED` 记录按 `studentId` 去重；
同一学生正式参加多个活动只计一人，候补者不计入。

### 3.4 分页

```text
offset = (page - MIN_PAGE) * pageSize
items  = 排序后的行[offset : offset + pageSize]
total  = 同一条件下的总行数
```

页码、每页条数分别校验为 `1~10000`、`1~100`。页码合法但越过最后一页时，
返回**成功** + 空列表 + 真实 `total`（规格 8.3），不报错。

两类列表均按 `registrationId` 升序稳定排序；`total` 与 `items` 在同一
`runRead` 回调内取得，因此二者必然一致。

### 3.5 参数校验顺序

```text
1. requireId(studentId / activityId)
2. status 白名单（仅 None 或三种状态字符串）
3. requireInteger(page)
4. requireInteger(pageSize)
5. runRead 内：实体存在性 → 计数 → 取页
```

实体存在性检查放在 `runRead` 内部，保证「查到的实体」与「统计的快照」是同一份。

## 4. 错误映射

| 情形 | 错误码 | 字段 |
| --- | --- | --- |
| ID 非正整数 / 布尔 / 小数 / 字符串 | `VALIDATION_ERROR` | `studentId` / `activityId` |
| 状态不是三种字符串也不是 `None` | `VALIDATION_ERROR` | `status` |
| 页码或每页越界、非整数 | `VALIDATION_ERROR` | `page` / `pageSize` |
| 日期格式错误、非法日期、年份越界 | `VALIDATION_ERROR` | `startDate` |
| 天数越界、非整数、统计终点越上界 | `VALIDATION_ERROR` | `days` |
| 学生不存在 | `STUDENT_NOT_FOUND` | `studentId` |
| 活动不存在 | `ACTIVITY_NOT_FOUND` | `activityId` |
| 仓储抛出非业务异常 | `INTERNAL_ERROR` | 无 |

`message` 全部为中文，且不含内部状态、堆栈或学生资料。

## 5. 一致读保证

`runRead` 在锁内复制三个字典并用 `MappingProxyType` 包装，
复制完成后释放锁再执行回调。回调全程读取同一份快照，因此：

- 分页 `total` 与 `items` 来自同一时刻；
- 统计三类计数来自同一时刻；
- 快照是只读的，视图层拿到的是不可变实体，后续写入不会改写已返回结果。

`tests/queries/testQueryService.py` 中的
`testPageSnapshotConsistentUnderLaterWrite` 与 `testSnapshotIsReadOnly`
把这两条钉死。

## 6. 界面设计

`QueryView` 是一个 `ttk.Frame`，内部再套一层 `Notebook` 分成四个子页签：

```text
刷新 | <选项加载错误提示>
├── 个人报名记录   学生下拉 + 页码 + 每页 + 查询 → 结果表
├── 活动报名名单   活动下拉 + 状态 + 页码 + 每页 + 查询 → 结果表
├── 活动统计       活动下拉 + 查询统计 → 文本块
└── 总览统计       开始日期 + 天数 + 统计 → 文本块
```

实现要点：

- **下拉框按显示文本映射实体编号**（`dict[label] = id`），不使用下拉索引。
  索引会随选项顺序变化而指向别人（缺陷 D-3）。
- `refresh()` 重新载入两个列表并**尽量保留用户原有选择**；原选择消失时清空。
- 选项加载失败时不再静默置空，而是在工具条红色提示真实原因（缺陷 D-5）。
- 每页结果为空时给出「暂无记录 / 暂无符合条件的记录」提示，而不是只显示「共 0 条」。
- 所有时间列用 `formatDateTime` 按北京时间 `YYYY-MM-DD HH:MM:SS` 显示，
  `cancelledAt is None` 时显示空串（不依赖时间戳真假值）。
- 界面不构造第二个 `Tk()`，不使用跨模块事件总线，写操作由对应模块自己刷新。

## 7. 与骨架的衔接

`QueryView` 需要 `studentService.listStudents()` 与
`activityService.listActivities()` 来填充下拉框，这两个方法属于 A、B 的公开接口
（规格 4.5、4.6），本模块只消费不实现。二者返回失败 Result 时，
界面显示错误提示而不是崩溃。

## 8. 当前状态与已知限制

- 已接入真实公共骨架（基线 cf69fa5，同步 main 27ffd5b），
  模块实现见提交 7e4a89a。
- QueryRepository 与 QueryService 的语句覆盖率 100%（见 handoff.md 3.3）。
- 骨架中的状态常量名为 STATUS_*、错误码为 ERROR_*，本模块直接复用，不另建副本；
  代码缩进按 AGENTS.md 使用 2 空格。
- 界面为 Tk，自动化测试只覆盖「取值与文案是否正确」，
  视觉检查以 evidence/ 下截图为准，不用截图替代业务测试。
- 学生模块尚未提交，界面下拉框的学生数据在集成前由只读适配器提供
  （见 handoff.md 6.1）。
