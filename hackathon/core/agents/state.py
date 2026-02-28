from typing import TypedDict, Annotated, Dict
import operator

class InterviewState(TypedDict):
    """
    The state for the LangGraph HR Interview automation.
    """
    # Inputs
    cv_content: str
    jd_content: str
    culture_content: str
    
    # Outputs: dictionary matching agent name to their generated questions
    # Using 'operator.ior' to update the dictionary as nodes run in parallel
    generated_questions: Annotated[Dict[str, str], operator.ior]
