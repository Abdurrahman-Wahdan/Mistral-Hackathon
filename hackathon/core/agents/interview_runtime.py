import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from hackathon.config.settings import settings
from hackathon.core.agents.reporting import generate_reports_for_interview
from hackathon.core.prompts.prompts import (
    CONDUCT_INTERVIEW_KICKOFF_PROMPT,
    CONDUCT_INTERVIEW_SYSTEM_PROMPT,
)
from hackathon.core.tools.interviewer_tools import (
    INTERVIEWER_TOOLS,
    get_logged_question_progress,
    reset_session_outputs_dir,
    set_session_outputs_dir,
)
from hackathon.llm.factory import get_llm
from hackathon.llm.retry import ainvoke_with_retry

# Keep path handling local to this module.
project_root = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = project_root / "data"
JOB_DESCRIPTIONS_DIR = DATA_DIR / "job_descriptions"

JOB_TITLE_TO_DESCRIPTION_FILE = {
    "software engineer": "software_engineer.md",
    "data scientist": "data_scientist.md",
    "product manager": "product_manager.md",
    "ux designer": "ux_designer.md",
    "devops engineer": "devops_engineer.md",
    "ai engineer": "ai_engineer.md",
    "marketing manager": "marketing_manager.md",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _strip_json_fences(content: str) -> str:
    if content.startswith("```json") and content.endswith("```"):
        return content[7:-3].strip()
    if content.startswith("```") and content.endswith("```"):
        return content[3:-3].strip()
    return content


def _extract_json_like_fields(content: str) -> tuple[str, bool] | None:
    match = re.search(
        r'"message_to_candidate"\s*:\s*"(?P<msg>.*?)"\s*,\s*"end_interview"\s*:\s*(?P<end>true|false)',
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    msg = match.group("msg")
    msg = msg.replace('\\"', '"').replace("\\n", "\n").strip()
    end_interview = match.group("end").lower() == "true"
    return msg, end_interview


def _continuation_message(unique_logged: int) -> str:
    remaining = max(0, 3 - unique_logged)
    if remaining <= 1:
        return "Thanks for sharing. Before we conclude, I would like to ask one more behavioral question."
    return (
        "Thanks for sharing. Before we conclude, I would like to cover "
        f"{remaining} more behavioral areas."
    )


def _is_question_source_file(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix in {".json", ".md"}
        and not path.name.endswith("_logs.json")
        and not path.name.startswith("analysis_")
        and not path.name.startswith("simulation_")
        and not path.name.startswith("final_")
        and path.name != "question_bank.json"
        and path.name not in {"job_description.md", "candidate.md", "company_culture.md"}
    )


def _bootstrap_session_questions(session_outputs_dir: Path) -> None:
    session_outputs_dir.mkdir(parents=True, exist_ok=True)
    if any(_is_question_source_file(p) for p in session_outputs_dir.iterdir()):
        return

    source_dir = project_root / "outputs"
    if not source_dir.exists():
        return

    for src in source_dir.iterdir():
        if _is_question_source_file(src):
            target = session_outputs_dir / src.name
            if not target.exists():
                target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _select_job_description_source(job_title: str | None) -> Path:
    if job_title:
        key = job_title.strip().lower()
        mapped = JOB_TITLE_TO_DESCRIPTION_FILE.get(key)
        if mapped:
            candidate = JOB_DESCRIPTIONS_DIR / mapped
            if candidate.exists():
                return candidate
    # Backward-compatible default.
    return DATA_DIR / "job_description.md"


def _materialize_session_job_description(outputs_dir: Path, job_title: str | None) -> None:
    source = _select_job_description_source(job_title)
    if not source.exists():
        return
    (outputs_dir / "job_description.md").write_text(
        source.read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def _extract_highlights(markdown: str, max_items: int = 6) -> list[str]:
    highlights: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("- ", "* ")):
            highlights.append(stripped[2:].strip())
        elif re.match(r"^\d+\.\s+", stripped):
            highlights.append(re.sub(r"^\d+\.\s+", "", stripped).strip())
        if len(highlights) >= max_items:
            break
    return highlights


@dataclass
class SessionState:
    session_id: str
    outputs_dir: Path
    messages: list = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    turn_count: int = 0
    ended: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class InterviewSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._sessions_lock = asyncio.Lock()
        llm = get_llm(
            model_id=settings.HR_INTERVIEW_MODEL,
            temperature=settings.HR_INTERVIEW_TEMPERATURE,
        )
        self._interviewer_with_tools = llm.bind_tools(INTERVIEWER_TOOLS)

    def _new_session_outputs_dir(self, session_id: str) -> Path:
        return project_root / "outputs" / "sessions" / session_id

    async def create_session(
        self,
        session_id: str | None = None,
        job_title: str | None = None,
    ) -> tuple[SessionState, str]:
        sid = session_id.strip() if isinstance(session_id, str) and session_id.strip() else f"session_{uuid4().hex[:12]}"
        outputs_dir = self._new_session_outputs_dir(sid)
        _bootstrap_session_questions(outputs_dir)
        _materialize_session_job_description(outputs_dir, job_title)

        kickoff = CONDUCT_INTERVIEW_KICKOFF_PROMPT
        if job_title and job_title.strip():
            kickoff = (
                f"{CONDUCT_INTERVIEW_KICKOFF_PROMPT}\n\n"
                f"Candidate target role: {job_title.strip()}"
            )

        state = SessionState(
            session_id=sid,
            outputs_dir=outputs_dir,
            messages=[
                SystemMessage(content=CONDUCT_INTERVIEW_SYSTEM_PROMPT),
                HumanMessage(content=kickoff),
            ],
        )

        async with self._sessions_lock:
            self._sessions[sid] = state

        assistant_message, end_interview = await self._generate_assistant_turn(state)
        if end_interview:
            # Keep state sane; the runtime already enforces 3 logged questions before ending.
            state.ended = True
        return state, assistant_message

    async def get_session(self, session_id: str) -> SessionState | None:
        async with self._sessions_lock:
            return self._sessions.get(session_id)

    async def process_turn(self, session_id: str, candidate_message: str) -> dict:
        state = await self.get_session(session_id)
        if state is None:
            raise KeyError(f"session '{session_id}' not found")

        async with state.lock:
            if state.ended:
                return {
                    "session_id": state.session_id,
                    "assistant_message": "This interview session has already ended.",
                    "end_interview": True,
                    "turn_count": state.turn_count,
                    "progress": get_logged_question_progress(state.outputs_dir),
                }

            candidate_message = (candidate_message or "").strip()
            if candidate_message:
                state.messages.append(HumanMessage(content=candidate_message))

            assistant_message, end_interview = await self._generate_assistant_turn(state)
            state.turn_count += 1
            state.updated_at = _utc_now_iso()
            if end_interview:
                state.ended = True

            return {
                "session_id": state.session_id,
                "assistant_message": assistant_message,
                "end_interview": end_interview,
                "turn_count": state.turn_count,
                "progress": get_logged_question_progress(state.outputs_dir),
            }

    async def finish_session(self, session_id: str, force: bool = False) -> dict:
        state = await self.get_session(session_id)
        if state is None:
            raise KeyError(f"session '{session_id}' not found")

        async with state.lock:
            if not force and not state.ended:
                # Allow graceful finish even if user ends early.
                state.ended = True

            reports_dir = state.outputs_dir / "reports"
            summary = await generate_reports_for_interview(
                logs_dir=state.outputs_dir,
                context_dir=project_root / "outputs",
                output_dir=reports_dir,
            )
            state.updated_at = _utc_now_iso()
            return {
                "session_id": state.session_id,
                "ended": state.ended,
                "turn_count": state.turn_count,
                "outputs_dir": str(state.outputs_dir),
                "reports_dir": str(reports_dir),
                "summary": summary,
            }

    async def build_review_payload(self, session_id: str, job_title: str = "") -> dict:
        state = await self.get_session(session_id)
        if state is None:
            raise KeyError(f"session '{session_id}' not found")

        reports_dir = state.outputs_dir / "reports"
        final_report_path = reports_dir / "final_interview_report.md"
        summary_path = reports_dir / "analysis_summary.json"

        if not final_report_path.exists():
            await self.finish_session(session_id, force=True)

        report_content = ""
        if final_report_path.exists():
            report_content = final_report_path.read_text(encoding="utf-8")

        analysis_summary: dict[str, Any] = {}
        if summary_path.exists():
            try:
                analysis_summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                analysis_summary = {}

        highlights = _extract_highlights(report_content)
        if not highlights:
            results = analysis_summary.get("results", []) if isinstance(analysis_summary, dict) else []
            for item in results:
                if item.get("status") == "ok":
                    highlights.append(f"Category analyzed: {item.get('category', 'unknown')}")
                elif item.get("status") == "error":
                    highlights.append(f"Analysis error in {item.get('category', 'unknown')}")
            highlights = highlights[:6]

        summary_text = ""
        for line in report_content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            summary_text = stripped
            break
        if not summary_text:
            role = job_title.strip() or "the selected role"
            summary_text = (
                f"Interview analysis for {role} was generated. "
                "Review the detailed report for strengths and improvement areas."
            )

        created_at = _utc_now_iso()
        if final_report_path.exists():
            created_at = datetime.fromtimestamp(final_report_path.stat().st_mtime, tz=timezone.utc).isoformat()

        slug = _safe_slug(job_title or state.session_id or "interview")
        file_name = f"{slug or 'interview'}-review-report.md"
        if final_report_path.exists():
            file_name = final_report_path.name

        return {
            "summary": summary_text,
            "analysisHighlights": highlights or [
                "Detailed report was generated.",
                "No bullet highlights were extracted automatically.",
            ],
            "report": {
                "id": f"report-{session_id}",
                "fileName": file_name,
                "createdAt": created_at,
                "mimeType": "text/markdown",
                "content": report_content or "Report content is empty.",
            },
        }

    async def _generate_assistant_turn(self, state: SessionState) -> tuple[str, bool]:
        while True:
            token = set_session_outputs_dir(state.outputs_dir)
            try:
                response = await ainvoke_with_retry(self._interviewer_with_tools, state.messages)
                tool_calls = response.tool_calls or []
                if tool_calls:
                    state.messages.append(response)
                    for tool_call in tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        tool_func = next((t for t in INTERVIEWER_TOOLS if t.name == tool_name), None)
                        if tool_func is None:
                            continue
                        tool_result = tool_func.invoke(tool_args)
                        state.messages.append(
                            ToolMessage(
                                name=tool_name,
                                content=str(tool_result),
                                tool_call_id=tool_call["id"],
                            )
                        )
                    continue
            finally:
                reset_session_outputs_dir(token)

            content = _normalize_text(response.content)
            if not content:
                fallback = (
                    "I want to make sure we are aligned. "
                    "Could you clarify your last point with a concrete example?"
                )
                state.messages.append(AIMessage(content=fallback))
                state.messages.append(SystemMessage(content=(
                    "Internal rule reminder: previous assistant message was empty. "
                    "Always provide a non-empty JSON response."
                )))
                return fallback, False

            content = _strip_json_fences(content)
            end_interview = False
            try:
                parsed = json.loads(content)
                assistant_message = str(parsed.get("message_to_candidate", content)).strip()
                end_interview = bool(parsed.get("end_interview", False))
            except json.JSONDecodeError:
                extracted = _extract_json_like_fields(content)
                if extracted is not None:
                    assistant_message, end_interview = extracted
                else:
                    assistant_message = content

            if not assistant_message:
                assistant_message = "I want to make sure we are aligned. Could you share a concrete example?"
                state.messages.append(SystemMessage(content=(
                    "Internal rule reminder: message_to_candidate was empty. "
                    "Always return a non-empty message."
                )))

            if end_interview:
                progress = get_logged_question_progress(state.outputs_dir)
                if progress["unique_logged"] < 3:
                    end_interview = False
                    assistant_message = _continuation_message(progress["unique_logged"])
                    state.messages.append(AIMessage(content=json.dumps({
                        "message_to_candidate": assistant_message,
                        "end_interview": False,
                    })))
                    state.messages.append(SystemMessage(content=(
                        "Internal rule reminder: attempted to conclude early. "
                        f"Unique logged questions are {progress['unique_logged']}/3. "
                        "Continue and ask a new behavioral question."
                    )))
                else:
                    state.messages.append(response)
            else:
                state.messages.append(response)

            return assistant_message, end_interview
