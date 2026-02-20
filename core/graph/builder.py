"""LangGraph builder: constructs the workflow graph."""

from langgraph.graph import StateGraph, END
from core.graph.state import GraphState
from core.graph.nodes import (
    refine_node,
    generate_manim_code_node,
    run_manim_node,
    fix_manim_code_node,
    should_retry
)


def build_graph() -> StateGraph:
    """Build and compile the LangGraph workflow."""
    
    # Create graph
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("refine", refine_node)
    workflow.add_node("generate_code", generate_manim_code_node)
    workflow.add_node("run_manim", run_manim_node)
    workflow.add_node("fix_code", fix_manim_code_node)
    
    # Define edges
    workflow.set_entry_point("refine")
    workflow.add_edge("refine", "generate_code")
    workflow.add_edge("generate_code", "run_manim")
    
    # Conditional edge: retry or end
    workflow.add_conditional_edges(
        "run_manim",
        should_retry,
        {
            "end": END,
            "fix": "fix_code"
        }
    )
    
    # Fix code loops back to run_manim
    workflow.add_edge("fix_code", "run_manim")
    
    # Compile graph
    return workflow.compile()