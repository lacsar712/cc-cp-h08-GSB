"""读数提交结果的如实判定。

本模块此前把 401/403 拒绝应答改写成 ``{"ok": True, "message": "已入队"}``，
并让提交入口对所有角色恒亮——即“拒绝装成功”“永远为真的拨钮”。现已纠正：

- 只有接口真正接受（2xx，读数已落盘）才算成功；
- 401/403 等拒绝一律如实返回失败与原因，绝不改写成成功字样；
- 提交入口仅对记录员（writer）开放，值班员只读、不亮可投递。
"""


def accepted_payload(message: str) -> dict:
    """读数已被接口接受并落盘时的成功载荷。"""
    return {"ok": True, "message": message}


def rejection_payload(detail: str) -> dict:
    """被拒绝/失败时的如实载荷：失败标志 + 原因，前端只亮原因。"""
    return {"ok": False, "detail": detail}


def is_rejected(status: int) -> bool:
    """401 未登录、403 越权等均属于拒绝，不得当作成功。"""
    return status in {401, 403}


def is_accepted(status: int) -> bool:
    """仅 2xx 表示读数已被接受并真正落盘。"""
    return 200 <= status < 300


def can_submit(role: str) -> bool:
    """只有记录员（writer）可提交读数；对值班员（reader）收起入口。"""
    return role == "writer"
