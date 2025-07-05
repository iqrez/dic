import discord

async def run_audio_diagnostics(bot: discord.Client, guild_id: int) -> str:
    guild = bot.get_guild(guild_id)
    if not guild or not guild.voice_client:
        return "No active voice connection"
    vc = guild.voice_client
    state = "playing" if vc.is_playing() else "paused" if vc.is_paused() else "idle"
    volume = getattr(vc.source, 'volume', 'n/a')
    return f"Voice state: {state}, volume: {volume}"
