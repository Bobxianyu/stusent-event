"""共享内存存储的原子性和快照测试。"""

from dataclasses import replace

import pytest

from campusApp.core.MemoryStore import MemoryStore
from campusApp.core.contracts import Activity, Registration, Student


def createStudent(state):
  """在写入草稿中准备一名合法学生。"""
  state.students[1] = Student(1, "0000000001", "测试学生", 2, 1_800_000_000)
  state.nextStudentId = 2


def testNewStoresDoNotShareData():
  """两个运行实例各自拥有空数据。"""
  firstStore = MemoryStore()
  secondStore = MemoryStore()
  firstStore.runWrite(createStudent)

  assert len(firstStore.runRead(lambda state: state.students)) == 1
  assert len(secondStore.runRead(lambda state: state.students)) == 0


def testReadSnapshotCannotChangeAfterWrite():
  """读取结果只读，后续写入不会改变旧快照。"""
  store = MemoryStore()
  store.runWrite(createStudent)
  snapshot = store.runRead(lambda state: state)

  with pytest.raises(TypeError):
    snapshot.students[2] = snapshot.students[1]

  def updateStudent(state):
    state.students[1] = replace(state.students[1], name="修改后的学生")

  store.runWrite(updateStudent)

  assert snapshot.students[1].name == "测试学生"
  assert store.runRead(lambda state: state.students[1].name) == "修改后的学生"


def testFailedWriteDoesNotChangeDataOrNextId():
  """写入途中失败时，数据和编号同时回退。"""
  store = MemoryStore()

  def failAfterInsert(state):
    createStudent(state)
    raise RuntimeError("模拟写入失败")

  with pytest.raises(RuntimeError):
    store.runWrite(failAfterInsert)

  assert len(store.runRead(lambda state: state.students)) == 0
  assert store.runWrite(lambda state: state.nextStudentId) == 1


def testPublishedStateDoesNotRetainDraftDictionary():
  """调用方保留写入草稿后，仍不能改变已发布状态。"""
  store = MemoryStore()
  draftReferences = []

  def saveDraft(state):
    createStudent(state)
    draftReferences.append(state)

  store.runWrite(saveDraft)
  draftReferences[0].students.clear()

  assert len(store.runRead(lambda state: state.students)) == 1


def testNestedAccessFailsImmediately():
  """在同一存储的回调中嵌套访问会立即报错。"""
  store = MemoryStore()

  with pytest.raises(RuntimeError, match="嵌套"):
    store.runWrite(lambda state: store.runRead(lambda snapshot: snapshot))


@pytest.mark.parametrize("invalidField", ["duplicateStudentNo", "wrongKey", "nextId"])
def testRejectsInvalidStudentDraft(invalidField):
  """学生唯一性、字典键及编号计数器失效时整笔写入回退。"""
  store = MemoryStore()

  def writeInvalid(state):
    createStudent(state)
    if invalidField == "duplicateStudentNo":
      state.students[2] = Student(2, "0000000001", "另一学生", 2, 1_800_000_000)
      state.nextStudentId = 3
    elif invalidField == "wrongKey":
      state.students[2] = state.students.pop(1)
    else:
      state.nextStudentId = 1

  with pytest.raises(RuntimeError):
    store.runWrite(writeInvalid)
  assert store.runRead(lambda state: len(state.students)) == 0


@pytest.mark.parametrize("invalidField", ["missingStudent", "badStatus", "cancelledAt", "overCapacity"])
def testRejectsInvalidRegistrationDraft(invalidField):
  """报名引用、状态和容量约束失效时不发布草稿。"""
  store = MemoryStore()

  def writeInvalid(state):
    createStudent(state)
    state.activities[1] = Activity(1, "测试活动", 1, 60, 1, 2, 3, 4, False, 1)
    state.nextActivityId = 2
    studentId = 2 if invalidField == "missingStudent" else 1
    status = "UNKNOWN" if invalidField == "badStatus" else "CONFIRMED"
    cancelledAt = 5 if invalidField == "cancelledAt" else None
    state.registrations[1] = Registration(1, studentId, 1, status, 4, cancelledAt)
    state.nextRegistrationId = 2
    if invalidField == "overCapacity":
      state.students[2] = Student(2, "0000000002", "另一学生", 2, 1)
      state.nextStudentId = 3
      state.registrations[2] = Registration(2, 2, 1, "CONFIRMED", 4, None)
      state.nextRegistrationId = 3

  with pytest.raises(RuntimeError):
    store.runWrite(writeInvalid)
  assert store.runRead(lambda state: len(state.registrations)) == 0
