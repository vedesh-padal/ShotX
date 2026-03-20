"""Screen Recorder Backend.

Handles wrapping CLI recording tools (ffmpeg for X11, wf-recorder for Wayland)
and processing logic for generating high-quality MP4/GIF outputs.
"""
import logging
import os
import signal
import subprocess
from pathlib import Path

from PySide6.QtCore import QRect

logger = logging.getLogger(__name__)


class ScreenRecorderError(Exception):
    pass


class ScreenRecorder:
    def __init__(self, fps: int = 30, audio: bool = False):
        self.fps = fps
        self.audio = audio
        self.is_recording = False
        self._process: subprocess.Popen | None = None
        self._output_path: Path | None = None
        self._is_wayland = self._check_is_wayland()

    def _check_is_wayland(self) -> bool:
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        wayland_display = os.environ.get("WAYLAND_DISPLAY", "")
        return session_type == "wayland" or bool(wayland_display)

    def check_dependencies(self) -> None:
        """Check if required command line tools are installed and supported by compositor."""
        if self._is_wayland:
            # GNOME uses Mutter, which explicitly does not support wlr-screencopy.
            # GNOME restricts programmatic screen recording for security reasons.
            desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
            if "gnome" in desktop:
                raise ScreenRecorderError(
                    "GNOME Wayland heavily restricts automatic screen recording. "
                    "ShotX programmatic recording is not supported on GNOME Wayland.\n\n"
                    "Please use GNOME's built-in recorder (Ctrl+Shift+Alt+R) or switch to an X11 session."
                )

            if not self._check_command("wf-recorder"):
                raise ScreenRecorderError(
                    "wf-recorder is not installed. Please install it for Wayland screen recording."
                )
        else:
            if not self._check_command("ffmpeg"):
                raise ScreenRecorderError("ffmpeg is not installed. Please install it for X11 screen recording.")

    def _check_command(self, cmd: str) -> bool:
        try:
            result = subprocess.run(["which", cmd], capture_output=True, text=True, timeout=2)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def start_recording(self, output_path: Path, rect: QRect | None = None) -> None:
        """Start subprocess for recording."""
        self.check_dependencies()
        if self.is_recording:
            return

        self._output_path = output_path

        if self._is_wayland:
            cmd = self._build_wf_recorder_cmd(output_path, rect)
        else:
            cmd = self._build_ffmpeg_x11_cmd(output_path, rect)

        logger.info(f"Starting screen recording with command: {' '.join(cmd)}")

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self.is_recording = True

    def stop_recording(self) -> Path | None:
        """Gracefully stop recording and wait for muxing.
        Returns the output path of the recorded video."""
        if not self.is_recording or not self._process:
            return None

        logger.info("Stopping screen recording...")
        # Send SIGINT to gracefully stop ffmpeg / wf-recorder (crucial for finalizing MP4 headers)
        self._process.send_signal(signal.SIGINT)

        try:
            # Wait for process to flush buffers and finalize the file
            _, stderr = self._process.communicate(timeout=10.0)
            if self._process.returncode != 0 and b"error" in stderr.lower():
                logger.debug(f"Recorder stderr output: {stderr.decode(errors='replace')}")
        except subprocess.TimeoutExpired:
            logger.warning("Recorder backend did not exit gracefully in 10s. Forcing kill.")
            self._process.kill()
            self._process.wait()

        self.is_recording = False
        self._process = None

        return self._output_path

    def create_gif_from_video(self, video_path: Path, gif_path: Path) -> Path | None:
        """Convert an MP4 to a high-quality GIF using FFmpeg palette generation."""
        if not self._check_command("ffmpeg"):
            raise ScreenRecorderError("ffmpeg is required for GIF generation.")

        logger.info(f"Generating GIF from video: {video_path}")

        # FFmpeg command to generate high quality GIF using palette
        cmd = [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", f"fps={min(15, self.fps)},scale=:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            str(gif_path)
        ]

        process = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        if process.returncode != 0:
            logger.error("Failed to generate GIF")
            return None

        return gif_path

    def _build_wf_recorder_cmd(self, output_path: Path, rect: QRect | None) -> list[str]:
        cmd = ["wf-recorder", "-f", str(output_path)]

        if rect and not rect.isNull():
            # Geometry format for wf-recorder: "x,y wxh"
            cmd.extend(["-g", f"{rect.x()},{rect.y()} {rect.width()}x{rect.height()}"])

        if self.audio:
            cmd.append("--audio")

        return cmd

    def _build_ffmpeg_x11_cmd(self, output_path: Path, rect: QRect | None) -> list[str]:
        # $DISPLAY is required for x11grab
        display = os.environ.get("DISPLAY", ":0")

        cmd = [
            "ffmpeg", "-y",
            "-f", "x11grab",
            "-framerate", str(self.fps)
        ]

        if rect and not rect.isNull():
            # x11grab takes video size and offset in strictly positional format
            cmd.extend(["-video_size", f"{rect.width()}x{rect.height()}"])
            cmd.extend(["-i", f"{display}+{rect.x()},{rect.y()}"])
        else:
            # Full screen needs monitor resolution (hack: skip getting size from xrandr and just grab 0,0)
            # We actually really should pass the full resolution here if possible, but leaving out -video_size
            # might default to primary display size or we can infer it.
            # Using QScreen properties from calling class for fullscreen is safer generally.
            # But for simplicity simply grab from DISPLAY
            cmd.extend(["-i", display])

        if self.audio:
            cmd.extend(["-f", "pulse", "-i", "default"])

        cmd.append(str(output_path))
        return cmd
