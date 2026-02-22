"""FastMCP server for executing Manim code."""

import subprocess
import sys
import os
import tempfile
import logging
import re
import time
import uuid
import threading
from pathlib import Path
from typing import Optional
from fastmcp import FastMCP
from pydantic import BaseModel
from core.manim_client.safety import UnsafeCodeError, validate_generated_manim_code

# Initialize FastMCP app
mcp = FastMCP("Manim Server")

# Set up file logger (not stderr, to avoid MCP protocol issues)
log_file = Path(__file__).parent.parent.parent / "manim_execution.log"
logger = logging.getLogger("manim_mcp")
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(str(log_file), mode='a')
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.handlers = [file_handler]

# Avoid overlapping renders in the same server process (common in Inspector UI retries).
_render_lock = threading.Lock()


class RenderRequest(BaseModel):
    code: str
    scene_name: Optional[str] = None
    quality: str = "medium"  # low, medium, high
    resolution: str = "1920x1080"


class RenderResult(BaseModel):
    success: bool
    video_path: Optional[str] = None
    stderr: Optional[str] = None
    stdout: Optional[str] = None


def _parse_resolution(value: str) -> Optional[str]:
    """Parse WIDTHxHEIGHT (or WIDTH,HEIGHT) into Manim's -r format."""
    match = re.fullmatch(r"\s*(\d{2,5})\s*[xX,]\s*(\d{2,5})\s*", value or "")
    if not match:
        return None

    width = int(match.group(1))
    height = int(match.group(2))
    if width <= 0 or height <= 0:
        return None
    return f"{width},{height}"


def _normalize_code_input(code: str) -> str:
    """Normalize incoming code text from Inspector form/JSON inputs."""
    normalized = (code or "").replace("\r\n", "\n").replace("\r", "\n")
    # Inspector form fields can send escaped newlines as literal characters.
    if "\\n" in normalized and "\n" not in normalized:
        normalized = normalized.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
    return normalized


@mcp.tool()
def render_manim_scene(request: RenderRequest) -> RenderResult:
    """Validate, render, and locate the output video for a Manim scene request."""
    acquired = _render_lock.acquire(blocking=False)
    if not acquired:
        return RenderResult(
            success=False,
            video_path=None,
            stderr="Another render is already running in this server instance. Wait and retry.",
            stdout=None,
        )

    try:
        logger.info("=" * 60)
        logger.info("Starting render_manim_scene")
        logger.info(f"scene_name={request.scene_name} quality={request.quality}")

        code_text = _normalize_code_input(request.code)

        try:
            validate_generated_manim_code(code_text)
        except UnsafeCodeError as exc:
            error_message = str(exc)
            if "invalid syntax line 1" in error_message and "\n" not in code_text:
                error_message += (
                    " Hint: if using MCP Inspector form, paste escaped newlines "
                    "(\\n) in code, or switch to raw JSON args mode."
                )
            return RenderResult(
                success=False,
                video_path=None,
                stderr=error_message,
                stdout=None,
            )
        
        # Use a unique run directory to avoid request collisions.
        temp_root = Path(tempfile.gettempdir()) / "manim_mcp"
        temp_root.mkdir(exist_ok=True)
        run_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
        run_dir = temp_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        temp_script_path = run_dir / "scene_script.py"
        temp_script_path.write_text(code_text, encoding="utf-8")
        logger.info(f"Wrote script to: {temp_script_path}")
        
        try:
            # Determine scene name
            scene_name = request.scene_name
            if not scene_name:
                # Try to extract from code
                for line in code_text.split('\n'):
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
            ]

            resolution_arg = _parse_resolution(request.resolution)
            if resolution_arg:
                cmd.extend(["-r", resolution_arg])

            cmd.extend(
                [
                    "--renderer", "cairo",
                    "--disable_caching",
                    "--progress_bar", "none",
                    script_path_str,
                    scene_name,
                ]
            )
            
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
                cwd=str(run_dir),  # Run from run dir for consistent output
                stdin=subprocess.DEVNULL,
                close_fds=True,
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
                
                # Method 2: Search in this run's media folder.
                if video_path is None:
                    search_bases = [
                        run_dir / "media" / "videos" / "scene_script",
                        run_dir / "media" / "videos",
                    ]
                    
                    for base in search_bases:
                        if base.exists():
                            exact_matches = sorted(
                                base.rglob(f"{scene_name}.mp4"),
                                key=lambda p: p.stat().st_mtime,
                                reverse=True,
                            )
                            if exact_matches:
                                video_path = str(exact_matches[0].resolve())
                                logger.info(f"Found video by search: {video_path}")
                                break
                    
                    # Method 3: Search more broadly
                    if video_path is None:
                        for base in search_bases:
                            if base.exists():
                                mp4_matches = sorted(
                                    base.rglob("*.mp4"),
                                    key=lambda p: p.stat().st_mtime,
                                    reverse=True,
                                )
                                if mp4_matches:
                                    # Take the most recently modified mp4.
                                    video_path = str(mp4_matches[0].resolve())
                                    logger.info(f"Found video (fallback): {video_path}")
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
    finally:
        if acquired:
            _render_lock.release()


if __name__ == "__main__":
    mcp.run()
