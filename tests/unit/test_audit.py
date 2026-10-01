from rbrs.audit import audit, audit_markdown
from tests.conftest import REPO


def test_audit_on_repository_data(tmp_path: object) -> None:
    r = audit(REPO / "data", results_dir=str(tmp_path))
    assert r["ac07_pass"] and r["ac10_pass"]  # AC-07, AC-10
    assert r["ready_for_paper"] is False  # sourced I/F/C still missing
    assert "INT-LED-EFF" in r["interventions_used_by_active_rules_missing_data"]
    assert "lhv_dry_wood" in r["factors_source_needed"]
    assert "# RBRS audit" in audit_markdown(r)
