import discord
from typing import Optional


def create_embed(title: str, description: str, color: discord.Color = discord.Color.blue(), thumbnail: Optional[str] = None, footer: Optional[str] = None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if footer:
        embed.set_footer(text=footer)
    return embed


def create_success_embed(title: str, description: str) -> discord.Embed:
    return create_embed(title, description, discord.Color.green())


def create_error_embed(title: str, description: str) -> discord.Embed:
    return create_embed(title, description, discord.Color.red())


class MusicControlView(discord.ui.View):
    def __init__(self, bot, guild_id: Optional[int] = None, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.guild_id = guild_id

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.gray, emoji="⏸️")
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            return
        voice = interaction.guild.voice_client
        if voice and voice.is_playing():
            voice.pause()
        await interaction.response.defer(ephemeral=True)

    @discord.ui.button(label="Resume", style=discord.ButtonStyle.green, emoji="▶️")
    async def resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            return
        voice = interaction.guild.voice_client
        if voice and voice.is_paused():
            voice.resume()
        await interaction.response.defer(ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.blurple, emoji="⏭️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            return
        voice = interaction.guild.voice_client
        if voice and voice.is_playing():
            voice.stop()
        await interaction.response.defer(ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.red, emoji="⏹️")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            return
        voice = interaction.guild.voice_client
        if voice:
            await voice.disconnect()
        self.bot.queues.pop(interaction.guild.id, None)
        await interaction.response.defer(ephemeral=True)


class PlaylistView(discord.ui.View):
    def __init__(self, bot, guild_id: int, user_id: int, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id

    @discord.ui.button(label="Coming Soon", style=discord.ButtonStyle.gray)
    async def soon(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Playlist features coming soon!", ephemeral=True)
