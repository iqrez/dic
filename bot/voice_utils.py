import asyncio
import discord
import logging

logger = logging.getLogger(__name__)

async def robust_voice_connect(channel: discord.VoiceChannel, bot, max_retries: int = 3):
    """Simplified voice connection helper."""
    for attempt in range(max_retries):
        try:
            return await channel.connect()
        except Exception as e:
            logger.warning(f"Voice connection attempt {attempt+1} failed: {e}")
            await asyncio.sleep(2)
    return None
