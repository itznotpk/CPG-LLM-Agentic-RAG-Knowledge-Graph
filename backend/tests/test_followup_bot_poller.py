"""Bot poller dispatch tests. All collaborators mocked."""
from unittest.mock import AsyncMock, patch

import pytest

from agent.followup import bot_poller as bp
from agent.followup.triage import TriageResult

ENROLLMENT = {"id": 2, "consultation_id": 101, "patient_nric": "X",
              "patient_first_name": "Ahmad", "telegram_chat_id": 555}


def _update(text):
    return {"update_id": 1, "message": {"chat": {"id": 555}, "text": text}}


async def test_start_with_valid_token_binds_and_schedules():
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    with patch.object(bp, "get_client", lambda: tg), \
         patch.object(bp, "bind_enrollment", AsyncMock(return_value=ENROLLMENT)) as bind, \
         patch.object(bp, "load_plan", AsyncMock(return_value={"summary": "s"})), \
         patch.object(bp, "generate_protocol", AsyncMock(return_value=[])), \
         patch.object(bp, "schedule_checkins", AsyncMock(return_value=0)) as sched, \
         patch.object(bp, "log_message", AsyncMock()):
        await bp.handle_update(_update("/start tok123"))
    bind.assert_awaited_once_with("tok123", 555)
    sched.assert_awaited_once()
    assert tg.send_message.await_count >= 1  # welcome sent


async def test_start_with_bad_token_sends_expired_reply():
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    with patch.object(bp, "get_client", lambda: tg), \
         patch.object(bp, "bind_enrollment", AsyncMock(return_value=None)), \
         patch.object(bp, "log_message", AsyncMock()):
        await bp.handle_update(_update("/start nope"))
    sent = tg.send_message.await_args.args[1]
    assert "expired" in sent.lower()


async def test_tripwire_reply_escalates_without_llm():
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    classify = AsyncMock()
    with patch.object(bp, "get_client", lambda: tg), \
         patch.object(bp, "active_enrollment_for_chat", AsyncMock(return_value=ENROLLMENT)), \
         patch.object(bp, "load_plan", AsyncMock(return_value={})), \
         patch.object(bp, "classify_reply", classify), \
         patch.object(bp, "create_alert", AsyncMock()) as alert, \
         patch.object(bp, "log_message", AsyncMock()):
        await bp.handle_update(_update("I have chest pain"))
    classify.assert_not_awaited()          # tripwire short-circuits the LLM
    alert.assert_awaited_once()
    assert alert.await_args.args[1] == "critical"


async def test_normal_reply_goes_through_triage_and_alerts_on_escalate():
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    result = TriageResult(classification="ESCALATE", rationale="worsening", patient_reply="Flagged.")
    with patch.object(bp, "get_client", lambda: tg), \
         patch.object(bp, "active_enrollment_for_chat", AsyncMock(return_value=ENROLLMENT)), \
         patch.object(bp, "load_plan", AsyncMock(return_value={"summary": "s"})), \
         patch.object(bp, "classify_reply", AsyncMock(return_value=result)), \
         patch.object(bp, "create_alert", AsyncMock()) as alert, \
         patch.object(bp, "log_message", AsyncMock()):
        await bp.handle_update(_update("feeling more tired and swollen"))
    alert.assert_awaited_once()
    assert alert.await_args.args[1] == "major"


async def test_no_active_enrollment_gets_fixed_reply():
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    with patch.object(bp, "get_client", lambda: tg), \
         patch.object(bp, "active_enrollment_for_chat", AsyncMock(return_value=None)), \
         patch.object(bp, "log_message", AsyncMock()):
        await bp.handle_update(_update("hello?"))
    sent = tg.send_message.await_args.args[1]
    assert "active follow-up plan" in sent
