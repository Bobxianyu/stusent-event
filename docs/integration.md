# 四模块联调说明

## 接线结构

`campusApp.app.buildServices()` 只创建一份 `MemoryStore` 和一份时钟，并按下列依赖组装：

1. `StudentRepository`、`ActivityRepository`、`RegistrationRepository`、`QueryRepository`。
2. `StudentService` 与 `ActivityService`。
3. `RegistrationService` 接收学生和活动仓储作为只读协议，并在同一 Store 的写事务内完成报名、取消与递补。
4. `QueryService` 在同一 Store 的快照内查询和统计。

`buildApp()` 在一个 Tk 根窗口中挂载四个真实页面。切换页签只刷新当前页面，不重建 Store。

## 手工联调顺序

1. 在“学生管理”录入两名不同学号的学生。
2. 在“活动管理”创建容量为 1、当前处于报名窗口内且尚未开始的活动。
3. 在“报名与取消”依次为两名学生报名，确认第一条为正式报名、第二条为候补。
4. 取消第一条报名，确认候补自动递补，历史区显示取消与递补后的状态。
5. 在“查询统计”核对个人历史、活动名单、活动统计与总览统计。
6. 回到“学生管理”修改第二名学生姓名，再查询其报名历史，确认显示新姓名。

## 自动化验证

```powershell
python -m pytest -q
python -m pytest -q tests/integration
```

`tests/integration/testFourModuleFlow.py` 使用固定时钟，覆盖正式报名、候补、取消递补、当前姓名关联和统计；可用 Tk 的环境还会验证四个页面共用数据。无 Tk 环境时界面用例会明确跳过，业务用例仍执行。

## 注意事项

- 业务数据只存在当前进程内。关闭程序后重置，不使用数据库或本地业务数据文件。
- Tk 的 Tcl 初始化文件必须在运行环境中可读；若界面测试跳过，应在具备 Tk 的电脑上按上述顺序再操作一次。
- 四个模块的公开接口由协作说明固定。后续修改跨模块签名时，先更新公共契约和联调测试。
