import os
from dataclasses import dataclass

@dataclass
class Config:
    discord_token: str
    default_volume: float = 0.5
    auto_disconnect_delay: int = 300
    ffmpeg_executable: str = "ffmpeg"
    ffmpeg_options: dict = None


def setup_environment():
    """Placeholder for any environment setup logic."""
    return


def get_config() -> Config:
    token = os.getenv("DISCORD_BOT_TOKEN", "demo_token")
    default_volume = float(os.getenv("DEFAULT_VOLUME", 0.5))
    auto_disconnect_delay = int(os.getenv("AUTO_DISCONNECT_DELAY", 300))
    ffmpeg_executable = os.getenv("FFMPEG_EXECUTABLE", "ffmpeg")
    ffmpeg_opts = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn",
    }
    return Config(
        discord_token=token,
        default_volume=default_volume,
        auto_disconnect_delay=auto_disconnect_delay,
        ffmpeg_executable=ffmpeg_executable,
        ffmpeg_options=ffmpeg_opts,
    )
