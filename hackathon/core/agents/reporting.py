import asyncio
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from hackathon.config.settings import settings
from hackathon.llm.factory import get_llm
from hackathon.llm.retry import ainvoke_with_retry
from hackathon.core.prompts.prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    ANALYSIS_USER_PROMPT,
    ANALYSIS_FINAL_SYSTEM_PROMPT,
    ANALYSIS_FINAL_USER_PROMPT,
)


def _read_file(filepath: Path) -> str:
    try:
        return filepath.read_text(encoding="utf-8")
    except Exception:
        return ""


def _build_transcript(qa_json: list[dict]) -> str:
    transcript = ""
    for i, exchange in enumerate(qa_json, 1):
        question = exchange.get("question", "")
        conversation = exchange.get("conversation", [])
        transcript += f"--- Topic {i}: {question} ---\n"
        if conversation:
            for turn in conversation:
                role = turn.get("role", "unknown").upper()
                message = turn.get("message", "")
                transcript += f"{role}: {message}\n"
        else:
            transcript += f"CANDIDATE: {exchange.get('candidate_answer', '')}\n"
        transcript += "\n"
    return transcript


def _load_context_data(category_name: str, context_dir: Path) -> str:
    for ext in (".json", ".md"):
        context_path = context_dir / f"{category_name}{ext}"
        context_data = _read_file(context_path)
        if context_data:
            return context_data
    return "(No original context file found for this category.)"


async def _analyze_single_category(
    llm: Any,
    log_path: Path,
    context_dir: Path,
    output_dir: Path,
    semaphore: asyncio.Semaphore,
) -> dict:
    category_name = log_path.name.replace("_logs.json", "")

    async with semaphore:
        qa_data = _read_file(log_path)
        if not qa_data:
            return {"category": category_name, "status": "skipped", "reason": "empty log"}

        try:
            qa_json = json.loads(qa_data)
            if not qa_json:
                return {"category": category_name, "status": "skipped", "reason": "no Q&A entries"}
        except json.JSONDecodeError:
            return {"category": category_name, "status": "skipped", "reason": "invalid JSON"}

        transcript = _build_transcript(qa_json)
        context_data = _load_context_data(category_name, context_dir)

        messages = [
            SystemMessage(
                content=ANALYSIS_SYSTEM_PROMPT.format(
                    category_name=category_name.replace("_", " ").title()
                )
            ),
            HumanMessage(
                content=ANALYSIS_USER_PROMPT.format(
                    context_data=context_data,
                    transcript=transcript,
                )
            ),
        ]

        try:
            response = await ainvoke_with_retry(llm, messages)
            analysis_result = str(response.content).strip()

            report_name = f"analysis_{category_name}.md"
            report_path = output_dir / report_name
            report_path.write_text(analysis_result, encoding="utf-8")

            return {
                "category": category_name,
                "status": "ok",
                "report_name": report_name,
                "report_path": str(report_path),
                "analysis": analysis_result,
            }
        except Exception as e:  # pragma: no cover - runtime safety
            return {"category": category_name, "status": "error", "reason": str(e)}


async def _build_final_report(llm: Any, category_reports: list[str]) -> str:
    joined_reports = "\n\n---\n\n".join(category_reports)
    messages = [
        SystemMessage(content=ANALYSIS_FINAL_SYSTEM_PROMPT),
        HumanMessage(content=ANALYSIS_FINAL_USER_PROMPT.format(category_reports=joined_reports)),
    ]
    response = await ainvoke_with_retry(llm, messages)
    return str(response.content).strip()


async def generate_reports_for_interview(
    logs_dir: Path,
    context_dir: Path | None = None,
    output_dir: Path | None = None,
    messages: list | None = None,
) -> dict:
    """Generate category and final interview reports for a given logs directory."""
    context_dir = context_dir or logs_dir
    output_dir = output_dir or logs_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    log_files = sorted(logs_dir.glob("*_logs.json"))

    if not log_files and messages and len(messages) > 2:
        import json as _json
        conversation = []
        for m in messages[2:]:
            m_type = getattr(m, "type", "")
            if m_type == "human":
                conversation.append({"role": "candidate", "message": str(getattr(m, "content", ""))})
            elif m_type == "ai":
                content = str(getattr(m, "content", ""))
                if "message_to_candidate" in content:
                    try:
                        parsed = _json.loads(content)
                        content = parsed.get("message_to_candidate", content)
                    except Exception:
                        # naive regex extraction if JSON fails
                        import re
                        match = re.search(r'"message_to_candidate"\s*:\s*"(.*?)"', content, flags=re.IGNORECASE | re.DOTALL)
                        if match:
                            content = match.group(1).replace('\\"', '"').replace("\\n", "\n")
                if content and not list(getattr(m, "tool_calls", [])):
                    conversation.append({"role": "interviewer", "message": content})
                    
        if conversation:
            fallback_path = logs_dir / "early_termination_logs.json"
            mock_json = [{
                "question": "Early termination evaluation based on partial transcript",
                "conversation": conversation
            }]
            fallback_path.write_text(_json.dumps(mock_json, ensure_ascii=False), encoding="utf-8")
            log_files = [fallback_path]

    if not log_files:
        summary = {
            "total_categories": 0,
            "successful_categories": 0,
            "failed_or_skipped_categories": 0,
            "results": [],
            "final_report_generated": False,
            "final_report_path": "",
            "reason": "no_logs",
        }
        (output_dir / "analysis_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return summary

    llm = get_llm(
        model_id=settings.HR_ANALYSIS_MODEL,
        temperature=settings.HR_ANALYSIS_TEMPERATURE,
    )

    semaphore = asyncio.Semaphore(max(1, settings.HR_ANALYSIS_CONCURRENCY))
    tasks = [
        _analyze_single_category(
            llm=llm,
            log_path=log_path,
            context_dir=context_dir,
            output_dir=output_dir,
            semaphore=semaphore,
        )
        for log_path in log_files
    ]
    results = await asyncio.gather(*tasks)

    successful = [r for r in results if r.get("status") == "ok"]
    failed = [r for r in results if r.get("status") in {"error", "skipped"}]

    final_report_generated = False
    final_report_path = ""
    final_report_error = ""

    if successful:
        category_reports = [r["analysis"] for r in successful]
        try:
            final_report = await _build_final_report(llm=llm, category_reports=category_reports)
            final_path = output_dir / "final_interview_report.md"
            final_path.write_text(final_report, encoding="utf-8")
            final_report_generated = True
            final_report_path = str(final_path)
        except Exception as e:  # pragma: no cover - runtime safety
            final_report_error = str(e)

    summary = {
        "total_categories": len(log_files),
        "successful_categories": len(successful),
        "failed_or_skipped_categories": len(failed),
        "results": results,
        "final_report_generated": final_report_generated,
        "final_report_path": final_report_path,
        "final_report_error": final_report_error,
    }

    summary_path = output_dir / "analysis_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


class PhaseScore(BaseModel):
    phase_name: str = Field(description="Name of the interview phase, e.g., 'First 5 minutes', 'Technical Deep Dive', 'Closing'")
    score: int = Field(description="Performance score for this phase (0 to 100)")


class Metric(BaseModel):
    label: str = Field(description="Name of the metric, e.g., 'Technical Depth', 'Communication', 'Problem Solving'")
    score: int = Field(description="Score out of 100")
    feedback: str = Field(description="Short sentence explaining the score")


class StructuredReview(BaseModel):
    overall_score: int = Field(description="Overall percentage score out of 100")
    summary: str = Field(description="A crisp, concise 2-3 sentence summary of the candidate's performance.")
    strengths: list[str] = Field(description="List of 3 to 5 key strengths.")
    weaknesses: list[str] = Field(description="List of 3 to 5 areas of concern or weaknesses.")
    phases: list[PhaseScore] = Field(description="Timeline phases of the interview with a performance score for each to build a chart. Roughly 3 to 5 phases.")
    detailed_metrics: list[Metric] = Field(description="3 to 5 detailed metrics representing different areas evaluated during the interview.")


async def generate_structured_review_from_report(final_report_content: str, transcript_content: str = "") -> dict:
    """Takes a raw markdown final report and transcript to extract structured data."""
    if not final_report_content.strip():
        # Fallback empty structure
        return {
            "overallScore": 0,
            "summary": "No report content available to analyze.",
            "strengths": [],
            "weaknesses": [],
            "phases": [],
            "detailed_metrics": [],
        }

    llm = get_llm(
        model_id=settings.HR_ANALYSIS_MODEL,
        temperature=0.1,  # Low temperature for strict structured extraction
    )

    system_prompt = (
        "You are an expert HR Data Extraction specialist. Given an interview markdown report "
        "AND the raw dialogue transcript, extract the candidate's performance into structured fields. "
        "Be completely objective and accurate. Evaluate their specific actions and dialogue from the log "
        "to generate robust 'phases' scores (how they did over time) and 'detailed_metrics' (specific skills). "
        "Do NOT hallucinate details not present in the text."
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Report Content:\n\n{final_report_content}\n\nTranscript:\n\n{transcript_content}"),
    ]

    extractor = llm.with_structured_output(StructuredReview)
    try:
        result = await extractor.ainvoke(messages)
        # Convert to a dict matching our frontend expectations
        return {
            "overallScore": result.overall_score,
            "summary": result.summary,
            "strengths": result.strengths,
            "weaknesses": result.weaknesses,
            "phases": [{"name": p.phase_name, "score": p.score} for p in result.phases],
            "detailed_metrics": [{"label": m.label, "score": m.score, "feedback": m.feedback} for m in result.detailed_metrics],
        }
    except Exception as e:
        print(f"Failed to extract structured data: {e}")
        return {
            "overallScore": 0,
            "summary": "Failed to parse structured review.",
            "strengths": [],
            "weaknesses": [],
            "phases": [],
            "detailed_metrics": [],
        }
