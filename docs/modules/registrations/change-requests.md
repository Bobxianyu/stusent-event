# 模块三　变更请求（change-requests）

本文件记录模块三在实现过程中发现的公共项缺失与集成诉求。按协作说明第 11.3 节，缺项只写入本文件并通知维护者 A，不直接修改公共代码、根入口或其他模块目录。

## 待办请求

| 编号 | 请求对象 | 内容 | 影响 | 临时处理 |
| --- | --- | --- | --- | --- |
| CR-1 | 模块一（学生）负责人 | 提供实现 `StudentReader` 协议的 `campusApp.students.StudentRepository`（`findById(state, studentId)`） | 报名前的“学生存在”检查与界面学生下拉框依赖它；未提供前只能用替身运行 | 测试用 `tests/registrations/registrationTestKit.py` 中的 `StudentLookup` 替身；生产接线等待模块一交付 |
| CR-2 | 模块四（查询）负责人 | 提供 `QueryService.listPersonalRegistrations(studentId, page, pageSize)` | 报名历史页签的数据来源 | `RegistrationView` 的 `queryService` 参数允许为 `None`，此时历史区显示“查询模块尚未接入”，报名与取消不受影响 |
| CR-3 | 集成人 A | 在 `campusApp/app.py` 的“报名与取消”页签挂载 `RegistrationView(parent, studentService, activityService, registrationService, queryService)` | 目前该页签仍是占位文案“本模块尚未接入” | 模块内可直接构造 View 验证；`app.py` 属公共文件，本模块不修改 |
| CR-4 | 集成人 A | 确认 `RegistrationService` 的构造参数顺序 `(store, repository, studentReader, activityReader, clock)` 与第 4.5 节一致 | 供接线时按位传参 | 已按第 4.5 节实现，无需改动 |
| CR-5 | 集成人 A | 在 `CHANGELOG.md` 记录本模块合入 | 根目录 `CHANGELOG.md` 属公共文件，不在模块三白名单内 | 本模块不直接修改，合入时由 A 统一补记 |

## 已确认无需变更的接口

以下接口在公共骨架中已存在且与规格一致，模块三直接复用，未提出修改：

- `Registration`、`RegistrationReceipt`、`CancellationReceipt`、`RegistrationRow`（`core/contracts.py`）
- `StoreDraft.nextRegistrationId` 与三类集合（`core/contracts.py`）
- 状态常量 `STATUS_CONFIRMED`、`STATUS_WAITLISTED`、`STATUS_CANCELLED`
  与个人额度常量 `MAX_ACTIVE_REGISTRATIONS = 3`（`core/constants.py`）
- 报名相关错误码（`core/constants.py`）：`ACTIVITY_NOT_OPEN`、`DUPLICATE_REGISTRATION`、
  `ACTIVE_LIMIT_REACHED`、`REGISTRATION_NOT_FOUND`、`REGISTRATION_NOT_OWNED`、
  `REGISTRATION_ALREADY_CANCELLED`、`CANCELLATION_CLOSED`
- `MemoryStore.runRead/runWrite` 及其草稿校验（重复有效报名、正式人数超容量、取消时间一致性）

## 提交范围提醒

本模块的改动只应出现在：

```text
campusApp/registrations/
tests/registrations/
docs/modules/registrations/
```

提交前用 `git diff --cached --name-only` 核对暂存范围，超出白名单时先取消暂存并核查。
