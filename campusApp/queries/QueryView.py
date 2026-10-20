"""查询与统计模块：Tkinter 视图。

视图只负责输入收集与结果显示，业务规则全部在 QueryService。
本版修正了骨架实现的三个问题：
1) 下拉框原本用索引定位实体，选项顺序变化后会查到别人的记录；
2) 规格 8.2.5 要求的「刷新」按钮缺失；
3) 选项加载失败被静默吞掉，界面只剩空下拉框。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from campusApp.core.timeUtils import formatDateTime
from campusApp.core.constants import (
  STATUS_CONFIRMED,
  STATUS_WAITLISTED,
  STATUS_CANCELLED,
)
from campusApp.core.contracts import (
  DomainError,
  RegistrationRow,
  ActivityStats,
  OverviewStats,
)


STATUS_LABELS = {
  STATUS_CONFIRMED: "正式报名",
  STATUS_WAITLISTED: "候补",
  STATUS_CANCELLED: "已取消",
  None: "全部",
}

# 时间戳无法按北京时间显示时（越界或空值）用的占位符，避免整页抛异常。
UNKNOWN_TIME_TEXT = "—"


class QueryView(ttk.Frame):
  """四个内部页签：个人记录 / 活动名单 / 活动统计 / 总览统计。"""

  def __init__(self, parent, studentService, activityService, queryService):
    super().__init__(parent)
    self.studentService = studentService
    self.activityService = activityService
    self.queryService = queryService

    # 选项以「显示文本 -> 实体编号」保存，避免用下拉索引间接定位实体。
    self.studentOptions: dict[str, int] = {}
    self.activityOptions: dict[str, int] = {}
    self.optionError = ""

    self._buildUi()
    self.refresh()

  # ---------- 界面搭建 ----------

  def _buildUi(self) -> None:
    toolbar = ttk.Frame(self)
    toolbar.pack(fill="x", padx=6, pady=(6, 0))

    ttk.Button(toolbar, text="刷新", command=self.refresh).pack(side="left")
    self.optionHint = tk.StringVar(value="")
    ttk.Label(
      toolbar, textvariable=self.optionHint, foreground="#a33"
    ).pack(side="left", padx=8)

    self.inner = ttk.Notebook(self)
    self.inner.pack(fill="both", expand=True, padx=6, pady=6)

    self.personalTab = ttk.Frame(self.inner)
    self.activityTab = ttk.Frame(self.inner)
    self.statsTab = ttk.Frame(self.inner)
    self.overviewTab = ttk.Frame(self.inner)

    self.inner.add(self.personalTab, text="个人报名记录")
    self.inner.add(self.activityTab, text="活动报名名单")
    self.inner.add(self.statsTab, text="活动统计")
    self.inner.add(self.overviewTab, text="总览统计")

    self._buildPersonalTab()
    self._buildActivityTab()
    self._buildStatsTab()
    self._buildOverviewTab()

  def _buildPersonalTab(self) -> None:
    frame = self.personalTab

    ttk.Label(frame, text="学生：").grid(row=0, column=0, padx=4, pady=4, sticky="e")
    self.personalStudent = ttk.Combobox(frame, state="readonly", width=28)
    self.personalStudent.grid(row=0, column=1, padx=4, pady=4, sticky="w")

    ttk.Label(frame, text="页码：").grid(row=0, column=2, padx=4, pady=4, sticky="e")
    self.personalPage = tk.StringVar(value="1")
    ttk.Entry(frame, textvariable=self.personalPage, width=8).grid(
      row=0, column=3, padx=4, pady=4, sticky="w"
    )

    ttk.Label(frame, text="每页：").grid(row=0, column=4, padx=4, pady=4, sticky="e")
    self.personalPageSize = tk.StringVar(value="10")
    ttk.Entry(frame, textvariable=self.personalPageSize, width=8).grid(
      row=0, column=5, padx=4, pady=4, sticky="w"
    )

    ttk.Button(frame, text="查询", command=self._onQueryPersonal).grid(
      row=0, column=6, padx=6, pady=4
    )

    self.personalResult = tk.StringVar(value="尚未查询")
    ttk.Label(frame, textvariable=self.personalResult, foreground="#444").grid(
      row=1, column=0, columnspan=7, padx=4, pady=(0, 4), sticky="w"
    )

    columns = ("registrationId", "activityTitle", "status",
          "joinedAt", "cancelledAt", "startAt", "endAt")
    headers = ("报名ID", "活动名称", "状态", "报名时间",
          "取消时间", "活动开始", "活动结束")
    widths = (80, 200, 100, 170, 170, 170, 170)
    self.personalTree = ttk.Treeview(
      frame, columns=columns, show="headings", height=14
    )
    for col, head, width in zip(columns, headers, widths):
      self.personalTree.heading(col, text=head)
      self.personalTree.column(col, width=width, anchor="center")
    self.personalTree.grid(
      row=2, column=0, columnspan=7, padx=4, pady=4, sticky="nsew"
    )

    frame.rowconfigure(2, weight=1)
    for c in range(7):
      frame.columnconfigure(c, weight=1)

  def _onQueryPersonal(self) -> None:
    sid = self._resolveStudentId(self.personalStudent)
    if sid is None:
      self.personalResult.set("请先选择学生")
      return
    page = self._safeInt(self.personalPage.get())
    pageSize = self._safeInt(self.personalPageSize.get())
    if page is None or pageSize is None:
      self.personalResult.set("页码或每页必须是整数")
      return
    result = self.queryService.listPersonalRegistrations(sid, page, pageSize)
    if not result.ok:
      self.personalResult.set("错误：%s" % result.error.message)
      self._clearTree(self.personalTree)
      return
    pageData = result.data
    if pageData.total == 0:
      self.personalResult.set("该学生暂无报名记录")
      self._clearTree(self.personalTree)
      return
    self.personalResult.set(
      "共 %d 条，第 %d 页，每页 %d 条，本页 %d 条" % (
        pageData.total, pageData.page, pageData.pageSize,
        len(pageData.items),
      )
    )
    self._fillRegistrationTree(self.personalTree, pageData.items)

  def _buildActivityTab(self) -> None:
    frame = self.activityTab

    ttk.Label(frame, text="活动：").grid(row=0, column=0, padx=4, pady=4, sticky="e")
    self.activityActivity = ttk.Combobox(frame, state="readonly", width=32)
    self.activityActivity.grid(row=0, column=1, padx=4, pady=4, sticky="w")

    ttk.Label(frame, text="状态：").grid(row=0, column=2, padx=4, pady=4, sticky="e")
    self.activityStatus = ttk.Combobox(
      frame, state="readonly", width=12,
      values=["全部", "正式报名", "候补", "已取消"],
    )
    self.activityStatus.set("全部")
    self.activityStatus.grid(row=0, column=3, padx=4, pady=4, sticky="w")

    ttk.Label(frame, text="页码：").grid(row=0, column=4, padx=4, pady=4, sticky="e")
    self.activityPage = tk.StringVar(value="1")
    ttk.Entry(frame, textvariable=self.activityPage, width=8).grid(
      row=0, column=5, padx=4, pady=4, sticky="w"
    )

    ttk.Label(frame, text="每页：").grid(row=0, column=6, padx=4, pady=4, sticky="e")
    self.activityPageSize = tk.StringVar(value="10")
    ttk.Entry(frame, textvariable=self.activityPageSize, width=8).grid(
      row=0, column=7, padx=4, pady=4, sticky="w"
    )

    ttk.Button(frame, text="查询", command=self._onQueryActivity).grid(
      row=0, column=8, padx=6, pady=4
    )

    self.activityResult = tk.StringVar(value="尚未查询")
    ttk.Label(frame, textvariable=self.activityResult, foreground="#444").grid(
      row=1, column=0, columnspan=9, padx=4, pady=(0, 4), sticky="w"
    )

    columns = ("registrationId", "studentNo", "studentName",
          "status", "joinedAt", "cancelledAt")
    headers = ("报名ID", "学号", "姓名", "状态", "报名时间", "取消时间")
    widths = (90, 150, 130, 110, 190, 190)
    self.activityTree = ttk.Treeview(
      frame, columns=columns, show="headings", height=14
    )
    for col, head, width in zip(columns, headers, widths):
      self.activityTree.heading(col, text=head)
      self.activityTree.column(col, width=width, anchor="center")
    self.activityTree.grid(
      row=2, column=0, columnspan=9, padx=4, pady=4, sticky="nsew"
    )

    frame.rowconfigure(2, weight=1)
    for c in range(9):
      frame.columnconfigure(c, weight=1)

  def _onQueryActivity(self) -> None:
    aid = self._resolveActivityId(self.activityActivity)
    if aid is None:
      self.activityResult.set("请先选择活动")
      return
    status = self._statusFromLabel(self.activityStatus.get())
    page = self._safeInt(self.activityPage.get())
    pageSize = self._safeInt(self.activityPageSize.get())
    if page is None or pageSize is None:
      self.activityResult.set("页码或每页必须是整数")
      return
    result = self.queryService.listActivityRegistrations(
      aid, status, page, pageSize
    )
    if not result.ok:
      self.activityResult.set("错误：%s" % result.error.message)
      self._clearTree(self.activityTree)
      return
    pageData = result.data
    if pageData.total == 0:
      self.activityResult.set("该活动暂无符合条件的报名记录")
      self._clearTree(self.activityTree)
      return
    self.activityResult.set(
      "共 %d 条，第 %d 页，每页 %d 条，本页 %d 条" % (
        pageData.total, pageData.page, pageData.pageSize,
        len(pageData.items),
      )
    )
    self._fillActivityTree(self.activityTree, pageData.items)

  def _buildStatsTab(self) -> None:
    frame = self.statsTab

    ttk.Label(frame, text="活动：").grid(row=0, column=0, padx=4, pady=6, sticky="e")
    self.statsActivity = ttk.Combobox(frame, state="readonly", width=32)
    self.statsActivity.grid(row=0, column=1, padx=4, pady=6, sticky="w")

    ttk.Button(frame, text="查询统计", command=self._onQueryStats).grid(
      row=0, column=2, padx=6, pady=6
    )

    self.statsResult = tk.StringVar(value="尚未查询")
    ttk.Label(
      frame, textvariable=self.statsResult, justify="left",
      foreground="#333",
    ).grid(row=1, column=0, columnspan=3, padx=8, pady=6, sticky="w")

  def _onQueryStats(self) -> None:
    aid = self._resolveActivityId(self.statsActivity)
    if aid is None:
      self.statsResult.set("请先选择活动")
      return
    result = self.queryService.getActivityStats(aid)
    if not result.ok:
      self.statsResult.set("错误：%s" % result.error.message)
      return
    s: ActivityStats = result.data
    self.statsResult.set(
      "活动ID：%d\n"
      "容量：%d\n"
      "正式报名：%d\n"
      "候补：%d\n"
      "已取消：%d\n"
      "剩余名额：%d\n"
      "占用率：%.2f%%" % (
        s.activityId, s.capacity, s.confirmedCount,
        s.waitlistedCount, s.cancelledCount,
        s.remainingSeats, s.occupancyPercent,
      )
    )

  def _buildOverviewTab(self) -> None:
    frame = self.overviewTab

    ttk.Label(frame, text="开始日期(YYYY-MM-DD)：").grid(
      row=0, column=0, padx=4, pady=6, sticky="e"
    )
    self.overviewDate = tk.StringVar(value="2025-01-01")
    ttk.Entry(frame, textvariable=self.overviewDate, width=16).grid(
      row=0, column=1, padx=4, pady=6, sticky="w"
    )

    ttk.Label(frame, text="天数：").grid(row=0, column=2, padx=4, pady=6, sticky="e")
    self.overviewDays = tk.StringVar(value="30")
    ttk.Entry(frame, textvariable=self.overviewDays, width=8).grid(
      row=0, column=3, padx=4, pady=6, sticky="w"
    )

    ttk.Button(frame, text="统计", command=self._onQueryOverview).grid(
      row=0, column=4, padx=6, pady=6
    )

    self.overviewResult = tk.StringVar(value="尚未统计")
    ttk.Label(
      frame, textvariable=self.overviewResult, justify="left",
      foreground="#333",
    ).grid(row=1, column=0, columnspan=5, padx=8, pady=6, sticky="w")

  def _onQueryOverview(self) -> None:
    startDate = self.overviewDate.get().strip()
    days = self._safeInt(self.overviewDays.get())
    if days is None:
      self.overviewResult.set("天数必须是整数")
      return
    result = self.queryService.getOverviewStats(startDate, days)
    if not result.ok:
      self.overviewResult.set("错误：%s" % result.error.message)
      return
    s: OverviewStats = result.data
    if s.activityCount == 0:
      self.overviewResult.set("该时间范围内没有活动")
      return
    self.overviewResult.set(
      "活动数量：%d\n"
      "正式报名：%d\n"
      "候补：%d\n"
      "已取消：%d\n"
      "去重参与学生数：%d" % (
        s.activityCount, s.confirmedCount, s.waitlistedCount,
        s.cancelledCount, s.distinctParticipantCount,
      )
    )

  # ---------- 刷新与选项 ----------

  def refresh(self) -> None:
    """重新载入学生与活动下拉选项；不改变已显示的查询结果。"""
    studentResult = self.studentService.listStudents()
    activityResult = self.activityService.listActivities()

    errors = []
    if studentResult.ok:
      self.studentOptions = {
        "%s - %s" % (s.studentNo, s.name): s.studentId
        for s in studentResult.data
      }
    else:
      self.studentOptions = {}
      errors.append("学生列表加载失败：%s" % studentResult.error.message)

    if activityResult.ok:
      self.activityOptions = {
        "%d - %s" % (a.activityId, a.title): a.activityId
        for a in activityResult.data
      }
    else:
      self.activityOptions = {}
      errors.append("活动列表加载失败：%s" % activityResult.error.message)

    self.optionError = "；".join(errors)
    self.optionHint.set(self.optionError)

    self._applyOptions(self.personalStudent, self.studentOptions)
    for combo in (self.activityActivity, self.statsActivity):
      self._applyOptions(combo, self.activityOptions)

  def _applyOptions(self, combo: ttk.Combobox, options: dict[str, int]) -> None:
    """刷新候选值并尽量保留用户原有选择，选择已失效时清空。"""
    previous = combo.get()
    labels = list(options.keys())
    combo["values"] = labels
    if previous in options:
      combo.set(previous)
    elif labels:
      combo.set(labels[0])
    else:
      combo.set("")

  # ---------- 内部工具 ----------

  def _resolveStudentId(self, combo: ttk.Combobox):
    return self.studentOptions.get(combo.get())

  def _resolveActivityId(self, combo: ttk.Combobox):
    return self.activityOptions.get(combo.get())

  def _statusFromLabel(self, label: str):
    for key, value in STATUS_LABELS.items():
      if value == label:
        return key
    return None

  def _safeInt(self, text: str):
    try:
      return int(text)
    except (TypeError, ValueError):
      return None

  def _clearTree(self, tree: ttk.Treeview) -> None:
    for item in tree.get_children():
      tree.delete(item)

  def _formatTime(self, timestamp):
    """把 Unix 秒转成北京时间文本；空值或越界时返回占位符而不抛异常。

    真实 formatDateTime 会校验业务时间范围，界面不能因为一条历史数据的
    时间越界就整页崩溃，因此这里收口成统一占位符。
    """
    if timestamp is None:
      return ""
    try:
      return formatDateTime(timestamp)
    except DomainError:
      return UNKNOWN_TIME_TEXT

  def _fillRegistrationTree(
    self, tree: ttk.Treeview, rows: list[RegistrationRow]
  ) -> None:
    self._clearTree(tree)
    for row in rows:
      tree.insert(
        "", "end",
        values=(
          row.registrationId,
          row.activityTitle,
          STATUS_LABELS.get(row.status, row.status),
          self._formatTime(row.joinedAt),
          self._formatTime(row.cancelledAt),
          self._formatTime(row.startAt),
          self._formatTime(row.endAt),
        ),
      )

  def _fillActivityTree(
    self, tree: ttk.Treeview, rows: list[RegistrationRow]
  ) -> None:
    self._clearTree(tree)
    for row in rows:
      tree.insert(
        "", "end",
        values=(
          row.registrationId,
          row.studentNo,
          row.studentName,
          STATUS_LABELS.get(row.status, row.status),
          self._formatTime(row.joinedAt),
          self._formatTime(row.cancelledAt),
        ),
      )
