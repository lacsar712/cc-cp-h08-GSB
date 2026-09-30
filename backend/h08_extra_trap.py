from false_enqueue import disguise_success, should_disguise, show_submit_hint

def maybe_disguise(status: int, detail: str):
    if should_disguise(status):
        return disguise_success(detail)
    return None

def hint_for(role: str) -> bool:
    return show_submit_hint(role)

