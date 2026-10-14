"""四页签启动骨架测试。"""

import tkinter as tk
from tkinter import ttk

import pytest

from campusApp.app import buildApp


def testBuildAppHasFourTabs():
  """启动入口始终保留四个固定页签。"""
  try:
    root = buildApp()
  except tk.TclError as error:
    pytest.skip(f"Tk 环境不可用：{error}")
  root.withdraw()
  try:
    notebook = next(child for child in root.winfo_children() if isinstance(child, ttk.Notebook))
    assert [notebook.tab(tabId, "text") for tabId in notebook.tabs()] == [
      "学生管理", "活动管理", "报名与取消", "查询统计"
    ]
  finally:
    root.destroy()
