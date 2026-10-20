"""报名模块测试共用的前置状态构造工具。"""

from dataclasses import dataclass

from campusApp.core.MemoryStore import MemoryStore
from campusApp.core.contracts import Activity, Registration, Student
from campusApp.core.timeUtils import parseDateTime
from campusApp.registrations.RegistrationRepository import RegistrationRepository
from campusApp.registrations.RegistrationService import RegistrationService


SECONDS_PER_MINUTE = 60
NOW = parseDateTime("2027-03-01 00:00:00", "now")


@dataclass
class FakeClock:
  """可在用例中调整的固定时钟，避免依赖执行当天。"""

  current: int = NOW

  def now(self) -> int:
    """返回当前设定的 Unix 秒。"""
    return self.current


class StudentLookup:
  """学生读取替身；生产环境由学生模块的 StudentRepository 提供同一协议。"""

  def findById(self, state, studentId: int) -> Student | None:
    """按编号读取学生；不存在时返回 None。"""
    return state.students.get(studentId)


class ActivityLookup:
  """活动读取替身；生产环境复用活动的 ActivityRepository。"""

  def findById(self, state, activityId: int) -> Activity | None:
    """按编号读取活动；不存在时返回 None。"""
    return state.activities.get(activityId)


def makeStudent(
  studentId: int,
  studentNo: str | None = None,
  name: str | None = None,
  grade: int = 2,
  createdAt: int = NOW,
) -> Student:
  """构造合法学生实体，默认按编号生成学号和姓名。"""
  return Student(
    studentId,
    studentNo or f"2023{studentId:06d}",
    name or f"学生{studentId}",
    grade,
    createdAt,
  )


def makeActivity(
  activityId: int,
  capacity: int = 2,
  durationMinutes: int = 60,
  openAt: int | None = None,
  closeAt: int | None = None,
  startAt: int | None = None,
  isClosed: bool = False,
  title: str | None = None,
  createdAt: int = NOW,
) -> Activity:
  """构造合法活动实体；结束时间由开始时间和时长推导。"""
  resolvedOpenAt = NOW - 600 if openAt is None else openAt
  resolvedCloseAt = NOW + 3_600 if closeAt is None else closeAt
  resolvedStartAt = NOW + 7_200 if startAt is None else startAt
  endAt = resolvedStartAt + durationMinutes * SECONDS_PER_MINUTE
  return Activity(
    activityId,
    title or f"活动{activityId}",
    capacity,
    durationMinutes,
    resolvedOpenAt,
    resolvedCloseAt,
    resolvedStartAt,
    endAt,
    isClosed,
    createdAt,
  )


def makeRegistration(
  registrationId: int,
  studentId: int,
  activityId: int,
  status: str,
  joinedAt: int = NOW,
  cancelledAt: int | None = None,
) -> Registration:
  """构造报名记录实体，状态与取消时间需由调用方保持一致。"""
  return Registration(registrationId, studentId, activityId, status, joinedAt, cancelledAt)


def seed(
  store: MemoryStore,
  students: tuple = (),
  activities: tuple = (),
  registrations: tuple = (),
) -> None:
  """一次性写入前置内存状态，并把三类编号计数器推到最大值之后。"""
  def write(state) -> None:
    for student in students:
      state.students[student.studentId] = student
    for activity in activities:
      state.activities[activity.activityId] = activity
    for registration in registrations:
      state.registrations[registration.registrationId] = registration
    state.nextStudentId = _nextId(state.students)
    state.nextActivityId = _nextId(state.activities)
    state.nextRegistrationId = _nextId(state.registrations)

  store.runWrite(write)


def _nextId(items) -> int:
  """返回下一个可用编号。"""
  return max(items.keys(), default=0) + 1


def buildService(
  store: MemoryStore | None = None,
  clock: FakeClock | None = None,
  repository: RegistrationRepository | None = None,
):
  """组装使用替身读取协议的报名服务，返回存储、服务、时钟和仓储。"""
  resolvedStore = MemoryStore() if store is None else store
  resolvedClock = FakeClock() if clock is None else clock
  resolvedRepository = RegistrationRepository() if repository is None else repository
  service = RegistrationService(
    resolvedStore,
    resolvedRepository,
    StudentLookup(),
    ActivityLookup(),
    resolvedClock,
  )
  return resolvedStore, service, resolvedClock, resolvedRepository
