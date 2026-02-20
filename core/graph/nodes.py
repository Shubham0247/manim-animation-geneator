"""LangGraph node functions (Single Responsibility Principle)."""

import logging
from core.graph.state import GraphState
from core.models import RefinedRequest, ManimCode, ManimExecutionResult
from core.llm.openai_client import OpenAILLMClient
from core.manim_client.mcp_client import MCPManimExecutor
from core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Initialize clients (could be injected via dependency injection for better testing)
_llm_client = OpenAILLMClient()
_manim_executor = MCPManimExecutor()


def refine_node(state: GraphState) -> GraphState:
    """Refine user prompt into detailed description."""
    logger.info("🔄 Step 1/4: Refining user prompt...")
    print("🔄 Step 1/4: Refining user prompt...")
    
    refined = _llm_client.refine_prompt(state["user_request"])
    state["refined"] = refined
    
    logger.info("✅ Step 1/4: Prompt refined successfully")
    print("✅ Step 1/4: Prompt refined successfully")
    
    return state


def generate_manim_code_node(state: GraphState) -> GraphState:
    """Generate Manim Python code from refined description."""
    logger.info("💻 Step 2/4: Generating Manim code...")
    print("💻 Step 2/4: Generating Manim code...")
    
    manim_code = _llm_client.generate_manim_code(state["refined"])
    state["manim_code"] = manim_code
    
    logger.info(f"✅ Step 2/4: Manim code generated (Scene: {manim_code.scene_name})")
    print(f"✅ Step 2/4: Manim code generated (Scene: {manim_code.scene_name})")
    
    return state


def run_manim_node(state: GraphState) -> GraphState:
    """Execute Manim code via MCP executor."""
    retry_count = state.get("retries", 0)
    step_num = 3 if retry_count == 0 else f"3.{retry_count + 1}"
    
    logger.info(f"🎬 Step {step_num}/4: Executing Manim code...")
    print(f"🎬 Step {step_num}/4: Executing Manim code...")
    
    execution = _manim_executor.execute(state["manim_code"])
    state["execution"] = execution
    
    if not execution.success:
        state["error_message"] = execution.stderr or "Unknown error occurred"
        logger.warning(f"❌ Step {step_num}/4: Execution failed")
        print(f"❌ Step {step_num}/4: Execution failed")
    else:
        logger.info(f"✅ Step {step_num}/4: Manim execution successful")
        print(f"✅ Step {step_num}/4: Manim execution successful")
    
    if "retries" not in state:
        state["retries"] = 0
    
    return state


def fix_manim_code_node(state: GraphState) -> GraphState:
    """Fix Manim code based on error message."""
    retry_num = state.get("retries", 0) + 1
    logger.info(f"🔧 Step 3.{retry_num}/4: Fixing Manim code (Attempt {retry_num})...")
    print(f"🔧 Step 3.{retry_num}/4: Fixing Manim code (Attempt {retry_num})...")
    
    fixed_code = _llm_client.fix_manim_code(
        previous_code=state["manim_code"],
        error_message=state.get("error_message", ""),
        refined=state["refined"]
    )
    state["manim_code"] = fixed_code
    state["retries"] = retry_num
    state["error_message"] = ""  # Clear error for next attempt
    
    logger.info(f"✅ Step 3.{retry_num}/4: Code fixed, retrying execution...")
    print(f"✅ Step 3.{retry_num}/4: Code fixed, retrying execution...")
    
    return state


def should_retry(state: GraphState) -> str:
    """Conditional edge function: decide whether to retry or end."""
    execution = state.get("execution")
    retries = state.get("retries", 0)
    
    if execution and execution.success:
        return "end"
    elif retries < settings.max_retries:
        return "fix"
    else:
        return "end"
