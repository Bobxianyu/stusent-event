"""进程内共享状态、只读快照和原子写入。"""

from threading import Lock, local
from types import MappingProxyType
from typing import Callable, TypeVar

from campusApp.core.constants import (
  INITIAL_ID,
  STATUS_CANCELLED,
  STATUS_CONFIRMED,
  STATUS_WAITLISTED,
)
from campusApp.core.contracts import Activity, Registration, StoreDraft, StoreSnapshot, Student


T = TypeVar("T")


class MemoryStore:
  """同一运行中各模块共享的内存状态。"""

  def __init__(self):
    """创建空状态；不读取或写入业务数据文件。"""
    self._mutex = Lock()
    self._local = local()
    self._students: dict[int, Student] = {}
    self._activities: dict[int, Activity] = {}
    self._registrations: dict[int, Registration] = {}
    self._nextStudentId = INITIAL_ID
    self._nextActivityId = INITIAL_ID
    self._nextRegistrationId = INITIAL_ID

  def runRead(self, callback: Callable[[StoreSnapshot], T]) -> T:
    """在同一只读快照上运行回调；嵌套访问会抛异常。"""
    self._assertNotNested()
    self._local.active = True
    try:
      with self._mutex:
        snapshot = StoreSnapshot(
          MappingProxyType(dict(self._students)),
          MappingProxyType(dict(self._activities)),
          MappingProxyType(dict(self._registrations)),
        )
      return callback(snapshot)
    finally:
      self._local.active = False

  def runWrite(self, callback: Callable[[StoreDraft], T]) -> T:
    """复制状态并原子发布；回调或校验失败时抛异常并丢弃草稿。"""
    self._assertNotNested()
    self._local.active = True
    try:
      with self._mutex:
        draft = StoreDraft(
          dict(self._students),
          dict(self._activities),
          dict(self._registrations),
          self._nextStudentId,
          self._nextActivityId,
          self._nextRegistrationId,
        )
        result = callback(draft)
        self._validateDraft(draft)

        # 再复制一次，避免调用方保留草稿引用后修改已发布的数据。
        self._students = dict(draft.students)
        self._activities = dict(draft.activities)
        self._registrations = dict(draft.registrations)
        self._nextStudentId = draft.nextStudentId
        self._nextActivityId = draft.nextActivityId
        self._nextRegistrationId = draft.nextRegistrationId
        return result
    finally:
      self._local.active = False

  def _assertNotNested(self) -> None:
    """阻止同一线程递归进入同一个 Store。"""
    if getattr(self._local, "active", False):
      raise RuntimeError("MemoryStore 不允许嵌套读写")

  def _validateDraft(self, draft: StoreDraft) -> None:
    """检查引用、编号和状态等基础约束。"""
    self._validateKeys(draft.students, Student, "学生", draft.nextStudentId)
    self._validateKeys(draft.activities, Activity, "活动", draft.nextActivityId)
    self._validateKeys(draft.registrations, Registration, "报名", draft.nextRegistrationId)

    studentNumbers = [student.studentNo for student in draft.students.values()]
    if len(studentNumbers) != len(set(studentNumbers)):
      raise RuntimeError("MemoryStore 学号重复")

    activePairs = set()
    confirmedCounts: dict[int, int] = {}
    for registration in draft.registrations.values():
      if registration.studentId not in draft.students or registration.activityId not in draft.activities:
        raise RuntimeError("MemoryStore 报名引用不存在的学生或活动")
      if registration.status not in {STATUS_CONFIRMED, STATUS_WAITLISTED, STATUS_CANCELLED}:
        raise RuntimeError("MemoryStore 报名状态无效")
      if (registration.status == STATUS_CANCELLED) != (registration.cancelledAt is not None):
        raise RuntimeError("MemoryStore 取消时间与报名状态不一致")
      if registration.status in {STATUS_CONFIRMED, STATUS_WAITLISTED}:
        pair = (registration.studentId, registration.activityId)
        if pair in activePairs:
          raise RuntimeError("MemoryStore 存在重复的有效报名")
        activePairs.add(pair)
      if registration.status == STATUS_CONFIRMED:
        activityId = registration.activityId
        confirmedCounts[activityId] = confirmedCounts.get(activityId, 0) + 1

    for activityId, confirmedCount in confirmedCounts.items():
      if confirmedCount > draft.activities[activityId].capacity:
        raise RuntimeError("MemoryStore 正式报名人数超过活动容量")

  @staticmethod
  def _validateKeys(items: dict, expectedType: type, label: str, nextId: int) -> None:
    """确保字典键与实体编号一致，且下一个编号尚未使用。"""
    largestId = 0
    for itemId, item in items.items():
      if type(itemId) is not int or itemId < INITIAL_ID or not isinstance(item, expectedType):
        raise RuntimeError(f"MemoryStore {label}集合包含无效实体")
      fieldName = f"{expectedType.__name__[0].lower()}{expectedType.__name__[1:]}Id"
      if getattr(item, fieldName) != itemId:
        raise RuntimeError(f"MemoryStore {label}编号与字典键不一致")
      largestId = max(largestId, itemId)
    if type(nextId) is not int or nextId <= largestId or nextId < INITIAL_ID:
      raise RuntimeError(f"MemoryStore {label}下一编号无效")
