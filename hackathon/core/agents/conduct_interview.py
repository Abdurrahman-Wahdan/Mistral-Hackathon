import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in pythonpath
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage

from hackathon.llm.factory import get_llm
from hackathon.llm.retry import ainvoke_with_retry
from hackathon.config.settings import settings
from hackathon.core.prompts.prompts import (
    CONDUCT_INTERVIEW_KICKOFF_PROMPT,
    CONDUCT_INTERVIEW_SYSTEM_PROMPT,
)
from hackathon.core.tools.interviewer_tools import (
    INTERVIEWER_TOOLS,
    set_session_outputs_dir,
    reset_session_outputs_dir,
    get_logged_question_progress,
)


def _strip_json_fences(content: str) -> str:
    if content.startswith("```json") and content.endswith("```"):
        return content[7:-3].strip()
    if content.startswith("```") and content.endswith("```"):
        return content[3:-3].strip()
    return content


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


def _continuation_message(unique_logged: int) -> str:
    remaining = max(0, 3 - unique_logged)
    if remaining <= 1:
        return "Thanks for sharing. Before we conclude, I would like to ask one more behavioral question."
    return (
        "Thanks for sharing. Before we conclude, I would like to cover "
        f"{remaining} more behavioral areas."
    )


async def main_async() -> None:
    parser = argparse.ArgumentParser(description="Run interactive HR interview in terminal.")
    parser.add_argument(
        "--session-id",
        default="",
        help="Optional session id for isolated logs under outputs/sessions/<session-id>/",
    )
    args = parser.parse_args()

    print("Initializing HR Terminal Interviewer Agent...")

    session_outputs_dir = project_root / "outputs"
    if args.session_id:
        session_outputs_dir = project_root / "outputs" / "sessions" / args.session_id
    token = set_session_outputs_dir(session_outputs_dir)

    try:
        llm = get_llm(
            model_id=settings.HR_INTERVIEW_MODEL,
            temperature=settings.HR_INTERVIEW_TEMPERATURE,
        )
        llm_with_tools = llm.bind_tools(INTERVIEWER_TOOLS)

        messages = [SystemMessage(content=CONDUCT_INTERVIEW_SYSTEM_PROMPT)]

        print("\n--- Live HR Interview Started ---")
        print("(Type 'quit' or 'exit' to end the interview)\n")

        kickoff = HumanMessage(content=CONDUCT_INTERVIEW_KICKOFF_PROMPT)
        messages.append(kickoff)

        while True:
            try:
                response = await ainvoke_with_retry(llm_with_tools, messages)
                tool_calls = response.tool_calls or []
                if tool_calls:
                    messages.append(response)
                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]

                        tool_func = next((t for t in INTERVIEWER_TOOLS if t.name == tool_name), None)
                        if tool_func:
                            tool_result = tool_func.invoke(tool_args)
                            messages.append(
                                ToolMessage(
                                    name=tool_name,
                                    content=str(tool_result),
                                    tool_call_id=tool_call["id"],
                                )
                            )
                    continue

                content = _normalize_text(response.content)
                if not content:
                    fallback = (
                        "I want to make sure I understood you correctly. "
                        "Could you clarify your last point with a concrete example?"
                    )
                    print(f"\n[HR Agent]: {fallback}")
                    messages.append(AIMessage(content=fallback))
                    messages.append(SystemMessage(content=(
                        "Internal rule reminder: Your previous assistant message was empty. "
                        "Always provide a non-empty JSON response to the candidate."
                    )))
                    user_input = await asyncio.to_thread(input, "\n[Candidate]: ")
                    if user_input.lower() in ["quit", "exit"]:
                        print(f"\nEnding interview. All logs saved in '{session_outputs_dir}'")
                        break
                    messages.append(HumanMessage(content=user_input))
                    continue

                try:
                    content = _strip_json_fences(content)
                    parsed = json.loads(content)
                    agent_msg = parsed.get("message_to_candidate", content)
                    end_interview = bool(parsed.get("end_interview", False))
                    if not str(agent_msg).strip():
                        agent_msg = (
                            "I want to make sure we are aligned. "
                            "Could you share a concrete example?"
                        )
                        messages.append(SystemMessage(content=(
                            "Internal rule reminder: message_to_candidate was empty. "
                            "Always return a non-empty message."
                        )))

                    if end_interview:
                        progress = get_logged_question_progress(session_outputs_dir)
                        if progress["unique_logged"] < 3:
                            end_interview = False
                            agent_msg = _continuation_message(progress["unique_logged"])
                            messages.append(AIMessage(content=json.dumps({
                                "message_to_candidate": agent_msg,
                                "end_interview": False,
                            })))
                            messages.append(SystemMessage(content=(
                                "Internal rule reminder: You attempted to conclude early. "
                                f"Unique logged questions are {progress['unique_logged']}/3. "
                                "Continue the interview and ask a new behavioral question."
                            )))
                        else:
                            messages.append(response)
                    else:
                        messages.append(response)

                    print(f"\n[HR Agent]: {agent_msg}")

                    if end_interview:
                        print("\n--- The HR Agent has concluded the interview ---")
                        print(f"All logs saved in '{session_outputs_dir}'")
                        break

                except json.JSONDecodeError:
                    print(f"\n[HR Agent (Raw Output)]: {content}")
                    messages.append(response)

                user_input = await asyncio.to_thread(input, "\n[Candidate]: ")
                if user_input.lower() in ["quit", "exit"]:
                    print(f"\nEnding interview. All logs saved in '{session_outputs_dir}'")
                    break

                messages.append(HumanMessage(content=user_input))

            except Exception as e:  # pragma: no cover - runtime safety
                print(f"\nError occurred: {e}")
                break
    finally:
        reset_session_outputs_dir(token)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
