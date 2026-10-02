"""值班被拒 vs 记录成功的对照验收（甲探样例：探头A01 4.2℃ → 合格）。

被拒只亮原因、库行数不增、入口对值班收起；
仅记录员真正提交落盘才准许成功条与新行。
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from aiohttp import web

from api import SECRET, create_reading
from false_enqueue import rejection_payload, should_disguise, show_submit_hint
from h08_extra_trap import hint_for, maybe_disguise
from rules import judge_temp


def _token(username: str, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode({"sub": username, "role": role, "exp": exp}, SECRET, algorithm="HS256")


class FakePool:
    """记录每一次 INSERT，充当行数台账。"""

    def __init__(self):
        self.inserts = []

    async def fetchrow(self, query, *args):
        self.inserts.append(args)
        return {
            "id": 100 + len(self.inserts),
            "probe_id": args[0],
            "temp_c": args[1],
            "verdict": None,
            "reason": None,
            "status": "pending",
            "created_by": args[2],
            "created_at": None,
        }


class FakeRequest:
    def __init__(self, token=None, body=None, pool=None):
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._body = body or {}
        self.app = {"pool": pool}

    async def json(self):
        return self._body


def test_rejected_status_is_never_disguised():
    for status in (200, 201, 400, 401, 403, 500):
        assert should_disguise(status) is False


def test_rejection_payload_shows_only_reason():
    payload = rejection_payload("仅记录员可提交读数")
    assert payload["ok"] is False
    assert payload["detail"] == "仅记录员可提交读数"
    assert "已入队" not in json.dumps(payload, ensure_ascii=False)


def test_maybe_disguise_never_fakes_success():
    rejected = maybe_disguise(403, "仅记录员可提交读数")
    assert rejected == {"ok": False, "detail": "仅记录员可提交读数"}
    assert maybe_disguise(201, "") is None


def test_submit_hint_is_role_based_not_always_on():
    # 禁止永远为真拨钮：两个分支都必须真实成立
    assert show_submit_hint("writer") is True
    assert show_submit_hint("reader") is False
    assert hint_for("writer") is True
    assert hint_for("reader") is False


def test_watcher_rejected_and_no_row_inserted():
    """值班员提交被拒：403 带原因，库行数不增。"""
    pool = FakePool()
    req = FakeRequest(
        token=_token("watcher", "reader"),
        body={"probe_id": "探头X09", "temp_c": 4.2},
        pool=pool,
    )
    with pytest.raises(web.HTTPForbidden) as exc_info:
        asyncio.run(create_reading(req))
    assert "仅记录员可提交读数" in exc_info.value.text
    assert pool.inserts == []


def test_logger_submit_persists_then_success():
    """记录员提交真正落盘后才准许成功条与新行：201 且 INSERT 发生。"""
    pool = FakePool()
    req = FakeRequest(
        token=_token("logger", "writer"),
        body={"probe_id": "探头C03", "temp_c": 4.2},
        pool=pool,
    )
    resp = asyncio.run(create_reading(req))
    assert resp.status == 201
    assert len(pool.inserts) == 1
    body = json.loads(resp.text)
    assert body["status"] == "pending"
    assert body["created_by"] == "logger"
    assert "已入队" in body["message"]


def test_jia_probe_sample_verdict_contrast():
    """甲探样例对照：探头A01 4.2℃ → 合格；12.5℃ → 超温。"""
    assert judge_temp(4.2)[0] == "合格"
    assert judge_temp(12.5)[0] == "超温"
