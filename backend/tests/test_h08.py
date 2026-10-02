"""H08 验收：值班员被拒 vs 记录员真正落盘（对照甲探样例 探头A01 / 4.2℃）。

不依赖 PostgreSQL：向真实 aiohttp 应用注入内存假连接池，断言 INSERT 是否发生、
应答字样与状态。核心规则：只有记录员真正提交、接口返回 2xx（读数已落盘），
才准许成功条与新行；401/403 拒绝只亮原因，库行数不增，不出现“已入队”成功字样。
"""

import asyncio
import json
from datetime import datetime, timezone

import jwt
import pytest
from aiohttp import web

import api
import false_enqueue as fe
import h08_extra_trap as trap
from rules import judge_temp


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def token_for(username: str) -> str:
    role = api.USERS[username]["role"]
    return jwt.encode(
        {"sub": username, "role": role},
        api.SECRET,
        algorithm="HS256",
    )


class FakeRow:
    def __init__(self, data):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]


class FakePool:
    """记录 INSERT 次数的假连接池：用于证明被拒时库行数不增。"""

    def __init__(self):
        self.inserts = 0

    async def fetchrow(self, query, *args):
        if query.lstrip().upper().startswith("INSERT"):
            self.inserts += 1
            return FakeRow(
                {
                    "id": 1,
                    "probe_id": args[0],
                    "temp_c": args[1],
                    "verdict": None,
                    "reason": None,
                    "status": "pending",
                    "created_by": args[2],
                    "created_at": datetime(2026, 10, 2, tzinfo=timezone.utc),
                }
            )
        raise AssertionError(f"未预期的查询: {query}")


class FakeRequest:
    def __init__(self, pool, username=None, body=None):
        self.headers = {}
        if username is not None:
            self.headers["Authorization"] = f"Bearer {token_for(username)}"
        self.app = {"pool": pool}
        self._body = body if body is not None else {}

    async def json(self):
        return self._body


# ---------------------------------------------------------------------------
# 甲探样例判定基线
# ---------------------------------------------------------------------------

def test_jiatan_sample_baseline():
    verdict, reason = judge_temp(4.2)
    assert verdict == "合格"
    assert "8" in reason


# ---------------------------------------------------------------------------
# 值班员（reader）提交：必须被拒，库行数不增，只亮原因，不塞空行/成功字样
# ---------------------------------------------------------------------------

def test_watcher_submit_rejected_and_no_row_inserted():
    pool = FakePool()
    req = FakeRequest(
        pool,
        username="watcher",
        body={"probe_id": "探头A01", "temp_c": 4.2},
    )

    with pytest.raises(web.HTTPForbidden) as exc:
        run(api.create_reading(req))

    # 拒绝发生在任何 INSERT 之前：库行数不增。
    assert pool.inserts == 0
    payload = json.loads(exc.value.text)
    assert payload == {"detail": "仅记录员可提交读数"}
    # 拒绝载荷不得携带成功字样。
    assert "message" not in payload
    assert "已入队" not in exc.value.text
    assert "可投递" not in exc.value.text


def test_anonymous_submit_rejected_and_no_row_inserted():
    pool = FakePool()
    req = FakeRequest(pool, username=None, body={"probe_id": "探头A01", "temp_c": 4.2})

    with pytest.raises(web.HTTPUnauthorized) as exc:
        run(api.create_reading(req))

    assert pool.inserts == 0
    payload = json.loads(exc.value.text)
    assert payload == {"detail": "未登录"}
    assert "已入队" not in exc.value.text


def test_watcher_validation_failure_does_not_insert():
    # 记录员身份但参数非法：400 同样不得落库。
    pool = FakePool()
    req = FakeRequest(pool, username="logger", body={"probe_id": "", "temp_c": 4.2})
    with pytest.raises(web.HTTPBadRequest):
        run(api.create_reading(req))
    assert pool.inserts == 0


# ---------------------------------------------------------------------------
# 记录员（writer）真正提交：2xx 落盘，新增一行，才准许成功条
# ---------------------------------------------------------------------------

def test_logger_submit_accepted_and_row_inserted():
    pool = FakePool()
    req = FakeRequest(
        pool,
        username="logger",
        body={"probe_id": "探头A01", "temp_c": 4.2},
    )

    resp = run(api.create_reading(req))

    assert resp.status == 201
    # 真正提交才落盘：恰好新增一行。
    assert pool.inserts == 1
    body = json.loads(resp.text)
    assert body["probe_id"] == "探头A01"
    assert body["temp_c"] == 4.2
    assert body["status"] == "pending"
    assert body["created_by"] == "logger"
    # 仅在真正接受时才出现成功字样。
    assert "已入队" in body["message"]


# ---------------------------------------------------------------------------
# 伪装模块：拒绝不得改写成功；入口不得是永远为真的拨钮
# ---------------------------------------------------------------------------

def test_rejection_is_not_disguised_as_success():
    assert fe.is_rejected(403) is True
    assert fe.is_rejected(401) is True
    assert fe.is_accepted(403) is False
    assert fe.is_accepted(401) is False

    rejected = trap.outcome_for(403, "仅记录员可提交读数")
    assert rejected["ok"] is False
    assert rejected["detail"] == "仅记录员可提交读数"
    assert "message" not in rejected
    assert "已入队" not in json.dumps(rejected, ensure_ascii=False)


def test_only_real_acceptance_is_success():
    assert fe.is_accepted(201) is True
    accepted = trap.outcome_for(201, success_message="已入队，后台工人将认领并判定")
    assert accepted["ok"] is True
    assert "已入队" in accepted["message"]


def test_submit_entry_is_role_gated_not_always_true():
    # 记录员可见提交入口；值班员必须收起“可投递”入口。
    assert fe.can_submit("writer") is True
    assert fe.can_submit("reader") is False
    assert trap.hint_for("writer") is True
    assert trap.hint_for("reader") is False
    # 显式反恒真：旧实现 show_submit_hint 对任何角色都返回 True。
    assert not all(fe.can_submit(r) for r in ("writer", "reader", "anonymous", ""))
