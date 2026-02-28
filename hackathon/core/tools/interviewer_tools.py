import json
from pathlib import Path
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

# Ensure project root is available to locate data and outputs
project_root = Path(__file__).resolve().parent.parent.parent.parent

OUTPUTS_DIR = project_root / "outputs"
DATA_DIR = project_root / "data"

@tool
def read_document(doc_name: str) -> str:
    """Read a document from the data directory. Valid docs are 'cv', 'jd', and 'culture'."""
    mapping = {
        "cv": "candidate.md",
        "jd": "job_description.md",
        "culture": "company_culture.md"
    }
    file_name = mapping.get(doc_name)
    if not file_name:
        return f"Error: document '{doc_name}' not found. Use 'cv', 'jd', or 'culture'."
    
    path = DATA_DIR / file_name
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: Could not read {file_name}"

@tool
def list_categories() -> str:
    """List all available HR interview question categories."""
    if not OUTPUTS_DIR.exists():
        return "Outputs directory not found."
    
    # Support both .json and .md question files, but exclude log files and analysis files
    files = [
        f.name for f in OUTPUTS_DIR.iterdir()
        if (f.suffix in (".json", ".md"))
        and not f.name.endswith("_logs.json")
        and not f.name.startswith("analysis_")
    ]
    return json.dumps({"categories": files})

@tool
def read_questions(category_file: str) -> str:
    """Read the questions for a specific category from the outputs directory."""
    path = OUTPUTS_DIR / category_file
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: {category_file} not found."

@tool
def get_asked_questions() -> str:
    """Returns all questions already asked during this interview session, grouped by category.
    
    Call this before asking a new question to make sure you don't repeat yourself.
    """
    if not OUTPUTS_DIR.exists():
        return json.dumps({"asked_questions": []})
    
    asked = {}
    for log_file in OUTPUTS_DIR.glob("*_logs.json"):
        category = log_file.stem.replace("_logs", "")
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                entries = json.load(f)
            asked[category] = [entry.get("question", "") for entry in entries]
        except (json.JSONDecodeError, Exception):
            asked[category] = []
    
    if not asked:
        return json.dumps({"asked_questions": [], "message": "No questions have been asked yet."})
    
    return json.dumps({"asked_questions": asked}, ensure_ascii=False, indent=2)

@tool
def log_qa(category_file: str, question: str, conversation: list) -> str:
    """Log the full conversation segment for a question into a JSON log file.

    Call this when you are done with a particular question and are ready to move on.
    
    Args:
        category_file: The category file name (e.g. 'risk_integrity_assessment.json')
        question: The opening question you asked to start this segment.
        conversation: The full back-and-forth exchange for this question segment.
                      MUST be a list of dictionaries. Each dictionary MUST have exactly two keys:
                      'role' (string: 'hr' or 'candidate') and 'message' (string: the actual text).
                      Example: [{"role": "hr", "message": "..."}, {"role": "candidate", "message": "..."}]
    """
    # Strip any extension (.json or .md) so log files are always category_logs.json
    stem = Path(category_file).stem
    log_file_name = f"{stem}_logs.json"
    log_file = OUTPUTS_DIR / log_file_name
    
    entry = {
        "question": question,
        "conversation": conversation if isinstance(conversation, list) else []
    }
    
    logs = []
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            logs = loaded if isinstance(loaded, list) else []
        except json.JSONDecodeError:
            logs = []
            
    logs.append(entry)
    
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=4, ensure_ascii=False)
        
    return f"Successfully logged conversation segment to {log_file_name}"

# Export all tools for the agent to bind
INTERVIEWER_TOOLS = [read_document, list_categories, read_questions, get_asked_questions, log_qa]

def summarize_memory(messages: list, llm, system_prompt: str) -> list:
    """
    Context summarization is currently disabled.
    Returns the full message history unchanged.
    """
    return messages
