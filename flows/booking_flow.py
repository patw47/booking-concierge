"""
Booking concierge conversation flow — Sprint 3.

pipecat-ai-flows is NOT used here: it has no official support for
OpenAIRealtimeLLMService (context_aggregator mismatch, server-side context
not reset-able by LLMMessagesUpdateFrame). Instead, state is tracked locally
and language switches are applied via LLMUpdateSettingsFrame → session.update.

States (linear, but branching allowed):
  GREETING → INFO / BOOKING_COLLECT → BOOKING_CONFIRM → FAREWELL

Language switching: LLM calls switch_to_french / switch_to_english at any
point. The tool pushes a full prompt swap via LLMUpdateSettingsFrame.
"""

import asyncio
from enum import Enum

from loguru import logger
from pipecat.adapters.schemas.direct_function import tool_options
from pipecat.frames.frames import LLMUpdateSettingsFrame
from pipecat.services.llm_service import FunctionCallParams, LLMSettings


class FlowState(Enum):
    GREETING = "greeting"
    INFO = "info"
    BOOKING_COLLECT = "booking_collect"
    BOOKING_CONFIRM = "booking_confirm"
    FAREWELL = "farewell"


class BookingFlow:
    """Lightweight state tracker for the booking concierge conversation."""

    def __init__(self):
        self.state = FlowState.GREETING
        self.language = "en"

    def transition(self, new_state: FlowState):
        logger.info(f"[flow] {self.state.value} → {new_state.value} (lang={self.language})")
        self.state = new_state

    def make_tools(self, llm, prompts: dict):
        """
        Return flow-navigation tool functions closed over `llm` and `prompts`.

        Args:
            llm: OpenAIRealtimeLLMService instance — used to push LLMUpdateSettingsFrame.
            prompts: dict with keys "en" and "fr" (full system prompt strings).

        Returns:
            (switch_to_french, switch_to_english, end_conversation)
        """
        flow = self

        async def _push_prompt(lang: str):
            try:
                await llm.push_frame(
                    LLMUpdateSettingsFrame(delta=LLMSettings(system_instruction=prompts[lang]))
                )
            except Exception as exc:
                logger.error(f"[flow] push_frame language={lang} failed: {exc}")

        @tool_options(cancel_on_interruption=False)
        async def switch_to_french(params: FunctionCallParams):
            """Switch the entire conversation to French immediately.
            Call this as soon as the guest speaks or writes in French.
            """
            flow.language = "fr"
            logger.info(f"[flow] Language → FR (state={flow.state.value})")
            # Scheduled after result_callback so the frame is not pushed while
            # the LLM is still processing this tool call.
            asyncio.create_task(_push_prompt("fr"))
            await params.result_callback({"ok": True, "language": "fr"})

        @tool_options(cancel_on_interruption=False)
        async def switch_to_english(params: FunctionCallParams):
            """Switch the entire conversation to English immediately.
            Call this as soon as the guest speaks or writes in English.
            """
            flow.language = "en"
            logger.info(f"[flow] Language → EN (state={flow.state.value})")
            asyncio.create_task(_push_prompt("en"))
            await params.result_callback({"ok": True, "language": "en"})

        @tool_options(cancel_on_interruption=False)
        async def end_conversation(params: FunctionCallParams):
            """Signal that the conversation is complete.
            Call this after the guest has been thanked and the booking confirmed
            or after they say goodbye.
            """
            flow.transition(FlowState.FAREWELL)
            await params.result_callback({
                "ok": True,
                "message": "Thank the guest warmly, wish them a pleasant stay, and say goodbye.",
            })

        return switch_to_french, switch_to_english, end_conversation
