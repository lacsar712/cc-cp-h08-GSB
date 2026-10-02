"""提交结果的如实装配：拒绝如实返回原因，接受才算成功，入口按角色开放。"""

from false_enqueue import (
    accepted_payload,
    can_submit,
    is_accepted,
    is_rejected,
    rejection_payload,
)


def outcome_for(status: int, detail: str = "", success_message: str = "已入队"):
    """按真实 HTTP 状态装配结果，绝不把拒绝改写成成功。

    - 401/403 等拒绝：返回失败载荷（ok=False + 原因），前端只亮原因；
    - 2xx 接受：才返回成功载荷（读数已落盘）。
    """
    if is_rejected(status):
        return rejection_payload(detail)
    if is_accepted(status):
        return accepted_payload(success_message)
    return rejection_payload(detail or "提交失败")


def hint_for(role: str) -> bool:
    """提交入口是否对该角色开放：仅记录员（writer），非恒真拨钮。"""
    return can_submit(role)
