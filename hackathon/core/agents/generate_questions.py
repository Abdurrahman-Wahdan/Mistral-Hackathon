import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is in pythonpath
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from hackathon.core.agents.graph import build_interview_graph


def load_document(filename: str) -> str:
    path = project_root / "data" / filename
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Could not find {path}")
        return ""


def _write_questions_to_dir(questions_dict: dict, output_dir: Path) -> None:
    """Write generated questions dict to output_dir, one JSON per category."""
    output_dir.mkdir(parents=True, exist_ok=True)
    consolidated = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "categories": {},
    }

    for agent_name, payload in questions_dict.items():
        safe_name = agent_name.replace(" & ", "_").replace(" ", "_").lower()
        output_file = output_dir / f"{safe_name}.json"

        output_data = payload if isinstance(payload, dict) else {
            "category": agent_name,
            "questions": [str(payload)],
            "question_count": 1,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "raw_response": str(payload),
            "error": "",
        }

        output_data.setdefault("category", agent_name)
        output_data.setdefault("questions", [])
        output_data.setdefault("question_count", len(output_data.get("questions", [])))
        output_data.setdefault("generated_at_utc", datetime.now(timezone.utc).isoformat())
        output_data.setdefault("raw_response", "")
        output_data.setdefault("error", "")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)

        consolidated["categories"][safe_name] = output_data

    (output_dir / "question_bank.json").write_text(
        json.dumps(consolidated, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


async def generate_questions_to_dir(
    cv_content: str,
    jd_content: str,
    culture_content: str,
    output_dir: Path,
) -> None:
    """Generate tailored interview questions and write them to output_dir."""
    app = build_interview_graph()
    input_state = {
        "cv_content": cv_content,
        "jd_content": jd_content,
        "culture_content": culture_content,
        "generated_questions": {},
    }

    if hasattr(app, "ainvoke"):
        final_state = await app.ainvoke(input_state)
    else:  # pragma: no cover
        final_state = app.invoke(input_state)

    _write_questions_to_dir(final_state.get("generated_questions", {}), output_dir)


async def main_async() -> None:
    print("Loading HR documents...")
    cv_content = load_document("candidate.md")
    jd_content = load_document("job_description.md")
    culture_content = load_document("company_culture.md")

    if not cv_content or not jd_content or not culture_content:
        print("Missing required documents in 'data/' directory. Exiting.")
        return

    print("Running Mistral HR Agents in parallel (async)... This may take a minute.")
    output_dir = project_root / "outputs"
    await generate_questions_to_dir(cv_content, jd_content, culture_content, output_dir)
    print(f"\nSaved questions to: {output_dir}")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
