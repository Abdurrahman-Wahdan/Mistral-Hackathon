from langgraph.graph import StateGraph, END
from hackathon.core.agents.state import InterviewState
from hackathon.core.agents.nodes import (
    cultural_alignment_node,
    behavioral_competencies_node,
    motivation_trajectory_node,
    learning_agility_node,
    emotional_intelligence_node,
    risk_integrity_node
)

def build_interview_graph():
    """Build and compile the parallel LangGraph workflow."""
    workflow = StateGraph(InterviewState)
    
    # Add the 6 specialized agent nodes
    workflow.add_node("cultural_agent", cultural_alignment_node)
    workflow.add_node("behavioral_agent", behavioral_competencies_node)
    workflow.add_node("motivation_agent", motivation_trajectory_node)
    workflow.add_node("learning_agent", learning_agility_node)
    workflow.add_node("emotional_agent", emotional_intelligence_node)
    workflow.add_node("risk_agent", risk_integrity_node)
    
    # Establish parallel execution: START connects to all nodes
    workflow.set_entry_point("cultural_agent")
    
    # In LangGraph, to fan-out from START to multiple nodes in parallel, 
    # we can just set them all as entry points by adding Conditional Edges from START, OR we can use standard edges
    workflow.add_edge("__start__", "cultural_agent")
    workflow.add_edge("__start__", "behavioral_agent")
    workflow.add_edge("__start__", "motivation_agent")
    workflow.add_edge("__start__", "learning_agent")
    workflow.add_edge("__start__", "emotional_agent")
    workflow.add_edge("__start__", "risk_agent")
    
    # Fan-in: All nodes connect directly to END 
    # The reducer in the State (operator.ior) handles aggregating the dictionaries
    workflow.add_edge("cultural_agent", END)
    workflow.add_edge("behavioral_agent", END)
    workflow.add_edge("motivation_agent", END)
    workflow.add_edge("learning_agent", END)
    workflow.add_edge("emotional_agent", END)
    workflow.add_edge("risk_agent", END)
    
    # Compile the graph
    app = workflow.compile()
    
    return app
