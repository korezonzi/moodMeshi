import json

import anthropic

from app.config import settings

MODEL = "claude-sonnet-4-20250514"

PRESENTATION_SYSTEM = """You are a presentation specialist who creates compelling reveal.js HTML presentations.

Create a single-file HTML presentation using reveal.js 5.x with the following specifications:
- 8-10 slides covering the MoodMeshi application
- Modern, visually appealing design with warm colors matching the app theme
- Include code examples, architecture diagrams (ASCII art), and demo screenshots descriptions
- Use Japanese for most content, English for technical terms
- Embed all CSS inline in the HTML file

The presentation should cover:
1. Title slide - MoodMeshi introduction
2. Problem statement - The difficulty of deciding what to eat based on mood
3. Solution overview - How MoodMeshi works
4. Architecture - Orchestrator-Workers pattern with Claude AI
5. Tech stack - Claude AI, Rakuten Recipe API, FastAPI, HTMX
6. Demo results - Show example proposals (if provided)
7. Key features - Mood analysis, parallel AI agents, seasonal recommendations
8. Future possibilities - Potential enhancements
9. Summary / Call to action

Return a complete, valid HTML file that can be opened in a browser."""


def generate_presentation(demo_result: dict | None, output_path: str) -> str:
    """Generate a reveal.js presentation as a single HTML file.

    Args:
        demo_result: Optional demo result from run_orchestrator to include in slides
        output_path: Path to write the HTML file

    Returns:
        Path to the generated HTML file
    """
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    demo_context = ""
    if demo_result:
        demo_context = f"""
Demo Result to include in slides:
{json.dumps(demo_result, ensure_ascii=False, indent=2)}
"""

    user_message = f"""Create a complete reveal.js presentation for MoodMeshi.

MoodMeshi is a web application that:
- Takes user's mood as text input
- Uses Claude AI (Orchestrator-Workers pattern) to analyze mood
- Searches Rakuten Recipe API for matching recipes
- Provides 3 personalized meal proposals with nutrition and seasonal insights
- Built with FastAPI + Jinja2 + HTMX

Architecture:
- Orchestrator (Claude Sonnet): Analyzes mood, integrates results
- Worker A - RecipeHunter (Claude Haiku + Tool Use): Searches Rakuten API
- Worker B - NutritionAdvisor (Claude Haiku): Provides nutrition advice
- Worker C - SeasonalSommelier (Claude Haiku): Seasonal food recommendations
- All 3 workers run in parallel with asyncio.gather()

{demo_context}

Please create a complete, self-contained HTML file with reveal.js embedded via CDN.
Use warm colors (primary: #e8531d, accent: #f5a623) matching the MoodMeshi brand.
Make it visually impressive for a presentation."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=PRESENTATION_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    )

    html_content = ""
    for block in response.content:
        if hasattr(block, "text"):
            html_content += block.text

    # Extract HTML if wrapped in code blocks
    if "```html" in html_content:
        start = html_content.find("```html") + 7
        end = html_content.rfind("```")
        if end > start:
            html_content = html_content[start:end].strip()
    elif "```" in html_content:
        start = html_content.find("```") + 3
        end = html_content.rfind("```")
        if end > start:
            html_content = html_content[start:end].strip()

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path
