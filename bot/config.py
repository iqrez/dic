import os
import logging
from dataclasses import dataclass, field

@dataclass
class BotConfig:
    discord_token: str = "demo_token"
    default_volume: float = 0.5
    auto_disconnect_delay: int = 300
    ffmpeg_executable: str = "ffmpeg"
    ffmpeg_options: dict = field(default_factory=lambda: {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    })

async def setup_environment() -> None:
    """Placeholder for environment setup."""
    logging.getLogger(__name__).info("Environment setup complete")


def get_config() -> BotConfig:
    """Load configuration from environment variables."""
    token = os.getenv('DISCORD_BOT_TOKEN', 'demo_token')
    default_volume = float(os.getenv('DEFAULT_VOLUME', 0.5))
    auto_disconnect = int(os.getenv('AUTO_DISCONNECT_DELAY', 300))
    ffmpeg_exec = os.getenv('FFMPEG_EXECUTABLE', 'ffmpeg')
    return BotConfig(
        discord_token=token,
        default_volume=default_volume,
        auto_disconnect_delay=auto_disconnect,
        ffmpeg_executable=ffmpeg_exec,
    )
