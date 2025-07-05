import discord


def create_embed(title: str, description: str, color=discord.Color.blue(), thumbnail=None, footer=None):
    embed = discord.Embed(title=title, description=description, color=color)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if footer:
        embed.set_footer(text=footer)
    return embed


def create_success_embed(title: str, description: str):
    return create_embed(title, description, discord.Color.green())


def create_error_embed(title: str, description: str):
    return create_embed(title, description, discord.Color.red())


class MusicControlView(discord.ui.View):
    def __init__(self, bot, guild_id: int | None = None, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.guild_id = guild_id

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if voice and voice.is_playing():
            voice.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Pause/Resume", style=discord.ButtonStyle.secondary)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if voice:
            if voice.is_paused():
                voice.resume()
            elif voice.is_playing():
                voice.pause()
        await interaction.response.defer()


class PlaylistView(discord.ui.View):
    def __init__(self, bot, guild_id: int, user_id: int, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id

    @discord.ui.button(label="Close", style=discord.ButtonStyle.gray)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
