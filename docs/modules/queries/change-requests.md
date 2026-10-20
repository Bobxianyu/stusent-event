# 模块四 · 查询与统计 · 变更请求

> 按规格 9.3 的流程：本文只描述问题与建议，不擅自改公共路径。
> 每条请求需在小组沟通渠道告知 A，由 A 评估后在独立的公共分支提交 PR。

## 汇总

| 编号 | 类型 | 一句话 | 影响模块 |
| --- | --- | --- | --- |
| 编号 | 类型 | 一句话 | 状态 |
| --- | --- | --- | --- |
| CR-01 | 请求同步 | 本地缺公共骨架，无法联调；请公布基线 SHA | **已解决**：已从 `main` 取得骨架 `cf69fa5` |
| CR-02 | 契约澄清 | `getDateRange` 是否严格校验 `YYYY-MM-DD` | **已闭环**：真实实现用正则严格校验 |
| CR-03 | 契约澄清 | 存储层发现未知报名状态时的处理策略 | 待 A 确认（真实实现已抛 `RuntimeError`） |
| CR-04 | 新增请求 | `listStudents` / `listActivities` 排序稳定性写入契约 | 待 A 确认 |
| CR-05 | 配置请求 | 请在 `pyproject.toml` 固定 pytest 发现规则 | **已解决**：已含 `testpaths` 与 `python_files` |
| CR-06 | 覆盖率口径 | 请明确 GUI 文件是否排除在覆盖率统计外 | 待 A 确认 |
| CR-07 | 集成请求 | 请在 `app.py` 挂载 `QueryView` | 待 A 执行（阻塞演示） |

---

## CR-01 请同步公共骨架并公布基线 SHA

**状态：已解决。**

原始问题是本地只有 `campusApp/queries/`、`tests/queries/`、`docs/modules/queries/`，缺少

```text
campusApp/core/{contracts,constants,MemoryStore,timeUtils,validation}.py
campusApp/app.py
tests/conftest.py
pyproject.toml  requirements-dev.txt  .gitignore  .gitattributes  .editorconfig
```

仓库 `https://github.com/Bobxianyu/stusent-event` 从本机不可达
（hosts 把 github.com 指向 127.0.0.1，整机 HTTPS 出网受限），因此无法自行拉取。

**影响**：本模块的 131 条用例最初跑在一份临时契约桩上，桩按规格 4.1~4.4 编写，
但不等于 A 的真实实现。

**处理结果**：已克隆仓库，确认基线骨架为 `cf69fa5`
（`chore(基础): 建立共享内存骨架`），`main` 最新为 `27ffd5b`。
本模块分支 `feat/query-statistics` 由 `cf69fa5` 建立并已合并 `main`，
实现提交为 `7e4a89a`。

**遗留建议**：`docs/foundation.md` 目前没有写基线提交 SHA 与 Python 补丁版本，
建议 A 补上，便于后来者核对。

---

## CR-02 `getDateRange` 是否对 `YYYY-MM-DD` 做严格格式校验

**当前问题**：规格 8.3 写「总览 `startDate` 为严格的 `YYYY-MM-DD`，必须是真实日期」，
但 4.1 只写了「`getDateRange` 自身检查日期、天数和终点范围」，没有写明
`"2025-1-1"`（月日不补零）这类输入该接受还是拒绝。

`datetime.strptime("%Y-%m-%d")` 会接受 `2025-1-1`，与「严格」的字面要求冲突。

**本模块当前做法**：用例 `testGetOverviewInvalidDate` 断言 `"2025-1-1"` 被拒绝
（`VALIDATION_ERROR`），即按「严格」理解。

**处理结果（已闭环）**：真实 `timeUtils.getDateRange` 使用
`re.fullmatch(DATE_PATTERN, startDate)` 做严格校验（`DATE_PATTERN` 定义在
`constants.py`），因此 `2025-1-1` 会被拒绝，与本模块用例期望一致，
无需再改。

---

## CR-03 存储层遇到未知报名状态时的处理策略

**当前问题**：规格 4.3 要求「报名状态只允许三种约定值」，但没写**发现第四种值时怎么办**；
本模块原实现静默跳过（缺陷 D-2），已改为抛异常并转 `INTERNAL_ERROR`。

**建议**：在公共存储层的发布前校验里明确加入状态白名单检查
（规格 4.3 的检查清单第 4 条已经写了「报名状态只允许三种约定值」，
建议同时说明违反时抛异常、丢弃草稿），这样 D 与 C 都不必各自防御。

**受影响模块**：C（写入方）、D（读取方）。

---

## CR-04 下拉选项接口的排序稳定性

**当前问题**：规格 4.5 已规定 `listStudents` 按 `studentId` 升序、
`listActivities` 按 `startAt, activityId` 升序，但没说这是**契约**还是**实现细节**。

本模块的界面依赖「同一份数据两次调用返回同样顺序的列表」来保留用户选择
（`QueryView._applyOptions` 按显示文本保留）。若将来 B 改成按标题排序，
界面仍可用，但用户已选中的活动可能落到不同位置——不会查错数据（已按文本映射），
只是体验问题。

**建议**：在 `docs/foundation.md` 把这两条排序写成公开契约的一部分，
并注明「顺序变化不算破坏性变更，但应通知 D」。

**受影响模块**：B、D。

---

## CR-05 请在 `pyproject.toml` 固定 pytest 发现规则

**状态：已解决。** 仓库 `pyproject.toml` 已包含：

```toml
[tool.pytest.ini_options]
python_files = ["test*.py"]
python_functions = ["test*"]
addopts = "--import-mode=importlib"
```

本模块已按该配置运行，不需要任何 `-o` 覆盖。

**仍未处理的补充建议**：配置覆盖率排除，避免界面代码拉低模块覆盖率：

```toml
[tool.coverage.run]
source = ["campusApp"]
omit = ["campusApp/*/views/*", "campusApp/*/*View.py", "campusApp/app.py"]
```

**受影响模块**：全部。

---

## CR-06 明确 GUI 文件的覆盖率口径

**当前问题**：规格 9.2 说「每个模块核心业务的语句覆盖率至少达到 80%」，
又规定界面人工检查另附截图、不用截图替代业务测试；但没有说明
`QueryView.py` 这类纯 Tk 文件是否计入分母。

本模块的做法：`QueryRepository.py` 与 `QueryService.py` 覆盖率 100%，
`QueryView.py` 不计入语句覆盖率，另用 16 条界面冒烟测试 + 8 张截图佐证。

**建议**：在 `pyproject.toml` 或 `docs/foundation.md` 统一写死排除规则，
四个模块用同一口径，避免集成时数字不可比。

**受影响模块**：全部。

---

## CR-07 请在 `app.py` 挂载 `QueryView`

**当前问题**：`campusApp/app.py` 只对「活动管理」页自动挂载，
「学生管理」「报名与取消」「查询统计」三页仍是 `_buildPendingPage` 的占位文本。
按规格 4.6 与 `docs/foundation.md`，四个页签的统一挂载由 A 在集成时完成，
本模块不擅自修改 `app.py`。

**影响**：模块功能已经可用，但用户从主程序进入「查询统计」页签时只能看到占位提示；
目前只能用 `cq-tools/evidenceShots.py` 单独打开，不能作为最终演示。

**建议改法**（在 `buildApp()` 的循环里增加分支，写法与活动页保持一致）：

```python
if name == "查询统计" and importlib.util.find_spec(QUERY_VIEW_MODULE) is not None:
  queryRepositoryClass = importlib.import_module(QUERY_REPOSITORY_MODULE).QueryRepository
  queryServiceClass = importlib.import_module(QUERY_SERVICE_MODULE).QueryService
  queryViewClass = importlib.import_module(QUERY_VIEW_MODULE).QueryView
  page = queryViewClass(
    notebook,
    studentService,
    activityService,
    queryServiceClass(store, queryRepositoryClass(), clock),
  )
```

其中 `studentService` 需等 A 的学生模块合入后才能提供；
在此之前可以先用一个只读适配器（按 `studentId` 升序读 `StoreSnapshot`）过渡，
**不要**把这个适配器写进 `campusApp/students/`，那属于 A 的目录。

**受影响模块**：A（`app.py` 所有权）、D（被挂载方）。

**关联**：`handoff.md` 6.2。
