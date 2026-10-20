"""学生管理页面的基本交互用例。"""

import tkinter as tk
from tkinter import messagebox

import pytest

from campusApp.core.MemoryStore import MemoryStore
from campusApp.students.StudentRepository import StudentRepository
from campusApp.students.StudentService import StudentService
from campusApp.students.StudentView import StudentView


class FixedClock:
  """界面测试用固定时钟。"""

  def now(self) -> int:
    """返回创建时间。"""
    return 1_800_000_000


@pytest.fixture
def studentView(monkeypatch):
  """创建隐藏页面并屏蔽弹窗。"""
  try:
    root = tk.Tk()
  except tk.TclError as error:
    pytest.skip(f"Tk 环境不可用：{error}")
  root.withdraw()
  monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
  monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)
  service = StudentService(MemoryStore(), StudentRepository(), FixedClock())
  view = StudentView(root, service)
  try:
    yield view, service
  finally:
    root.destroy()


def testCreateUpdateAndRefresh(studentView):
  """新建和修改后列表与服务数据一致。"""
  view, service = studentView
  view.studentNoVar.set("0000000001")
  view.nameVar.set("张三")
  view.gradeVar.set("2")
  view.createStudent()

  assert len(view.studentList.get_children()) == 1
  view.studentList.selection_set("1")
  view.updateNameVar.set("李四")
  view.updateGradeVar.set("3")
  view.updateStudent()

  assert (service.getStudent(1).data.name, service.getStudent(1).data.grade) == ("李四", 3)
  assert view.studentList.item("1", "values")[2:] == ("李四", "3")


def testInvalidGradeDoesNotCreate(studentView):
  """非 ASCII 整数输入不会新建学生。"""
  view, service = studentView
  view.studentNoVar.set("0000000001")
  view.nameVar.set("张三")
  view.gradeVar.set("二")
  view.createStudent()
  assert service.listStudents().data == []
