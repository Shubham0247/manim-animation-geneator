"""FastMCP server for executing Manim code."""

import subprocess
import sys
import os
import tempfile
import logging
import re
from pathlib import Path
from typing import Optional
from fastmcp import FastMCP
from pydantic import BaseModel

# Initialize FastMCP app
mcp = FastMCP("Manim Server")

# Set up file logger (not stderr, to avoid MCP protocol issues)
log_file = Path(__file__).parent.parent.parent / "manim_execution.log"
logger = logging.getLogger("manim_mcp")
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(str(log_file), mode='a')
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.handlers = [file_handler]


class RenderRequest(BaseModel):
    """Request model for rendering Manim code."""
    code: str
    scene_name: Optional[str] = None
    quality: str = "medium"  # low, medium, high
    resolution: str = "1920x1080"


class RenderResult(BaseModel):
    """Result model for Manim rendering."""
    success: bool
    video_path: Optional[str] = None
    stderr: Optional[str] = None
    stdout: Optional[str] = None


@mcp.tool()
def render_manim_scene(request: RenderRequest) -> RenderResult:
    """
    Render a Manim scene from Python code.
    
    Args:
        request: RenderRequest containing code, scene_name, quality, and resolution
        
    Returns:
        RenderResult with success status and video path
    """
    try:
        logger.info("=" * 60)
        logger.info("Starting render_manim_scene")
        logger.info(f"scene_name={request.scene_name} quality={request.quality}")
        
        # Write code to a persistent temp file (not auto-delete)
        temp_dir = Path(tempfile.gettempdir()) / "manim_mcp"
        temp_dir.mkdir(exist_ok=True)
        
        temp_script_path = temp_dir / "scene_script.py"
        temp_script_path.write_text(request.code, encoding="utf-8")
        logger.info(f"Wrote script to: {temp_script_path}")
        
        try:
            # Determine scene name
            scene_name = request.scene_name
            if not scene_name:
                # Try to extract from code
                for line in request.code.split('\n'):
                    if 'class' in line and 'Scene' in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == 'class':
                                scene_name = parts[i + 1].split('(')[0].strip()
                                break
                        break
                if not scene_name:
                    scene_name = "Scene"
            
            logger.info(f"Using scene name: {scene_name}")
            
            # Quality mapping
            quality_flag = {
                "low": "-ql",
                "medium": "-qm",
                "high": "-qh"
            }.get(request.quality.lower(), "-qm")
            
            # Build command - use forward slashes for path
            script_path_str = str(temp_script_path).replace("\\", "/")
            
            cmd = [
                sys.executable,
                "-m", "manim",
                quality_flag,
                "--renderer", "cairo",
                "--disable_caching",
                "--progress_bar", "none",
                script_path_str,
                scene_name
            ]
            
            logger.info(f"Running command: {' '.join(cmd)}")
            
            # Set up environment for subprocess - critical for Windows
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            # Disable Manim's rich console output that can hang
            env["TERM"] = "dumb"
            env["NO_COLOR"] = "1"
            
            # On Windows, use CREATE_NO_WINDOW to prevent console window
            # and avoid stdout/stdin handle inheritance issues
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            # Use subprocess.run with timeout - simpler and more reliable than Popen
            logger.info("Starting manim subprocess...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                env=env,
                cwd=str(temp_dir),  # Run from temp dir for consistent output
                creationflags=creation_flags if sys.platform == "win32" else 0,
            )
            
            logger.info(f"Manim completed with return code: {result.returncode}")
            logger.info(f"STDOUT:\n{result.stdout}")
            logger.info(f"STDERR:\n{result.stderr}")
            
            # Find generated video
            video_path = None
            combined_output = result.stdout + "\n" + result.stderr
            
            if result.returncode == 0:
                # Method 1: Parse output for video path
                for line in combined_output.split('\n'):
                    if '.mp4' in line:
                        path_match = re.search(r'([A-Za-z]:)?[/\\][^\s]+\.mp4', line)
                        if path_match:
                            candidate = path_match.group(0).replace("\\", "/")
                            if Path(candidate).exists():
                                video_path = str(Path(candidate).resolve())
                                logger.info(f"Found video from output: {video_path}")
                                break
                
                # Method 2: Search in media folder (check temp_dir/media first, then cwd/media)
                if video_path is None:
                    quality_dir = {
                        "low": "480p15",
                        "medium": "720p30",
                        "high": "1080p60"
                    }.get(request.quality.lower(), "720p30")
                    
                    script_stem = temp_script_path.stem
                    
                    search_bases = [
                        temp_dir / "media" / "videos",
                        Path.cwd() / "media" / "videos",
                    ]
                    
                    for base in search_bases:
                        if base.exists():
                            # Search for any mp4 file matching the scene name
                            for mp4_file in base.rglob(f"{scene_name}.mp4"):
                                video_path = str(mp4_file.resolve())
                                logger.info(f"Found video by search: {video_path}")
                                break
                            if video_path:
                                break
                    
                    # Method 3: Search more broadly
                    if video_path is None:
                        for base in search_bases:
                            if base.exists():
                                for mp4_file in base.rglob("*.mp4"):
                                    # Take the most recently modified mp4
                                    video_path = str(mp4_file.resolve())
                                    logger.info(f"Found video (fallback): {video_path}")
                                    break
                            if video_path:
                                break
            
            success = result.returncode == 0 and video_path is not None
            logger.info(f"Final result: success={success}, video_path={video_path}")
            
            return RenderResult(
                success=success,
                video_path=video_path,
                stderr=result.stderr if result.returncode != 0 else None,
                stdout=result.stdout,
            )
        
        except subprocess.TimeoutExpired:
            logger.error("Manim execution timed out after 5 minutes")
            return RenderResult(
                success=False,
                video_path=None,
                stderr="Manim execution timed out after 5 minutes",
                stdout=None,
            )
        
        except Exception as e:
            logger.exception(f"Error during manim execution: {e}")
            return RenderResult(
                success=False,
                video_path=None,
                stderr=f"Error executing Manim subprocess: {str(e)}",
                stdout=None
            )
    
    except Exception as e:
        logger.exception(f"Error in render_manim_scene: {e}")
        return RenderResult(
            success=False,
            video_path=None,
            stderr=f"Error executing Manim: {str(e)}",
            stdout=None
        )


if __name__ == "__main__":
    mcp.run()
