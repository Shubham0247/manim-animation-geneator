"""OpenAI LLM client wrapper for LangGraph nodes."""

import re
from openai import AzureOpenAI
from core.config import settings
from core.models import UserRequest, RefinedRequest, ManimCode
from core.llm.prompts import (
    REFINE_SYSTEM_MESSAGE,
    GENERATE_SYSTEM_MESSAGE,
    FIX_SYSTEM_MESSAGE,
    NORMALIZE_SYSTEM_MESSAGE,
    NORMALIZE_STRICT_SYSTEM_MESSAGE,
    refine_prompt_text,
    generate_code_prompt,
    fix_code_prompt,
    normalize_layout_prompt,
    normalize_layout_strict_prompt,
)


class OpenAILLMClient:
    """Single-responsibility class for OpenAI API interactions."""
    
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            azure_deployment=settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
        )
        self.model = settings.openai_model or settings.azure_openai_deployment
    
    def refine_prompt(self, user_request: UserRequest) -> RefinedRequest:
        """Refine and clarify the user's prompt for better Manim code generation."""
        prompt = refine_prompt_text(user_request.prompt)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": REFINE_SYSTEM_MESSAGE},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2500,
        )
        
        refined_description = response.choices[0].message.content.strip()
        
        return RefinedRequest(
            original_prompt=user_request.prompt,
            refined_description=refined_description
        )
    
    def generate_manim_code(self, refined: RefinedRequest) -> ManimCode:
        """Generate Manim Python code from refined description."""
        prompt = generate_code_prompt(refined.refined_description)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": GENERATE_SYSTEM_MESSAGE},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=4000,
        )
        
        code = response.choices[0].message.content.strip()
        
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        code = code.strip()
        
        scene_name = None
        for line in code.split("\n"):
            if "class" in line and "Scene" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "class":
                        scene_name = parts[i + 1].split("(")[0].strip()
                        break
                break

        manim_code = ManimCode(code=code, scene_name=scene_name)
        return self._normalize_layout(manim_code, refined)
    
    def fix_manim_code(
        self, 
        previous_code: ManimCode, 
        error_message: str,
        refined: RefinedRequest
    ) -> ManimCode:
        """Fix Manim code based on error message."""
        prompt = fix_code_prompt(
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
        
        code = response.choices[0].message.content.strip()
        
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        code = code.strip()
        
        scene_name = None
        for line in code.split("\n"):
            if "class" in line and "Scene" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "class":
                        scene_name = parts[i + 1].split("(")[0].strip()
                        break
                break
        
        fixed_code = ManimCode(code=code, scene_name=scene_name)
        return self._normalize_layout(fixed_code, refined)

    def _normalize_layout(self, manim_code: ManimCode, refined: RefinedRequest) -> ManimCode:
        """Second-pass cleanup to avoid overlaps and absolute coordinates."""
        try:
            prompt = normalize_layout_prompt(
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
            if code.startswith("```python"):
                code = code[9:]
            elif code.startswith("```"):
                code = code[3:]
            if code.endswith("```"):
                code = code[:-3]
            code = code.strip()

            if self._needs_layout_fix(code):
                code = self._normalize_layout_strict(code, refined.refined_description)

            scene_name = manim_code.scene_name
            for line in code.split("\n"):
                if "class" in line and "Scene" in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "class":
                            scene_name = parts[i + 1].split("(")[0].strip()
                            break
                    break

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

    def _normalize_layout_strict(self, code: str, refined_description: str) -> str:
        """Stricter second pass if issues remain."""
        prompt = normalize_layout_strict_prompt(
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
        if new_code.startswith("```python"):
            new_code = new_code[9:]
        elif new_code.startswith("```"):
            new_code = new_code[3:]
        if new_code.endswith("```"):
            new_code = new_code[:-3]
        return new_code.strip()
