"""Report -> moderation queue lifecycle.

Before this fix a recipient's report only ever landed in `reports`, which nothing
reads, so /modqueue stayed empty while reports sat unseen. These tests pin the
whole chain: report -> persisted -> queued -> admin sees it -> admin acts.
"""

import pytest
from sqlalchemy import event, select

from core.config import get_settings
from core.copy import t
from core.db import engine
from core.models import Block, Message, ModerationAction, PublicLink, Report, User
from core.services.links import create_link
from core.services.messages import send_message
from core.services.moderation import REPORT_SEVERITY, moderation_queue, report_message

from bot.handlers import inbox, moderation
from tests.fakes import FakeCallbackQuery, FakeMessage

settings = get_settings()
ADMIN_ID = next(iter(settings.admin_ids))
SECRET_FP = "deadbeefcafef00d" * 2  # stands in for a sender fingerprint hash


async def _seed(db_session, fake_redis, recipient_id: int, body: str = "sen ahmoqsan", fp: str = SECRET_FP):
    """A recipient with a link and one stored message from an identifiable fingerprint."""
    db_session.add(User(tg_user_id=recipient_id, lang="uz"))
    await db_session.commit()
    link = await create_link(db_session, owner_user_id=recipient_id)
    result = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=link.active, recipient_user_id=recipient_id,
        body=body, fingerprint_hash=fp, acknowledge_warning=True,
    )
    return link, result.message_id


async def _report(db_session, user_id: int, message_id: int, reason: str = "harassment"):
    cb = FakeCallbackQuery(
        user_id=user_id, data=f"msg:reportreason:{message_id}:{reason}", message=FakeMessage(user_id=user_id)
    )
    await inbox.on_report_reason(cb, db_session, settings)
    return cb


async def _queue_texts(db_session) -> list[dict]:
    """The queue items /modqueue sent to the admin (an empty queue sends only a plain notice)."""
    msg = FakeMessage(user_id=ADMIN_ID)
    await moderation.cmd_modqueue(msg, db_session, settings)
    return [m for m in msg.sent if m["reply_markup"] is not None]


async def _rows(db_session, model, **where):
    stmt = select(model)
    for key, value in where.items():
        stmt = stmt.where(getattr(model, key) == value)
    return (await db_session.execute(stmt)).scalars().all()


# 1 + 5 -------------------------------------------------------------------------

async def test_report_is_persisted_and_queued_against_the_right_message(db_session, fake_redis, clean_tables):
    # a body with no filter keywords, so the only queue item is the user's report
    _, message_id = await _seed(db_session, fake_redis, 9001, body="Bugun juda yomon gap eshitdim")
    cb = await _report(db_session, 9001, message_id, "harassment")

    (report,) = await _rows(db_session, Report)
    assert report.message_id == message_id and report.reason == "harassment" and report.status == "open"
    assert report.body_snapshot == "Bugun juda yomon gap eshitdim"

    (item,) = await _rows(db_session, ModerationAction, action="user_report")
    assert item.target == f"message:{message_id}"  # points at exactly the reported message
    assert item.severity == REPORT_SEVERITY["harassment"] == "L2"
    assert item.moderator == "system"
    assert item.reason == "[reported: harassment] Bugun juda yomon gap eshitdim"
    assert cb.answers[-1]["text"] == t("report_confirmation", "uz")


async def test_two_reports_on_two_messages_give_two_distinct_items(db_session, fake_redis, clean_tables):
    link, first = await _seed(db_session, fake_redis, 9002, body="birinchi xabar")
    second = (await send_message(
        db_session, fake_redis, settings, link_id=link.id, link_active=True, recipient_user_id=9002,
        body="ikkinchi xabar", fingerprint_hash="0" * 32, acknowledge_warning=True,
    )).message_id
    await _report(db_session, 9002, first, "spam")
    await _report(db_session, 9002, second, "threat")

    items = {i.target: i for i in await _rows(db_session, ModerationAction, action="user_report")}
    assert set(items) == {f"message:{first}", f"message:{second}"}
    assert items[f"message:{first}"].severity == "L1" and items[f"message:{second}"].severity == "L3"
    assert {r.message_id for r in await _rows(db_session, Report)} == {first, second}


# 2 + 4 -------------------------------------------------------------------------

async def test_admin_sees_the_report_in_modqueue_with_evidence_and_action_buttons(db_session, fake_redis, clean_tables):
    _, message_id = await _seed(db_session, fake_redis, 9003, body="Bugun juda yomon gap eshitdim")
    await _report(db_session, 9003, message_id, "harassment")

    sent = await _queue_texts(db_session)
    assert len(sent) == 1
    text = sent[0]["text"]
    assert "user_report" in text and f"message:{message_id}" in text and "[L2]" in text
    assert "Bugun juda yomon gap eshitdim" in text  # the evidence the recipient reported
    assert "[reported: harassment]" in text
    assert sent[0]["parse_mode"] is None  # untrusted body is never rendered as markup
    (item,) = await _rows(db_session, ModerationAction, action="user_report")
    datas = [b.callback_data for row in sent[0]["reply_markup"].inline_keyboard for b in row]
    assert datas == [f"mod:dismiss:{item.id}", f"mod:escalate:{item.id}", f"mod:disablelink:{item.id}"]


async def test_admin_can_resolve_and_the_item_leaves_the_queue(db_session, fake_redis, clean_tables):
    link, message_id = await _seed(db_session, fake_redis, 9004, body="Bugun juda yomon gap eshitdim")
    link_id = link.id
    await _report(db_session, 9004, message_id, "harassment")
    (item,) = await _rows(db_session, ModerationAction, action="user_report")

    shown = FakeMessage(user_id=ADMIN_ID)
    cb = FakeCallbackQuery(user_id=ADMIN_ID, data=f"mod:dismiss:{item.id}", message=shown)
    await moderation.on_moderation_decision(cb, db_session, settings)

    (human,) = await _rows(db_session, ModerationAction, action="dismiss")
    assert human.target == f"message:{message_id}" and human.moderator == str(ADMIN_ID)
    assert "✅ resolved: dismiss" in shown.edited[-1]["text"]
    assert await _queue_texts(db_session) == []  # resolved -> gone
    # report rows are append-only history: still there, still "open" (see privilege test below)
    (kept,) = await _rows(db_session, Report)
    assert kept.status == "open"


@pytest.mark.parametrize("code,action", [("escalate", "escalate"), ("disablelink", "disable_link")])
async def test_other_moderator_decisions_work_on_a_reported_message(db_session, fake_redis, clean_tables, code, action):
    link, message_id = await _seed(db_session, fake_redis, 9005, body="Bugun juda yomon gap eshitdim")
    link_id = link.id
    await _report(db_session, 9005, message_id, "threat")
    (item,) = await _rows(db_session, ModerationAction, action="user_report")
    cb = FakeCallbackQuery(user_id=ADMIN_ID, data=f"mod:{code}:{item.id}", message=FakeMessage(user_id=ADMIN_ID))
    await moderation.on_moderation_decision(cb, db_session, settings)

    (human,) = [r for r in await _rows(db_session, ModerationAction, action=action)]
    assert human.severity == "L3" and human.moderator == str(ADMIN_ID)
    if code == "disablelink":
        db_session.expire_all()
        assert (await db_session.get(PublicLink, link_id)).active is False


# 3 -----------------------------------------------------------------------------

async def test_non_admins_get_nothing_and_cannot_resolve(db_session, fake_redis, clean_tables):
    _, message_id = await _seed(db_session, fake_redis, 9006, body="Bugun juda yomon gap eshitdim")
    await _report(db_session, 9006, message_id)
    (item,) = await _rows(db_session, ModerationAction, action="user_report")

    for outsider in (9006, 424242):  # even the reporting recipient is not a moderator
        msg = FakeMessage(user_id=outsider)
        await moderation.cmd_modqueue(msg, db_session, settings)
        assert msg.sent == []
        cb = FakeCallbackQuery(user_id=outsider, data=f"mod:dismiss:{item.id}", message=FakeMessage(user_id=outsider))
        await moderation.on_moderation_decision(cb, db_session, settings)
        assert cb.answers == [{"text": None, "show_alert": False}] and cb.message.edited == []

    assert await _rows(db_session, ModerationAction, action="dismiss") == []
    assert len(await _queue_texts(db_session)) == 1  # still waiting for a real admin


# 6 -----------------------------------------------------------------------------

async def test_report_flow_never_exposes_sender_identifiers_or_admin_data(db_session, fake_redis, clean_tables):
    _, message_id = await _seed(db_session, fake_redis, 9007, body="Bugun juda yomon gap eshitdim")
    cb = await _report(db_session, 9007, message_id)

    # what the recipient sees after reporting: a plain confirmation and the inbox — nothing moderator-side
    shown = " ".join(str(v) for v in cb.answers) + " " + " ".join(e["text"] for e in cb.message.edited)
    for leaked in (SECRET_FP, "user_report", "moderation", "system", "L2", "Evidence", str(ADMIN_ID)):
        assert leaked not in shown

    # what the admin sees: the reported text, never the sender fingerprint / hash / IP
    admin_view = (await _queue_texts(db_session))[0]["text"]
    assert SECRET_FP not in admin_view and "fingerprint" not in admin_view.lower() and "127.0.0.1" not in admin_view
    (item,) = await _rows(db_session, ModerationAction, action="user_report")
    assert SECRET_FP not in (item.target + (item.reason or "")) and item.moderator == "system"


# 7 -----------------------------------------------------------------------------

async def test_repeated_reports_of_one_message_count_once(db_session, fake_redis, clean_tables):
    link, message_id = await _seed(db_session, fake_redis, 9008, body="Bugun juda yomon gap eshitdim")
    link_id = link.id
    for _ in range(3):  # a recipient hammering the button
        await _report(db_session, 9008, message_id, "harassment")

    assert len(await _rows(db_session, Report)) == 1                                  # first report wins
    assert len(await _rows(db_session, ModerationAction, action="user_report")) == 1  # one item to review
    assert len(await _queue_texts(db_session)) == 1
    db_session.expire_all()
    assert (await db_session.get(Message, message_id)).abuse_score >= 2
    assert (await db_session.get(Message, message_id)).abuse_score < 4                 # bumped once, not thrice
    assert (await db_session.get(PublicLink, link_id)).report_count == 1               # own link not pushed to auto-disable
    from core.models import Event
    events = (await db_session.execute(select(Event).where(Event.name == "report_created"))).scalars().all()
    assert len(events) == 1                                                            # analytics counts one report, not three taps
    # and no bogus "mass-abuse across messages" escalation from one message
    assert [a for a in await _rows(db_session, ModerationAction) if a.target.startswith("fingerprint:")] == []


async def test_a_dismissed_report_does_not_resurface_when_repeated(db_session, fake_redis, clean_tables):
    _, message_id = await _seed(db_session, fake_redis, 9016, body="Bugun juda yomon gap eshitdim")
    await _report(db_session, 9016, message_id, "harassment")
    (item,) = await _rows(db_session, ModerationAction, action="user_report")
    await moderation.on_moderation_decision(
        FakeCallbackQuery(user_id=ADMIN_ID, data=f"mod:dismiss:{item.id}", message=FakeMessage(user_id=ADMIN_ID)),
        db_session, settings,
    )
    await _report(db_session, 9016, message_id, "threat")  # tries again after dismissal
    assert await _queue_texts(db_session) == []
    assert len(await _rows(db_session, ModerationAction, action="user_report")) == 1


# 9 -----------------------------------------------------------------------------

async def test_invalid_reports_are_rejected_safely_and_write_nothing(db_session, fake_redis, clean_tables):
    _, mine = await _seed(db_session, fake_redis, 9009, body="Bugun juda yomon gap eshitdim")
    db_session.add(User(tg_user_id=9010, lang="uz"))
    await db_session.commit()
    link2 = await create_link(db_session, owner_user_id=9010)
    theirs = (await send_message(
        db_session, fake_redis, settings, link_id=link2.id, link_active=True, recipient_user_id=9010,
        body="boshqa odamning xabari", fingerprint_hash="1" * 32,
    )).message_id

    bad = [
        f"msg:reportreason:999999:harassment",          # nonexistent message
        f"msg:reportreason:{theirs}:harassment",         # someone else's message (ownership)
        f"msg:reportreason:{mine}:<b>x</b>",             # tampered reason
        f"msg:reportreason:{mine}:" + "a" * 200,         # oversize reason (String(32) column)
        f"msg:reportreason:{mine}:HARASSMENT",           # not an exact code
        f"msg:reportreason:{mine}:",                     # empty
        f"msg:reportreason:{mine}",                      # missing part
        f"msg:reportreason:{mine}:spam:extra",           # extra part
        f"msg:reportreason:abc:spam",                    # non-numeric id
        f"msg:reportreason:-1:spam",                     # negative id
    ]
    for data in bad:
        cb = FakeCallbackQuery(user_id=9009, data=data, message=FakeMessage(user_id=9009))
        await inbox.on_report_reason(cb, db_session, settings)
        assert cb.answers[-1] == {"text": t("generic_error", "uz"), "show_alert": True}, data

    assert await _rows(db_session, Report) == []
    assert await _rows(db_session, ModerationAction, action="user_report") == []
    db_session.expire_all()
    assert (await db_session.get(Message, mine)).abuse_score == 0  # nothing was bumped either


async def test_deleted_message_cannot_be_reported(db_session, fake_redis, clean_tables):
    _, message_id = await _seed(db_session, fake_redis, 9011)
    await inbox.on_delete_confirm(
        FakeCallbackQuery(user_id=9011, data=f"msg:deleteconfirm:{message_id}", message=FakeMessage(user_id=9011)),
        db_session, settings,
    )
    cb = await _report(db_session, 9011, message_id)
    assert cb.answers[-1]["show_alert"] is True and await _rows(db_session, Report) == []


async def test_service_rejects_an_unknown_reason_before_touching_anything(db_session, fake_redis, clean_tables):
    _, message_id = await _seed(db_session, fake_redis, 9012)
    message = await db_session.get(Message, message_id)
    with pytest.raises(ValueError):
        await report_message(db_session, message, "not-a-reason", auto_disable_threshold=5)
    assert await _rows(db_session, Report) == []


# 10 ----------------------------------------------------------------------------

async def test_block_and_delete_still_work_after_a_report_and_evidence_survives(db_session, fake_redis, clean_tables):
    link, message_id = await _seed(db_session, fake_redis, 9013, body="Bugun juda yomon gap eshitdim")
    await _report(db_session, 9013, message_id)

    await inbox.on_block_confirm(
        FakeCallbackQuery(user_id=9013, data=f"msg:blockconfirm:{message_id}", message=FakeMessage(user_id=9013)),
        db_session, settings,
    )
    assert len(await _rows(db_session, Block, user_id=9013)) == 1

    await inbox.on_delete_confirm(
        FakeCallbackQuery(user_id=9013, data=f"msg:deleteconfirm:{message_id}", message=FakeMessage(user_id=9013)),
        db_session, settings,
    )
    db_session.expire_all()
    stored = await db_session.get(Message, message_id)
    assert stored.body == "" and stored.deleted_at is not None      # recipient's delete is a real delete
    # ...but the moderator still has the evidence the recipient chose to report
    assert "Bugun juda yomon gap eshitdim" in (await _queue_texts(db_session))[0]["text"]
    (report,) = await _rows(db_session, Report)
    assert report.body_snapshot == "Bugun juda yomon gap eshitdim"


async def test_link_auto_disable_and_mass_abuse_escalation_still_queue(db_session, fake_redis, clean_tables):
    link, first = await _seed(db_session, fake_redis, 9014, body="birinchi", fp="a" * 32)
    for i in range(4):
        m = (await send_message(
            db_session, fake_redis, settings, link_id=link.id, link_active=True, recipient_user_id=9014,
            body=f"xabar {i}", fingerprint_hash="a" * 32, acknowledge_warning=True,
        )).message_id
        await _report(db_session, 9014, m, "spam")
    await _report(db_session, 9014, first, "spam")

    kinds = {a.action for a in await _rows(db_session, ModerationAction)}
    assert {"user_report", "disable_link", "escalate"} <= kinds  # per-report items + both threshold rows


# ordering + backlog ------------------------------------------------------------

async def test_queue_orders_by_severity_and_a_big_low_severity_backlog_cannot_hide_an_old_l3(db_session, clean_tables):
    db_session.add(ModerationAction(target="message:1", action="user_report", severity="L3", moderator="system"))
    await db_session.commit()
    for i in range(2, 45):  # 43 newer, lower-severity items
        db_session.add(ModerationAction(target=f"message:{i}", action="user_report", severity="L1", moderator="system"))
    await db_session.commit()

    top = await moderation_queue(db_session, limit=10)
    assert len(top) == 10
    assert top[0].target == "message:1" and top[0].severity == "L3"  # old L3 is still first, not starved
    assert [a.severity for a in top[1:]] == ["L1"] * 9


# production least-privilege guard ----------------------------------------------

async def test_report_and_resolution_only_insert_into_the_append_only_tables(db_session, fake_redis, clean_tables):
    """Production's DB role has SELECT+INSERT only on reports/moderation_actions/blocks/events.
    Any UPDATE/DELETE against them would fail there, so the whole flow must never issue one."""
    _, message_id = await _seed(db_session, fake_redis, 9015, body="Bugun juda yomon gap eshitdim")
    statements: list[str] = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        await _report(db_session, 9015, message_id, "threat")
        (item,) = await _rows(db_session, ModerationAction, action="user_report")
        await moderation.on_moderation_decision(
            FakeCallbackQuery(user_id=ADMIN_ID, data=f"mod:escalate:{item.id}", message=FakeMessage(user_id=ADMIN_ID)),
            db_session, settings,
        )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)

    guarded = ("reports", "moderation_actions", "blocks", "events")
    for sql in statements:
        head = sql.strip().upper()
        if head.startswith(("UPDATE", "DELETE")):
            assert not any(f" {tbl} " in f" {sql.lower()} " or f'"{tbl}"' in sql.lower() for tbl in guarded), sql
    assert any(s.strip().upper().startswith("INSERT INTO MODERATION_ACTIONS") for s in statements)
