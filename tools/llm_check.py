"""Drafts one case per rule with the configured model and records what the guardrail made of each (ticket 26).

Reads exported cases, so it needs no database. It calls the API once per case, which costs money, so it
refuses to run without ANTHROPIC_API_KEY; IFIC_LLM_MODEL is optional (default: ific_guard.llm.model.DEFAULT_MODEL).
For each case it records whether the rewrite passed the guardrail and which numbers and citations the
rewrite added or dropped compared with the template.

    ANTHROPIC_API_KEY=... uv run python tools/llm_check.py \\
        outputs/ific_3074/cases.json outputs/ific_3076/cases.json --out outputs/llm-check.md
"""
import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from ific_guard.llm import configured_model, draft, generate
from ific_guard.llm.guardrail import citations_in, numbers_in
from ific_guard.llm.template import CaseView

# Ticket 26's six kinds, each with the rules that count for it, in order of preference.
KINDS = {
    "BR names Finland": ["fin-named-by-br"],
    "No space-to-Earth allocation": ["m4-no-space-to-earth"],
    "Station overlap": ["station-rx-overlap"],
    "pfd": ["pfd-gso-art21", "pfd-ngso-art21", "pfd-gso-app5", "pfd-ngso-app5"],
    "CEPT condition": ["pfd-gso-cept", "pfd-ngso-cept"],
    "Terrestrial": ["terrestrial-p1546"],
}


def view_of(row: dict, case_id: int) -> CaseView:
    deadline = row.get("comment_deadline")
    return CaseView(
        id=case_id, domain=row["domain"], rule_id=row["rule_id"], severity=row["severity"], title=row["title"], adm=row.get("adm"),
        network=row.get("network"), notice_ids=row["notice_ids"], details=row["details"], first_issue=row["issue_no"],
        last_issue=row["issue_no"], comment_deadline=date.fromisoformat(deadline) if deadline else None,
        source_sha256=row["source_sha256"],
    )


def pick(rows: list[dict]) -> dict[str, tuple[int, dict] | None]:
    """The highest-ranked case of each kind; a calculated one when the kind has any."""
    chosen: dict[str, tuple[int, dict] | None] = {}
    for kind, rules in KINDS.items():
        candidates = [(i, r) for rule in rules for i, r in enumerate(rows, 1) if r["rule_id"] == rule]
        calculated = [(i, r) for i, r in candidates if isinstance(r["details"].get("margin_db"), (int, float))]
        chosen[kind] = (calculated or candidates or [None])[0]
    return chosen


def changes(template: str, rewrite: str) -> tuple[list[str], list[str]]:
    before = numbers_in(template) | citations_in(template)
    after = numbers_in(rewrite) | citations_in(rewrite)
    return sorted(after - before), sorted(before - after)


def section(kind: str, view: CaseView, result, template) -> str:
    passed = result.source == "llm"
    lines = [f"### {kind}: {view.network} ({view.adm}), `{view.rule_id}`, IFIC {view.issue_no}", ""]
    lines.append(f"- **Guardrail:** {'passed' if passed else 'rejected, template used: ' + (result.fallback_reason or '')}")
    for v in result.violations:
        lines.append(f"  - {v.kind} `{v.value}`: {v.why}")
    if passed:
        added, dropped = changes(template.letter + template.explanation, result.letter + result.explanation)
        lines.append(f"- **Numbers and citations the rewrite added:** {', '.join(added) or 'none'}")
        lines.append(f"- **Dropped from the template:** {', '.join(dropped) or 'none'}")
        lines.append("- **Claims changed:** [reviewer: read the two texts below and note any claim the rewrite strengthened or added]")
        lines += ["", "<details><summary>Rewrite</summary>", "", "```text", result.explanation, "", result.letter, "```", "", "</details>"]
    lines += ["", "<details><summary>Template</summary>", "", "```text", template.explanation, "", template.letter, "```", "", "</details>", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("exports", nargs="+", type=Path, help="cases.json files from `ific_guard.cli export`")
    parser.add_argument("--out", type=Path, default=Path("outputs/llm-check.md"))
    args = parser.parse_args()

    model = configured_model()
    if model is None:
        sys.exit("No model is configured: set ANTHROPIC_API_KEY (IFIC_LLM_MODEL is optional). Each case is one paid API call.")
    rows = [row for path in args.exports for row in json.loads(path.read_text())]
    chosen = pick(rows)

    body, missing, passed = [], [], 0
    for kind, found in chosen.items():
        if found is None:
            missing.append(kind)
            continue
        view = view_of(found[1], found[0])
        print(f"{kind}: {view.network} ...", file=sys.stderr, flush=True)
        template, result = draft(view), generate(view, model)
        passed += result.source == "llm"
        body.append(section(kind, view, result, template))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    head = [
        "# Drafting with a real model (ticket 26)", "",
        f"Model: `{model.name}` · Run: {now} · Exports: {', '.join(str(p) for p in args.exports)} · Cost: [from the Anthropic Console]", "",
        f"{passed} of {len(body)} rewrites passed the guardrail. A rejected rewrite falls back to the template, so the expert never sees it.",
    ]
    if missing:
        head.append(f"Not in these exports, so not run: {', '.join(missing)}.")
    head += ["", "File a ticket for anything below that the guardrail let through and shouldn't have.", ""]
    args.out.write_text("\n".join(head + body))
    print(f"wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
