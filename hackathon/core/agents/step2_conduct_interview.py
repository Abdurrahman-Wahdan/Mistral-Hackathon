import os
import sys
import json
from pathlib import Path

# Ensure project root is in pythonpath
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from hackathon.llm.factory import get_llm
from hackathon.config.settings import settings
from hackathon.core.tools.interviewer_tools import INTERVIEWER_TOOLS, summarize_memory

SYSTEM_PROMPT = """
You are the company's Interactive HR Agent. You are conducting a live terminal interview with a candidate.
Your goal is to conduct a natural, free-flowing HR interview.

### Your Workflow:
1. GREETING: Start the conversation naturally (e.g., "Hello, welcome to the interview..."). Do NOT ask a hardcoded question immediately. Build rapport first.
2. PREPARATION: Based on the conversation flow, use the 'list_categories' tool to see what HR areas we are evaluating. Then use 'read_questions' to fetch potential questions for a specific category.
3. ASKING: Before selecting a question to ask, ALWAYS call the 'get_asked_questions' tool first to see which questions have already been logged. Never ask a question that is already in the logged list. Seamlessly weave ONE new question at a time into the conversation. Let the interview flow naturally depending on their answers. Do not rush.
4. LOGGING: When you are done exploring a question topic (i.e., you are ready to move to a new question or conclude), call the 'log_qa' tool. Pass the opening question and the FULL conversation thread for that topic as a list of {role, message} objects — include every follow-up and clarification exchange between you and the candidate from the moment you asked the question until you are moving on. 'role' must be either 'hr' or 'candidate'.
5. CONCLUDING: You are in charge of the interview. When you feel you have gathered enough behavioral signals (e.g., after 3-4 detailed questions), gracefully conclude the interview, thank the candidate, and set "end_interview": true in your JSON output.

### Output format STRICT REQUIREMENT:
You must communicate with the user ONLY using valid JSON. The terminal script will parse your JSON and display the message.

Whenever you want to speak to the candidate, your response MUST be a JSON object like this:
{
    "message_to_candidate": "Hello, how is your day going? I'm excited to speak with you today.",
    "end_interview": false
}

If you are just calling tools internally, you don't need to output this JSON, but whenever you speak to the candidate, output standard JSON. Do not include markdown code blocks around the JSON (e.g. no ```json). Return RAW JSON ONLY.

Keep your tone professional, empathetic, human-like, and strictly HR-focused. DO NOT ASK TECHNICAL QUESTIONS.
"""

def main():
    print("Initializing HR Terminal Interviewer Agent...")
    
    # Needs Mistral Large for strong tool calling and strict JSON output compliance
    llm = get_llm(model_id="mistral-large-latest", temperature=0.1)
    llm_with_tools = llm.bind_tools(INTERVIEWER_TOOLS)
    
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    
    print("\n--- Live HR Interview Started ---")
    print("(Type 'quit' or 'exit' to end the interview)\n")
    
    # Initial kick-off so the LLM starts speaking first
    kickoff = HumanMessage(content="The candidate has joined the terminal. Please greet them naturally to start the conversation. Do not jump straight into interview questions yet. REMEMBER to output strictly JSON!")
    messages.append(kickoff)
    
    while True:
        try:
            response = llm_with_tools.invoke(messages)
            messages.append(response)
            
            # Handle tool calls if any
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    
                    # dispatch to correct tool
                    tool_func = next((t for t in INTERVIEWER_TOOLS if t.name == tool_name), None)
                    if tool_func:
                        tool_result = tool_func.invoke(tool_args)
                        messages.append(ToolMessage(
                            name=tool_name,
                            content=str(tool_result),
                            tool_call_id=tool_call["id"]
                        ))
                # if tools were called, loop back to let model process tool output
                continue

            # Process textual response (should be JSON due to prompt constraint)
            content = response.content.strip()
            
            # Try to parse JSON output to get the message to candidate
            try:
                # Remove markdown fences if the model forgot
                if content.startswith("```json"):
                    content = content[7:-3].strip()
                elif content.startswith("```"):
                    content = content[3:-3].strip()
                    
                parsed = json.loads(content)
                agent_msg = parsed.get("message_to_candidate", content)
                end_interview = parsed.get("end_interview", False)
                
                print(f"\n[HR Agent]: {agent_msg}")
                
                if end_interview:
                    print("\n--- The HR Agent has concluded the interview ---")
                    print("All logs saved in 'outputs/' directory.")
                    break
                    
            except json.JSONDecodeError:
                # fallback if it messed up the json
                print(f"\n[HR Agent (Raw Output)]: {content}")
            
            # Get user input
            user_input = input("\n[Candidate]: ")
            if user_input.lower() in ['quit', 'exit']:
                print("\nEnding interview. All logs saved in 'outputs/' directory.")
                break
                
            messages.append(HumanMessage(content=user_input))

        except Exception as e:
            print(f"\nError occurred: {e}")
            break

if __name__ == "__main__":
    main()
