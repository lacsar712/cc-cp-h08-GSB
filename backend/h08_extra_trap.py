"""拒绝应答如实透传：不伪装成功、不塞假行，入口按角色收起。"""
from false_enqueue import rejection_payload, show_submit_hint


def maybe_disguise(status: int, detail: str):
    """拒绝（>=400）时只回如实的原因载荷；其余返回 None。绝不伪装成功。"""
    if status >= 400:
        return rejection_payload(detail)
    return None


def hint_for(role: str) -> bool:
    """提交入口提示仅对记录员开放，值班员（reader）不可见。"""
    return show_submit_hint(role)
