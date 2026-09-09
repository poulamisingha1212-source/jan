import pandas as pd
from model.agents import AGENTS, AGENT_REGISTRY, get_coordinator
from model.risk_engine import score_dataset, generate_case_packet, RULE_DESCRIPTIONS


def _scored_sample(n):
    """Score rows from the bundled sample dataset through the agent system."""
    from backend.services.ingestion import _reshape_long_format
    raw = pd.read_csv("data/mplads_raw_sample.csv")
    scored = score_dataset(_reshape_long_format(raw))
    return scored.dropna(subset=["work_id"]).head(n)


def test_agent_pool_loads():
    """Five specialist agents are registered with complete metadata."""
    assert len(AGENTS) == 5
    keys = {a.key for a in AGENTS}
    assert keys == {'financial', 'timeline', 'duplicate', 'vendor', 'compliance'}
    for agent in AGENTS:
        assert agent.key in AGENT_REGISTRY
        assert agent.title and agent.description
        assert 0 < agent.weight <= 1
        assert agent.FLAG_WEIGHTS, f"{agent.key} agent defines no flags"
        # every flag an agent can raise must have a human explanation
        for flag in agent.FLAG_WEIGHTS:
            assert flag in RULE_DESCRIPTIONS, f"no description for flag '{flag}'"


def test_agents_produce_scores_and_flags():
    """Every agent returns a 0..1 score plus a flag list per work."""
    coordinator = get_coordinator()
    assert set(coordinator.weights) == {a.key for a in AGENTS}
    assert abs(sum(coordinator.weights.values()) - 1.0) < 1e-9

    scored = _scored_sample(20)
    for agent in AGENTS:
        col = f'{agent.key}_score'
        assert col in scored.columns
        assert scored[col].between(0, 1).all(), f"{col} out of [0,1]"
        assert f'{agent.key}_flags' in scored.columns


def test_score_dataset_unified_formula_outputs():
    """Coordinator outputs every column the API layer depends on."""
    scored = _scored_sample(10)
    for col in ('final_risk_score', 'priority_rank', 'risk_tier',
                'likelihood_score', 'impact_score', 'recommended_action',
                'rule_flags_triggered', 'rule_flag_count', 'agent_breakdown',
                'is_anomaly', 'agents_flagged'):
        assert col in scored.columns

    assert scored['final_risk_score'].between(0, 100).all()
    assert scored['likelihood_score'].between(0, 1).all()
    assert set(scored['risk_tier'].unique()) <= {
        'High Risk - Review', 'Medium Risk - Monitor', 'Low Risk'}
    # agent_breakdown must be valid JSON with one entry per agent
    import json
    for _, row in scored.iterrows():
        payload = json.loads(row['agent_breakdown'])
        assert len(payload['agents']) == 5


def test_generate_case_packet():
    """Case packet contains agent findings, explainability causes and impact note."""
    row = _scored_sample(1).iloc[0]
    work_id = str(row['work_id'])

    packet = generate_case_packet(work_id, work_row=row.to_dict())
    assert packet['work_id'] == work_id
    assert packet['final_risk_score'] == row['final_risk_score']
    assert packet['priority_rank'] == int(row['priority_rank'])
    assert packet['risk_tier'] == row['risk_tier']
    assert isinstance(packet['causes'], list)
    assert len(packet['causes']) > 0
    assert "Sanctioned value" in packet['impact_note']

    # multi-agent dossier
    assert packet['agents_total'] == 5
    assert 0 <= packet['agents_flagged'] <= 5
    assert len(packet['agent_findings']) == 5
    for finding in packet['agent_findings']:
        assert {'key', 'title', 'description', 'weight', 'score', 'flags'} <= set(finding)
        assert finding['score'] >= 0
    # findings are ordered most-suspicious-first
    scores = [f['score'] for f in packet['agent_findings']]
    assert scores == sorted(scores, reverse=True)


def test_case_packet_from_db_shaped_row():
    """A row as stored in the DB (flags + breakdown as strings) still decodes."""
    row = _scored_sample(1).iloc[0]
    db_row = {
        'work_id': str(row['work_id']),
        'mp_name': row.get('mp_name'),
        'state': row.get('state'),
        'rule_flags_triggered': str(list(row['rule_flags_triggered'])),
        'agent_breakdown': row['agent_breakdown'],
        'final_risk_score': row['final_risk_score'],
        'priority_rank': int(row['priority_rank']),
        'risk_tier': row['risk_tier'],
        'recommended_action': row['recommended_action'],
        'rule_flag_count': int(row['rule_flag_count']),
        'sanction_amount': float(row['sanction_amount']),
    }
    packet = generate_case_packet(db_row['work_id'], work_row=db_row)
    assert packet['agents_total'] == 5
    assert packet['rule_flags_triggered'] == sorted(row['rule_flags_triggered'])


def test_risk_score_consistency_and_zero_drift():
    """Zero drift between freshly scored rows and the case packet generator."""
    df = _scored_sample(5)
    for _, row in df.iterrows():
        packet = generate_case_packet(row['work_id'], work_row=row.to_dict())
        assert packet['final_risk_score'] == row['final_risk_score']
        assert packet['priority_rank'] == int(row['priority_rank'])
        assert packet['risk_tier'] == row['risk_tier']
