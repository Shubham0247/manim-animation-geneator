"""Prompt templates for the LLM client."""

REFINE_SYSTEM_MESSAGE = (
    "You are a world-class motion graphics director. Create detailed storyboards "
    "that result in visually stunning, professional animations. Focus on beautiful "
    "aesthetics, smooth motion, and clear visual hierarchy."
)

GENERATE_SYSTEM_MESSAGE = (
    "You are an elite Manim developer who creates broadcast-quality, visually "
    "stunning animations. Your code is clean, well-organized, and produces "
    "beautiful, professional results. You never overlap elements and always "
    "use proper spacing."
)

FIX_SYSTEM_MESSAGE = (
    "You are an expert Manim debugger who fixes code while preserving visual "
    "quality. Output only valid, polished Python code."
)

NORMALIZE_SYSTEM_MESSAGE = (
    "You specialize in Manim layout cleanup. You remove overlaps and absolute "
    "coordinates while preserving the original content."
)

NORMALIZE_STRICT_SYSTEM_MESSAGE = (
    "You remove absolute coordinates, wrap long text, and prevent overlap while "
    "preserving the story."
)


def refine_prompt_text(user_prompt: str) -> str:
    return f"""
You are a professional animation planner for Manim Community Edition.

USER REQUEST: "{user_prompt}"

Create a clear, general storyboard that can be used for ANY topic (not just math).

GENERAL QUALITY RULES:
1. Keep the scene uncluttered (max 5 elements on screen at once).
2. Use consistent styling and colors, but do not force a specific palette.
3. Avoid overlap by describing relative placement (top, center, bottom, left, right).
4. Introduce elements in sequence and remove old elements before new ones.
5. Keep text short and readable (6 words max per label).

ANIMATION FLOW (general, not specific coordinates):
• Start with a short title or context (top or center).
• Show the main object/idea in the center.
• Add a single label or supporting element below or beside it.
• Transition by fading out old elements before new ones.
• End with a clean final frame and a short pause.

OUTPUT FORMAT (simple steps):
STEP 1: [What appears] at [general position]
STEP 2: [How it animates]
STEP 3: [Optional label or supporting element]
STEP 4: [Transition/clear]
...
FINAL: [What remains on screen]

Output ONLY the storyboard. No code. No explanations.
"""


def generate_code_prompt(refined_description: str) -> str:
    return f"""
You are a Manim Community Edition developer. Implement this storyboard clearly and cleanly.

STORYBOARD:
{refined_description}

REQUIREMENTS:
1. Output ONLY valid Python code (no markdown, no explanations)
2. Code MUST start with: from manim import *
3. Define exactly ONE Scene class
4. Must execute without errors

GENERAL QUALITY RULES (keep them broad):
• Avoid overlapping elements by using relative placement (top, center, bottom, left, right)
• Keep 3-5 elements max on screen at once
• Use short, readable text
• Clear old elements before introducing new ones
• Use consistent but simple styling

POSITIONING GUIDANCE (no hard coordinates):
• Titles near top using to_edge(UP)
• Main content centered with move_to(ORIGIN)
• Labels placed next_to(...) with a reasonable buff
• Groups arranged with arrange(...) and adequate spacing

ANIMATION GUIDANCE:
• Use FadeIn/Write/Create for entrances
• Use FadeOut before switching scenes
• Use Transform/ReplacementTransform for morphing
• Add short waits for clarity (0.5–1s)

MANIM RULES:
• Use Text() for normal text
• Use MathTex() only for real math
• Avoid deprecated APIs (CONFIG, TextMobject, TexMobject)
• DO NOT use external assets (SVGMobject, ImageMobject, file loads)
• Use only built-in shapes (Circle, Square, Rectangle, Triangle, Line, Arrow, Dot)

Generate the complete Manim script now.
"""


def fix_code_prompt(
    refined_description: str,
    previous_code: str,
    error_message: str,
) -> str:
    return f"""
You are an expert Manim debugger. Fix this broken script while keeping it clear and readable.

ANIMATION REQUIREMENT:
{refined_description}

BROKEN CODE:
{previous_code}

ERROR MESSAGE:
{error_message}

FIX REQUIREMENTS:
1. Output ONLY corrected Python code (no markdown, no explanations)
2. Keep the same Scene class name
3. Preserve the overall visual style and clarity
4. Ensure proper positioning (no overlaps)

COMMON FIXES:
• CONFIG → self.camera.background_color = "#0f0f1a"
• TextMobject → Text("text", font_size=36)
• TexMobject → MathTex(r"formula")
• Undefined colors → Use hex: "#00d4ff", "#8b5cf6", "#ff6b6b"
• Missing import → Ensure 'from manim import *'
• Undefined object → Define before use
• Wrong syntax → Use Manim Community v0.18+ syntax

VISUAL QUALITY TO PRESERVE:
• Clear spacing with reasonable buff values
• Consistent styling and readable text
• Smooth animations and short waits for clarity
• Avoid overcrowding the scene

Return the fully corrected Manim script.
"""


def normalize_layout_prompt(refined_description: str, code: str) -> str:
    return f"""
You are a Manim layout editor. Rewrite this script to improve clarity and avoid overlaps.

GOALS:
1. Keep the SAME scene content and meaning.
2. Remove absolute numeric coordinates (no move_to([x, y, 0]) or set_x/set_y with numbers).
3. Use relative placement ONLY: to_edge, next_to, arrange, align_to, shift with directions.
4. Keep 3-5 elements on screen at once.
5. Add FadeOut for old elements before adding new ones in the same area.
6. Keep text short and readable.

STORYBOARD CONTEXT:
{refined_description}

SCRIPT TO FIX:
{code}

OUTPUT RULES:
- Output ONLY valid Python code.
- Keep the same Scene class name.
- Start with: from manim import *
"""


def normalize_layout_strict_prompt(refined_description: str, code: str) -> str:
    return f"""
You are a strict Manim layout fixer. Rewrite the code to remove any layout risks.

STRICT RULES:
1. No absolute numeric coordinates (no move_to([x, y, z]), no set_x/set_y, no np.array positions).
2. Use only relative placement: to_edge, next_to, arrange, align_to, shift with LEFT/RIGHT/UP/DOWN multipliers.
3. If text is long, insert '\\n' every 4-6 words and reduce font_size for multi-line text (28-32).
4. Keep at most 5 visible elements at once. FadeOut old elements before adding new ones.
5. Replace any external assets (SVGMobject/ImageMobject) with built-in shapes.
6. Keep the same Scene class name and overall meaning.

STORYBOARD CONTEXT:
{refined_description}

SCRIPT TO FIX:
{code}

OUTPUT ONLY valid Python code (no markdown).
Start with: from manim import *
"""
