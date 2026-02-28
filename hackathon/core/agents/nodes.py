import logging
from langchain_core.messages import SystemMessage, HumanMessage
from hackathon.llm.factory import get_llm
from hackathon.core.agents.state import InterviewState
from hackathon.core.prompts.prompts import (
    CULTURAL_ALIGNMENT_PROMPT,
    BEHAVIORAL_COMPETENCIES_PROMPT,
    MOTIVATION_TRAJECTORY_PROMPT,
    LEARNING_AGILITY_PROMPT,
    EMOTIONAL_INTELLIGENCE_PROMPT,
    RISK_INTEGRITY_PROMPT,
)

logger = logging.getLogger(__name__)

def _generate_questions(state: InterviewState, agent_name: str, prompt_template: str) -> dict:
    """Helper to format prompt, call Mistral LLM, and update state."""
    logger.info(f"Running Agent: {agent_name}")
    
    formatted_sys = prompt_template.format(
        cv_content=state["cv_content"],
        jd_content=state["jd_content"],
        culture_content=state["culture_content"],
    )
    
    # We use a human message to kick off the generation based on the specific system context
    messages = [
        SystemMessage(content=formatted_sys),
        HumanMessage(content="Please generate the targeted interview questions now.")
    ]
    
    try:
        # The user requested mistral-medium-latest for all generic HR tasks
        llm = get_llm(model_id="mistral-medium-latest", temperature=0.2)
        response = llm.invoke(messages)
        result = response.content
    except Exception as e:
        logger.error(f"Error calling LLM in {agent_name}: {e}")
        result = f"Error generating questions: {e}"
        
    return {"generated_questions": {agent_name: result}}

def cultural_alignment_node(state: InterviewState):
    return _generate_questions(state, "Cultural Alignment & Values Fit", CULTURAL_ALIGNMENT_PROMPT)

def behavioral_competencies_node(state: InterviewState):
    return _generate_questions(state, "Core Behavioral Competencies", BEHAVIORAL_COMPETENCIES_PROMPT)

def motivation_trajectory_node(state: InterviewState):
    return _generate_questions(state, "Motivation & Career Trajectory", MOTIVATION_TRAJECTORY_PROMPT)

def learning_agility_node(state: InterviewState):
    return _generate_questions(state, "Learning Agility & Growth Mindset", LEARNING_AGILITY_PROMPT)

def emotional_intelligence_node(state: InterviewState):
    return _generate_questions(state, "Interpersonal & Emotional Intelligence", EMOTIONAL_INTELLIGENCE_PROMPT)

def risk_integrity_node(state: InterviewState):
    return _generate_questions(state, "Risk & Integrity Assessment", RISK_INTEGRITY_PROMPT)
