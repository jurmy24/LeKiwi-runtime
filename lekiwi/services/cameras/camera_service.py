import threading
import logging
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import cv2


# Debug: directory for saving images
DEBUG_IMAGE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "images"


@dataclass
class CameraConfig:
    """Configuration for a single camera."""
    device_id: int
    width: int = 640
    height: int = 480
    fps: int = 30
    jpeg_quality: int = 85


class CameraService:
    """
    Service for capturing images from one or more cameras.
    
    Each camera runs in its own background thread, continuously capturing
    frames and encoding them as JPEG. The latest frame for each camera
    is stored and can be retrieved instantly via get_image().
    
    Usage:
        camera_config = {
            "front": CameraConfig(device_id=0, width=640, height=480),
            "side": CameraConfig(device_id=2, width=640, height=480),
        }
        service = CameraService(camera_config)
        service.start()
        
        # Get latest frame as JPEG bytes
        image_bytes = service.get_image("front")
        
        service.stop()
    """
    
    def __init__(self, cameras: dict[str, CameraConfig]):
        """
        Initialize the camera service.
        
        Args:
            cameras: Dict mapping camera labels to their configurations.
                     Example: {"front": CameraConfig(device_id=0)}
        """
        self.cameras = cameras
        self.logger = logging.getLogger("service.cameras")
        
        # Per-camera state
        self._captures: dict[str, cv2.VideoCapture] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._frames: dict[str, Optional[bytes]] = {}
        self._frame_locks: dict[str, threading.Lock] = {}
        
        # Global state
        self._running = threading.Event()
    
    def start(self) -> None:
        """Start capture threads for all configured cameras."""
        if self._running.is_set():
            self.logger.warning("Camera service is already running")
            return
        
        self._running.set()
        
        for label, config in self.cameras.items():
            # Initialize capture
            cap = cv2.VideoCapture(config.device_id)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)
            cap.set(cv2.CAP_PROP_FPS, config.fps)
            
            if not cap.isOpened():
                self.logger.error(f"Failed to open camera '{label}' (device {config.device_id})")
                continue
            
            self._captures[label] = cap
            self._frames[label] = None
            self._frame_locks[label] = threading.Lock()
            
            # Start capture thread
            thread = threading.Thread(
                target=self._capture_loop,
                args=(label, config),
                daemon=True,
                name=f"camera-{label}"
            )
            self._threads[label] = thread
            thread.start()
            
            self.logger.info(f"Started camera '{label}' (device {config.device_id}, {config.width}x{config.height})")
        
        self.logger.info(f"Camera service started with {len(self._captures)} camera(s)")
    
    def stop(self, timeout: float = 5.0) -> None:
        """Stop all capture threads and release cameras."""
        if not self._running.is_set():
            self.logger.warning("Camera service is not running")
            return
        
        self.logger.info("Stopping camera service...")
        self._running.clear()
        
        # Wait for threads to finish
        for label, thread in self._threads.items():
            if thread.is_alive():
                thread.join(timeout=timeout)
                if thread.is_alive():
                    self.logger.warning(f"Camera thread '{label}' did not stop within timeout")
        
        # Release captures
        for label, cap in self._captures.items():
            cap.release()
            self.logger.info(f"Released camera '{label}'")
        
        # Clear state
        self._captures.clear()
        self._threads.clear()
        self._frames.clear()
        self._frame_locks.clear()
        
        self.logger.info("Camera service stopped")
    
    def _capture_loop(self, label: str, config: CameraConfig) -> None:
        """Background thread that continuously captures frames from a camera."""
        cap = self._captures[label]
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, config.jpeg_quality]
        
        while self._running.is_set():
            ret, frame = cap.read()
            
            if not ret:
                self.logger.warning(f"Failed to read frame from camera '{label}'")
                continue
            
            # Rotate 180 degrees (camera is mounted upside down)
            frame = cv2.rotate(frame, cv2.ROTATE_180)
            
            # Encode as JPEG
            success, jpeg_bytes = cv2.imencode('.jpg', frame, encode_params)
            
            if not success:
                self.logger.warning(f"Failed to encode frame from camera '{label}'")
                continue
            
            # Store the latest frame
            with self._frame_locks[label]:
                self._frames[label] = jpeg_bytes.tobytes()
    
    def get_image(self, label: str) -> Optional[bytes]:
        """
        Get the latest image from a camera as JPEG bytes.
        
        Args:
            label: The camera label (e.g., "front", "side")
        
        Returns:
            JPEG-encoded image bytes, or None if no frame is available
            or the camera doesn't exist.
        """
        if label not in self._frame_locks:
            self.logger.warning(f"Camera '{label}' not found")
            return None
        
        with self._frame_locks[label]:
            image_bytes = self._frames[label]
        
        # # Debug: save image to disk
        # if image_bytes:
        #     DEBUG_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        #     timestamp = int(time.time() * 1000)
        #     debug_path = DEBUG_IMAGE_DIR / f"{label}_{timestamp}.jpg"
        #     debug_path.write_bytes(image_bytes)
        #     self.logger.debug(f"Saved debug image: {debug_path}")
        
        return image_bytes
    
    def get_all_images(self) -> dict[str, Optional[bytes]]:
        """
        Get the latest images from all cameras.
        
        Returns:
            Dict mapping camera labels to their latest JPEG bytes.
        """
        result = {}
        for label in self._frames.keys():
            result[label] = self.get_image(label)
        return result
    
    @property
    def is_running(self) -> bool:
        """Check if the camera service is running."""
        return self._running.is_set()
    
    @property
    def camera_labels(self) -> list[str]:
        """Get list of configured camera labels."""
        return list(self.cameras.keys())
