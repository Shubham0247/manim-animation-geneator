"""OpenAI LLM client wrapper for LangGraph nodes."""

import ast
import logging
import re
from openai import AzureOpenAI, OpenAI
from core.config import settings
from core.models import UserRequest, RefinedRequest, ManimCode
from core.llm.prompts import (
    REFINE_SYSTEM_MESSAGE,
    GENERATE_SYSTEM_MESSAGE,
    FIX_SYSTEM_MESSAGE,
    REPAIR_SYNTAX_SYSTEM_MESSAGE,
    NORMALIZE_SYSTEM_MESSAGE,
    NORMALIZE_STRICT_SYSTEM_MESSAGE,
    refine_prompt_text,
    generate_code_prompt,
    fix_code_prompt,
    repair_syntax_prompt,
    normalize_layout_prompt,
    normalize_layout_strict_prompt,
)

logger = logging.getLogger(__name__)


class OpenAILLMClient:
    """Single-responsibility class for OpenAI API interactions."""
    
    def __init__(self):
        azure_enabled = bool(settings.azure_openai_endpoint and settings.azure_openai_deployment)

        if azure_enabled:
            api_key = settings.azure_openai_api_key or settings.openai_api_key
            self.client = AzureOpenAI(
                api_key=api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                azure_deployment=settings.azure_openai_deployment,
                api_version=settings.azure_openai_api_version,
            )
            self.model = settings.openai_model or settings.azure_openai_deployment
        else:
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
            self.model = settings.openai_model or "gpt-4.1-mini"
    
    def refine_prompt(self, user_request: UserRequest) -> RefinedRequest:
        """Refine and clarify the user's prompt for better Manim code generation."""
        prompt = refine_prompt_text(user_request.prompt)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": REFINE_SYSTEM_MESSAGE},
                {"role": "user", "content": prompt}
            ],
            temperature=0.25,
            max_tokens=2500,
        )
        
        refined_description = response.choices[0].message.content.strip()
        
        return RefinedRequest(
            original_prompt=user_request.prompt,
            refined_description=refined_description
        )
    
    def generate_manim_code(self, refined: RefinedRequest) -> ManimCode:
        """Generate Manim Python code from refined description."""
        prompt = generate_code_prompt(
            original_prompt=refined.original_prompt,
            refined_description=refined.refined_description,
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": GENERATE_SYSTEM_MESSAGE},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=4000,
        )
        
        code = self._strip_code_fences(response.choices[0].message.content.strip())
        code = self._ensure_syntax_valid(code, refined)

        manim_code = ManimCode(code=code, scene_name=self._extract_scene_name(code))
        normalized = self._normalize_layout(manim_code, refined)
        final_code = self._ensure_syntax_valid(normalized.code, refined, fallback_code=code)
        return ManimCode(code=final_code, scene_name=self._extract_scene_name(final_code))
    
    def fix_manim_code(
        self, 
        previous_code: ManimCode, 
        error_message: str,
        refined: RefinedRequest
    ) -> ManimCode:
        """Fix Manim code based on error message."""
        prompt = fix_code_prompt(
            original_prompt=refined.original_prompt,
            refined_description=refined.refined_description,
            previous_code=previous_code.code,
            error_message=error_message,
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": FIX_SYSTEM_MESSAGE},
                {"role": "user", "content": prompt}
            ],
            temperature=0.15,
            max_tokens=4000,
        )
        
        code = self._strip_code_fences(response.choices[0].message.content.strip())
        code = self._ensure_syntax_valid(code, refined, fallback_code=previous_code.code)

        fixed_code = ManimCode(code=code, scene_name=self._extract_scene_name(code))
        normalized = self._normalize_layout(fixed_code, refined)
        final_code = self._ensure_syntax_valid(
            normalized.code,
            refined,
            fallback_code=fixed_code.code,
        )
        return ManimCode(code=final_code, scene_name=self._extract_scene_name(final_code))

    def _normalize_layout(self, manim_code: ManimCode, refined: RefinedRequest) -> ManimCode:
        """Second-pass cleanup to avoid overlaps and absolute coordinates."""
        if not self._needs_layout_fix(manim_code.code):
            return manim_code

        try:
            prompt = normalize_layout_prompt(
                original_prompt=refined.original_prompt,
                refined_description=refined.refined_description,
                code=manim_code.code,
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": NORMALIZE_SYSTEM_MESSAGE},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=3000,
            )

            code = response.choices[0].message.content.strip()
            code = self._strip_code_fences(code)

            if self._get_syntax_error(code):
                logger.warning("Layout normalization produced invalid Python; using original generated code.")
                return manim_code

            if self._needs_layout_fix(code):
                relaxed_layout_code = code
                code = self._normalize_layout_strict(
                    code=code,
                    original_prompt=refined.original_prompt,
                    refined_description=refined.refined_description,
                )
                if self._get_syntax_error(code):
                    logger.warning("Strict layout normalization produced invalid Python; keeping relaxed layout code.")
                    code = relaxed_layout_code

            scene_name = self._extract_scene_name(code) or manim_code.scene_name

            return ManimCode(code=code, scene_name=scene_name)
        except Exception:
            return manim_code

    @staticmethod
    def _needs_layout_fix(code: str) -> bool:
        """Heuristics to detect overlap-prone or absolute coordinate usage."""
        if re.search(r"move_to\(\s*[\[\(]\s*-?\d", code):
            return True
        if re.search(r"\.shift\(\s*[\[\(]\s*-?\d", code):
            return True
        if re.search(r"\bset_[xy]\(", code):
            return True
        if re.search(r"np\.array\(", code):
            return True
        if "SVGMobject" in code or "ImageMobject" in code:
            return True
        for line in code.splitlines():
            if "Text(" in line:
                match = re.search(r'Text\(\s*([\'"])(.*?)\1', line)
                if match and len(match.group(2)) > 40:
                    return True
        return False

    def _normalize_layout_strict(
        self,
        code: str,
        original_prompt: str,
        refined_description: str,
    ) -> str:
        """Stricter second pass if issues remain."""
        prompt = normalize_layout_strict_prompt(
            original_prompt=original_prompt,
            refined_description=refined_description,
            code=code,
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": NORMALIZE_STRICT_SYSTEM_MESSAGE},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=3000,
        )

        new_code = response.choices[0].message.content.strip()
        return self._strip_code_fences(new_code)

    @staticmethod
    def _strip_code_fences(code: str) -> str:
        """Strip markdown code fences if present."""
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        return code.strip()

    @staticmethod
    def _extract_scene_name(code: str) -> str | None:
        """Extract first Scene class name from generated code."""
        for line in code.split("\n"):
            if "class" in line and "Scene" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "class" and i + 1 < len(parts):
                        return parts[i + 1].split("(")[0].strip()
        return None

    @staticmethod
    def _get_syntax_error(code: str) -> str | None:
        """Return syntax error text if code is invalid, else None."""
        try:
            ast.parse(code)
            return None
        except SyntaxError as exc:
            line = f" line {exc.lineno}" if exc.lineno else ""
            return f"{exc.msg}{line}"

    def _ensure_syntax_valid(
        self,
        code: str,
        refined: RefinedRequest,
        fallback_code: str | None = None,
    ) -> str:
        """Repair syntax with a dedicated pass when generated code is invalid."""
        syntax_error = self._get_syntax_error(code)
        if not syntax_error:
            return code

        logger.warning("Generated code failed syntax check: %s", syntax_error)
        prompt = repair_syntax_prompt(
            original_prompt=refined.original_prompt,
            refined_description=refined.refined_description,
            broken_code=code,
            syntax_error=syntax_error,
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": REPAIR_SYNTAX_SYSTEM_MESSAGE},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=4000,
        )

        repaired_code = self._strip_code_fences(response.choices[0].message.content.strip())
        repaired_error = self._get_syntax_error(repaired_code)
        if not repaired_error:
            return repaired_code

        logger.warning("Syntax repair pass failed: %s", repaired_error)
        if fallback_code and not self._get_syntax_error(fallback_code):
            return fallback_code
        return code
