import os
import sys
from pathlib import Path
import json

# Ensure project root is in pythonpath
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from hackathon.core.agents.graph import build_interview_graph
from hackathon.config.settings import settings

def load_document(filename: str) -> str:
    path = project_root / "data" / filename
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Could not find {path}")
        return ""

def main():
    print("Loading HR documents...")
    cv_content = load_document("candidate.md")
    jd_content = load_document("job_description.md")
    culture_content = load_document("company_culture.md")
    
    if not cv_content or not jd_content or not culture_content:
        print("Missing required documents in 'data/' directory. Exiting.")
        return
        
    print("Initializing LangGraph automation...")
    app = build_interview_graph()
    
    # Initialize the state variable.
    # We pass an empty dict for generated_questions as it will be populated.
    input_state = {
        "cv_content": cv_content,
        "jd_content": jd_content,
        "culture_content": culture_content,
        "generated_questions": {}
    }
    
    print("Running Mistral HR Agents in parallel... This may take a minute.")
    
    # Run the graph
    final_state = app.invoke(input_state)
    
    print("\n--- Generation Complete ---\n")
    
    output_dir = project_root / "outputs"
    
    # Ensure directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write out each agent's output into a separate file
    questions_dict = final_state.get("generated_questions", {})
    for agent_name, questions in questions_dict.items():
        # Clean filename: replace spaces and ampersands
        safe_name = agent_name.replace(" & ", "_").replace(" ", "_").lower()
        output_file = output_dir / f"{safe_name}.json"
        
        output_data = {
            "category": agent_name,
            "questions": questions
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
            
        print(f"Saved {agent_name} guide to: {output_file}")


if __name__ == "__main__":
    main()
