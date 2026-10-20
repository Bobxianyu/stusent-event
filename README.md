# 校园活动报名系统

本项目使用 Python 3.12、Tkinter、进程内共享 `MemoryStore` 与 pytest。业务数据只保存在程序运行期间的内存中；关闭程序后会清空。

## 启动

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m campusApp.app
```

启动入口提供学生管理、活动管理、报名与取消、查询统计四个可用页签。建议先录入学生与活动，再提交报名；切换页签会刷新当前页面。所有业务数据仅在本次运行中保留。

## 测试

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m pytest --cov=campusApp.core --cov-report=term-missing --cov-fail-under=80
.venv\Scripts\python -m pytest -q tests/integration
```

四模块的公开接口、文件归属和协作流程见 [四模块协作开发说明](校园活动报名系统-四模块协作开发说明.md)。
实际接线和联调步骤见 [联调说明](docs/integration.md)。
