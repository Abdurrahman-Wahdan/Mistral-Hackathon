import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from shutil import copy2
from typing import Any

# Ensure project root is in pythonpath
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage

from hackathon.llm.factory import get_llm
from hackathon.llm.retry import ainvoke_with_retry
from hackathon.config.settings import settings
from hackathon.core.agents.reporting import generate_reports_for_interview
from hackathon.core.prompts.prompts import (
    CONDUCT_INTERVIEW_SYSTEM_PROMPT,
    SIMULATE_CANDIDATE_SYSTEM_PROMPT,
    SIMULATE_INTERVIEWER_KICKOFF_PROMPT,
    SIMULATION_DEFAULT_SCENARIO,
    SIMULATION_SCENARIO_INSTRUCTIONS,
)
from hackathon.core.tools.interviewer_tools import (
    INTERVIEWER_TOOLS,
    set_session_outputs_dir,
    reset_session_outputs_dir,
)


def read_file(filepath: Path) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _normalize_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if "text" in item:
                    parts.append(str(item["text"]))
                elif "content" in item:
                    parts.append(str(item["content"]))
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return "\n".join(p for p in parts if p).strip()
    return str(content).strip()


def _strip_json_fences(text: str) -> str:
    if text.startswith("```json") and text.endswith("```"):
        return text[7:-3].strip()
    if text.startswith("```") and text.endswith("```"):
        return text[3:-3].strip()
    return text


def _prepare_session_outputs(source_outputs_dir: Path, session_outputs_dir: Path) -> int:
    session_outputs_dir.mkdir(parents=True, exist_ok=True)
    if not source_outputs_dir.exists():
        return 0

    copied = 0
    for file_path in source_outputs_dir.iterdir():
        if not file_path.is_file():
            continue
        if file_path.suffix not in (".json", ".md"):
            continue
        if file_path.name.endswith("_logs.json"):
            continue
        if file_path.name.startswith("analysis_"):
            continue
        if file_path.name.startswith("simulation_"):
            continue
        if file_path.name.startswith("final_"):
            continue
        copy2(file_path, session_outputs_dir / file_path.name)
        copied += 1

    return copied


def _collect_log_metrics(session_outputs_dir: Path) -> dict:
    questions: list[str] = []
    categories: dict[str, int] = {}

    for log_file in session_outputs_dir.glob("*_logs.json"):
        category = log_file.stem.replace("_logs", "")
        try:
            data = json.loads(log_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        if not isinstance(data, list):
            continue

        categories[category] = len(data)
        for entry in data:
            question = (entry or {}).get("question", "")
            if isinstance(question, str) and question.strip():
                questions.append(question.strip())

    unique_questions = len(set(questions))
    return {
        "categories_logged": len(categories),
        "segments_logged": sum(categories.values()),
        "questions_logged": len(questions),
        "unique_questions": unique_questions,
        "repeated_questions": max(0, len(questions) - unique_questions),
        "category_breakdown": categories,
    }


def _evaluate_run(
    transcript: list[dict],
    scenario_name: str,
    ended_normally: bool,
    json_parse_failures: int,
    repeated_questions: int,
) -> dict:
    hr_messages = [t["message"].lower() for t in transcript if t.get("role") == "hr"]

    rude_lexicon = {
        "stupid",
        "idiot",
        "shut up",
        "nonsense",
        "useless",
        "pathetic",
    }
    technical_lexicon = {
        "algorithm",
        "api",
        "framework",
        "debug",
        "code",
        "coding",
        "llm",
        "system design",
        "architecture",
    }
    redirect_lexicon = {
        "let's refocus",
        "let us refocus",
        "back to",
        "to answer",
        "could you address",
        "please focus",
        "let me bring you back",
    }

    professionalism_issues = sum(
        1 for msg in hr_messages for token in rude_lexicon if token in msg
    )
    technical_question_hits = sum(
        1
        for msg in hr_messages
        if "?" in msg and any(token in msg for token in technical_lexicon)
    )
    redirect_count = sum(
        1 for msg in hr_messages if any(token in msg for token in redirect_lexicon)
    )

    difficult_scenarios = {
        "rude_candidate",
        "off_topic_candidate",
        "evasive_candidate",
        "silent_candidate",
        "contradictory_candidate",
    }
    needs_redirect = scenario_name in difficult_scenarios

    score = 100
    score -= json_parse_failures * 10
    score -= repeated_questions * 15
    score -= professionalism_issues * 20
    score -= technical_question_hits * 10
    if not ended_normally:
        score -= 15
    if needs_redirect and redirect_count == 0:
        score -= 10

    return {
        "quality_score": max(0, score),
        "professionalism_issues": professionalism_issues,
        "technical_question_hits": technical_question_hits,
        "redirect_count": redirect_count,
        "needs_redirect": needs_redirect,
        "redirect_observed": redirect_count > 0,
    }


def _append_monitor_entry(simulations_dir: Path, entry: dict) -> None:
    monitor_file = simulations_dir / "monitor.jsonl"
    with open(monitor_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


async def run_single_scenario(
    scenario_name: str,
    scenario_instruction: str,
    cv_content: str,
    jd_content: str,
    session_outputs_dir: Path,
    max_turns: int,
    verbose: bool,
) -> dict:
    start_time = datetime.now(timezone.utc)
    token = set_session_outputs_dir(session_outputs_dir)

    interviewer_llm = get_llm(
        model_id=settings.HR_INTERVIEW_MODEL,
        temperature=settings.HR_INTERVIEW_TEMPERATURE,
    )
    interviewer_with_tools = interviewer_llm.bind_tools(INTERVIEWER_TOOLS)
    interviewer_messages = [SystemMessage(content=CONDUCT_INTERVIEW_SYSTEM_PROMPT)]

    candidate_llm = get_llm(
        model_id=settings.HR_SIM_CANDIDATE_MODEL,
        temperature=settings.HR_SIM_CANDIDATE_TEMPERATURE,
    )
    formatted_candidate_prompt = SIMULATE_CANDIDATE_SYSTEM_PROMPT.format(
        cv_content=cv_content,
        jd_content=jd_content,
    )
    formatted_candidate_prompt += (
        "\n\n### Scenario Behavior\n"
        f"Scenario: {scenario_name}\n"
        f"{scenario_instruction}"
    )
    candidate_messages = [SystemMessage(content=formatted_candidate_prompt)]

    kickoff = HumanMessage(content=SIMULATE_INTERVIEWER_KICKOFF_PROMPT)
    interviewer_messages.append(kickoff)

    transcript: list[dict] = []
    tool_usage: Counter[str] = Counter()
    tool_call_count = 0
    json_parse_failures = 0
    interviewer_turns = 0
    candidate_turns = 0
    ended_normally = False
    forced_termination = False
    error_message = ""
    quality_gate_failures: list[str] = []

    try:
        for _ in range(max_turns):
            response = await ainvoke_with_retry(interviewer_with_tools, interviewer_messages)
            tool_calls = response.tool_calls or []
            if tool_calls:
                interviewer_messages.append(response)
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_call_count += 1
                    tool_usage[tool_name] += 1

                    tool_func = next((t for t in INTERVIEWER_TOOLS if t.name == tool_name), None)
                    if tool_func:
                        tool_result = tool_func.invoke(tool_args)
                        interviewer_messages.append(
                            ToolMessage(
                                name=tool_name,
                                content=str(tool_result),
                                tool_call_id=tool_call["id"],
                            )
                        )
                continue

            interviewer_turns += 1
            raw_content = _normalize_text(response.content)
            if not raw_content:
                json_parse_failures += 1
                agent_msg = (
                    "I want to make sure we are aligned. "
                    "Could you clarify your last point with a concrete example?"
                )
                interviewer_messages.append(AIMessage(content=agent_msg))
                interviewer_messages.append(SystemMessage(content=(
                    "Internal rule reminder: Your previous assistant message was empty. "
                    "Always provide a non-empty JSON response."
                )))
                transcript.append({"role": "hr", "message": agent_msg})
                if verbose:
                    print(f"\n[HR Agent][{scenario_name}]: {agent_msg}")

                candidate_messages.append(HumanMessage(content=agent_msg))
                candidate_response = await ainvoke_with_retry(candidate_llm, candidate_messages)
                candidate_msg = _normalize_text(candidate_response.content)
                candidate_turns += 1
                transcript.append({"role": "candidate", "message": candidate_msg})
                if verbose:
                    print(f"\n[Candidate Agent][{scenario_name}]: {candidate_msg}")
                candidate_messages.append(candidate_response)
                interviewer_messages.append(HumanMessage(content=candidate_msg))
                continue

            clean_content = _strip_json_fences(raw_content)

            end_interview = False
            try:
                parsed = json.loads(clean_content)
                agent_msg = parsed.get("message_to_candidate", clean_content)
                end_interview = bool(parsed.get("end_interview", False))
            except json.JSONDecodeError:
                agent_msg = clean_content
                json_parse_failures += 1
            if not str(agent_msg).strip():
                agent_msg = (
                    "I want to make sure we are aligned. "
                    "Could you share a concrete example?"
                )
                interviewer_messages.append(SystemMessage(content=(
                    "Internal rule reminder: message_to_candidate was empty. "
                    "Always return a non-empty message."
                )))

            if end_interview:
                interviewer_messages.append(response)
            else:
                interviewer_messages.append(response)

            transcript.append({"role": "hr", "message": agent_msg})
            if verbose:
                print(f"\n[HR Agent][{scenario_name}]: {agent_msg}")

            if end_interview:
                ended_normally = True
                break

            candidate_messages.append(HumanMessage(content=agent_msg))
            candidate_response = await ainvoke_with_retry(candidate_llm, candidate_messages)
            candidate_msg = _normalize_text(candidate_response.content)
            candidate_turns += 1

            transcript.append({"role": "candidate", "message": candidate_msg})
            if verbose:
                print(f"\n[Candidate Agent][{scenario_name}]: {candidate_msg}")

            candidate_messages.append(candidate_response)
            interviewer_messages.append(HumanMessage(content=candidate_msg))
        else:
            forced_termination = True

    except Exception as exc:  # pragma: no cover - runtime safety
        error_message = str(exc)

    finally:
        reset_session_outputs_dir(token)

    history_metrics = _collect_log_metrics(session_outputs_dir)
    quality_metrics = _evaluate_run(
        transcript=transcript,
        scenario_name=scenario_name,
        ended_normally=ended_normally,
        json_parse_failures=json_parse_failures,
        repeated_questions=history_metrics["repeated_questions"],
    )

    if not ended_normally:
        quality_gate_failures.append("interview_not_concluded_normally")
    if history_metrics["unique_questions"] < 1:
        quality_gate_failures.append("no_logged_questions")

    end_time = datetime.now(timezone.utc)
    if error_message:
        status = "error"
    elif quality_gate_failures:
        status = "failed"
    else:
        status = "success"

    return {
        "scenario": scenario_name,
        "start_time_utc": start_time.isoformat(),
        "end_time_utc": end_time.isoformat(),
        "duration_seconds": round((end_time - start_time).total_seconds(), 2),
        "status": status,
        "error": error_message,
        "metrics": {
            "ended_normally": ended_normally,
            "forced_termination": forced_termination,
            "interviewer_turns": interviewer_turns,
            "candidate_turns": candidate_turns,
            "tool_call_count": tool_call_count,
            "tool_usage": dict(tool_usage),
            "json_parse_failures": json_parse_failures,
            **history_metrics,
            **quality_metrics,
            "quality_gate_failures": quality_gate_failures,
        },
        "transcript": transcript,
    }


async def main_async() -> None:
    parser = argparse.ArgumentParser(description="Run autonomous HR interview simulations.")
    parser.add_argument(
        "--scenario",
        default=SIMULATION_DEFAULT_SCENARIO,
        choices=sorted(SIMULATION_SCENARIO_INSTRUCTIONS.keys()),
        help="Single candidate behavior scenario to run.",
    )
    parser.add_argument(
        "--all-scenarios",
        action="store_true",
        help="Run all built-in scenarios in one batch.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=18,
        help="Maximum interviewer speaking turns before forcing stop.",
    )
    parser.add_argument(
        "--run-name",
        default="",
        help="Optional run folder name under outputs/simulations/.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress full conversation print output.",
    )
    parser.add_argument(
        "--no-transcript",
        action="store_true",
        help="Do not persist full transcript JSON files.",
    )
    parser.add_argument(
        "--skip-reports",
        action="store_true",
        help="Skip post-simulation report generation.",
    )
    args = parser.parse_args()

    print("Initializing Autonomous HR Simulation...")

    cv_path = project_root / "data" / "candidate.md"
    jd_path = project_root / "data" / "job_description.md"
    cv_content = read_file(cv_path)
    jd_content = read_file(jd_path)

    if not cv_content or not jd_content:
        print("Error: Could not find candidate.md or job_description.md in data/ folder.")
        return

    scenarios = (
        sorted(SIMULATION_SCENARIO_INSTRUCTIONS.keys())
        if args.all_scenarios
        else [args.scenario]
    )

    run_name = args.run_name or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    simulations_dir = project_root / "outputs" / "simulations"
    run_root = simulations_dir / run_name
    run_root.mkdir(parents=True, exist_ok=True)

    question_bank_source = project_root / "outputs"

    all_results: list[dict] = []
    for scenario_name in scenarios:
        scenario_dir = run_root / scenario_name
        session_outputs_dir = scenario_dir / "session_outputs"
        copied_files = _prepare_session_outputs(question_bank_source, session_outputs_dir)

        print(f"\n--- Running scenario: {scenario_name} ---")
        if copied_files == 0:
            print("Warning: No question bank files were copied. Generate questions first if needed.")

        result = await run_single_scenario(
            scenario_name=scenario_name,
            scenario_instruction=SIMULATION_SCENARIO_INSTRUCTIONS[scenario_name],
            cv_content=cv_content,
            jd_content=jd_content,
            session_outputs_dir=session_outputs_dir,
            max_turns=args.max_turns,
            verbose=not args.quiet,
        )

        scenario_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = scenario_dir / "metrics.json"
        metrics_path.write_text(
            json.dumps({k: v for k, v in result.items() if k != "transcript"}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        if not args.no_transcript:
            transcript_path = scenario_dir / "transcript.json"
            transcript_path.write_text(
                json.dumps(result["transcript"], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        if not args.skip_reports:
            reports_dir = scenario_dir / "reports"
            report_summary = await generate_reports_for_interview(
                logs_dir=session_outputs_dir,
                context_dir=session_outputs_dir,
                output_dir=reports_dir,
            )
            result["reporting"] = {
                "final_report_generated": report_summary.get("final_report_generated", False),
                "final_report_path": report_summary.get("final_report_path", ""),
                "summary_path": str(reports_dir / "analysis_summary.json"),
                "failed_or_skipped_categories": report_summary.get("failed_or_skipped_categories", 0),
            }
            if report_summary.get("final_report_generated"):
                print(f"Generated final report: {report_summary.get('final_report_path')}")
            else:
                result["metrics"].setdefault("quality_gate_failures", []).append(
                    "final_report_not_generated"
                )
                if result.get("status") != "error":
                    result["status"] = "failed"
                print(
                    "Report generation incomplete: "
                    f"{report_summary.get('final_report_error') or report_summary.get('reason', 'unknown')}"
                )
        else:
            result["reporting"] = {
                "final_report_generated": False,
                "final_report_path": "",
                "summary_path": "",
                "failed_or_skipped_categories": 0,
                "skipped": True,
            }

        monitor_entry = {
            "run_name": run_name,
            "scenario": scenario_name,
            "timestamp_utc": result["end_time_utc"],
            "status": result["status"],
            "quality_score": result["metrics"]["quality_score"],
            "ended_normally": result["metrics"]["ended_normally"],
            "repeated_questions": result["metrics"]["repeated_questions"],
            "json_parse_failures": result["metrics"]["json_parse_failures"],
            "redirect_observed": result["metrics"]["redirect_observed"],
            "final_report_generated": result.get("reporting", {}).get("final_report_generated", False),
        }
        _append_monitor_entry(simulations_dir, monitor_entry)

        all_results.append(result)
        print(
            "Scenario complete: "
            f"status={result['status']}, "
            f"score={result['metrics']['quality_score']}, "
            f"logs={result['metrics']['segments_logged']}"
        )

    completed = len(all_results)
    success = sum(1 for r in all_results if r["status"] == "success")
    avg_score = (
        round(sum(r["metrics"]["quality_score"] for r in all_results) / completed, 2)
        if completed
        else 0
    )
    summary = {
        "run_name": run_name,
        "scenarios": scenarios,
        "completed": completed,
        "successful": success,
        "failed": completed - success,
        "average_quality_score": avg_score,
        "results": [
            {
                "scenario": r["scenario"],
                "status": r["status"],
                "quality_score": r["metrics"]["quality_score"],
                "ended_normally": r["metrics"]["ended_normally"],
                "repeated_questions": r["metrics"]["repeated_questions"],
                "json_parse_failures": r["metrics"]["json_parse_failures"],
                "quality_gate_failures": r["metrics"].get("quality_gate_failures", []),
                "final_report_generated": r.get("reporting", {}).get("final_report_generated", False),
                "final_report_path": r.get("reporting", {}).get("final_report_path", ""),
            }
            for r in all_results
        ],
    }
    (run_root / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n--- Simulation batch complete ---")
    print(f"Run folder: {run_root}")
    print(f"Monitor file: {simulations_dir / 'monitor.jsonl'}")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
