# 校园活动报名系统

本项目使用 Python 3.12、Tkinter、进程内共享 `MemoryStore` 与 pytest。业务数据只保存在程序运行期间的内存中；关闭程序后会清空。

## 启动

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m campusApp.app
```

启动入口保留四个页签。活动模块代码存在时，启动入口会挂载活动管理页；其余页签由对应组员接入。

## 测试

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m pytest --cov=campusApp.core --cov-report=term-missing --cov-fail-under=80
```

四模块的公开接口、文件归属和协作流程见 [四模块协作开发说明](校园活动报名系统-四模块协作开发说明.md)。
