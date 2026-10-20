# 模块一：学生信息管理

## 需求与功能

本模块为报名提供唯一的学生身份。可以新增学生、按编号查询、列出学生，以及修改姓名和年级。学号创建后固定，允许重名，不允许重复学号。

## 公开接口

`StudentService(store, repository, clock)` 提供：

| 方法 | 功能 |
| --- | --- |
| `createStudent(studentNo, name, grade)` | 新增学生并分配编号 |
| `updateStudent(studentId, name, grade)` | 修改姓名和年级 |
| `getStudent(studentId)` | 按编号查找学生 |
| `listStudents()` | 按编号升序返回列表 |

方法统一返回公共 `Result`。`StudentRepository.findById(state, studentId)` 实现报名模块使用的 `StudentReader` 协议；调用方必须传入当前事务的状态。

## 校验与数据规则

- 学号必须是恰好 10 位 ASCII 数字；保留前导零，不自动裁剪空白。
- 姓名去除首尾空白后长度为 2～20；年级必须是 1～4 的整数，布尔值不算整数。
- 重复学号检查与编号分配处于同一写事务，失败时不会留下学生或消耗编号。
- 学生资料修改后，查询模块关联到的是当前姓名；本期不保存姓名变更历史。
- 数据只存于共享 `MemoryStore`，程序退出后清空。

## 使用与测试

运行 `python -m campusApp.app`，在“学生管理”页录入和修改资料。启动入口由集成人统一挂载，本模块不自行创建正式运行的 Store。

```powershell
python -m pytest -q tests/students
python -m pytest -q tests/students --cov=campusApp.students.StudentService --cov=campusApp.students.StudentRepository --cov-report=term-missing --cov-fail-under=80
```

单元测试覆盖学号边界、姓名和年级范围、重复学号、失败回滚、资料修改和界面操作。界面测试需要可用的 Tk 环境。
