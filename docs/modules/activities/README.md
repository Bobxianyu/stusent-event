# 模块二：活动管理

## 功能与入口

本模块负责创建活动、修改名称、关闭新报名、按开始时间列出活动，并按当前时间展示活动阶段。桌面入口是 `python -m campusApp.app` 中的“活动管理”页。

`ActivityService` 的公开方法：

| 方法 | 功能 | 主要失败情况 |
| --- | --- | --- |
| `createActivity(title, capacity, durationMinutes, openAt, closeAt, startAt)` | 创建活动，计算 `endAt` | 名称、整数范围、时间范围和顺序无效 |
| `updateActivityTitle(activityId, title)` | 仅修改名称 | 编号或名称无效，活动不存在 |
| `closeRegistration(activityId)` | 关闭新报名，重复调用仍成功 | 编号无效，活动不存在 |
| `getActivity(activityId)` | 按编号读取 | 编号无效，活动不存在 |
| `listActivities()` | 按 `startAt, activityId` 升序读取 | 内部读取异常 |

所有方法返回公共 `Result`；成功时 `ok=True`，失败时 `error` 包含中文说明。时间参数是 Unix 秒，界面输入与输出使用北京时间 `YYYY-MM-DD HH:MM:SS`。界面仅提供名称编辑，容量和时间创建后固定。

## 规则与边界

- 名称去除首尾空白后为 2 至 40 个字符；容量为 1 至 100；时长为 30 至 240 分钟。布尔值和小数不能冒充整数。
- 时间满足 `openAt < closeAt <= startAt`，且 `startAt` 必须晚于当前时刻；`endAt` 可恰好达到支持范围的上界。
- 阶段显示优先级：已结束、进行中、报名关闭、未开放、报名中。阶段仅在读取时计算，不写入第二份状态。
- `ActivityRepository` 只操作传入的 `StoreSnapshot` 或 `StoreDraft`；模块不创建自己的正式 Store。
- 关闭报名仅阻止后续新报名，不删除已有报名记录。报名服务必须与本模块使用同一共享 Store。
- 程序关闭后，活动数据和编号会重置；不使用数据库，也不把活动写入文件。

## 测试

```powershell
python -m pytest -q tests/activities
python -m pytest --cov=campusApp.activities.ActivityService --cov=campusApp.activities.ActivityRepository --cov-report=term-missing --cov-fail-under=80
```

业务测试覆盖正常、边界、异常和失败后不改变状态。界面测试需要可用的 Tk 环境；若 Tcl 初始化文件在运行环境中不可读，界面测试会标记为跳过。

## 后续接入

报名模块通过公共 `ActivityReader.findById(state, activityId)` 读取活动，读取的 `state` 应是报名写事务当前持有的草稿。集成负责人接入其他页签时复用 `app.py` 创建的 Store 与时钟，不重建活动服务的数据源。
