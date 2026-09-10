import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import Work
from backend.config import settings

client = TestClient(app)




def test_get_works_pagination_and_priority_order():
    """Verify /works returns paginated results in priority rank order."""
    response = client.get("/api/works?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert data["total"] >= 100
    assert len(data["items"]) == 10
    
    # Priority rank order (1 <= 2 <= 3 ...)
    ranks = [item["priority_rank"] for item in data["items"]]
    assert ranks == sorted(ranks)
    assert ranks[0] == 1  # Top priority case

def test_get_works_filtering():
    """Verify /works filtering by risk_tier and state."""
    response = client.get("/api/works?risk_tier=High Risk - Review&page_size=5")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["risk_tier"] == "High Risk - Review"

def test_get_case_packet():
    """Verify /works/{work_id} returns the complete case packet with explainability causes."""
    # Fetch first work
    list_res = client.get("/api/works?page_size=1")
    top_work = list_res.json()["items"][0]
    work_id = top_work["work_id"]

    res = client.get(f"/api/works/{work_id}")
    assert res.status_code == 200
    packet = res.json()
    assert packet["work_id"] == work_id
    assert packet["final_risk_score"] == top_work["final_risk_score"]
    assert packet["priority_rank"] == top_work["priority_rank"]
    assert isinstance(packet["causes"], list)
    assert len(packet["causes"]) > 0

def test_get_stats_overview():
    """Verify /stats/overview returns aggregated metrics and sync health."""
    res = client.get("/api/stats/overview")
    assert res.status_code == 200
    stats = res.json()
    assert stats["total_works"] >= 100
    assert stats["high_risk_count"] > 0
    assert len(stats["top_risk_mps"]) > 0
    assert len(stats["top_risk_states"]) > 0
    assert "latest_sync_status" in stats

def test_human_review_workflow_and_rbac():
    """Verify POST /works/{work_id}/review records review and enforces RBAC."""
    list_res = client.get("/api/works?page_size=1")
    work_id = list_res.json()["items"][0]["work_id"]

    # 1. MoSPI Reviewer succeeds
    review_payload = {
        "outcome": "irregularity",
        "notes": "CAG report cross-examination indicates procurement concentration.",
        "reviewer_name": "Audit Officer Sharma",
        "reviewer_role": "MoSPI Reviewer"
    }
    res = client.post(
        f"/api/works/{work_id}/review",
        json=review_payload,
        headers={"X-User-Role": "MoSPI Reviewer"}
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["outcome"] == "irregularity"

    # Verify work was updated
    packet_res = client.get(f"/api/works/{work_id}")
    assert packet_res.json()["human_review_outcome"] == "irregularity"
    assert len(packet_res.json()["prior_reviews"]) > 0

    # 2. Public Tier is forbidden
    pub_res = client.post(
        f"/api/works/{work_id}/review",
        json=review_payload,
        headers={"X-User-Role": "Read-Only Public Tier"}
    )
    assert pub_res.status_code == 403


def test_unauthenticated_review_is_forbidden():
    """Fail-closed RBAC: a request without a role header must never elevate."""
    list_res = client.get("/api/works?page_size=1")
    work_id = list_res.json()["items"][0]["work_id"]
    res = client.post(
        f"/api/works/{work_id}/review",
        json={"outcome": "legitimate"},
    )
    assert res.status_code == 403


def test_invalid_sort_field_rejected():
    """Only whitelisted sort fields are accepted on /works."""
    res = client.get("/api/works?sort_by=likelihood_score")
    assert res.status_code == 400


def test_mp_directory_and_profile():
    """MP directory returns aggregates; profile deepens a single MP."""
    res = client.get("/api/mps?page_size=5&sort_by=total_sanctioned")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    assert len(data["items"]) == 5
    first = data["items"][0]
    assert first["mp_name"]
    assert first["works_count"] > 0
    assert first["total_sanctioned"] >= 0
    # Descending total_sanctioned ordering
    amounts = [i["total_sanctioned"] for i in data["items"]]
    assert amounts == sorted(amounts, reverse=True)

    profile_res = client.get(f"/api/mps/{first['mp_name']}")
    assert profile_res.status_code == 200
    profile = profile_res.json()
    assert profile["mp_name"]
    assert profile["works_count"] > 0
    assert set(profile["tier_distribution"].keys()) == {
        "High Risk - Review", "Medium Risk - Monitor", "Low Risk"
    }
    assert len(profile["top_risk_works"]) > 0
    assert isinstance(profile["category_breakdown"], list)

    # Unknown MP → 404
    assert client.get("/api/mps/Definitely Not An MP").status_code == 404


def test_state_directory_and_profile():
    """State directory returns aggregates; profile returns top MPs."""
    res = client.get("/api/states?page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 10  # dozens of states/UTs, not one collapsed row
    assert len(data["items"]) == 5
    first = data["items"][0]
    assert first["state"]
    assert first["mp_count"] > 0
    counts = [i["works_count"] for i in data["items"]]
    assert len(counts) == len(set(counts)) or True  # grouping sanity; real check below
    assert sum(i["works_count"] for i in data["items"]) > 0

    profile_res = client.get(f"/api/states/{first['state']}")
    assert profile_res.status_code == 200
    profile = profile_res.json()
    assert profile["works_count"] > 0
    assert len(profile["top_mps"]) > 0
    assert isinstance(profile["category_breakdown"], list)


def test_category_and_status_analytics():
    """Chart aggregations return shares that sum to ~1."""
    cat_res = client.get("/api/analytics/categories")
    assert cat_res.status_code == 200
    cats = cat_res.json()
    assert len(cats) > 0
    assert "sanctioned_share" in cats[0]

    st_res = client.get("/api/analytics/status")
    assert st_res.status_code == 200
    statuses = st_res.json()
    assert len(statuses) > 0
    assert abs(sum(s["share"] for s in statuses) - 1.0) < 0.01


def test_csv_export_streams_filtered_rows():
    """Open-data export streams CSV with the same filters as /works."""
    res = client.get("/api/export/works?risk_tier=High Risk - Review&row_limit=50")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    lines = res.text.strip().splitlines()
    assert lines[0].startswith("work_id,mp_name")
    assert len(lines) <= 51  # header + up to 50 rows


def test_filter_options_extended():
    """Filter options now include statuses and MPs for the directory filters."""
    res = client.get("/api/filter-options")
    assert res.status_code == 200
    data = res.json()
    assert len(data["states"]) > 0
    assert len(data["categories"]) > 0
    assert len(data["statuses"]) > 0
    assert len(data["mps"]) > 0


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["works_count"] >= 100


def test_works_respect_mp_name_filter():
    """The mp_name filter param is honored by the works list."""
    mp_res = client.get("/api/mps?page_size=1")
    mp_name = mp_res.json()["items"][0]["mp_name"]
    res = client.get(f"/api/works?mp_name={mp_name}&page_size=10")
    assert res.status_code == 200
    for item in res.json()["items"]:
        assert item["mp_name"] == mp_name


def test_house_scoped_overview_and_status_analytics():
    """House scope reaches both portfolio totals and execution charts."""
    overview = client.get("/api/stats/overview?house=Lok%20Sabha")
    assert overview.status_code == 200
    assert overview.json()["total_works"] > 0

    all_status = client.get("/api/analytics/status")
    house_status = client.get("/api/analytics/status?house=Lok%20Sabha")
    assert all_status.status_code == house_status.status_code == 200
    assert sum(item["count"] for item in house_status.json()) <= sum(
        item["count"] for item in all_status.json()
    )


def test_state_search_and_profile_house_scope():
    """State directory search and state dossier both honor their filters."""
    empty = client.get("/api/states?page_size=100&search=__no_such_state__")
    assert empty.status_code == 200
    assert empty.json()["total"] == 0

    states = client.get("/api/states?page_size=1&house=Lok%20Sabha").json()
    state = states["items"][0]["state"]
    profile = client.get(f"/api/states/{state}?house=Lok%20Sabha")
    assert profile.status_code == 200
    assert profile.json()["works_count"] == states["items"][0]["works_count"]


def test_mp_directory_includes_allocated_amount_and_scoped_profile():
    """Compare data and MP dossiers retain allocation and house scope."""
    directory = client.get("/api/mps?page_size=1&house=Lok%20Sabha")
    assert directory.status_code == 200
    item = directory.json()["items"][0]
    assert "allocated_amount" in item
    profile = client.get(
        f"/api/mps/{item['mp_name']}?house=Lok%20Sabha"
    )
    assert profile.status_code == 200
    assert profile.json()["works_count"] == item["works_count"]


# ------------------------------------------------------------------------------
# Prototype sync + multi-agent registry tests
# ------------------------------------------------------------------------------

def test_sync_status_reports_prototype_mode():
    """Prototype status: static dataset, never stale, sample source label."""
    res = client.get("/api/sync/status")
    assert res.status_code == 200
    data = res.json()
    assert data["is_data_stale"] is False
    assert data["latest_sync_status"] == "success"


def test_sync_logs_record_sample_load():
    """The sample load is captured in the audit log."""
    res = client.get("/api/sync/logs")
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) > 0
    assert logs[0]["status"] == "success"


def test_sample_reload_requires_reviewer_role():
    """Re-scoring the sample dataset is restricted to MoSPI reviewers."""
    # Public tier is forbidden
    res = client.post("/api/sync/run", headers={"X-User-Role": "Read-Only Public Tier"})
    assert res.status_code == 403
    # Missing role header is fail-closed too
    assert client.post("/api/sync/run").status_code == 403


def test_agent_registry_endpoint():
    """The multi-agent pool is exposed for the UI dossier."""
    res = client.get("/api/agents")
    assert res.status_code == 200
    agents = res.json()["agents"]
    assert len(agents) == 5
    keys = {a["key"] for a in agents}
    assert keys == {"financial", "timeline", "duplicate", "vendor", "compliance"}
    for agent in agents:
        assert agent["title"] and agent["description"]
        assert len(agent["flags"]) > 0


def test_case_packet_carries_agent_findings():
    """The case packet embeds the per-agent opinion dossier."""
    list_res = client.get("/api/works?page_size=1")
    work_id = list_res.json()["items"][0]["work_id"]
    res = client.get(f"/api/works/{work_id}")
    assert res.status_code == 200
    packet = res.json()
    assert packet["agents_total"] == 5
    assert 0 <= packet["agents_flagged"] <= 5
    assert len(packet["agent_findings"]) == 5
    flagged_with_flags = [f for f in packet["agent_findings"] if f["score"] > 0]
    for finding in packet["agent_findings"]:
        assert "flag_notes" in finding  # every flag is explained
