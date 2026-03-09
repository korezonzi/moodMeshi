"""Slack Bolt AsyncApp and event handlers for MoodMeshi.

Handles:
  - /meshi slash command (with or without text argument)
  - moodmeshi_modal view submission
  - moodmeshi_show_more button action
"""

import asyncio
import logging
from typing import Any

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from app.agents.orchestrator import run_orchestrator
from app.agents.types import FinalProposal
from app.config import settings
from app.slack_formatter import (
    build_error_blocks,
    build_modal_view,
    build_progress_blocks,
    build_result_blocks,
)

logger = logging.getLogger(__name__)

bolt_app = AsyncApp(
    token=settings.SLACK_BOT_TOKEN,
    signing_secret=settings.SLACK_SIGNING_SECRET,
    process_before_response=True,
)
bolt_handler = AsyncSlackRequestHandler(bolt_app)

# In-memory cache for "show more" button: "{channel}:{ts}" -> FinalProposal
_proposal_cache: dict[str, FinalProposal] = {}

_MAX_CACHE_SIZE = 100


def _cache_proposal(channel: str, ts: str, proposal: FinalProposal) -> None:
    """Store a proposal and evict oldest entries when cache is full."""
    key = f"{channel}:{ts}"
    if len(_proposal_cache) >= _MAX_CACHE_SIZE:
        oldest = next(iter(_proposal_cache))
        del _proposal_cache[oldest]
    _proposal_cache[key] = proposal


async def _run_and_update_via_chat(
    user_input: str,
    channel: str,
    ts: str,
    client: Any,
) -> None:
    """Background task: run orchestrator and update a chat message by ts."""

    async def progress_callback(phase: str, _message: str) -> None:
        blocks = build_progress_blocks(phase, user_input)
        try:
            await client.chat_update(channel=channel, ts=ts, blocks=blocks, text="処理中...")
        except Exception:
            logger.exception("Failed to update progress message")

    try:
        proposal, _log = await run_orchestrator(user_input, progress_callback)
        result_blocks = build_result_blocks(proposal, show_all=False)
        await client.chat_update(channel=channel, ts=ts, blocks=result_blocks, text="提案が完成しました！")
        _cache_proposal(channel, ts, proposal)
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
    """
    await ack()

    user_input: str = (body.get("text") or "").strip()
    channel_id: str = body.get("channel_id", "")

    if not user_input:
        # Store channel_id in modal so submission knows where to post
        trigger_id: str = body.get("trigger_id", "")
        modal = build_modal_view()
        modal["private_metadata"] = channel_id
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
        _run_and_update_via_chat(user_input, channel_id, ts, client)
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

    # Retrieve channel_id stored when the modal was opened
    channel_id: str = body.get("view", {}).get("private_metadata", "")

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
        _run_and_update_via_chat(user_input, channel_id, ts, client)
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
    cache_key = f"{channel}:{ts}"

    proposal = _proposal_cache.get(cache_key)
    if proposal is None:
        try:
            await client.chat_update(
                channel=channel,
                ts=ts,
                blocks=build_error_blocks(
                    "キャッシュが見つかりません。もう一度 /meshi を実行してください。"
                ),
                text="エラー",
            )
        except Exception:
            logger.exception("Failed to send cache-miss error")
        return

    try:
        await client.chat_update(
            channel=channel,
            ts=ts,
            blocks=build_result_blocks(proposal, show_all=True),
            text="全候補を表示しました",
        )
    except Exception:
        logger.exception("Failed to update message for show_more")
