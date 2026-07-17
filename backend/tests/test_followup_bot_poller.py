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


async def test_stop_dispatch_logs_both_directions():
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    logm = AsyncMock()
    with patch.object(bp, "get_client", lambda: tg), \
         patch.object(bp, "stop_enrollment", AsyncMock(return_value=True)), \
         patch.object(bp, "log_message", logm):
        await bp.handle_update(_update("STOP"))
    directions = [c.args[2] for c in logm.await_args_list]
    assert "inbound" in directions and "outbound" in directions


# --- load_plan reconstruction from the decomposed consultations columns ---

CONSULT_ROW = {
    "care_plan_summary": "HFrEF optimisation, clinically stable.",
    "medication_recommendations": {
        "start": [{"name": "Beta-blocker (bisoprolol)", "dose": "1.25 mg OD, titrate to 10 mg OD"}],
        "stop": [{"name": "Gliclazide", "dose": ""}],
        "continue": [],
    },
    "monitoring": [{"parameter": "Serum potassium", "schedule": "Baseline + after each drug initiation"}],
    "lifestyle_goals": [{"goal": "Sodium restriction <2 g/day", "detail": "to reduce fluid retention"}],
    "referrals": [{"specialty": "Cardiology", "urgency": "urgent"}],
    "safety_flags": [{"title": "Enalapril + Spironolactone - hyperkalaemia risk", "severity": "MAJOR"}],
    "next_review": "2026-08-01",
}


def _plan_pool(row):
    from unittest.mock import MagicMock
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=row)
    pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool


async def test_load_plan_reconstructs_from_decomposed_columns():
    with patch.object(bp, "db_pool", _plan_pool(CONSULT_ROW)):
        plan = await bp.load_plan(236)
    assert plan["summary"] == "HFrEF optimisation, clinically stable."
    # meds flatten into recommendations carrying their action
    meds = [r for r in plan["recommendations"] if r["recommendation_type"] == "pharmacological"]
    assert {"start", "stop"} == {m["action"] for m in meds}
    assert any("bisoprolol" in m["intervention"].lower() for m in meds)
    # monitoring passes through with parameter intact (protocol._first_red_flag reads it)
    assert plan["monitoring"][0]["parameter"] == "Serum potassium"
    # clinician safety flags are available to triage, but NOT as patient-facing red flags
    assert "hyperkalaemia" in plan["safety_flags"][0].lower()
    assert not plan.get("safety_netting")
    assert plan["follow_up"][0]["when"] == "2026-08-01"


async def test_load_plan_recovers_red_flags_from_monitoring_targets():
    """P7 trip-wires live in monitoring[].target — plan.red_flags is never persisted."""
    row = dict(CONSULT_ROW)
    row["monitoring"] = [
        {"parameter": "Weight", "schedule": "daily", "target": "report gain >2 kg in 3 days"},
        {"parameter": "Serum potassium", "schedule": "after each titration"},  # no target
    ]
    with patch.object(bp, "db_pool", _plan_pool(row)):
        plan = await bp.load_plan(236)
    # only the item carrying a trip-wire becomes a patient-facing red flag
    assert plan["safety_netting"] == ["Weight: report gain >2 kg in 3 days"]
    # and it reaches the triage context the classifier actually reads
    assert "Red flags: Weight: report gain >2 kg in 3 days" in bp.plan_context_text(plan)


async def test_load_plan_handles_json_encoded_columns():
    import json as _json
    encoded = dict(CONSULT_ROW)
    encoded["medication_recommendations"] = _json.dumps(CONSULT_ROW["medication_recommendations"])
    encoded["monitoring"] = _json.dumps(CONSULT_ROW["monitoring"])
    with patch.object(bp, "db_pool", _plan_pool(encoded)):
        plan = await bp.load_plan(236)
    assert any("bisoprolol" in r["intervention"].lower() for r in plan["recommendations"])
    assert plan["monitoring"][0]["parameter"] == "Serum potassium"


async def test_load_plan_missing_row_returns_empty_dict():
    with patch.object(bp, "db_pool", _plan_pool(None)):
        assert await bp.load_plan(999) == {}


def test_plan_context_text_includes_safety_flags_for_triage():
    txt = bp.plan_context_text({
        "summary": "HFrEF",
        "safety_flags": ["Enalapril + Spironolactone - hyperkalaemia risk"],
        "monitoring": [{"parameter": "Serum potassium"}],
    })
    assert "hyperkalaemia" in txt.lower()
    assert "Serum potassium" in txt


async def test_bare_start_button_does_not_claim_link_expired():
    """Pressing Telegram's Start button sends '/start' with no token — that is
    NOT an expired link, and telling the patient so sends them back to the clinic."""
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    bind = AsyncMock(return_value=None)
    with patch.object(bp, "get_client", lambda: tg), \
         patch.object(bp, "bind_enrollment", bind), \
         patch.object(bp, "log_message", AsyncMock()):
        await bp.handle_update(_update("/start"))
    bind.assert_not_awaited()  # nothing to bind — don't hit the DB
    sent = tg.send_message.await_args.args[1]
    assert "expired" not in sent.lower()
    assert "qr" in sent.lower()  # points them at the QR code they were given


@pytest.mark.parametrize("text", ["STOP", "stop", "Stop", "/stop", "/STOP", "stop please"])
async def test_all_opt_out_forms_stop_enrollment(text):
    """Patients opt out via the command menu (/stop) or by typing STOP. Any form
    that misses this branch is silently routed to the LLM as a symptom report."""
    tg = AsyncMock(); tg.send_message = AsyncMock(return_value=True)
    stop = AsyncMock(return_value=True)
    classify = AsyncMock()
    with patch.object(bp, "get_client", lambda: tg), \
         patch.object(bp, "stop_enrollment", stop), \
         patch.object(bp, "classify_reply", classify), \
         patch.object(bp, "log_message", AsyncMock()):
        await bp.handle_update(_update(text))
    stop.assert_awaited_once()
    classify.assert_not_awaited()  # must never reach triage
