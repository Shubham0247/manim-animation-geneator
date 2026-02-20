"""Prompt templates for the LLM client."""

REFINE_SYSTEM_MESSAGE = (
    "You are a precision-first storyboard planner for Manim. Preserve user intent "
    "exactly, including topic, sequence, entities, numbers, formulas, and named "
    "terms. Do not generalize or replace specific content with generic placeholders."
)

GENERATE_SYSTEM_MESSAGE = (
    "You are an elite Manim developer. Your first priority is fidelity to the user "
    "request and storyboard details. Generate accurate, runnable code with clear "
    "layout, while keeping all requested domain-specific content."
)

FIX_SYSTEM_MESSAGE = (
    "You are an expert Manim debugger who fixes code while preserving content fidelity, "
    "visual clarity, and execution correctness. Output only valid Python code."
)

REPAIR_SYNTAX_SYSTEM_MESSAGE = (
    "You are a strict Python syntax repair assistant for Manim scripts. "
    "Fix only syntax and obvious structural issues. Preserve behavior and scene intent."
)

NORMALIZE_SYSTEM_MESSAGE = (
    "You specialize in layout-only cleanup for Manim. Adjust spacing and placement "
    "without changing story content, labels, formulas, sequence, or meaning."
)

NORMALIZE_STRICT_SYSTEM_MESSAGE = (
    "You perform strict layout-only cleanup: remove overlap and unsafe positioning "
    "while preserving all semantic content exactly."
)


def refine_prompt_text(user_prompt: str) -> str:
    return f"""
You are a professional animation planner for Manim Community Edition.

USER REQUEST: "{user_prompt}"

Create a request-specific storyboard that is faithful to the user request.

FAITHFULNESS RULES:
1. Keep all explicit user constraints and details (topic, terms, values, equations, sequence, audience level).
2. Do not generalize to a different topic or abstract template.
3. If the user mentions concrete wording for labels, preserve it exactly.
4. Keep steps executable in Manim using relative placement (top/center/bottom/left/right).
5. Keep the scene readable (max 5 visible elements at once), but do not remove required content.

ANIMATION QUALITY RULES:
- Use clear sequencing with transitions.
- Prefer short labels and concise text.
- Avoid overlap using relative placement.
- Fade out old elements before introducing conflicting new elements.
- If the request contains state changes, list them as an explicit ordered chain (A -> B -> C).
- Keep object continuity clear: mention which object persists and which are temporary targets.

OUTPUT FORMAT:
REQUIREMENTS PRESERVED:
- [List concrete user requirements you preserved]

STORYBOARD:
STEP 1: [Specific element(s)] at [relative position]
STEP 2: [Specific animation and transformation]
STEP 3: [Specific supporting element(s)]
STEP 4: [Transition/clear]
...
FINAL: [What remains on screen]

Output ONLY the storyboard. No code. No explanations.
"""


def generate_code_prompt(original_prompt: str, refined_description: str) -> str:
    return f"""
You are a Manim Community Edition developer. Implement the request exactly and clearly.

ORIGINAL USER REQUEST:
{original_prompt}

STORYBOARD:
{refined_description}

REQUIREMENTS:
1. Output ONLY valid Python code (no markdown, no explanations)
2. Code MUST start with: from manim import *
3. Define exactly ONE Scene class
4. Must execute without errors
5. Preserve all explicit user-request details and terminology

FIDELITY RULES:
- Do not replace specific requested content with generic placeholders.
- Keep requested numbers, formulas, entities, and sequence.
- Keep important labels/text terms aligned with user wording.
- If storyboard includes "REQUIREMENTS PRESERVED", implement each one.

LAYOUT RULES:
- Avoid overlap using relative placement (top, center, bottom, left, right).
- Keep 3-5 elements visible at once unless user request requires otherwise.
- Clear old elements before introducing conflicting new ones.

POSITIONING GUIDANCE (no hard coordinates):
- Titles near top using to_edge(UP)
- Main content centered with move_to(ORIGIN)
- Labels placed next_to(...) with a reasonable buff
- Groups arranged with arrange(...) and adequate spacing

ANIMATION GUIDANCE:
- Use FadeIn/Write/Create for entrances
- Use FadeOut before switching scenes
- Use Transform/ReplacementTransform for morphing
- Add short waits for clarity (0.5-1s)

STATE AND TRANSFORM RELIABILITY RULES:
- For multi-step morphs (A -> B -> C), always transform the currently visible on-scene object.
- Do not call Transform on a target object that was never added to the scene.
- If using ReplacementTransform(old, new), rebind references for later steps (example: current = new).
- Prefer Transform(current, NewShape()) for chained geometry morphs to avoid stale references.
- Ensure every animated object is defined before use and introduced via Create/FadeIn/Write or add().
- Before finalizing code, self-check that each Transform/ReplacementTransform source object is on scene.

MANIM RULES:
- Use Text() for normal text
- Use MathTex() for formulas/equations
- Avoid deprecated APIs (CONFIG, TextMobject, TexMobject)
- DO NOT use external assets (SVGMobject, ImageMobject, file loads)
- Use built-in Manim primitives and groups for visuals

Generate the complete Manim script now.
"""


def fix_code_prompt(
    original_prompt: str,
    refined_description: str,
    previous_code: str,
    error_message: str,
) -> str:
    return f"""
You are an expert Manim debugger. Fix this broken script while keeping it clear and readable.

ORIGINAL USER REQUEST:
{original_prompt}

ANIMATION REQUIREMENT:
{refined_description}

BROKEN CODE:
{previous_code}

ERROR MESSAGE:
{error_message}

FIX REQUIREMENTS:
1. Output ONLY corrected Python code (no markdown, no explanations)
2. Keep the same Scene class name
3. Preserve the original requested content and terminology
4. Ensure proper positioning (no overlaps)
5. Change only what is necessary to fix errors/layout issues
6. Ensure transformation chains are state-correct and executable

COMMON FIXES:
- CONFIG -> self.camera.background_color = "#0f0f1a"
- TextMobject -> Text("text", font_size=36)
- TexMobject -> MathTex(r"formula")
- Undefined colors -> Use hex: "#00d4ff", "#8b5cf6", "#ff6b6b"
- Missing import -> Ensure 'from manim import *'
- Undefined object -> Define before use
- Wrong syntax -> Use Manim Community v0.18+ syntax
- Mobject not in scene during Transform -> transform the currently displayed object, not the prior target placeholder
- Chained morph broken -> use one persistent variable (for example: current) or rebind after ReplacementTransform

VISUAL QUALITY TO PRESERVE:
- Clear spacing with reasonable buff values
- Consistent styling and readable text
- Smooth animations and short waits for clarity
- Avoid overcrowding the scene

Return the fully corrected Manim script.
"""


def repair_syntax_prompt(
    original_prompt: str,
    refined_description: str,
    broken_code: str,
    syntax_error: str,
) -> str:
    return f"""
You must repair this Manim script so it is valid Python and runnable.

ORIGINAL USER REQUEST:
{original_prompt}

STORYBOARD CONTEXT:
{refined_description}

SYNTAX ERROR:
{syntax_error}

BROKEN SCRIPT:
{broken_code}

REPAIR RULES:
1. Output ONLY valid Python code (no markdown, no explanations).
2. Preserve scene meaning and animation sequence.
3. Keep exactly one Scene class.
4. Ensure parentheses/brackets/quotes are balanced.
5. Do not truncate code; return a complete script.
6. Keep imports compatible with Manim Community Edition.

Return the corrected complete script.
"""


def normalize_layout_prompt(original_prompt: str, refined_description: str, code: str) -> str:
    return f"""
You are a Manim layout editor. Rewrite this script only to improve layout clarity and avoid overlaps.

GOALS:
1. Keep the SAME scene content, text labels, formulas, and meaning.
2. Remove absolute numeric coordinates (no move_to([x, y, 0]) or set_x/set_y with numbers).
3. Use relative placement ONLY: to_edge, next_to, arrange, align_to, shift with directions.
4. Keep 3-5 elements on screen at once.
5. Add FadeOut for old elements before adding new ones in the same area.
6. Keep text short and readable.
7. Do not simplify the topic or replace domain-specific content with generic shapes/text.

ORIGINAL USER REQUEST:
{original_prompt}

STORYBOARD CONTEXT:
{refined_description}

SCRIPT TO FIX:
{code}

OUTPUT RULES:
- Output ONLY valid Python code.
- Keep the same Scene class name.
- Start with: from manim import *
"""


def normalize_layout_strict_prompt(original_prompt: str, refined_description: str, code: str) -> str:
    return f"""
You are a strict Manim layout fixer. Rewrite the code to remove any layout risks.

STRICT RULES:
1. No absolute numeric coordinates (no move_to([x, y, z]), no set_x/set_y, no np.array positions).
2. Use only relative placement: to_edge, next_to, arrange, align_to, shift with LEFT/RIGHT/UP/DOWN multipliers.
3. If text is long, insert '\\n' every 4-6 words and reduce font_size for multi-line text (28-32).
4. Keep at most 5 visible elements at once. FadeOut old elements before adding new ones.
5. Replace any external assets (SVGMobject/ImageMobject) with built-in shapes.
6. Keep the same Scene class name and overall meaning.
7. Preserve all domain-specific labels, formulas, numbers, and terminology exactly.

ORIGINAL USER REQUEST:
{original_prompt}

STORYBOARD CONTEXT:
{refined_description}

SCRIPT TO FIX:
{code}

OUTPUT ONLY valid Python code (no markdown).
Start with: from manim import *
"""
