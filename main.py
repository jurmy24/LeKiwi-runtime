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
    openai,
    noise_cancellation,
)
from lekiwi.services import Priority
from lekiwi.services.motors import ArmsService, WheelsService
from lekiwi.services.pose_detection import PoseDetectionService

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


class LeKiwi(Agent):
    def __init__(self, port: str = "/dev/ttyACM0", robot_id: str = "biden_kiwi"):
        super().__init__(instructions=_load_system_prompt())
        # Three services running on separate threads, with LeKiwi agent dispatching events to them
        # self.wheels_service = WheelsService(port=port, robot_id=robot_id)
        self.arms_service = ArmsService(port=port, robot_id=robot_id)
        self.pose_service = PoseDetectionService(
            port=port,
            robot_id=robot_id,
            status_callback=self._handle_pose_status,  # callback method
        )

        # self.wheels_service.start()
        self.arms_service.start()
        self.pose_service.start()

        # Wake up
        self.arms_service.dispatch("play", "wake_up")

    def _handle_pose_status(self, status_type: str, details: dict):
        """
        Callback method to receive status updates from the PoseDetectionService.
        This runs in the context of the service's worker thread, but is called by it.
        """
        print(
            f"LeKiwi: Received pose status update - Type: {status_type}, Details: {details}"
        )

        if status_type == "PERSON_FALLEN":
            # The main thread (LiveKit orchestrator) decides what to do
            # In an Agent, this often means generating a reply or dispatching a motor action.

            # Example 1: Use the LLM to generate an urgent reply
            # You would need a mechanism to break into the current LLM flow.
            # For simplicity, let's dispatch an action for now.

            # Example 2: Dispatch a HIGH-priority motor action (e.g., look up, check)
            self.arms_service.dispatch("play", "wake_up", priority=Priority.HIGH)
            # log it
            print(f"LeKiwi: Person fallen detected, dispatching spin action")

            # Example 3: Log the event for the main LLM loop to pick up (complex, but robust)
            # You might set a flag or put an event in a queue monitored by the agent's reply loop.
            pass

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
            recordings = self.arms_service.get_available_recordings()

            if recordings:
                result = f"Available recordings: {', '.join(recordings)}"
                return result
            else:
                result = "No recordings found."
                return result
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
            # Send play event to animation service
            self.arms_service.dispatch("play", recording_name)
            result = f"Started playing recording: {recording_name}"
            return result
        except Exception as e:
            result = f"Error playing recording {recording_name}: {str(e)}"
            return result

    @function_tool
    async def get_configuration(self) -> str:
        """
        Get the status of the robot.
        """
        # TODO: Implement this with proper configuration checking and return as json () - see https://github.com/TARS-AI-Community/TARS-AI/blob/V2/src/character/TARS/persona.ini
        return "Status: Nominal"


# Entry to the agent
async def entrypoint(ctx: agents.JobContext):
    agent = LeKiwi()

    session = AgentSession(llm=openai.realtime.RealtimeModel(voice="verse"))

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
        instructions=f"""When you wake up, greet with: 'Systems nominal. What's the plan?' or 'All systems operational. Nice to see you sir.'"""
    )


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint, num_idle_processes=1)
    )
