import asyncio
import sys
from pathlib import Path

# Ensure project root is in pythonpath
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from hackathon.core.agents.reporting import generate_reports_for_interview

OUTPUTS_DIR = project_root / "outputs"


async def main_async():
    print("Initializing Post-Interview Analysis Agents...\n")

    if not OUTPUTS_DIR.exists():
        print("Outputs directory not found. Have you run the interview yet?")
        return

    summary = await generate_reports_for_interview(
        logs_dir=OUTPUTS_DIR,
        context_dir=OUTPUTS_DIR,
        output_dir=OUTPUTS_DIR,
    )

    if summary.get("total_categories", 0) == 0:
        print("No interview logs found (*_logs.json). Please run an interview simulation first.")
        return

    failed = [r for r in summary.get("results", []) if r.get("status") in {"error", "skipped"}]
    if failed:
        print("\nSome categories could not be analyzed:")
        for item in failed:
            print(f"  - {item.get('category')}: {item.get('reason')}")

    if summary.get("final_report_generated"):
        print("\nSaved consolidated report to final_interview_report.md")
    else:
        print(f"\nFinal report generation failed: {summary.get('final_report_error')}")

    print("Saved analysis summary JSON to analysis_summary.json")
    print("\nAll Post-Interview analyses are complete!")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
