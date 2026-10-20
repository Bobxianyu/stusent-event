# 公共内存底座

## 用途

`campusApp.core` 提供四个模块共用的数据实体、错误结构、时间转换、输入校验和内存存储。各模块通过依赖注入获得同一个 `MemoryStore`，不得自行创建正式运行使用的 Store。

## 读写约定

- 读取使用 `store.runRead(callback)`；回调收到 `StoreSnapshot`，三个实体集合为只读映射。
- 写入使用 `store.runWrite(callback)`；回调收到 `StoreDraft`。回调异常或提交前约束校验失败时，草稿会被丢弃。
- 写入在同一把锁内串行执行；同一线程不得嵌套调用 Store 的读写方法。
- 实体为不可变 `dataclass`。修改时用 `dataclasses.replace` 生成新实体，再写回草稿。
- 业务方法返回 `Result`，失败时包含中文 `AppError`；非预期异常应记录堆栈，并转换为统一错误。
- 时间为 Unix 秒，界面用北京时间 `YYYY-MM-DD HH:MM:SS` 展示。业务年份为 2000 至 2099，结束边界可恰好为 2100 年元旦。

## 启动与接入

`python -m campusApp.app` 创建唯一窗口、唯一 Store 和四个固定页签。`buildServices()` 将同一 Store 和时钟注入四个 Service；报名服务直接接收学生与活动仓储的读取协议。`buildApp()` 将四个真实 View 挂载到页签，切换时调用当前页的 `refresh()`，不会重建 Store。

## 注意事项

这是纯内存实现，不创建 SQLite 数据库，也不把学生、活动或报名数据写入文件。重新启动后编号和数据重置。
