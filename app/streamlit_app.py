import streamlit as st
import time
from core.graph.builder import build_graph
from core.graph.state import GraphState
from core.models import UserRequest
from pathlib import Path


def main():
    st.set_page_config(
        page_title="Manim Animation Generator",
        page_icon="🎬",
        layout="wide"
    )
    
    st.title("🎬 Manim Animation Generator")
    st.markdown("Generate beautiful mathematical animations using AI-powered code generation")
    
    if "graph" not in st.session_state:
        st.session_state.graph = build_graph()
    
    with st.form("animation_form"):
        user_prompt = st.text_area(
            "Describe the animation you want to create",
            placeholder="e.g., Create an animation showing how a neural network works",
            height=100
        )
        submit_button = st.form_submit_button("Generate Animation", type="primary")
    
    if submit_button and user_prompt:
        initial_state: GraphState = {
            "user_request": UserRequest(prompt=user_prompt),
            "retries": 0
        }
        
        progress_container = st.container()
        status_container = st.container()
        results_container = st.container()
        
        try:
            with progress_container:
                progress_bar = st.progress(0)
                status_text = st.empty()
                log_area = st.empty()
            
            log_messages = []
            
            def update_log(message: str):
                log_messages.append(message)
                log_display = "\n".join(log_messages[-10:])
                log_area.text_area("📋 Progress Log", value=log_display, height=150, disabled=True)
            
            final_state = None
            refined_shown = False
            code_shown = False
            
            try:
                status_text.text("🔄 Starting animation generation...")
                progress_bar.progress(5)
                update_log("🔄 Step 1/4: Starting...")
                
                accumulated_state = initial_state.copy()
                
                for event in st.session_state.graph.stream(initial_state):
                    for node_name, node_state in event.items():
                        if isinstance(node_state, dict):
                            accumulated_state.update(node_state)
                            final_state = accumulated_state
                        
                        if node_name == "refine":
                            status_text.text("🔄 Step 1/4: Refining your prompt with AI...")
                            progress_bar.progress(25)
                            update_log("🔄 Step 1/4: Refining your prompt with AI...")
                            
                        elif node_name == "generate_code":
                            status_text.text("💻 Step 2/4: Generating Manim Python code...")
                            progress_bar.progress(50)
                            update_log("💻 Step 2/4: Generating Manim Python code...")
                            
                            if not refined_shown and "refined" in accumulated_state:
                                with status_container:
                                    with st.expander("📝 Refined Description", expanded=True):
                                        st.write(accumulated_state["refined"].refined_description)
                                refined_shown = True
                                update_log("✅ Refined description generated")
                            
                            if not code_shown and "manim_code" in accumulated_state:
                                scene_name = accumulated_state["manim_code"].scene_name or "Unknown"
                                with status_container:
                                    with st.expander("💻 Generated Manim Code", expanded=False):
                                        st.code(accumulated_state["manim_code"].code, language="python")
                                code_shown = True
                                update_log(f"✅ Manim code generated (Scene: {scene_name})")
                            
                        elif node_name == "run_manim":
                            retries = accumulated_state.get("retries", 0)
                            if retries == 0:
                                status_text.text("🎬 Step 3/4: Executing Manim code (this may take a while)...")
                                progress_bar.progress(75)
                                update_log("🎬 Step 3/4: Executing Manim code...")
                            else:
                                status_text.text(f"🔧 Retrying execution (Attempt {retries + 1})...")
                                progress_bar.progress(70)
                                update_log(f"🔧 Retrying execution (Attempt {retries + 1})...")
                            
                            if "execution" in accumulated_state:
                                exec_result = accumulated_state["execution"]
                                if exec_result.success:
                                    update_log("✅ Manim execution successful!")
                                else:
                                    update_log(f"❌ Execution failed: {exec_result.stderr[:100] if exec_result.stderr else 'Unknown error'}")
                            
                        elif node_name == "fix_code":
                            retries = accumulated_state.get("retries", 0)
                            status_text.text(f"🔧 Step 3.{retries}/4: Fixing code based on error...")
                            progress_bar.progress(65)
                            update_log(f"🔧 Fixing code based on error (Attempt {retries})...")
                
                if final_state is None:
                    final_state = accumulated_state
                    
            except Exception as stream_error:
                update_log(f"⚠️ Streaming encountered issue, using standard execution...")
                status_text.text("⏳ Processing (using standard execution)...")
                progress_bar.progress(50)
                final_state = st.session_state.graph.invoke(initial_state)
            
            progress_bar.progress(100)
            status_text.text("✅ Animation generation completed!")
            update_log("✅ Animation generation completed!")
            time.sleep(0.5)
            
            with results_container:
                st.success("🎉 Animation generation completed!")
                
                if "refined" in final_state and not refined_shown:
                    with st.expander("📝 Refined Description", expanded=False):
                        st.write(final_state["refined"].refined_description)
                
                if "manim_code" in final_state and not code_shown:
                    with st.expander("💻 Generated Manim Code", expanded=False):
                        st.code(final_state["manim_code"].code, language="python")
                
                if "execution" in final_state:
                    execution = final_state["execution"]
                    
                    if execution.success and execution.video_path:
                        st.subheader("🎥 Generated Animation")
                        
                        video_path = Path(execution.video_path)
                        if video_path.exists():
                            with open(video_path, "rb") as video_file:
                                video_bytes = video_file.read()
                                st.video(video_bytes)
                            
                            st.info(f"✅ Video saved at: `{execution.video_path}`")
                        else:
                            st.error(f"❌ Video file not found at: {execution.video_path}")
                            if execution.stdout:
                                with st.expander("📋 Manim Output", expanded=False):
                                    st.text(execution.stdout)
                    else:
                        st.error("❌ Failed to generate animation")
                        if execution.stderr:
                            with st.expander("❌ Error Details", expanded=True):
                                st.code(execution.stderr, language="text")
                        if execution.stdout:
                            with st.expander("📋 Output", expanded=False):
                                st.text(execution.stdout)
                
                if final_state.get("retries", 0) > 0:
                    st.info(f"⚠️ Code was automatically fixed and retried {final_state['retries']} time(s)")
        
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
            with st.expander("🔍 Error Details", expanded=True):
                st.exception(e)
    
    elif submit_button and not user_prompt:
        st.warning("⚠️ Please enter a description for your animation")


if __name__ == "__main__":
    main()
