import asyncio
import logging
import discord

logger = logging.getLogger(__name__)

async def robust_voice_connect(channel: discord.VoiceChannel, bot: discord.Client, max_retries: int = 3) -> discord.VoiceClient | None:
    """Attempt to connect to a voice channel with retries."""
    for attempt in range(max_retries):
        try:
            return await channel.connect()
        except (discord.ClientException, discord.errors.ConnectionClosed, discord.errors.ClientException) as e:
            logger.warning(f"Voice connect failed (attempt {attempt + 1}): {e}")
            await asyncio.sleep(2 ** attempt)
        except Exception as e:
            logger.error(f"Voice connection error: {e}")
            await asyncio.sleep(2 ** attempt)
    return None
