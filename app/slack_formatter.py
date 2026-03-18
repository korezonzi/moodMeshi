"""Block Kit builder functions for the MoodMeshi Slack bot.

All functions are pure (no side effects) and return Slack Block Kit structures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.agents.types import FinalProposal, ProcessingLog, ProposedMeal

if TYPE_CHECKING:
    from app.database.repository import FavoriteMeal, SessionSummary

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

    action_buttons: list[dict] = []

    if not show_all and len(proposal.proposals) > 3:
        action_buttons.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "他の3候補も見る ▼"},
                "action_id": "moodmeshi_show_more",
            }
        )

    action_buttons.append(
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "処理ログを見る 📋"},
            "action_id": "moodmeshi_show_log",
        }
    )

    blocks.append({"type": "actions", "elements": action_buttons})

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


def _build_meal_blocks(meal: ProposedMeal, db_meal_id: int | None = None) -> list[dict]:
    """Build Block Kit blocks for a single meal proposal.

    db_meal_id: proposed_meals.id from DB. When provided, adds a save/favorite button.
    """
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

    # Action buttons: recipe link and optional save button
    action_elements: list[dict] = []

    if recipe.recipe_url:
        action_elements.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "レシピを見る ↗"},
                "url": recipe.recipe_url,
                "action_id": f"moodmeshi_recipe_link_{meal.rank}",
            }
        )

    if db_meal_id is not None:
        action_elements.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "⭐ 保存"},
                "action_id": "moodmeshi_save_recipe",
                "value": str(db_meal_id),
            }
        )

    if action_elements:
        blocks.append({"type": "actions", "elements": action_elements})

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


def build_log_blocks(log: ProcessingLog) -> list[dict]:
    """Build processing log blocks."""
    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "📋 *処理ログ*"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*🧠 気分分析（Phase 1）*\n{log.phase1_summary}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*👥 エージェントの作業（Phase 2）*"},
        },
    ]

    for agent in log.agent_logs:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{agent.agent_name}*\n"
                        f"_{agent.role}_\n"
                        f"• アクション: {agent.action}\n"
                        f"• 結果: {agent.result_summary}"
                    ),
                },
            }
        )

    blocks += [
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*🤖 最終統合（Phase 3）*\n{log.phase3_summary}",
            },
        },
    ]

    return blocks


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


def build_history_blocks(sessions: list[SessionSummary]) -> list[dict]:
    """Build search history blocks for /meshi history."""
    if not sessions:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "📭 まだ検索履歴がありません。`/meshi` で料理を探してみましょう！",
                },
            }
        ]

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "📅 *最近の提案履歴*"},
        },
        {"type": "divider"},
    ]

    for session in sessions:
        date_str = session.created_at.strftime("%-m/%-d %H:%M")
        keywords = "・".join(session.mood_keywords[:3]) if session.mood_keywords else session.user_input
        titles = "、".join(session.meal_titles[:3])
        if len(session.meal_titles) > 3:
            titles += " など"

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📅 *{date_str}* — {keywords}\n{titles}",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "再表示"},
                    "action_id": "moodmeshi_reshow_session",
                    "value": str(session.id),
                },
            }
        )

    return blocks


def build_favorites_blocks(meals: list[FavoriteMeal]) -> list[dict]:
    """Build favorited meals blocks for /meshi favorites."""
    if not meals:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "⭐ まだお気に入りがありません。レシピの「⭐ 保存」ボタンで追加できます！",
                },
            }
        ]

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "⭐ *お気に入りレシピ*"},
        },
        {"type": "divider"},
    ]

    for meal in meals:
        date_str = meal.created_at.strftime("%-m/%-d")
        category = f" ({meal.category_name})" if meal.category_name else ""
        text = f"*{meal.recipe_title}*{category} — {date_str}"
        if meal.why_recommended:
            text += f"\n_{meal.why_recommended}_"

        section: dict = {
            "type": "section",
            "text": {"type": "mrkdwn", "text": text},
        }
        if meal.food_image_url:
            section["accessory"] = {
                "type": "image",
                "image_url": meal.food_image_url,
                "alt_text": meal.recipe_title,
            }
        blocks.append(section)

        if meal.recipe_url:
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "レシピを見る ↗"},
                            "url": meal.recipe_url,
                            "action_id": f"moodmeshi_fav_link_{meal.id}",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🗑 削除"},
                            "action_id": "moodmeshi_save_recipe",
                            "value": str(meal.id),
                            "style": "danger",
                            "confirm": {
                                "title": {"type": "plain_text", "text": "削除しますか？"},
                                "text": {"type": "mrkdwn", "text": "お気に入りから外します。"},
                                "confirm": {"type": "plain_text", "text": "はい"},
                                "deny": {"type": "plain_text", "text": "キャンセル"},
                            },
                        },
                    ],
                }
            )

        blocks.append({"type": "divider"})

    return blocks


def build_settings_blocks(
    allergy_notes: str | None = None,
    preference_notes: str | None = None,
) -> list[dict]:
    """Build user settings display blocks."""
    allergy_text = allergy_notes or "_未設定_"
    pref_text = preference_notes or "_未設定_"

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "⚙️ *ユーザー設定*\n\n"
                    f"🚫 アレルギー: {allergy_text}\n"
                    f"💚 好み: {pref_text}"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✏️ 設定を変更"},
                    "action_id": "moodmeshi_open_settings_modal",
                    "style": "primary",
                }
            ],
        },
    ]


def build_settings_modal_view(
    allergy_notes: str | None = None,
    preference_notes: str | None = None,
) -> dict:
    """Build the settings input modal view."""
    return {
        "type": "modal",
        "callback_id": "moodmeshi_settings_modal",
        "title": {"type": "plain_text", "text": "⚙️ ユーザー設定"},
        "submit": {"type": "plain_text", "text": "保存"},
        "close": {"type": "plain_text", "text": "キャンセル"},
        "blocks": [
            {
                "type": "input",
                "block_id": "allergy_block",
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "allergy_input",
                    "initial_value": allergy_notes or "",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "例: エビ、カニ、ナッツ",
                    },
                    "multiline": False,
                },
                "label": {"type": "plain_text", "text": "🚫 アレルギー・苦手な食材"},
                "hint": {
                    "type": "plain_text",
                    "text": "次回の提案から除外されます",
                },
            },
            {
                "type": "input",
                "block_id": "preference_block",
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "preference_input",
                    "initial_value": preference_notes or "",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "例: 辛い料理が好き、和食中心",
                    },
                    "multiline": True,
                },
                "label": {"type": "plain_text", "text": "💚 好みの傾向"},
                "hint": {
                    "type": "plain_text",
                    "text": "提案の精度を高めるためのメモです",
                },
            },
        ],
    }
