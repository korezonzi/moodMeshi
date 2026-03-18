"""Slack Bolt AsyncApp and event handlers for MoodMeshi.

Handles:
  - /meshi slash command (with or without text argument)
  - moodmeshi_modal view submission
  - moodmeshi_show_more button action
"""

import asyncio
import logging
import re
from typing import Any

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from app.agents.orchestrator import run_orchestrator
from app.agents.types import FinalProposal, ProcessingLog
from app.config import settings
from app.slack_formatter import (
    build_error_blocks,
    build_favorites_blocks,
    build_history_blocks,
    build_log_blocks,
    build_modal_view,
    build_progress_blocks,
    build_result_blocks,
    build_settings_blocks,
    build_settings_modal_view,
)

logger = logging.getLogger(__name__)

bolt_app = AsyncApp(
    token=settings.SLACK_BOT_TOKEN,
    signing_secret=settings.SLACK_SIGNING_SECRET,
    process_before_response=True,
)
bolt_handler = AsyncSlackRequestHandler(bolt_app)

# In-memory cache: "{channel}:{ts}" -> (FinalProposal, ProcessingLog)
_cache: dict[str, tuple[FinalProposal, ProcessingLog]] = {}

_MAX_CACHE_SIZE = 100


def _store_cache(channel: str, ts: str, proposal: FinalProposal, log: ProcessingLog) -> None:
    """Store proposal + log and evict oldest entries when cache is full."""
    key = f"{channel}:{ts}"
    if len(_cache) >= _MAX_CACHE_SIZE:
        oldest = next(iter(_cache))
        del _cache[oldest]
    _cache[key] = (proposal, log)


async def _run_and_update_via_chat(
    user_input: str,
    channel: str,
    ts: str,
    client: Any,
    slack_user_id: str | None = None,
) -> None:
    """Background task: run orchestrator and update a chat message by ts."""

    async def progress_callback(phase: str, _message: str) -> None:
        blocks = build_progress_blocks(phase, user_input)
        try:
            await client.chat_update(channel=channel, ts=ts, blocks=blocks, text="処理中...")
        except Exception:
            logger.exception("Failed to update progress message")

    try:
        proposal, log = await run_orchestrator(
            user_input,
            progress_callback,
            user_id=slack_user_id,
            slack_channel_id=channel,
        )
        result_blocks = build_result_blocks(proposal, show_all=False)
        await client.chat_update(channel=channel, ts=ts, blocks=result_blocks, text="提案が完成しました！")
        _store_cache(channel, ts, proposal, log)
    except Exception as exc:
        logger.exception("Error in _run_and_update_via_chat: %s", exc)
        try:
            await client.chat_update(
                channel=channel,
                ts=ts,
                blocks=build_error_blocks(str(exc)),
                text="エラーが発生しました",
            )
        except Exception:
            logger.exception("Failed to send error update")


# ---------------------------------------------------------------------------
# Slash command: /meshi [text]
# ---------------------------------------------------------------------------


@bolt_app.command("/meshi")
async def handle_meshi_command(ack: Any, body: dict, client: Any) -> None:
    """Handle /meshi slash command.

    - With text argument: posts progress message to the channel, processes in background.
    - Without text argument: opens a modal with channel_id stored in private_metadata.
    Subcommands: history, favorites, settings
    """
    await ack()

    raw_text: str = (body.get("text") or "").strip()
    channel_id: str = body.get("channel_id", "")
    slack_user_id: str = body.get("user_id", "")

    # --- subcommand routing ---
    if raw_text == "history":
        await _handle_history_subcommand(slack_user_id, channel_id, client)
        return

    if raw_text == "favorites":
        await _handle_favorites_subcommand(slack_user_id, channel_id, client)
        return

    if raw_text.startswith("settings"):
        args = raw_text[len("settings"):].strip()
        await _handle_settings_subcommand(slack_user_id, channel_id, client, args)
        return

    user_input = raw_text

    if not user_input:
        # Store channel_id + user_id in modal so submission knows where to post
        trigger_id: str = body.get("trigger_id", "")
        modal = build_modal_view()
        modal["private_metadata"] = f"{channel_id}:{slack_user_id}"
        try:
            await client.views_open(trigger_id=trigger_id, view=modal)
        except Exception:
            logger.exception("Failed to open modal")
        return

    # Post initial progress message to the channel
    try:
        msg = await client.chat_postMessage(
            channel=channel_id,
            blocks=build_progress_blocks("phase1", user_input),
            text="処理中...",
        )
        ts: str = msg["ts"]
    except Exception:
        logger.exception("Failed to post initial message to channel %s", channel_id)
        return

    asyncio.create_task(
        _run_and_update_via_chat(user_input, channel_id, ts, client, slack_user_id=slack_user_id)
    )


# ---------------------------------------------------------------------------
# Modal submission: moodmeshi_modal
# ---------------------------------------------------------------------------


@bolt_app.view("moodmeshi_modal")
async def handle_modal_submission(ack: Any, body: dict, client: Any) -> None:
    """Handle submission of the mood input modal.

    Extracts user input (chip takes priority over free text), then posts
    the progress message to the channel stored in private_metadata.
    """
    await ack()

    values: dict = body.get("view", {}).get("state", {}).get("values", {})

    # Chip selection takes priority over free text
    chip_value: str | None = (
        values.get("mood_chip_block", {})
        .get("mood_chip", {})
        .get("selected_option", {})
        or {}
    ).get("value")

    free_text: str = (
        values.get("mood_text_block", {}).get("mood_text", {}).get("value") or ""
    ).strip()

    user_input = chip_value or free_text
    if not user_input:
        user_input = "なんとなく美味しいものが食べたい"

    # Retrieve channel_id and user_id stored when the modal was opened
    private_metadata: str = body.get("view", {}).get("private_metadata", "")
    if ":" in private_metadata:
        channel_id, slack_user_id = private_metadata.split(":", 1)
    else:
        channel_id = private_metadata
        slack_user_id = body.get("user", {}).get("id", "")

    if not channel_id:
        logger.error("No channel_id found in modal private_metadata")
        return

    # Post initial progress message to the original channel
    try:
        msg = await client.chat_postMessage(
            channel=channel_id,
            blocks=build_progress_blocks("phase1", user_input),
            text="処理中...",
        )
        ts: str = msg["ts"]
    except Exception:
        logger.exception("Failed to post initial message to channel %s", channel_id)
        return

    asyncio.create_task(
        _run_and_update_via_chat(user_input, channel_id, ts, client, slack_user_id=slack_user_id)
    )


# ---------------------------------------------------------------------------
# Button action: show more proposals
# ---------------------------------------------------------------------------


@bolt_app.action("moodmeshi_show_more")
async def handle_show_more(ack: Any, body: dict, client: Any) -> None:
    """Expand the result to show all 6 proposals."""
    await ack()

    channel: str = body.get("channel", {}).get("id", "")
    ts: str = body.get("message", {}).get("ts", "")
    cached = _cache.get(f"{channel}:{ts}")

    if cached is None:
        try:
            await client.chat_update(
                channel=channel,
                ts=ts,
                blocks=build_error_blocks("キャッシュが見つかりません。もう一度 /meshi を実行してください。"),
                text="エラー",
            )
        except Exception:
            logger.exception("Failed to send cache-miss error")
        return

    proposal, _log = cached
    try:
        await client.chat_update(
            channel=channel,
            ts=ts,
            blocks=build_result_blocks(proposal, show_all=True),
            text="全候補を表示しました",
        )
    except Exception:
        logger.exception("Failed to update message for show_more")


@bolt_app.action("moodmeshi_show_log")
async def handle_show_log(ack: Any, body: dict, client: Any) -> None:
    """Post the processing log as a thread reply."""
    await ack()

    channel: str = body.get("channel", {}).get("id", "")
    ts: str = body.get("message", {}).get("ts", "")
    cached = _cache.get(f"{channel}:{ts}")

    if cached is None:
        try:
            await client.chat_postMessage(
                channel=channel,
                thread_ts=ts,
                text="ログが見つかりません。もう一度 /meshi を実行してください。",
            )
        except Exception:
            logger.exception("Failed to send log cache-miss error")
        return

    _proposal, log = cached
    try:
        await client.chat_postMessage(
            channel=channel,
            thread_ts=ts,
            blocks=build_log_blocks(log),
            text="処理ログ",
        )
    except Exception:
        logger.exception("Failed to post log")


@bolt_app.action(re.compile(r"moodmeshi_recipe_link_\d+"))
async def handle_recipe_link(ack: Any) -> None:
    """Ack recipe link button clicks (the url field handles the actual navigation)."""
    await ack()


# ---------------------------------------------------------------------------
# Subcommand helpers
# ---------------------------------------------------------------------------


async def _handle_history_subcommand(user_id: str, channel_id: str, client: Any) -> None:
    """Handle /meshi history."""
    if not settings.DATABASE_URL:
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="DB機能が設定されていません。",
        )
        return

    from app.database import repository
    sessions = await repository.get_recent_sessions(user_id, limit=5)
    blocks = build_history_blocks(sessions)
    try:
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            blocks=blocks,
            text="検索履歴",
        )
    except Exception:
        logger.exception("Failed to post history")


async def _handle_favorites_subcommand(user_id: str, channel_id: str, client: Any) -> None:
    """Handle /meshi favorites."""
    if not settings.DATABASE_URL:
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="DB機能が設定されていません。",
        )
        return

    from app.database import repository
    meals = await repository.get_favorited_meals(user_id)
    blocks = build_favorites_blocks(meals)
    try:
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            blocks=blocks,
            text="お気に入りレシピ",
        )
    except Exception:
        logger.exception("Failed to post favorites")


async def _handle_settings_subcommand(
    user_id: str, channel_id: str, client: Any, args: str
) -> None:
    """Handle /meshi settings [args]."""
    if not settings.DATABASE_URL:
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="DB機能が設定されていません。",
        )
        return

    from app.database import repository

    if args:
        # Quick-save from command line: /meshi settings アレルギー: エビ
        allergy: str | None = None
        preference: str | None = None
        if "アレルギー:" in args or "アレルギー：" in args:
            allergy = re.sub(r"アレルギー[：:]", "", args).strip()
        elif "好み:" in args or "好み：" in args:
            preference = re.sub(r"好み[：:]", "", args).strip()
        else:
            preference = args

        await repository.upsert_user_prefs(user_id, allergy_notes=allergy, preference_notes=preference)
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="設定を保存しました！次回の提案から反映されます。",
        )
    else:
        prefs = await repository.get_user_prefs(user_id)
        allergy_notes = prefs.allergy_notes if prefs else None
        preference_notes = prefs.preference_notes if prefs else None
        blocks = build_settings_blocks(allergy_notes, preference_notes)
        try:
            await client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                blocks=blocks,
                text="ユーザー設定",
            )
        except Exception:
            logger.exception("Failed to post settings")


# ---------------------------------------------------------------------------
# Button action: save/favorite recipe
# ---------------------------------------------------------------------------


@bolt_app.action("moodmeshi_save_recipe")
async def handle_save_recipe(ack: Any, body: dict, client: Any) -> None:
    """Toggle favorite state for a meal."""
    await ack()

    if not settings.DATABASE_URL:
        return

    meal_id_str: str = (body.get("actions") or [{}])[0].get("value", "")
    if not meal_id_str.isdigit():
        return

    meal_id = int(meal_id_str)
    channel: str = body.get("channel", {}).get("id", "")
    ts: str = body.get("message", {}).get("ts", "")
    user_id: str = body.get("user", {}).get("id", "")

    from app.database import repository
    new_state = await repository.toggle_favorite(meal_id)

    # Notify user
    status = "⭐ お気に入りに追加しました！" if new_state else "✅ お気に入りを解除しました。"
    try:
        await client.chat_postEphemeral(
            channel=channel,
            user=user_id,
            thread_ts=ts,
            text=status,
        )
    except Exception:
        logger.exception("Failed to post save confirmation")


# ---------------------------------------------------------------------------
# Button action: reshow a past session
# ---------------------------------------------------------------------------


@bolt_app.action("moodmeshi_reshow_session")
async def handle_reshow_session(ack: Any, body: dict, client: Any) -> None:
    """Re-display all meals from a past session."""
    await ack()

    if not settings.DATABASE_URL:
        return

    session_id_str: str = (body.get("actions") or [{}])[0].get("value", "")
    if not session_id_str.isdigit():
        return

    channel: str = body.get("channel", {}).get("id", "")
    user_id: str = body.get("user", {}).get("id", "")

    from app.database import repository
    meals = await repository.get_session_meals(int(session_id_str))
    if not meals:
        await client.chat_postEphemeral(
            channel=channel, user=user_id, text="セッションが見つかりません。"
        )
        return

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "🍽️ *過去の提案*"},
        },
        {"type": "divider"},
    ]
    for meal in meals:
        title = meal.recipe_title or "（タイトルなし）"
        text = f"*{meal.rank}位: {title}*"
        if meal.why_recommended:
            text += f"\n{meal.why_recommended}"
        section: dict = {"type": "section", "text": {"type": "mrkdwn", "text": text}}
        if meal.food_image_url:
            section["accessory"] = {
                "type": "image",
                "image_url": meal.food_image_url,
                "alt_text": title,
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
                        }
                    ],
                }
            )
        blocks.append({"type": "divider"})

    try:
        await client.chat_postEphemeral(
            channel=channel, user=user_id, blocks=blocks, text="過去の提案"
        )
    except Exception:
        logger.exception("Failed to post reshow session")


# ---------------------------------------------------------------------------
# Button action: open settings modal
# ---------------------------------------------------------------------------


@bolt_app.action("moodmeshi_open_settings_modal")
async def handle_open_settings_modal(ack: Any, body: dict, client: Any) -> None:
    """Open the settings modal."""
    await ack()

    if not settings.DATABASE_URL:
        return

    user_id: str = body.get("user", {}).get("id", "")
    trigger_id: str = body.get("trigger_id", "")

    from app.database import repository
    prefs = await repository.get_user_prefs(user_id)
    allergy_notes = prefs.allergy_notes if prefs else None
    preference_notes = prefs.preference_notes if prefs else None

    modal = build_settings_modal_view(allergy_notes, preference_notes)
    modal["private_metadata"] = user_id
    try:
        await client.views_open(trigger_id=trigger_id, view=modal)
    except Exception:
        logger.exception("Failed to open settings modal")


# ---------------------------------------------------------------------------
# Modal submission: moodmeshi_settings_modal
# ---------------------------------------------------------------------------


@bolt_app.view("moodmeshi_settings_modal")
async def handle_settings_modal_submission(ack: Any, body: dict, client: Any) -> None:
    """Save user settings from modal."""
    await ack()

    if not settings.DATABASE_URL:
        return

    user_id: str = body.get("view", {}).get("private_metadata", "")
    if not user_id:
        user_id = body.get("user", {}).get("id", "")

    values: dict = body.get("view", {}).get("state", {}).get("values", {})
    allergy_notes: str | None = (
        values.get("allergy_block", {}).get("allergy_input", {}).get("value") or None
    )
    preference_notes: str | None = (
        values.get("preference_block", {}).get("preference_input", {}).get("value") or None
    )

    from app.database import repository
    await repository.upsert_user_prefs(user_id, allergy_notes=allergy_notes, preference_notes=preference_notes)


# Ack link button clicks for favorites list
@bolt_app.action(re.compile(r"moodmeshi_fav_link_\d+"))
async def handle_fav_link(ack: Any) -> None:
    """Ack favorite recipe link button clicks."""
    await ack()
