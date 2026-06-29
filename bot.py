"""
booking-concierge — Voice concierge agent for Villa Eden Bleu.
Sprint 2: tools wired (get_disponibilites → Google Sheet, creer_reservation → Telegram).

Run:
    python bot.py --transport webrtc
    # Open http://localhost:7860/client/ in browser
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.openai.realtime.events import (
    AudioConfiguration,
    AudioInput,
    InputAudioNoiseReduction,
    InputAudioTranscription,
    SemanticTurnDetection,
    SessionProperties,
)
from pipecat.services.openai.realtime.llm import OpenAIRealtimeLLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.workers.runner import WorkerRunner

from tools.disponibilites import get_disponibilites
from tools.reservation import creer_reservation

# Serve the prebuilt browser UI at /client/
from pipecat.runner.run import app
from pipecat_ai_prebuilt.frontend import PipecatPrebuiltUI

app.mount("/client", PipecatPrebuiltUI)

load_dotenv(override=True)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    """Load prompt file and strip markdown comment lines (lines starting with #)."""
    text = (_PROMPTS_DIR / filename).read_text(encoding="utf-8")
    # Strip single-hash metadata lines (# comment) but keep ## section headers.
    lines = [l for l in text.splitlines() if not (l.startswith("#") and not l.startswith("##"))]
    return "\n".join(lines).strip()


SYSTEM_PROMPT = _load_prompt("system_en.md")

transport_params = {
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
    ),
}


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    llm = OpenAIRealtimeLLMService(
        api_key=os.environ["OPENAI_API_KEY"],
        settings=OpenAIRealtimeLLMService.Settings(
            system_instruction=SYSTEM_PROMPT,
            session_properties=SessionProperties(
                audio=AudioConfiguration(
                    input=AudioInput(
                        transcription=InputAudioTranscription(),
                        turn_detection=SemanticTurnDetection(),
                        noise_reduction=InputAudioNoiseReduction(type="near_field"),
                    )
                ),
            ),
        ),
    )

    context = LLMContext(
        messages=[{"role": "developer", "content": "Greet the visitor briefly."}],
        tools=[get_disponibilites, creer_reservation],
    )

    # realtime_service_mode=True is required — decouples local aggregator from
    # OpenAI's server VAD turn frames to prevent double-firing.
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        realtime_service_mode=True,
    )

    pipeline = Pipeline([
        transport.input(),
        user_aggregator,
        llm,
        transport.output(),
        assistant_aggregator,
    ])

    idle_timeout = int(os.getenv("SESSION_TIMEOUT_SECS", "300"))
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=idle_timeout,
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected — starting pipeline")
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected — stopping worker")
        await worker.cancel()

    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)
    await runner.run()


async def bot(runner_args: RunnerArguments):
    """Entry point — also compatible with Pipecat Cloud."""
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main
    main()
