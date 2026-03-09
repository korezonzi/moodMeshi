"""Block Kit builder functions for the MoodMeshi Slack bot.

All functions are pure (no side effects) and return Slack Block Kit structures.
"""

from app.agents.types import FinalProposal, ProposedMeal

# Ordered list of phase keys matching orchestrator progress callbacks
PHASE_ORDER = ["phase1", "phase2_recipe", "phase2_nutrition", "phase2_seasonal", "phase3"]

PHASE_LABELS: dict[str, str] = {
    "phase1": "気分を分析中",
    "phase2_recipe": "レシピを探中",
    "phase2_nutrition": "栄養を分析中",
    "phase2_seasonal": "季節の食材を確認中",
    "phase3": "最終提案を生成中",
}

_DONE = "✅"
_RUNNING = "⏳"
_PENDING = "⬜"


def build_progress_blocks(current_phase: str, user_input: str) -> list[dict]:
    """Build progress indicator blocks. current_phase is the phase currently executing."""
    phase_index = PHASE_ORDER.index(current_phase) if current_phase in PHASE_ORDER else -1

    lines: list[str] = []
    for i, phase in enumerate(PHASE_ORDER):
        label = PHASE_LABELS[phase]
        if i < phase_index:
            icon = _DONE
        elif i == phase_index:
            icon = _RUNNING
        else:
            icon = _PENDING
        lines.append(f"{icon} {label}")

    progress_text = "\n".join(lines)

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*「{user_input}」の気分に合う料理を探しています...*",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": progress_text,
            },
        },
    ]


def build_result_blocks(proposal: FinalProposal, show_all: bool = False) -> list[dict]:
    """Build result display blocks.

    When show_all=False, shows top 3 proposals + a "show more" button.
    When show_all=True, shows all 6 proposals.
    """
    blocks: list[dict] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🍽️ *{proposal.greeting}*",
            },
        },
        {"type": "divider"},
    ]

    display_proposals = proposal.proposals[:6] if show_all else proposal.proposals[:3]

    for meal in display_proposals:
        blocks.extend(_build_meal_blocks(meal))
        blocks.append({"type": "divider"})

    if not show_all and len(proposal.proposals) > 3:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "他の3候補も見る ▼",
                        },
                        "action_id": "moodmeshi_show_more",
                    }
                ],
            }
        )

    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"_{proposal.closing_message}_",
            },
        }
    )

    return blocks


def _build_meal_blocks(meal: ProposedMeal) -> list[dict]:
    """Build Block Kit blocks for a single meal proposal."""
    recipe = meal.recipe
    title = recipe.recipe_title or "（タイトルなし）"

    # Build metadata line
    meta_parts: list[str] = []
    if recipe.recipe_indication:
        meta_parts.append(f"⏱ {recipe.recipe_indication}")
    if recipe.recipe_cost:
        meta_parts.append(f"💰 {recipe.recipe_cost}")
    meta_line = " | ".join(meta_parts) if meta_parts else ""

    # Build detail text
    detail_lines = [f"推奨理由: {meal.why_recommended}"]
    if meal.nutrition_point:
        detail_lines.append(f"🥗 栄養: {meal.nutrition_point}")
    if meal.seasonal_point:
        detail_lines.append(f"🌸 旬: {meal.seasonal_point}")

    detail_text = "\n".join(detail_lines)
    full_text = f"*{meal.rank}位: {title}*"
    if meta_line:
        full_text += f"\n{meta_line}"
    full_text += f"\n{detail_text}"

    section: dict = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": full_text,
        },
    }

    # Add thumbnail accessory when image URL is available
    if recipe.food_image_url:
        section["accessory"] = {
            "type": "image",
            "image_url": recipe.food_image_url,
            "alt_text": title,
        }

    blocks: list[dict] = [section]

    # Recipe link button
    if recipe.recipe_url:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "レシピを見る ↗",
                        },
                        "url": recipe.recipe_url,
                        "action_id": f"moodmeshi_recipe_link_{meal.rank}",
                    }
                ],
            }
        )

    return blocks


def build_modal_view() -> dict:
    """Build the mood input modal view."""
    mood_chip_options = [
        {"text": {"type": "plain_text", "text": "😫 疲れた"}, "value": "疲れた"},
        {"text": {"type": "plain_text", "text": "😊 元気"}, "value": "元気"},
        {"text": {"type": "plain_text", "text": "😟 落ち込んでいる"}, "value": "落ち込んでいる"},
        {"text": {"type": "plain_text", "text": "🥵 暑い"}, "value": "暑い"},
        {"text": {"type": "plain_text", "text": "🥶 寒い"}, "value": "寒い"},
        {"text": {"type": "plain_text", "text": "🍰 甘いものが食べたい"}, "value": "甘いものが食べたい"},
        {"text": {"type": "plain_text", "text": "🥩 がっつり食べたい"}, "value": "がっつり食べたい"},
        {"text": {"type": "plain_text", "text": "🥗 ヘルシーにしたい"}, "value": "ヘルシーにしたい"},
    ]

    return {
        "type": "modal",
        "callback_id": "moodmeshi_modal",
        "title": {"type": "plain_text", "text": "今日の気分を教えて 🍽️"},
        "submit": {"type": "plain_text", "text": "提案してもらう 🔍"},
        "close": {"type": "plain_text", "text": "キャンセル"},
        "blocks": [
            {
                "type": "input",
                "block_id": "mood_text_block",
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "mood_text",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "例: 疲れているけど元気を出したい",
                    },
                    "multiline": False,
                },
                "label": {"type": "plain_text", "text": "気分・今の状態"},
                "hint": {
                    "type": "plain_text",
                    "text": "自由に入力してください。気分チップと組み合わせてもOKです。",
                },
            },
            {
                "type": "input",
                "block_id": "mood_chip_block",
                "optional": True,
                "element": {
                    "type": "static_select",
                    "action_id": "mood_chip",
                    "placeholder": {"type": "plain_text", "text": "気分を選ぶ（任意）"},
                    "options": mood_chip_options,
                },
                "label": {"type": "plain_text", "text": "または気分チップから選ぶ"},
                "hint": {
                    "type": "plain_text",
                    "text": "チップを選んだ場合は優先されます",
                },
            },
        ],
    }


def build_error_blocks(message: str = "エラーが発生しました。") -> list[dict]:
    """Build error message blocks."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"⚠️ *{message}*\nしばらくしてからもう一度お試しください。",
            },
        }
    ]
