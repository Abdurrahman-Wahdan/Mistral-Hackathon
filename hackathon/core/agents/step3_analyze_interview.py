import os
import sys
import json
from pathlib import Path

# Ensure project root is in pythonpath
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from langchain_core.messages import SystemMessage, HumanMessage
from hackathon.llm.factory import get_llm

OUTPUTS_DIR = project_root / "outputs"

ANALYSIS_SYSTEM_PROMPT = """
You are an expert HR Interview Evaluator. 
Your task is to analyze a candidate's responses to behavioral interview questions for a specific HR category.

You will be provided with:
1. The original category context and the questions that were generated to evaluate the candidate in this area.
2. The exact transcript of the Q&A from the live interview.

### Your Goal:
Write a comprehensive evaluation report for the candidate based ONLY on this category. 
Do not hallucinate external context. 

### Format Requirement (Markdown):
# Category Evaluation: {category_name}

## 1. Summary of Behavioral Signals
(Write a short paragraph summarizing their overall performance in this category)

## 2. Strong Points
* (Bullet points extracting concrete positive behaviors or evidence from their answers)

## 3. Areas of Concern / Red Flags
* (Bullet points noting any evasiveness, weak answers, or troubling behavioral indicators)

## 4. Final Recommendation
(A short conclusive paragraph on whether the candidate meets the standards for this specific category and why)
"""

def read_file(filepath: Path) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return ""

def main():
    print("Initializing Post-Interview Analysis Agents...\n")
    
    if not OUTPUTS_DIR.exists():
        print("Outputs directory not found. Have you run the interview yet?")
        return

    log_files = list(OUTPUTS_DIR.glob("*_logs.json"))
    if not log_files:
        print("No interview logs found (*_logs.json). Please run an interview simulation first.")
        return

    # User requested to use 'mistral-medium-latest' for consistency in HR tasks
    llm = get_llm(model_id="mistral-medium-latest", temperature=0.2)

    all_summaries = []

    for log_path in log_files:
        # Extract category from 'category_logs.json'
        # e.g. 'risk_integrity_assessment_logs.json' -> 'risk_integrity_assessment'
        category_name = log_path.name.replace("_logs.json", "")
        context_file_name = f"{category_name}.md"
        context_path = OUTPUTS_DIR / context_file_name
        
        print(f"[{category_name}] Analyzing candidate responses...")
        
        # 1. Read the Q&A logs
        qa_data = read_file(log_path)
        if not qa_data:
            print(f"  -> Skipping {category_name}: Log file is empty or missing.")
            continue
            
        try:
            qa_json = json.loads(qa_data)
            if not qa_json:
                print(f"  -> Skipping {category_name}: No Q&A pairs inside log file.")
                continue
        except json.JSONDecodeError:
            print(f"  -> Skipping {category_name}: Failed to parse JSON logs.")
            continue

        # Format conversation log elegantly for the analysis prompt
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
                # Fallback for old format
                transcript += f"CANDIDATE: {exchange.get('candidate_answer', '')}\n"
            transcript += "\n"

        # 2. Read original category questions as context — JSON takes priority over MD
        context_data = ""
        for ext in (".json", ".md"):
            context_path = OUTPUTS_DIR / f"{category_name}{ext}"
            context_data = read_file(context_path)
            if context_data:
                break
        if not context_data:
            context_data = "(No original context file found for this category.)"

        # 3. Prepare Prompt
        messages = [
            SystemMessage(content=ANALYSIS_SYSTEM_PROMPT.format(category_name=category_name.replace("_", " ").title())),
            HumanMessage(content=f"### Original Context & Questions:\n{context_data}\n\n### Interview Transcript:\n{transcript}")
        ]

        # 4. Invoke the Analyst LLM
        try:
            response = llm.invoke(messages)
            analysis_result = response.content.strip()
            
            # Save the individual category report
            report_name = f"analysis_{category_name}.md"
            report_path = OUTPUTS_DIR / report_name
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(analysis_result)
            
            print(f"  -> Saved individual report to {report_name}")
            
            # Keep for the global summary
            all_summaries.append(f"\n\n{analysis_result}")
            
        except Exception as e:
            print(f"  -> Error analyzing {category_name}: {e}")

    print("\nAll Post-Interview analyses are complete!")

if __name__ == "__main__":
    main()
