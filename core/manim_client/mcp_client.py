import asyncio
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import logging
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Optional

from fastmcp import Client

from core.manim_client.interfaces import IManimExecutor
from core.manim_client.safety import UnsafeCodeError, validate_generated_manim_code
from core.models import ManimCode, ManimExecutionResult
from core.config import settings

logger = logging.getLogger(__name__)


class MCPManimExecutor(IManimExecutor):
    def __init__(self, mcp_server_path: Optional[str] = None):
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
        """Execute Manim code via MCP. Falls back to direct subprocess only on transport errors."""
        try:
            validate_generated_manim_code(code.code)
        except UnsafeCodeError as exc:
            return ManimExecutionResult(
                success=False,
                video_path=None,
                stderr=str(exc),
                stdout=None,
            )

        logger.info("Starting Manim execution via MCP...")
        try:
            return self._execute_via_mcp(code)
        except Exception as exc:
            logger.exception("MCP execution failed, falling back to direct subprocess: %s", exc)
            print("   [Manim] MCP execution failed, falling back to direct subprocess...")
            return self._execute_direct(code)

    def _execute_via_mcp(self, code: ManimCode) -> ManimExecutionResult:
        scene_name = code.scene_name or self._extract_scene_name(code.code)
        request_payload = {
            "code": code.code,
            "scene_name": scene_name,
            "quality": settings.manim_default_quality,
            "resolution": settings.manim_default_resolution,
        }

        timeout = settings.mcp_timeout_seconds
        logger.info("Calling MCP tool render_manim_scene with timeout=%ss", timeout)
        tool_result = self._run_async(
            self._call_render_tool,
            request_payload,
            timeout,
        )
        return self._parse_mcp_tool_result(tool_result)

    async def _call_render_tool(self, request_payload: dict[str, Any], timeout: int):
        from mcp_servers.manim_server.main import mcp as manim_mcp_server

        async with Client(
            manim_mcp_server,
            timeout=timeout,
            init_timeout=timeout,
        ) as client:
            try:
                return await client.call_tool(
                    "render_manim_scene",
                    {"request": request_payload},
                    timeout=timeout,
                    raise_on_error=False,
                )
            except Exception:
                logger.debug(
                    "Nested 'request' payload failed, retrying with flat payload.",
                    exc_info=True,
                )
                return await client.call_tool(
                    "render_manim_scene",
                    request_payload,
                    timeout=timeout,
                    raise_on_error=False,
                )

    @staticmethod
    def _run_async(async_fn, *args):
        """Run async code from sync context, including environments with active event loops."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(async_fn(*args))

        result_box: dict[str, Any] = {}
        error_box: dict[str, Exception] = {}

        def _target():
            try:
                result_box["value"] = asyncio.run(async_fn(*args))
            except Exception as exc:  # pragma: no cover - thread branch
                error_box["error"] = exc

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join()

        if "error" in error_box:
            raise error_box["error"]
        return result_box["value"]

    def _parse_mcp_tool_result(self, tool_result) -> ManimExecutionResult:
        """Convert FastMCP CallToolResult to internal execution result model."""
        if getattr(tool_result, "is_error", False):
            stderr = self._extract_text_content(getattr(tool_result, "content", []))
            return ManimExecutionResult(
                success=False,
                video_path=None,
                stderr=stderr or "MCP tool reported an error.",
                stdout=None,
            )

        payload = self._extract_structured_payload(tool_result)
        if payload is None:
            stderr = self._extract_text_content(getattr(tool_result, "content", []))
            return ManimExecutionResult(
                success=False,
                video_path=None,
                stderr=stderr or "MCP tool returned no structured payload.",
                stdout=None,
            )

        video_path = payload.get("video_path")
        if isinstance(video_path, str) and video_path:
            video_candidate = Path(video_path)
            if video_candidate.exists():
                video_path = str(video_candidate.resolve())

        return ManimExecutionResult(
            success=bool(payload.get("success")),
            video_path=video_path,
            stderr=payload.get("stderr"),
            stdout=payload.get("stdout"),
        )

    @staticmethod
    def _extract_structured_payload(tool_result) -> Optional[dict[str, Any]]:
        """Extract dict payload from FastMCP result object."""
        data = getattr(tool_result, "data", None)
        if data is not None:
            if hasattr(data, "model_dump"):
                dumped = data.model_dump()
                if isinstance(dumped, dict):
                    return dumped
            if is_dataclass(data):
                dumped = asdict(data)
                if isinstance(dumped, dict):
                    return dumped
            if isinstance(data, dict):
                return data

        structured = getattr(tool_result, "structured_content", None)
        if isinstance(structured, dict):
            nested = structured.get("result")
            if isinstance(nested, dict):
                return nested
            return structured

        return None

    @staticmethod
    def _extract_text_content(content_blocks) -> Optional[str]:
        """Extract human-readable text from MCP content blocks."""
        parts: list[str] = []
        for block in content_blocks or []:
            text = getattr(block, "text", None)
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        if not parts:
            return None
        return "\n".join(parts)

    @staticmethod
    def _extract_scene_name(code_text: str) -> str:
        for line in code_text.split("\n"):
            if "class" in line and "Scene" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "class" and i + 1 < len(parts):
                        return parts[i + 1].split("(")[0].strip()
        return "Scene"

    def _execute_direct(self, code: ManimCode) -> ManimExecutionResult:
        """Fallback path: execute Manim directly via subprocess."""
        try:
            logger.info("Starting direct Manim subprocess fallback...")

            run_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
            run_dir = self.base_temp_dir / run_id
            run_dir.mkdir(parents=True, exist_ok=True)

            script_path = run_dir / "scene_script.py"
            script_path.write_text(code.code, encoding="utf-8")
            logger.info(f"Wrote script to: {script_path}")

            scene_name = code.scene_name or self._extract_scene_name(code.code)
            logger.info(f"Scene name: {scene_name}")

            quality = settings.manim_default_quality.lower()
            quality_flag = {
                "low": "-ql",
                "medium": "-qm",
                "high": "-qh",
            }.get(quality, "-qm")

            script_path_str = str(script_path).replace("\\", "/")
            cmd = [
                sys.executable,
                "-m",
                "manim",
                quality_flag,
            ]

            resolution_arg = self._parse_resolution(settings.manim_default_resolution)
            if resolution_arg:
                cmd.extend(["-r", resolution_arg])

            cmd.extend(
                [
                    "--renderer",
                    "cairo",
                    "--disable_caching",
                    "--progress_bar",
                    "none",
                    script_path_str,
                    scene_name,
                ]
            )

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

            video_path = self._find_video(result, scene_name, run_dir)
            success = result.returncode == 0 and video_path is not None

            if success:
                logger.info(f"Success! Video at: {video_path}")
                print(f"   [Manim] Video generated: {video_path}")
            else:
                logger.warning(f"Failed. Return code: {result.returncode}")
                print("   [Manim] Execution failed")

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

        except Exception as exc:
            error_msg = f"Manim execution error: {str(exc)}"
            logger.exception(error_msg)
            print(f"   [Manim] Error: {exc}")
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
        run_dir: Path,
    ) -> Optional[str]:
        """Find the generated video file."""
        combined_output = (result.stdout or "") + "\n" + (result.stderr or "")

        for line in combined_output.split("\n"):
            if ".mp4" in line:
                path_match = re.search(r"([A-Za-z]:)?[/\\][^\s]+\.mp4", line)
                if path_match:
                    candidate = path_match.group(0).replace("\\", "/")
                    candidate_path = Path(candidate)
                    if candidate_path.exists():
                        return str(candidate_path.resolve())

        search_bases = [
            run_dir / "media" / "videos" / "scene_script",
            run_dir / "media" / "videos",
            self.output_dir / "media" / "videos",
        ]

        for base in search_bases:
            if base.exists():
                matches = sorted(
                    base.rglob(f"{scene_name}.mp4"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if matches:
                    return str(matches[0].resolve())

        for base in search_bases:
            if base.exists():
                matches = sorted(
                    base.rglob("*.mp4"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if matches:
                    return str(matches[0].resolve())

        return None

    @staticmethod
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
