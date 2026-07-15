import pytest
from agent.models import EbmEvidence, TreatmentPlan, Recommendation
from agent.ebm_lookup import evidence_tier_for, build_europepmc_query


def test_ebm_evidence_defaults_and_treatmentplan_field():
    ev = EbmEvidence(
        title="Ticagrelor vs Clopidogrel in NSTEMI",
        abstract_snippet="In this systematic review, ticagrelor reduced...",
        journal="Cochrane Database Syst Rev",
        year=2024,
        pub_type="systematic-review",
        evidence_tier="high",
        pmid="12345678",
        doi="10.1002/abc",
        url="https://europepmc.org/article/MED/12345678",
    )
    assert ev.cpg_gap is False
    plan = TreatmentPlan(
        icd_primary="BA41.1",
        summary="s",
        recommendations=[Recommendation(
            intervention="Start ticagrelor",
            type="pharmacological",
            cpg_source="CPG NSTEMI",
            rationale="Evidence-based therapy"
        )],
        confidence=0.8,
    )
    assert plan.ebm_evidence == []
    plan.ebm_evidence = [ev]
    assert plan.ebm_evidence[0].evidence_tier == "high"


@pytest.mark.parametrize("pub_types, expected", [
    (["systematic-review"], "high"),
    (["Meta-Analysis"], "high"),
    (["Randomized Controlled Trial"], "moderate"),
    (["Guideline"], "moderate"),
    (["Journal Article"], "low"),
    ([], "low"),
    (["case-reports"], "low"),
])
def test_evidence_tier_for(pub_types, expected):
    assert evidence_tier_for(pub_types) == expected


def test_build_query_combines_disease_terms_filters_and_recency():
    q = build_europepmc_query(["NSTEMI"], ["ticagrelor"], recency_years=7)
    assert "NSTEMI" in q and "ticagrelor" in q
    # pub-type pyramid filter present
    assert "systematic review" in q.lower()
    assert "randomized controlled trial" in q.lower()
    # recency filter present as a PUB_YEAR range
    assert "PUB_YEAR" in q
    # has-abstract constraint so we never feed empty abstracts to synthesis
    assert "HAS_ABSTRACT:Y" in q


def test_build_query_empty_terms_still_valid():
    q = build_europepmc_query(["Atrial Fibrillation"], [])
    assert "Atrial Fibrillation" in q
    assert q.strip() != ""


# Tests for parse_europepmc_response
from agent.ebm_lookup import parse_europepmc_response

_SAMPLE = {
    "resultList": {"result": [
        {
            "id": "12345678", "pmid": "12345678", "doi": "10.1002/abc",
            "title": "Ticagrelor in NSTEMI: a systematic review",
            "journalTitle": "Cochrane Database Syst Rev", "pubYear": "2024",
            "abstractText": "A" * 900,
            "pubTypeList": {"pubType": ["Journal Article", "systematic-review"]},
        },
        {  # no abstract -> should be dropped
            "id": "999", "title": "No abstract paper", "pubYear": "2023",
            "pubTypeList": {"pubType": ["Journal Article"]},
        },
    ]}
}


def test_parse_builds_models_grades_and_truncates_and_drops_abstractless():
    out = parse_europepmc_response(_SAMPLE, snippet_chars=500)
    assert len(out) == 1
    ev = out[0]
    assert ev.pmid == "12345678"
    assert ev.evidence_tier == "high"
    assert len(ev.abstract_snippet) <= 500
    assert ev.url == "https://europepmc.org/article/MED/12345678"


def test_parse_empty_payload_returns_empty():
    assert parse_europepmc_response({}) == []
    assert parse_europepmc_response({"resultList": {"result": []}}) == []


import agent.ebm_lookup as ebm


class _FakeResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}
    def json(self):
        return self._json
    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("err", request=None, response=None)


class _FakeClient:
    def __init__(self, resp=None, exc=None):
        self._resp, self._exc = resp, exc
        self.calls = 0
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def get(self, url, params=None):
        self.calls += 1
        if self._exc:
            raise self._exc
        return self._resp


async def test_fetch_returns_parsed_and_caches(monkeypatch):
    ebm._EBM_CACHE.clear()
    fake = _FakeClient(resp=_FakeResp(200, _SAMPLE))
    monkeypatch.setattr(ebm.httpx, "AsyncClient", lambda *a, **k: fake)
    out = await ebm.fetch_ebm_evidence(["NSTEMI"], ["ticagrelor"], limit=5)
    assert len(out) == 1 and out[0].pmid == "12345678"
    # second identical call is served from cache (no new client call)
    calls_before = fake.calls
    out2 = await ebm.fetch_ebm_evidence(["NSTEMI"], ["ticagrelor"], limit=5)
    assert out2[0].pmid == "12345678"
    assert fake.calls == calls_before  # cache hit


async def test_fetch_fail_open_on_exception(monkeypatch):
    ebm._EBM_CACHE.clear()
    import httpx
    fake = _FakeClient(exc=httpx.ConnectError("boom"))
    monkeypatch.setattr(ebm.httpx, "AsyncClient", lambda *a, **k: fake)
    out = await ebm.fetch_ebm_evidence(["NSTEMI"], ["ticagrelor"], limit=5, timeout_s=0.1)
    assert out == []  # never raises, returns empty


async def test_fetch_empty_diseases_short_circuits(monkeypatch):
    ebm._EBM_CACHE.clear()
    called = {"n": 0}
    def _boom(*a, **k):
        called["n"] += 1
        raise AssertionError("should not hit network")
    monkeypatch.setattr(ebm.httpx, "AsyncClient", _boom)
    assert await ebm.fetch_ebm_evidence([], ["ticagrelor"]) == []
    assert called["n"] == 0
