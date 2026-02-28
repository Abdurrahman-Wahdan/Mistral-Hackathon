import os
import sys
import json
from pathlib import Path

# Ensure project root is in pythonpath
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from hackathon.llm.factory import get_llm
from hackathon.core.tools.interviewer_tools import INTERVIEWER_TOOLS, summarize_memory
from hackathon.core.agents.step2_conduct_interview import SYSTEM_PROMPT as INTERVIEWER_PROMPT

def read_file(filepath: Path) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

CANDIDATE_SYSTEM_PROMPT = """
You are a job candidate participating in an HR interview.
Your background is described in the provided CV.
You are applying for the role described in the provided Job Description.

### Your Goal:
Answer the HR Interviewer's questions naturally, as if you were a real human participating in a chat-based text interview.
Stay in character based on your CV.
Answer the behavioral questions using the STAR format (Situation, Task, Action, Result) where appropriate, but keep it conversational and concise. Do NOT give walls of text. Provide natural, human-length responses.
Do not output JSON. Just output plain text responses as the candidate.

### Context Documents:
**Your CV:**
{cv_content}

**Target Job Description:**
{jd_content}
"""

def main():
    print("Initializing Autonomous HR Simulation...")
    
    cv_path = project_root / "data" / "candidate.md"
    jd_path = project_root / "data" / "job_description.md"
    
    cv_content = read_file(cv_path)
    jd_content = read_file(jd_path)
    
    if not cv_content or not jd_content:
        print("Error: Could not find candidate.md or job_description.md in data/ folder.")
        return

    # Initialize Interviewer Agent (Mistral Large for strong tool calling & JSON)
    interviewer_llm = get_llm(model_id="mistral-large-latest", temperature=0.1)
    interviewer_with_tools = interviewer_llm.bind_tools(INTERVIEWER_TOOLS)
    interviewer_messages = [SystemMessage(content=INTERVIEWER_PROMPT)]
    
    # Initialize Candidate Agent
    candidate_llm = get_llm(model_id="mistral-large-latest", temperature=0.5)
    formatted_candidate_prompt = CANDIDATE_SYSTEM_PROMPT.format(
        cv_content=cv_content,
        jd_content=jd_content
    )
    candidate_messages = [SystemMessage(content=formatted_candidate_prompt)]
    
    print("\n--- Autonomous AI Interview Started ---")
    
    # Kick off the interviewer
    kickoff = HumanMessage(content="The candidate has joined the terminal. Please greet them naturally to start the conversation. Do not jump straight into interview questions yet. REMEMBER to output strictly JSON!")
    interviewer_messages.append(kickoff)
    
    while True:
        try:
            # ---------------------------
            # INTERVIEWER TURN
            # ---------------------------
            response = interviewer_with_tools.invoke(interviewer_messages)
            interviewer_messages.append(response)
            
            # Handle tool calls for the interviewer
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    
                    tool_func = next((t for t in INTERVIEWER_TOOLS if t.name == tool_name), None)
                    if tool_func:
                        tool_result = tool_func.invoke(tool_args)
                        interviewer_messages.append(ToolMessage(
                            name=tool_name,
                            content=str(tool_result),
                            tool_call_id=tool_call["id"]
                        ))
                continue # Loop back to let the interviewer process the tool result
            
            # Textual response from Interviewer
            content = response.content.strip()
            
            agent_msg = ""
            end_interview = False
            
            try:
                # Strip markdown codeblocks if mistral generated them
                if content.startswith("```json"):
                    content = content[7:-3].strip()
                elif content.startswith("```"):
                    content = content[3:-3].strip()
                    
                parsed = json.loads(content)
                agent_msg = parsed.get("message_to_candidate", content)
                end_interview = parsed.get("end_interview", False)
                print(f"\n[HR Agent]: {agent_msg}")
            except json.JSONDecodeError:
                print(f"\n[HR Agent (Raw Output)]: {content}")
                agent_msg = content
                
            if end_interview:
                print("\n--- The HR Agent has concluded the interview ---")
                print("All logs saved in 'outputs/' directory.")
                break
                
            # ---------------------------
            # CANDIDATE TURN
            # ---------------------------
            candidate_messages.append(HumanMessage(content=agent_msg))
            candidate_response = candidate_llm.invoke(candidate_messages)
            candidate_msg = candidate_response.content.strip()
            
            print(f"\n[Candidate Agent]: {candidate_msg}")
            
            # Feed candidate response back into histories
            candidate_messages.append(candidate_response)
            interviewer_messages.append(HumanMessage(content=candidate_msg))
            
        except Exception as e:
            print(f"\nError occurred during simulation: {e}")
            break

if __name__ == "__main__":
    main()
