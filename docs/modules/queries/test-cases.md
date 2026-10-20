# 模块四 · 查询与统计 · 测试用例表

> 执行环境：真实公共骨架（`cf69fa5`）+ 提交 `7e4a89a`
> 「实际结果」全部来自真实运行，「是否通过」取自 `evidence/test-results.json`
> （131 条，`passed=131`、`failed=0`、`skipped=0`、`pytestExit=0`）。
> 尚未执行的用例一律标「未执行」，不预填「通过」。

## 0. 说明

### 0.1 代码标识

| 文件 | 内容 SHA-256（前 8 位） |
| --- | --- |
| `campusApp/queries/QueryService.py` | `e540f699` |
| `campusApp/queries/QueryRepository.py` | `7753344f` |
| `campusApp/queries/QueryView.py` | 见提交 `7e4a89a`（含 D-8 修复） |
| `tests/queries/testQueryService.py` | `f1dab863` |

下表「代码 SHA」列统一使用本次运行的提交 **`7e4a89a`**，
即 `feat(查询): 实现查询与统计模块`，可由 `git show 7e4a89a` 找回当时的完整代码。

### 0.2 前置状态约定

所有前置状态都在**独立** `MemoryStore` 中通过写回调准备，满足公共约束：

- 同一学生同一活动最多一条未取消记录（`STATUS_CONFIRMED` / `STATUS_WAITLISTED`）；
- 取消历史可以有多条，因此「取消后再报名」用两条记录表达；
- 引用的学生与活动必须存在；编号计数器同步到最大编号 + 1；
- 时间一律使用合法 Unix 秒（真实 `formatDateTime` / `validateTimestamp` 会校验范围）。

**不使用**「正式报名数超过容量」「同一学生两条未取消记录」这类非法内存状态造数——
真实 `MemoryStore._validateDraft` 会直接拒绝。

### 0.3 证据位置

`docs/modules/queries/evidence/` 下的截图；机器可读结果在
`evidence/test-results.json`。

## 1. 个人报名历史（D-1，规格 8.2.1 / 8.5）

| 用例编号 | 测试方法 | 需求 | 前置状态 | 输入 | 预期结果 | 实际结果 | 通过 | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TC-D1-01 | `testListPersonalStudentNotFound` | D-1 | 空 Store | `(999, 1, 10)` | `STUDENT_NOT_FOUND` | 返回该错误码 | 是 | test-results.json |
| TC-D1-02 | `testListPersonalTotalAndOrder` | D-1 | 学生 1，活动 1/2/3，记录乱序插入 | `(1, 1, 10)` | `total=3`，按编号升序 `[1,2,3]` | 与预期一致 | 是 | `01-个人报名记录-有数据.png` |
| TC-D1-03 | `testListPersonalOnlyOwnRows` | D-1 | 两学生各一条记录 | `(1, 1, 10)` | 只返回学生 1 的 1 条 | `total=1` | 是 | test-results.json |
| TC-D1-04 | `testListPersonalRowCarriesCurrentProfile` | D-1 | 学生「张三」+ 活动「迎新晚会」 | `(1, 1, 10)` | 行内含当前学号/姓名/活动名/状态 | 字段一致 | 是 | `01-个人报名记录-有数据.png` |
| TC-D1-05 | `testListPersonalIncludesCancelledAndEnded` | D-1 | 一条已取消 + 一条已结束活动的正式 | `(1, 1, 10)` | 两条都返回，不做时间过滤 | `total=2` | 是 | test-results.json |
| TC-D1-06 | `testListPersonalBeyondLast` | D-1 | 1 条记录 | `(1, 2, 10)` | 成功 + 空列表 + `total=1` | 与预期一致 | 是 | test-results.json |
| TC-D1-07 | `testListPersonalLastPagePartial` | D-1 | 5 条记录 | `(1, 3, 2)` | 第 3 页 1 条，`total=5` | 与预期一致 | 是 | test-results.json |
| TC-D1-08 | `testListPersonalPaginationNoOverlap` | D-1 | 4 条记录 | 第 1、2 页，每页 2 | `[1,2]` 与 `[3,4]` 无重叠 | 与预期一致 | 是 | test-results.json |
| TC-D1-09 | `testListPersonalPageNormalBoundary` | D-1 | 学生存在、无记录 | 页码 1/2/5000/9999/10000 | 全部成功 | 5 组全部成功 | 是 | test-results.json |
| TC-D1-10 | `testListPersonalPageRobustBoundary` | D-1 | 同上 | 页码 0/-1/10001 | `VALIDATION_ERROR`，`field=page` | 与预期一致 | 是 | `07-个人报名记录-页码越界.png` |
| TC-D1-11 | `testListPersonalPageSizeNormalBoundary` | D-1 | 同上 | 每页 1/2/50/99/100 | 全部成功 | 5 组全部成功 | 是 | test-results.json |
| TC-D1-12 | `testListPersonalPageSizeRobustBoundary` | D-1 | 同上 | 每页 0/-1/101 | `VALIDATION_ERROR`，`field=pageSize` | 与预期一致 | 是 | test-results.json |
| TC-D1-13 | `testListPersonalInvalidStudentId` | D-1 | 空 Store | `studentId` = 0/-1/True/1.5/"1"/None | 全部 `VALIDATION_ERROR` | 6 组全部拒绝 | 是 | test-results.json |
| TC-D1-14 | `testListPersonalBoolPageRejected` | D-1 | 学生存在 | `page=True`、`pageSize=True` | 排除布尔 | 与预期一致 | 是 | test-results.json |
| TC-D1-15 | `testListPersonalInternalError` | D-1 | 仓储注入故障 | `(1, 1, 10)` | `INTERNAL_ERROR` + 中文文案 | 文案「查询个人报名记录时发生内部错误」 | 是 | test-results.json |

## 2. 活动报名名单（D-2，规格 8.2.2 / 8.3）

| 用例编号 | 测试方法 | 需求 | 前置状态 | 输入 | 预期结果 | 实际结果 | 通过 | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TC-D2-01 | `testListActivityNotFound` | D-2 | 空 Store | `(999, None, 1, 10)` | `ACTIVITY_NOT_FOUND` | 与预期一致 | 是 | test-results.json |
| TC-D2-02 | `testListActivityInvalidStatus` | D-2 | 活动存在 | `status` = ""/"UNKNOWN"/123/0/True/列表 | 全部 `VALIDATION_ERROR` | 6 组全部拒绝 | 是 | test-results.json |
| TC-D2-03 | `testListActivityStatusFilter` | D-2 | 1 确认 + 1 候补 + 1 取消 | `status` = None/三种状态 | total 依次 3/1/1/1 | 与预期一致 | 是 | `03-活动报名名单-候补过滤.png` |
| TC-D2-04 | `testListActivityFilterConsistentWithItems` | D-2 | 2 确认 + 1 候补 | `status=CONFIRMED` | `total=2` 且 items 全为确认 | 与预期一致 | 是 | test-results.json |
| TC-D2-05 | `testListActivityEmptyResultIsSuccess` | D-2 | 活动存在、无记录 | `(1, None, 1, 10)` | 成功 + 空列表 + `total=0` | 与预期一致 | 是 | `02-个人报名记录-无结果.png` |
| TC-D2-06 | `testListActivityPagingValidation` | D-2 | 活动存在 | (0,10)/(10001,10)/(1,0)/(1,101) | 全部 `VALIDATION_ERROR` | 4 组全部拒绝 | 是 | test-results.json |
| TC-D2-07 | `testListActivityInvalidEntityId` | D-2 | 空 Store | `activityId=0` | `VALIDATION_ERROR` | 与预期一致 | 是 | test-results.json |
| TC-D2-08 | `testListActivityInternalError` | D-2 | 仓储注入故障 | `(1, None, 1, 10)` | `INTERNAL_ERROR` | 文案「查询活动报名名单时发生内部错误」 | 是 | test-results.json |

## 3. 活动统计（D-3，规格 8.2.3 / 8.3）

| 用例编号 | 测试方法 | 需求 | 前置状态 | 输入 | 预期结果 | 实际结果 | 通过 | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TC-D3-01 | `testGetActivityStatsNotFound` | D-3 | 空 Store | `(999)` | `ACTIVITY_NOT_FOUND` | 与预期一致 | 是 | test-results.json |
| TC-D3-02 | `testGetActivityStatsCounts` | D-3 | 容量 4；1 取消 + 2 确认 + 1 候补 | `(1)` | 确认 2、候补 1、取消 1、剩余 2、占用 50.0 | 与预期完全一致 | 是 | `04-活动统计.png` |
| TC-D3-03 | `testGetActivityStatsEmptyActivity` | D-3 | 容量 7，无记录 | `(1)` | 计数全 0、剩余 7、占用 0.0 | 与预期一致 | 是 | test-results.json |
| TC-D3-04 | `testGetActivityStatsFullActivity` | D-3 | 容量 2，2 确认 + 1 候补 + 1 取消历史 | `(1)` | 剩余 0、占用 100.0 | 与预期一致 | 是 | test-results.json |
| TC-D3-05 | `testGetActivityStatsOccupancyRounding` | D-3 | 容量 3 | 1 人 / 2 人正式 | 33.33 / 66.67 | 与预期一致 | 是 | test-results.json |
| TC-D3-06 | `testGetActivityStatsMinimumCapacity` | D-3 | 容量 1（下边界） | 0 人 / 1 人 | 0.0 / 100.0，不除零 | 与预期一致 | 是 | test-results.json |
| TC-D3-07 | `testGetActivityStatsWaitlistDoesNotOccupySeat` | D-3 | 容量 2，2 确认 + 1 候补 | `(1)` | 剩余 0、占用 100.0 | 与预期一致 | 是 | test-results.json |
| TC-D3-08 | `testGetActivityStatsInvalidId` | D-3 | 空 Store | 0/-1/None/"1"/2.5 | 全部 `VALIDATION_ERROR` | 5 组全部拒绝 | 是 | test-results.json |
| TC-D3-09 | `testGetActivityStatsDoesNotMutateStore` | D-3 | 有数据 | `(1)` | 调用前后集合长度不变 | 前后一致 | 是 | test-results.json |
| TC-D3-10 | `testGetActivityStatsInternalError` | D-3 | 仓储注入故障 | `(1)` | `INTERNAL_ERROR` | 文案「统计活动时发生内部错误」 | 是 | test-results.json |

## 4. 总览统计（D-4，规格 8.2.4 / 8.3）

### 4.1 天数与日期校验

| 用例编号 | 测试方法 | 需求 | 前置状态 | 输入 | 预期结果 | 实际结果 | 通过 | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TC-D4-01 | `testGetOverviewDaysNormalBoundary` | D-4 | 空 Store | days = 1/2/180/364/365 | 全部成功 | 5 组全部成功 | 是 | test-results.json |
| TC-D4-02 | `testGetOverviewDaysRobustBoundary` | D-4 | 空 Store | days = 0/-1/366 | `VALIDATION_ERROR`，`field=days` | 与预期一致 | 是 | `06-总览统计-天数越界.png` |
| TC-D4-03 | `testGetOverviewDaysMustBeInteger` | D-4 | 空 Store | days = True/1.5/"30"/None | 排除布尔与字符串 | 4 组全部拒绝 | 是 | test-results.json |
| TC-D4-04 | `testGetOverviewInvalidDate` | D-4 | 空 Store | ""/"2025-1-1"/"2025/01/01"/"2025-13-01"/"2025-02-30"/"20250101"/带时间/abc | `VALIDATION_ERROR`，`field=startDate` | 8 组全部拒绝 | 是 | test-results.json |
| TC-D4-05 | `testGetOverviewDateMustBeString` | D-4 | 空 Store | 20250101/None/列表 | `VALIDATION_ERROR` | 3 组全部拒绝 | 是 | test-results.json |
| TC-D4-06 | `testGetOverviewNonLeapFeb29` | D-4 | 空 Store | "2023-02-29"、"2025-02-29" | `VALIDATION_ERROR` | 与预期一致 | 是 | test-results.json |
| TC-D4-07 | `testGetOverviewDateOutOfRange` | D-4 | 空 Store | "1999-12-31"、"2100-01-01" | `VALIDATION_ERROR` | 与预期一致 | 是 | test-results.json |

### 4.2 区间与日期运算

| 用例编号 | 测试方法 | 需求 | 前置状态 | 输入 | 预期结果 | 实际结果 | 通过 | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TC-D4-08 | `testGetOverviewLeapDay` | D-4 | 2024-02-29 09:00 开始的活动 | "2024-02-29" 1 天 / "2024-02-28" 1 天 / 2 天 | 1 / 0 / 1 | 与预期一致 | 是 | test-results.json |
| TC-D4-09 | `testGetOverviewCrossMonth` | D-4 | 01-31 与 02-01 各一活动 | "2025-01-31" 1 天 / 2 天 | 1 / 2 | 与预期一致 | 是 | test-results.json |
| TC-D4-10 | `testGetOverviewCrossYear` | D-4 | 12-31 与 01-01 各一活动 | "2025-12-31" 1 天 / 2 天 | 1 / 2 | 与预期一致 | 是 | test-results.json |
| TC-D4-11 | `testGetOverviewStartBoundaryIncluded` | D-4 | 活动恰在区间起点那一秒开始 | "2025-03-10" 1 天 | 计入，`activityCount=1` | 与预期一致 | 是 | test-results.json |
| TC-D4-12 | `testGetOverviewEndBoundaryExcluded` | D-4 | 活动恰在区间终点那一秒开始 | 1 天 / 2 天 | 0 / 1（终点排除） | 与预期一致 | 是 | test-results.json |
| TC-D4-13 | `testGetOverviewEndsAtUpperBound` | D-4 | 活动 2099-12-31 23:00 开始 | "2099-12-31" 1 天 | 成功，终点恰为上界 | 与预期一致 | 是 | test-results.json |
| TC-D4-14 | `testGetOverviewExceedsUpperBound` | D-4 | 空 Store | "2099-12-31" 365 天 | 终点越界 → `VALIDATION_ERROR` | 与预期一致 | 是 | test-results.json |

### 4.3 计数口径

| 用例编号 | 测试方法 | 需求 | 前置状态 | 输入 | 预期结果 | 实际结果 | 通过 | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TC-D4-15 | `testGetOverviewCountsByStartRange` | D-4 | 1-01 与 1-02 各一活动 | "2025-01-01" 1 天 | 活动 1、确认 1、候补 1、去重 1 | 与预期一致 | 是 | `05-总览统计.png` |
| TC-D4-16 | `testGetOverviewDistinctParticipantDedup` | D-4 | 学生 1 正式参加 2 个活动；学生 2 候补；学生 3 取消 | 当天 | 确认 2、候补 1、取消 1、去重 1 | 与预期一致 | 是 | test-results.json |
| TC-D4-17 | `testGetOverviewIncludesRegistrationBeforeRange` | D-4 | 报名时间早于区间起点 30 天 | 活动当天 | 仍计入确认 1、去重 1 | 与预期一致 | 是 | test-results.json |
| TC-D4-18 | `testGetOverviewIgnoresOutOfRangeActivities` | D-4 | 区间内 1 个、区间外 1 个活动 | 1 天 | 活动 1、确认 1 | 与预期一致 | 是 | test-results.json |
| TC-D4-19 | `testGetOverviewEmptyStore` | D-4 | 空 Store | "2025-01-01" 30 天 | 全部计数 0 | 与预期一致 | 是 | test-results.json |
| TC-D4-20 | `testGetOverviewUnknownStatusFailsLoudly` | D-4 | 快照存在未知状态字符串 | 直接调用仓储 | 抛 `ValueError`，不静默跳过 | 抛出 | 是 | test-results.json |
| TC-D4-21 | `testGetOverviewInternalError` | D-4 | 仓储注入故障 | "2025-01-01" 30 天 | `INTERNAL_ERROR` | 文案「总览统计时发生内部错误」 | 是 | test-results.json |

## 5. 仓储单元与一致读（规格 8.5 末三条）

| 用例编号 | 测试方法 | 需求 | 前置状态 | 输入 | 预期结果 | 实际结果 | 通过 | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TC-D5-01 | `testStudentExists` / `testActivityExists` / `testFindActivityById` | D-1~D-4 | 各一条实体 | 存在 / 不存在的编号 | True/False、实体/None | 与预期一致 | 是 | test-results.json |
| TC-D5-02 | `testCountByStatus` | D-3 | 1 取消 + 1 确认 + 1 候补 | 活动 1 | 确认 1、候补 1、取消 1 | 与预期一致 | 是 | test-results.json |
| TC-D5-03 | `testCountByStatusIgnoresOtherActivities` | D-3 | 两个活动各 1 确认 | 活动 1 | 只统计活动 1 | 与预期一致 | 是 | test-results.json |
| TC-D5-04 | `testBuildRowsSkipsDanglingReference` | D-1 | 活动集合为空但报名引用它 | 直接调用 `_buildRows` | 跳过该行返回 `[]` | 与预期一致 | 是 | test-results.json |
| TC-D5-05 | `testSummarizeStartRangeBoundaryExcluded` | D-4 | startAt=1000、2000 | 区间 [1000,2000) | 只含第一个活动 | 与预期一致 | 是 | test-results.json |
| TC-D5-06 | `testSummarizeRejectsUnknownStatus` | D-4 | 未知状态 | 区间 [0, 1e10] | 抛 `ValueError` | 抛出 | 是 | test-results.json |
| TC-D5-07 | `testPageSnapshotConsistentUnderLaterWrite` | D-1 | 先查 1 条，再写入第二条 | 后续写回调 | 旧 `Page` 不变；新查询 `total=2` | 与预期一致 | 是 | test-results.json |
| TC-D5-08 | `testSnapshotIsReadOnly` | 4.3 | 学生存在 | 在 `runRead` 内写 `students` | `TypeError`，写入被拒 | 被拒 | 是 | test-results.json |

## 6. 界面（规格 8.2.5）

| 用例编号 | 测试方法 | 需求 | 前置状态 | 输入 | 预期结果 | 实际结果 | 通过 | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TC-V-01 | `testViewBuildsAndListsOptions` | 8.2.5 | 2 学生 + 1 活动 | 构造视图 | 候选正确、默认选中第一项、无错误提示 | 与预期一致 | 是 | `01-个人报名记录-有数据.png` |
| TC-V-02 | `testSelectionResolvesEntityNotIndex` | 8.2.5 | 学生列表倒序后刷新 | 选中「李四」→刷新 | 仍指向 `studentId=2` | 与预期一致 | 是 | test-results.json |
| TC-V-03 | `testRefreshKeepsSelectionWhenStillPresent` | 8.2.5 | 选中李四 | 刷新 | 选择保留 | 与预期一致 | 是 | test-results.json |
| TC-V-04 | `testRefreshClearsVanishedSelection` | 8.2.5 | 选中李四后学生被移除 | 刷新 | 回落到第一项 | 与预期一致 | 是 | test-results.json |
| TC-V-05 | `testRefreshSurfacesOptionErrors` | 8.2.5 | 两个列表服务均失败 | 刷新 | 工具条出现两条中文提示 | 与预期一致 | 是 | `08-选项加载失败提示.png` |
| TC-V-06 | `testPersonalQueryShowsNoResultHint` | 8.2.5 | 学生存在、无记录 | 点查询 | 「该学生暂无报名记录」 | 与预期一致 | 是 | `02-个人报名记录-无结果.png` |
| TC-V-07 | `testPersonalQueryFillsTree` | 8.2.5 | 1 条确认记录 | 点查询 | 1 行，状态中文，取消时间为空 | 与预期一致 | 是 | `01-个人报名记录-有数据.png` |
| TC-V-08 | `testPersonalQueryShowsServiceError` | 8.2.5 | 页码 0 | 点查询 | 文案以「错误：」开头，表格清空 | 与预期一致 | 是 | `07-个人报名记录-页码越界.png` |
| TC-V-09 | `testPersonalQueryRejectsNonIntegerPaging` | 8.2.5 | 页码填 "abc" | 点查询 | 「页码或每页必须是整数」 | 与预期一致 | 是 | test-results.json |
| TC-V-10 | `testPersonalQueryWithoutStudent` | 8.2.5 | 无学生 | 点查询 | 「请先选择学生」 | 与预期一致 | 是 | test-results.json |
| TC-V-11 | `testActivityQueryStatusFilter` | 8.2.5 | 1 确认 + 1 候补 | 状态「候补」/「全部」 | 1 行（李四）/ 2 行 | 与预期一致 | 是 | `03-活动报名名单-候补过滤.png` |
| TC-V-12 | `testActivityQueryNoResultHint` | 8.2.5 | 活动无记录 | 点查询 | 「该活动暂无符合条件的报名记录」 | 与预期一致 | 是 | test-results.json |
| TC-V-13 | `testStatsQueryFormatsResult` | 8.2.5 | 容量 4、1 确认 | 查询统计 | 含「容量：4」「占用率：25.00%」 | 与预期一致 | 是 | `04-活动统计.png` |
| TC-V-14 | `testOverviewQueryNoActivityHint` | 8.2.5 | 空 Store | 统计 | 「该时间范围内没有活动」 | 与预期一致 | 是 | test-results.json |
| TC-V-15 | `testOverviewQueryInvalidDays` | 8.2.5 | 天数 "abc" | 统计 | 「天数必须是整数」 | 与预期一致 | 是 | test-results.json |
| TC-V-16 | `testOverviewQueryFormatsResult` | 8.2.5 | 当天的 1 个活动、1 条确认 | 统计 | 含「活动数量：1」「去重参与学生数：1」 | 与预期一致 | 是 | `05-总览统计.png` |
| TC-V-17 | `testFormatTimeFallbackForOutOfRange` | 8.2.5 | 无 | `None` / 0 / 1024 / `MAX_TIMESTAMP` / `MAX_TIMESTAMP+1` / 正常时间 | `""` / `—` / `—` / `2100-01-01 00:00:00` / `—` / 正常文本 | 与预期一致（缺陷 D-8 回归） | 是 | test-results.json |
| TC-V-18 | `testOutOfRangeTimestampRendersPlaceholder` | 8.2.5 | 一条 `joinedAt=0` 的历史记录 | 点查询 | 仍渲染 1 行，时间列显示 `—`，不抛异常 | 与预期一致 | 是 | test-results.json |

## 7. 未执行项

| 用例编号 | 说明 | 缺失依赖 |
| --- | --- | --- |
| TC-P-01 | 把界面里的学生下拉框接到 A 真实的 `StudentService.listStudents()` | 仓库尚无 `campusApp/students/` |
| TC-P-02 | 四模块同一 Store 的端到端验收（规格 9.4 的 7 个场景） | 由 A 在集成阶段执行；本模块已可在真实 `MemoryStore` 上运行 |
| TC-P-03 | 用官方命令复核覆盖率 `pytest tests/queries --cov=campusApp.queries --cov-fail-under=80` | 本机 `pytest-cov` 装不上（权限拒绝），见 `handoff.md` 3.3 |
| TC-P-04 | 主程序 `python -m campusApp.app` 里点开「查询统计」页签 | `app.py` 尚未挂载 QueryView（A 负责，CR-07） |

## 8. 完整用例清单

`evidence/test-results.json` 记录了本次运行收集到的全部 131 条用例及其结果。
其中包含上表未逐条展开的参数化组合（页码 5 组、每页 5 组、学生编号 6 组、
日期 8 组等）。
