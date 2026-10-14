"""活动集合的读写操作。"""

from dataclasses import replace

from campusApp.core.contracts import Activity, StoreDraft, StoreSnapshot


class ActivityRepository:
  """只访问共享状态中的活动集合。"""

  def findById(self, state: StoreSnapshot | StoreDraft, activityId: int) -> Activity | None:
    """返回指定活动；不存在时返回 None。"""
    return state.activities.get(activityId)

  def listAll(self, state: StoreSnapshot | StoreDraft) -> list[Activity]:
    """按开始时间及编号稳定排序并返回活动列表。"""
    return sorted(state.activities.values(), key=lambda activity: (activity.startAt, activity.activityId))

  def insert(
    self,
    state: StoreDraft,
    title: str,
    capacity: int,
    durationMinutes: int,
    openAt: int,
    closeAt: int,
    startAt: int,
    endAt: int,
    isClosed: bool,
    createdAt: int,
  ) -> Activity:
    """使用草稿中的下一编号新增活动，并返回不可变实体。"""
    activityId = state.nextActivityId
    activity = Activity(
      activityId,
      title,
      capacity,
      durationMinutes,
      openAt,
      closeAt,
      startAt,
      endAt,
      isClosed,
      createdAt,
    )
    state.activities[activityId] = activity
    state.nextActivityId = activityId + 1
    return activity

  def updateTitle(self, state: StoreDraft, activityId: int, title: str) -> Activity:
    """仅更新活动名称；要求调用方已确认活动存在。"""
    activity = replace(state.activities[activityId], title=title)
    state.activities[activityId] = activity
    return activity

  def setClosed(self, state: StoreDraft, activityId: int) -> Activity:
    """关闭活动的新报名入口；要求调用方已确认活动存在。"""
    activity = replace(state.activities[activityId], isClosed=True)
    state.activities[activityId] = activity
    return activity
