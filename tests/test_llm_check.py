from tools.llm_check import KINDS, changes, pick


def row(rule_id, margin=None):
    details = {"margin_db": margin} if margin is not None else {}
    return {"rule_id": rule_id, "details": details}


def test_picks_a_calculated_case_of_each_kind_and_reports_kinds_it_lacks():
    rows = [row("pfd-ngso-app5"), row("pfd-gso-art21", 2.0), row("fin-named-by-br")]
    chosen = pick(rows)
    assert chosen["pfd"] == (2, rows[1])  # the calculated one, though an earlier pfd case exists
    assert chosen["BR names Finland"] == (3, rows[2])
    assert chosen["Terrestrial"] is None and set(chosen) == set(KINDS)


def test_changes_lists_numbers_and_citations_added_and_dropped():
    added, dropped = changes("Margin 4.5 dB under No. 9.14.", "Margin 4.5 dB under No. 9.21, notice 42.")
    assert "42" in added and "rr:9.21" in added and "rr:9.14" in dropped
