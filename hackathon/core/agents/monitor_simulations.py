import json
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SIMULATIONS_DIR = PROJECT_ROOT / "outputs" / "simulations"
MONITOR_FILE = SIMULATIONS_DIR / "monitor.jsonl"


def _load_entries() -> list[dict]:
    if not MONITOR_FILE.exists():
        return []

    entries: list[dict] = []
    for line in MONITOR_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def main() -> None:
    entries = _load_entries()
    if not entries:
        print("No simulation monitor entries found.")
        print(f"Expected file: {MONITOR_FILE}")
        return

    by_scenario: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        by_scenario[entry.get("scenario", "unknown")].append(entry)

    print(f"Total monitored runs: {len(entries)}")
    print(f"Scenarios tracked: {len(by_scenario)}\n")

    for scenario in sorted(by_scenario):
        rows = by_scenario[scenario]
        total = len(rows)
        success = sum(1 for r in rows if r.get("status") == "success")
        avg_score = sum(float(r.get("quality_score", 0)) for r in rows) / total
        avg_json_fail = sum(int(r.get("json_parse_failures", 0)) for r in rows) / total
        avg_repeats = sum(int(r.get("repeated_questions", 0)) for r in rows) / total
        redirects = sum(1 for r in rows if bool(r.get("redirect_observed", False)))

        latest = rows[-1]

        print(f"Scenario: {scenario}")
        print(f"  Runs: {total}")
        print(f"  Success Rate: {success}/{total}")
        print(f"  Avg Quality Score: {avg_score:.2f}")
        print(f"  Avg JSON Parse Failures: {avg_json_fail:.2f}")
        print(f"  Avg Repeated Questions: {avg_repeats:.2f}")
        print(f"  Redirect Observed: {redirects}/{total}")
        print(
            "  Latest: "
            f"run={latest.get('run_name')}, "
            f"status={latest.get('status')}, "
            f"score={latest.get('quality_score')}"
        )
        print()


if __name__ == "__main__":
    main()
