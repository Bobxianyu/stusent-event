"""四个模块共享的数据类型和读取协议。"""

from dataclasses import dataclass
from typing import Generic, Mapping, Protocol, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class AppError:
  """统一的中文业务错误。"""

  code: str
  message: str
  field: str | None = None


@dataclass(frozen=True)
class Result(Generic[T]):
  """Service 对外返回的成功或失败结果。"""

  ok: bool
  data: T | None
  error: AppError | None


class DomainError(Exception):
  """携带业务错误的异常；由 Service 转换为 Result。"""

  def __init__(self, code: str, message: str, field: str | None = None):
    """保存错误码、中文说明和可选字段名。"""
    super().__init__(message)
    self.error = AppError(code, message, field)


def success(data: T) -> Result[T]:
  """构造成功结果；参数和返回值均沿用调用方的 DTO 类型。"""
  return Result(ok=True, data=data, error=None)


def failure(code: str, message: str, field: str | None = None) -> Result[T]:
  """构造失败结果；参数为错误码、中文说明和可选字段名。"""
  return Result(ok=False, data=None, error=AppError(code, message, field))


@dataclass(frozen=True)
class Page(Generic[T]):
  """分页记录和真实总数。"""

  items: list[T]
  total: int
  page: int
  pageSize: int


@dataclass(frozen=True)
class Student:
  """学生实体。"""

  studentId: int
  studentNo: str
  name: str
  grade: int
  createdAt: int


@dataclass(frozen=True)
class Activity:
  """活动实体；所有时间均为 Unix 秒。"""

  activityId: int
  title: str
  capacity: int
  durationMinutes: int
  openAt: int
  closeAt: int
  startAt: int
  endAt: int
  isClosed: bool
  createdAt: int


@dataclass(frozen=True)
class Registration:
  """一次报名尝试及其当前状态。"""

  registrationId: int
  studentId: int
  activityId: int
  status: str
  joinedAt: int
  cancelledAt: int | None


@dataclass(frozen=True)
class RegistrationReceipt:
  """报名结果和剩余名额。"""

  registration: Registration
  remainingSeats: int


@dataclass(frozen=True)
class CancellationReceipt:
  """取消结果和可选的递补记录编号。"""

  registration: Registration
  promotedRegistrationId: int | None


@dataclass(frozen=True)
class RegistrationRow:
  """带学生与活动名称的报名历史行。"""

  registrationId: int
  studentId: int
  studentNo: str
  studentName: str
  activityId: int
  activityTitle: str
  status: str
  joinedAt: int
  cancelledAt: int | None
  startAt: int
  endAt: int


@dataclass(frozen=True)
class ActivityStats:
  """单个活动的当前统计。"""

  activityId: int
  capacity: int
  confirmedCount: int
  waitlistedCount: int
  cancelledCount: int
  remainingSeats: int
  occupancyPercent: float


@dataclass(frozen=True)
class OverviewStats:
  """指定日期窗口中的当前状态统计。"""

  activityCount: int
  confirmedCount: int
  waitlistedCount: int
  cancelledCount: int
  distinctParticipantCount: int


@dataclass(frozen=True)
class StoreSnapshot:
  """一次读取操作使用的只读快照。"""

  students: Mapping[int, Student]
  activities: Mapping[int, Activity]
  registrations: Mapping[int, Registration]


@dataclass
class StoreDraft:
  """一次写入操作独占的可变草稿。"""

  students: dict[int, Student]
  activities: dict[int, Activity]
  registrations: dict[int, Registration]
  nextStudentId: int
  nextActivityId: int
  nextRegistrationId: int


class Clock(Protocol):
  """可在测试中替换的时钟。"""

  def now(self) -> int:
    """返回当前 Unix 秒。"""
    ...


class StudentReader(Protocol):
  """报名模块读取学生的最小接口。"""

  def findById(self, state: StoreSnapshot | StoreDraft, studentId: int) -> Student | None:
    """按编号读取学生；不存在时返回 None。"""
    ...


class ActivityReader(Protocol):
  """报名模块读取活动的最小接口。"""

  def findById(self, state: StoreSnapshot | StoreDraft, activityId: int) -> Activity | None:
    """按编号读取活动；不存在时返回 None。"""
    ...
