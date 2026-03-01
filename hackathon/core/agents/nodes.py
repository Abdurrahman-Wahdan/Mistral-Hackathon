import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage

from hackathon.llm.factory import get_llm
from hackathon.llm.retry import ainvoke_with_retry
from hackathon.config.settings import settings
from hackathon.core.agents.state import InterviewState
from hackathon.core.prompts.prompts import (
    CULTURAL_ALIGNMENT_PROMPT,
    CULTURAL_ALIGNMENT_USER_PROMPT,
    BEHAVIORAL_COMPETENCIES_PROMPT,
    BEHAVIORAL_COMPETENCIES_USER_PROMPT,
    MOTIVATION_TRAJECTORY_PROMPT,
    MOTIVATION_TRAJECTORY_USER_PROMPT,
    LEARNING_AGILITY_PROMPT,
    LEARNING_AGILITY_USER_PROMPT,
    EMOTIONAL_INTELLIGENCE_PROMPT,
    EMOTIONAL_INTELLIGENCE_USER_PROMPT,
    RISK_INTEGRITY_PROMPT,
    RISK_INTEGRITY_USER_PROMPT,
)

logger = logging.getLogger(__name__)


def _extract_text(content: Any) -> str:
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


def _strip_fences(text: str) -> str:
    if text.startswith("```json") and text.endswith("```"):
        return text[7:-3].strip()
    if text.startswith("```") and text.endswith("```"):
        return text[3:-3].strip()
    return text


def _normalize_questions(raw_text: str) -> list[str]:
    clean = _strip_fences(raw_text)

    # Preferred format: {"questions": ["...", "...", "..."]}
    try:
        parsed = json.loads(clean)
        if isinstance(parsed, dict):
            questions = parsed.get("questions", [])
            if isinstance(questions, list):
                normalized = [str(q).strip() for q in questions if str(q).strip()]
                return normalized[:3]
    except json.JSONDecodeError:
        pass

    # Fallback: extract list-like lines.
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    extracted: list[str] = []
    for line in lines:
        candidate = re.sub(r"^[-*\d\.)\s]+", "", line).strip()
        if not candidate:
            continue
        if len(candidate) < 15:
            continue
        extracted.append(candidate)
        if len(extracted) == 3:
            break

    if extracted:
        return extracted

    return [clean] if clean else []


def _render_prompt_template(template: str, state: InterviewState) -> str:
    """
    Render only known placeholders and leave any other braces untouched.
    This avoids KeyError when prompt text includes JSON examples such as:
    {"questions": ["..."]}.
    """
    rendered = str(template)
    replacements = {
        "{cv_content}": state.get("cv_content", ""),
        "{jd_content}": state.get("jd_content", ""),
        "{culture_content}": state.get("culture_content", ""),
    }
    for key, value in replacements.items():
        rendered = rendered.replace(key, str(value))
    return rendered


async def _generate_questions(
    state: InterviewState,
    agent_name: str,
    prompt_template: str,
    user_prompt: str,
) -> dict:
    """Helper to format prompt, call Mistral LLM, and update state."""
    logger.info(f"Running Agent: {agent_name}")

    formatted_sys = _render_prompt_template(prompt_template, state)

    messages = [
        SystemMessage(content=formatted_sys),
        HumanMessage(content=user_prompt),
    ]

    result_payload: dict[str, Any] = {
        "category": agent_name,
        "questions": [],
        "question_count": 0,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "raw_response": "",
        "error": "",
    }

    try:
        llm = get_llm(
            model_id=settings.HR_QUESTION_GEN_MODEL,
            temperature=settings.HR_QUESTION_GEN_TEMPERATURE,
        )
        response = await ainvoke_with_retry(llm, messages)
        raw_response = _extract_text(response.content)
        questions = _normalize_questions(raw_response)

        result_payload["raw_response"] = raw_response
        result_payload["questions"] = questions
        result_payload["question_count"] = len(questions)
    except Exception as e:  # pragma: no cover - runtime safety
        logger.error(f"Error calling LLM in {agent_name}: {e}")
        result_payload["error"] = str(e)

    return {"generated_questions": {agent_name: result_payload}}


async def cultural_alignment_node(state: InterviewState):
    return await _generate_questions(
        state,
        "Cultural Alignment & Values Fit",
        CULTURAL_ALIGNMENT_PROMPT,
        CULTURAL_ALIGNMENT_USER_PROMPT,
    )


async def behavioral_competencies_node(state: InterviewState):
    return await _generate_questions(
        state,
        "Core Behavioral Competencies",
        BEHAVIORAL_COMPETENCIES_PROMPT,
        BEHAVIORAL_COMPETENCIES_USER_PROMPT,
    )


async def motivation_trajectory_node(state: InterviewState):
    return await _generate_questions(
        state,
        "Motivation & Career Trajectory",
        MOTIVATION_TRAJECTORY_PROMPT,
        MOTIVATION_TRAJECTORY_USER_PROMPT,
    )


async def learning_agility_node(state: InterviewState):
    return await _generate_questions(
        state,
        "Learning Agility & Growth Mindset",
        LEARNING_AGILITY_PROMPT,
        LEARNING_AGILITY_USER_PROMPT,
    )


async def emotional_intelligence_node(state: InterviewState):
    return await _generate_questions(
        state,
        "Interpersonal & Emotional Intelligence",
        EMOTIONAL_INTELLIGENCE_PROMPT,
        EMOTIONAL_INTELLIGENCE_USER_PROMPT,
    )


async def risk_integrity_node(state: InterviewState):
    return await _generate_questions(
        state,
        "Risk & Integrity Assessment",
        RISK_INTEGRITY_PROMPT,
        RISK_INTEGRITY_USER_PROMPT,
    )
