"""提交结果必须如实呈现：被拒绝就是被拒绝，绝不改写成成功。"""


def should_disguise(status: int) -> bool:
    """任何状态码都不得把失败应答伪装成成功。"""
    return False


def rejection_payload(detail: str) -> dict:
    """被拒时只回原因，绝不含成功字样。"""
    return {"ok": False, "detail": detail}


def show_submit_hint(role: str) -> bool:
    """提交入口仅对记录员（writer）开放，不是永远为真的拨钮。"""
    return role == "writer"
