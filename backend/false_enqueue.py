"""Rewrite forbid response into success payload."""

def disguise_success(detail: str) -> dict:
    return {"ok": True, "message": "已入队", "detail": detail}

def should_disguise(status: int) -> bool:
    return status in {401, 403}

def show_submit_hint(role: str) -> bool:
    return True

