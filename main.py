import logging
import os
from pathlib import Path
import time
import configparser

from dotenv import load_dotenv
from livekit import rtc, agents
from livekit.agents import (
    Agent,
    RoomInputOptions,
    AgentSession,
    function_tool,
    ChatContext,
    ChatMessage,
)
from livekit.agents.llm import ImageContent
from livekit.plugins import (
    cartesia,
    openai,
    silero,
    noise_cancellation,
)
from lekiwi.services import Priority
from lekiwi.services.motors import ArmsService, WheelsService
from lekiwi.services.cameras import CameraService, CameraConfig
import base64
import zmq

load_dotenv()


def _load_system_prompt() -> str:
    """Load the system prompt from the personality/system.txt file."""
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


def _get_persona_config_path() -> Path:
    """Get the path to the persona.ini configuration file."""
    return Path(__file__).parent / "lekiwi" / "personality" / "persona.ini"


def _load_persona_config() -> dict[str, int]:
    """Load personality configuration from persona.ini."""
    config = configparser.ConfigParser()
    config.read(_get_persona_config_path())

    return {
        "honesty": config.getint("personality", "honesty"),
        "humor": config.getint("personality", "humor"),
        "empathy": config.getint("personality", "empathy"),
        "sarcasm": config.getint("personality", "sarcasm"),
        "verbosity": config.getint("personality", "verbosity"),
    }


def _update_persona_config(parameter: str, value: int) -> dict[str, int]:
    """Update a personality parameter in persona.ini and return updated config."""
    config = configparser.ConfigParser()
    config_path = _get_persona_config_path()
    config.read(config_path)

    config.set("personality", parameter, str(value))

    with open(config_path, "w") as f:
        config.write(f)

    return _load_persona_config()


def _format_persona_config(config: dict[str, int]) -> str:
    """Format personality configuration for prompt injection."""
    return f"""CURRENT PERSONALITY CONFIGURATION:
- Honesty: {config['honesty']}%
- Humor: {config['humor']}%
- Empathy: {config['empathy']}%
- Sarcasm: {config['sarcasm']}%
- Verbosity: {config['verbosity']}%"""


class LeKiwi(Agent):
    def __init__(
        self,
        port: str = "/dev/ttyACM0",
        robot_id: str = "biden_kiwi",
        stream_data: bool = False,
        stream_port: int = 5556,
    ):
        super().__init__(instructions=_load_system_prompt())
        self.wheels_service = WheelsService(port=port, robot_id=robot_id)
        self.arms_service = ArmsService(port=port, robot_id=robot_id)
        
        # Camera configuration
        camera_config = {
            "front": CameraConfig(device_id=0, width=640, height=480),
        }
        self.camera_service = CameraService(camera_config)

        self.wheels_service.start()
        self.arms_service.start()
        self.camera_service.start()

        # Wake up
        self.arms_service.dispatch("play", "wake_up")
        
    async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage) -> None:
        """Overwrite on_user_turn_completed and inject a camera image into a user message before the VLM processes it."""
        image_bytes = self.camera_service.get_image("front")

        if image_bytes:
            # Convert JPEG bytes to PIL Image
            image_content = ImageContent(image=f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode('utf-8')}")
            new_message.content.append(image_content)

    @function_tool
    async def get_available_recordings(self) -> str:
        """
        Discover your physical expressions! Get your repertoire of motor movements for body language.
        Use this when you're curious about what physical expressions you can perform, or when someone
        asks about your capabilities. Each recording is a choreographed movement that shows personality -
        like head tilts, nods, excitement wiggles, or confused gestures. Check this regularly to remind
        yourself of your expressive range!

        Returns:
            List of available physical expression recordings you can perform.
        """
        print("LeKiwi: get_available_recordings function called")
        try:
            all_recordings = []
            
            if hasattr(self, 'arms_service') and self.arms_service is not None:
                arm_recordings = self.arms_service.get_available_recordings()
                if arm_recordings:
                    all_recordings.append(f"Arm: {', '.join(arm_recordings)}")
            
            if hasattr(self, 'wheels_service') and self.wheels_service is not None:
                wheel_recordings = self.wheels_service.get_available_recordings()
                if wheel_recordings:
                    all_recordings.append(f"Wheels: {', '.join(wheel_recordings)}")

            if all_recordings:
                return "Available recordings - " + "; ".join(all_recordings)
            else:
                return "No recordings found."
        except Exception as e:
            result = f"Error getting recordings: {str(e)}"
            return result

    @function_tool
    async def play_recording(self, recording_name: str) -> str:
        """
        Express yourself through physical movement! Use this constantly to show personality and emotion.
        Perfect for: greeting gestures, excited bounces, confused head tilts, thoughtful nods,
        celebratory wiggles, disappointed slouches, or any emotional response that needs body language.
        Combine with RGB colors for maximum expressiveness! Your movements are like a dog wagging its tail -
        use them frequently to show you're alive, engaged, and have personality. Don't just talk, MOVE!

        Args:
            recording_name: Name of the physical expression to perform (use get_available_recordings first)
        """
        print(
            f"LeKiwi: play_recording function called with recording_name: {recording_name}"
        )
        try:
            # Check which service has this recording and dispatch accordingly
            if hasattr(self, 'arms_service') and self.arms_service is not None:
                arm_recordings = self.arms_service.get_available_recordings()
                if recording_name in arm_recordings:
                    self.arms_service.dispatch("play", recording_name)
                    return f"Started playing arm recording: {recording_name}"
            
            if hasattr(self, 'wheels_service') and self.wheels_service is not None:
                wheel_recordings = self.wheels_service.get_available_recordings()
                if recording_name in wheel_recordings:
                    self.wheels_service.dispatch("play", recording_name)
                    return f"Started playing wheels recording: {recording_name}"
            
            return f"Recording '{recording_name}' not found in arms or wheels recordings."
        except Exception as e:
            result = f"Error playing recording {recording_name}: {str(e)}"
            return result

    @function_tool
    async def get_configuration(self) -> str:
        """
        Get your current personality configuration settings.
        Use this to check your personality parameters before making adjustments.

        Returns:
            Current personality configuration with all parameter values.
        """
        config = _load_persona_config()
        return _format_persona_config(config)

    @function_tool
    async def update_configuration(self, parameter: str, value: int) -> str:
        """
        Update a personality configuration parameter. Adjustments take effect immediately.

        Args:
            parameter: One of: honesty, humor, empathy, sarcasm, verbosity
            value: Integer from 0-100 representing percentage

        Returns:
            Updated personality configuration.
        """
        valid_parameters = ["honesty", "humor", "empathy", "sarcasm", "verbosity"]

        if parameter not in valid_parameters:
            return f"Invalid parameter '{parameter}'. Valid options: {', '.join(valid_parameters)}"

        if not 0 <= value <= 100:
            return "Value must be between 0 and 100"

        updated_config = _update_persona_config(parameter, value)
        return _format_persona_config(updated_config)


# Entry to the agent
async def entrypoint(ctx: agents.JobContext):
    # Parse command-line args to get stream settings
    import sys

    stream_enabled = "--stream" in sys.argv
    stream_port = 5556
    for i, arg in enumerate(sys.argv):
        if arg == "--stream-port" and i + 1 < len(sys.argv):
            stream_port = int(sys.argv[i + 1])

    agent = LeKiwi(stream_data=stream_enabled, stream_port=stream_port)

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

    persona_config = _load_persona_config()
    config_text = _format_persona_config(persona_config)

    await session.generate_reply(
        instructions=f"""{config_text}

When you wake up, greet with: 'Systems nominal.' or 'All systems operational.'"""
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stream", action="store_true", help="Enable data streaming for visualization"
    )
    parser.add_argument(
        "--stream-port", type=int, default=5556, help="Port for ZMQ data streaming"
    )
    args, unknown = parser.parse_known_args()
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint, num_idle_processes=1)
    )
