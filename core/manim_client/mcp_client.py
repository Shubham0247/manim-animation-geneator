"""MCP client implementation for Manim execution using FastMCP."""

import sys
import os
import subprocess
import re
import tempfile
import time
import uuid
import logging
from pathlib import Path
from typing import Optional
from core.manim_client.interfaces import IManimExecutor
from core.models import ManimCode, ManimExecutionResult
from core.config import settings

logger = logging.getLogger(__name__)


class MCPManimExecutor(IManimExecutor):
    """
    Manim executor implementation.
    
    Uses direct subprocess execution for reliability on Windows.
    MCP transport can have issues with subprocess stdout on Windows.
    """
    
    def __init__(self, mcp_server_path: Optional[str] = None):
        """
        Initialize Manim executor.
        
        Args:
            mcp_server_path: Path to the MCP server script (unused in direct mode).
        """
        if mcp_server_path is None:
            project_root = Path(__file__).parent.parent.parent
            self.mcp_server_path = project_root / "mcp_servers" / "manim_server" / "main.py"
        else:
            self.mcp_server_path = Path(mcp_server_path)
        
        self.output_dir = settings.manim_output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.base_temp_dir = Path(tempfile.gettempdir()) / "manim_executor"
        self.base_temp_dir.mkdir(exist_ok=True)
    
    def execute(self, code: ManimCode) -> ManimExecutionResult:
        """
        Execute Manim code directly via subprocess.
        
        This bypasses MCP for reliability, running Manim directly.
        """
        try:
            logger.info("Starting Manim execution...")
            
            run_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
            run_dir = self.base_temp_dir / run_id
            run_dir.mkdir(parents=True, exist_ok=True)

            script_path = run_dir / "scene_script.py"
            script_path.write_text(code.code, encoding="utf-8")
            logger.info(f"Wrote script to: {script_path}")
            
            scene_name = code.scene_name
            if not scene_name:
                for line in code.code.split('\n'):
                    if 'class' in line and 'Scene' in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == 'class':
                                scene_name = parts[i + 1].split('(')[0].strip()
                                break
                        break
                if not scene_name:
                    scene_name = "Scene"
            
            logger.info(f"Scene name: {scene_name}")
            
            quality = settings.manim_default_quality.lower()
            quality_flag = {
                "low": "-ql",
                "medium": "-qm",
                "high": "-qh"
            }.get(quality, "-qm")
            
            script_path_str = str(script_path).replace("\\", "/")
            
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
            print(f"   [Manim] Running: {' '.join(cmd)}")
            
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            env["TERM"] = "dumb"
            env["NO_COLOR"] = "1"
            
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            timeout = settings.mcp_timeout_seconds
            logger.info(f"Executing Manim with {timeout}s timeout...")
            print(f"   [Manim] Executing with {timeout}s timeout...")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
                cwd=str(run_dir),
                creationflags=creation_flags if sys.platform == "win32" else 0,
            )
            
            logger.info(f"Manim completed with return code: {result.returncode}")
            print(f"   [Manim] Completed with return code: {result.returncode}")
            
            if result.stdout:
                logger.debug(f"STDOUT: {result.stdout[:500]}")
            if result.stderr:
                logger.debug(f"STDERR: {result.stderr[:500]}")
            
            video_path = self._find_video(result, scene_name, quality, run_dir)
            
            success = result.returncode == 0 and video_path is not None
            
            if success:
                logger.info(f"Success! Video at: {video_path}")
                print(f"   [Manim] Video generated: {video_path}")
            else:
                logger.warning(f"Failed. Return code: {result.returncode}")
                print(f"   [Manim] Execution failed")
            
            return ManimExecutionResult(
                success=success,
                video_path=video_path,
                stderr=result.stderr if result.returncode != 0 else None,
                stdout=result.stdout,
            )
            
        except subprocess.TimeoutExpired:
            error_msg = f"Manim execution timed out after {settings.mcp_timeout_seconds} seconds"
            logger.error(error_msg)
            print(f"   [Manim] {error_msg}")
            return ManimExecutionResult(
                success=False,
                video_path=None,
                stderr=error_msg,
                stdout=None,
            )
            
        except Exception as e:
            error_msg = f"Manim execution error: {str(e)}"
            logger.exception(error_msg)
            print(f"   [Manim] Error: {e}")
            return ManimExecutionResult(
                success=False,
                video_path=None,
                stderr=error_msg,
                stdout=None,
            )
    
    def _find_video(
        self,
        result: subprocess.CompletedProcess,
        scene_name: str,
        quality: str,
        run_dir: Path,
    ) -> Optional[str]:
        """Find the generated video file."""
        combined_output = (result.stdout or "") + "\n" + (result.stderr or "")
        
        for line in combined_output.split('\n'):
            if '.mp4' in line:
                path_match = re.search(r'([A-Za-z]:)?[/\\][^\s]+\.mp4', line)
                if path_match:
                    candidate = path_match.group(0).replace("\\", "/")
                    candidate_path = Path(candidate)
                    if candidate_path.exists():
                        return str(candidate_path.resolve())
        
        quality_dir = {
            "low": "480p15",
            "medium": "720p30",
            "high": "1080p60"
        }.get(quality, "720p30")
        
        search_bases = [
            run_dir / "media" / "videos",
            Path.cwd() / "media" / "videos",
            self.output_dir / "media" / "videos",
        ]
        
        for base in search_bases:
            if base.exists():
                for mp4_file in base.rglob(f"{scene_name}.mp4"):
                    return str(mp4_file.resolve())
        
        for base in search_bases:
            if base.exists():
                mp4_files = list(base.rglob("*.mp4"))
                if mp4_files:
                    mp4_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    return str(mp4_files[0].resolve())
        
        return None
