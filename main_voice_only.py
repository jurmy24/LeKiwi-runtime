import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from livekit import rtc, agents
from livekit.agents import (
    Agent,
    RoomInputOptions,
    AgentSession,
    function_tool,
)
from livekit.plugins import (
    cartesia,
    openai,
    silero,
    noise_cancellation,
)

load_dotenv()


def _load_system_prompt() -> str:
    """Load the system prompt from the personality/system.txt file."""
    # Get the directory where this file is located
    current_dir = Path(__file__).parent
    system_prompt_path = current_dir / "lekiwi" / "personality" / "system.txt"

    try:
        with open(system_prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"System prompt file not found at {system_prompt_path}. "
            "Please ensure the file exists."
        )


class LeKiwiVoiceTest(Agent):
    def __init__(self):
        super().__init__(instructions=_load_system_prompt())
        # No motor services - voice AI only

    @function_tool
    async def get_configuration(self) -> str:
        """
        Get the status of the robot.
        """
        # TODO: Implement this with proper configuration checking and return as json () - see https://github.com/TARS-AI-Community/TARS-AI/blob/V2/src/character/TARS/persona.ini
        return "Status: Nominal (Voice Test Mode - No Motors Connected)"


# Entry to the agent
async def entrypoint(ctx: agents.JobContext):
    agent = LeKiwiVoiceTest()

    session = AgentSession(
        vad=silero.VAD.load(
            min_speech_duration=0.5,      # Require 500ms of continuous speech
            min_silence_duration=1.0,     # Require 1 second of silence to detect turn end
            activation_threshold=0.8,     # Very high threshold - ignore most sounds
        ),  # Voice Activity Detection - tuned to prevent interruption
        stt=cartesia.STT(),      # Or deepgram.STT() for faster/cheaper option
        llm=openai.LLM(model="gpt-4o-mini"),  # Fast streaming LLM
        tts=cartesia.TTS(
            model="sonic-3",
            voice="87748186-23bb-4158-a1eb-332911b0b708",
        ),
        # Disable interruption - bot must finish speaking before listening again
        preemptive_generation=False,      # Don't allow overlapping speech
        resume_false_interruption=False,  # Don't resume after interruption attempts
        allow_interruptions=False,        # Explicitly disable interruptions
    )

    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(
            audio_enabled=True,
            audio_sample_rate=16000,
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await session.generate_reply(
        instructions=f"""When you wake up, greet with: 'Systems nominal. Radio check complete. Over.'"""
    )


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint, num_idle_processes=1)
    )
