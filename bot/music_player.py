import asyncio
import discord
import yt_dlp
import logging
import sys
from discord.ext import commands
from typing import List, Dict, Any
from pathlib import Path

# Placeholder for external utilities (assumed to be defined elsewhere)
def create_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=discord.Color.blue())

def create_success_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=discord.Color.green())

def create_error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=discord.Color.red())

class MusicControlView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

class TransitionEffects:
    async def smart_fade_out(self, voice_client, guild_id: int, duration: float):
        pass
    async def smart_fade_in(self, voice_client, guild_id: int, volume: float, duration: float):
        pass
    async def smart_crossfade(self, voice_client, guild_id: int, song: Dict, duration: float, steps: int, curves: bool):
        pass

class DBManager:
    def get_or_create_guild(self, guild_id: int, guild_name: str):
        class Settings: fade_duration = 1.0; volume_steps = 10; smooth_curves = True; transition_type = "FADE"
        return Settings()
    async def add_search_history(self, guild_id: int, user_id: int, query: str, results: int = 0):
        pass
    async def add_play_history(self, guild_id: int, user_id: int, song: Dict):
        pass

class CacheManager:
    async def is_song_cached(self, url: str) -> Path:
        return None

# Bot Configuration (assumed)
class Config:
    discord_token = "YOUR_TOKEN_HERE"
    default_volume = 0.5
    auto_disconnect_delay = 300
    ffmpeg_executable = "ffmpeg"
    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def guild_check():
    async def predicate(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return False
        return True
    return commands.check(predicate)

class MusicBot(commands.Bot):
    def __init__(self, config, intents):
        super().__init__(command_prefix="/", intents=intents)
        self.config = config
        self.tree = discord.app_commands.CommandTree(self)
        self.queues = {}
        self.now_playing = {}
        self.volume_levels = {}
        self.loop_state = {}
        self.autoplay_state = {}
        self.menu_channels = {}
        self.status_messages = {}
        self.search_history = {}
        self.transition_effects = TransitionEffects()
        self.ffmpeg_options = self.config.ffmpeg_options

        # Placeholder external managers
        global db_manager, cache_manager
        db_manager = DBManager()
        cache_manager = CacheManager()

    @tree.command(name="play", description="Play a song from YouTube or SoundCloud")
    @guild_check()
    async def play(self, interaction: discord.Interaction, query: str):
        try:
            await interaction.response.defer()
            voice_client = interaction.guild.voice_client
            if not voice_client:
                voice_channel = interaction.user.voice.channel
                voice_client = await voice_channel.connect()
            results = await self.search_media(query, interaction.guild.id, user_id=interaction.user.id)
            if not results:
                embed = create_error_embed("No Results", f"No songs found for '{query}'.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            song = results[0]
            if interaction.guild.id not in self.queues:
                self.queues[interaction.guild.id] = []
            self.queues[interaction.guild.id].append(song)
            embed = create_success_embed("Added to Queue", f"**{song['title']}** added to queue!")
            await interaction.followup.send(embed=embed)
            if not voice_client.is_playing():
                await self.play_song(interaction.guild.id)
        except Exception as e:
            logger.error(f"Play command error: {e}", exc_info=True)
            embed = create_error_embed("Error", f"Failed to play: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @tree.command(name="skip", description="Skip the current song")
    @guild_check()
    async def skip(self, interaction: discord.Interaction):
        try:
            voice_client = interaction.guild.voice_client
            if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                guild_id = interaction.guild.id
                guild_settings = db_manager.get_or_create_guild(guild_id, interaction.guild.name)
                await self.transition_effects.smart_fade_out(voice_client, guild_id, guild_settings.fade_duration)
                voice_client.stop()
                embed = create_success_embed("Skipped", "Skipped to the next song.")
                await interaction.response.send_message(embed=embed)
            else:
                embed = create_error_embed("Nothing Playing", "There is no song currently playing to skip.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Skip command error: {e}", exc_info=True)
            embed = create_error_embed("Error", f"Failed to skip: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="stop", description="Stop music and clear queue")
    @guild_check()
    async def stop(self, interaction: discord.Interaction):
        try:
            guild_id = interaction.guild.id
            voice_client = interaction.guild.voice_client
            if voice_client:
                voice_client.stop()
                await voice_client.disconnect(force=True)
            if guild_id in self.queues:
                self.queues[guild_id].clear()
            embed = create_success_embed("Stopped", "Music stopped and queue cleared.")
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"Stop command error: {e}", exc_info=True)
            embed = create_error_embed("Error", f"Failed to stop: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="queue", description="Show the current music queue")
    @guild_check()
    async def queue(self, interaction: discord.Interaction):
        try:
            guild_id = interaction.guild.id
            queue = self.queues.get(guild_id, [])
            if not queue:
                embed = create_error_embed("Queue Empty", "There there are no songs in the queue.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            queue_text = "\n".join(f"{i+1}. **{song['title']}**" for i, song in enumerate(queue[:10]))
            if len(queue) > 10:
                queue_text += f"\n... and {len(queue) - 10} more songs"
            embed = create_embed("Current Queue", queue_text)
            embed.add_field(name="Total Songs", value=str(len(queue)), inline=True)
            view = MusicControlView(self)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Queue command error: {e}", exc_info=True)
            embed = create_error_embed("Error", f"Failed to show queue: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="menu", description="Show the music control panel")
    @guild_check()
    async def menu(self, interaction: discord.Interaction):
        try:
            embed = create_embed("Music Control Panel", "Use the buttons below to control music playback!")
            view = MusicControlView(self)
            await interaction.response.send_message(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Menu command error: {e}", exc_info=True)
            embed = create_error_embed("Error", f"Failed to show menu: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        max_retries = 3
        for attempt in range(max_retries):
            try:
                for guild in self.guilds:
                    await self._setup_guild(guild)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to setup guilds after {max_retries} attempts: {e}")
                logger.warning(f"Guild setup attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2 ** attempt)

    async def _setup_guild(self, guild: discord.Guild):
        try:
            guild_obj = db_manager.get_or_create_guild(guild.id, guild.name)
            bot_channel = None
            for channel in guild.text_channels:
                if channel.name.lower() in ['music', 'bot', 'music-bot']:
                    bot_channel = channel
                    break
            if not bot_channel:
                try:
                    bot_channel = await guild.create_text_channel('music-bot')
                    logger.info(f"Created music channel in {guild.name}")
                except discord.Forbidden:
                    bot_channel = guild.system_channel or next(iter(guild.text_channels), None)
                    if bot_channel:
                        logger.warning(f"Using existing channel {bot_channel.name} in {guild.name}")
                    else:
                        logger.error(f"No suitable channel found in {guild.name}")
                        return
            self.menu_channels[guild.id] = bot_channel.id
            embed = create_embed(
                "🎵 Music Bot Ready!",
                f"Hello {guild.name}! I'm ready to play music.\n\n"
                f"Use `/play <song>` to start playing music!\n"
                f"Use `/menu` to show the control panel.\n"
                f"Use `/help` to see all commands."
            )
            try:
                async for message in bot_channel.history(limit=20):
                    if message.author == self.user:
                        await message.delete()
                        await asyncio.sleep(0.1)
            except Exception as cleanup_error:
                logger.warning(f"Could not clean up old messages in {guild.name}: {cleanup_error}")
            view = MusicControlView(self)
            self.status_messages[guild.id] = await bot_channel.send(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Error setting up guild {guild.name}: {e}")

    async def search_media(self, query: str, guild_id: int, playlist: bool = False, user_id: int = 0) -> List[Dict[str, Any]]:
        logger.info(f"Searching for: {query}")
        if guild_id not in self.search_history:
            self.search_history[guild_id] = []
        if query not in self.search_history[guild_id]:
            self.search_history[guild_id].insert(0, query)
            self.search_history[guild_id] = self.search_history[guild_id][:20]
        if user_id:
            await db_manager.add_search_history(guild_id, user_id, query)
        if query.startswith("yt:"):
            search_prefix = 'ytsearch5'
            query = query[3:].strip()
        elif query.startswith("sc:"):
            search_prefix = 'scsearch5'
            query = query[3:].strip()
        elif "soundcloud.com" in query:
            search_prefix = 'scsearch5'
        else:
            search_prefix = 'ytsearch5'
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': not playlist,
            'extractflat': False,
            'quiet': True,
            'no_warnings': True,
            'skip_unavailable_fragments': True,
            'youtube_include_dash_manifest': False,
            'ignoreerrors': True,
            'extract_flat': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
        max_retries = 3
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_event_loop()
                if not any(domain in query.lower() for domain in ['youtube.com', 'youtu.be', 'soundcloud.com']):
                    search_query = f"{search_prefix}:{query}"
                else:
                    search_query = query
                info = await loop.run_in_executor(None, self._extract_info_sync, search_query, ydl_opts)
                if not info:
                    logger.warning(f"No results found for: {query} on attempt {attempt + 1}")
                    if attempt == max_retries - 1:
                        return []
                    continue
                entries = info.get('entries', [info]) if 'entries' in info else [info]
                results = []
                for e in entries:
                    if not e or not e.get('url'):
                        continue
                    audio_url = e.get('url')
                    if not audio_url and e.get('formats'):
                        for fmt in e.get('formats', []):
                            if fmt.get('acodec') != 'none' and fmt.get('url'):
                                audio_url = fmt.get('url')
                                break
                    if audio_url and audio_url.startswith(('http://', 'https://')):
                        music_platform = 'youtube'
                        if 'soundcloud' in e.get('extractor', '').lower():
                            music_platform = 'soundcloud'
                        result = {
                            'title': e.get('title', 'Unknown Title'),
                            'url': e.get('webpage_url', e.get('url')),
                            'audio_url': audio_url,
                            'duration': e.get('duration', 0),
                            'uploader': e.get('uploader', 'Unknown'),
                            'thumbnail': e.get('thumbnail', 'https://via.placeholder.com/150'),
                            'view_count': e.get('view_count', 0),
                            'platform': music_platform
                        }
                        results.append(result)
                logger.info(f"Found {len(results)} results for: {query}")
                if user_id:
                    await db_manager.add_search_history(guild_id, user_id, query, len(results))
                return results
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Search failed for '{query}' after {max_retries} attempts: {e}")
                    return []
                logger.warning(f"Search attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2 ** attempt)
        return []

    def _extract_info_sync(self, query: str, ydl_opts: dict):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(query, download=False)
        except Exception as e:
            logger.error(f"yt-dlp extraction error for {query}: {e}")
            return None

    async def play_song(self, guild_id: int):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                guild = self.get_guild(guild_id)
                if not guild or guild_id not in self.queues or not self.queues[guild_id]:
                    return
                voice_client = guild.voice_client
                if not voice_client:
                    logger.warning(f"No voice client for guild {guild_id}")
                    return
                song = self.queues[guild_id].pop(0)
                self.now_playing[guild_id] = song
                if db_manager:
                    await db_manager.add_play_history(guild_id, 0, song)
                cached_path = await cache_manager.is_song_cached(song.get('url', ''))
                if cached_path and cached_path.exists():
                    audio_source = str(cached_path)
                    logger.info(f"Playing from cache: {song['title']}")
                else:
                    audio_source = song.get('audio_url', song.get('url'))
                    if not audio_source:
                        logger.error(f"No audio URL for song: {song['title']}")
                        return
                    logger.info(f"Streaming: {song['title']}")
                def after_playing(error):
                    if error:
                        logger.error(f"Player error: {error}")
                    asyncio.run_coroutine_threadsafe(self._play_next(guild_id), self.loop)
                volume = self.volume_levels.get(guild_id, self.config.default_volume)
                guild_settings = db_manager.get_or_create_guild(guild_id, guild.name)
                fade_duration = guild_settings.fade_duration
                volume_steps = guild_settings.volume_steps
                smooth_curves = guild_settings.smooth_curves
                transition_type = guild_settings.transition_type
                if transition_type == "FADE" or transition_type == "QUICK_FADE":
                    await self.transition_effects.smart_fade_out(voice_client, guild_id, fade_duration)
                    if voice_client.is_playing():
                        voice_client.stop()
                    ffmpeg_before_options = f"{self.ffmpeg_options['before_options']} -ss 0"
                    ffmpeg_options = f"{self.ffmpeg_options['options']} -af \"volume={volume}\""
                    source = discord.FFmpegPCMAudio(
                        audio_source,
                        before_options=ffmpeg_before_options,
                        options=ffmpeg_options,
                        executable=self.config.ffmpeg_executable
                    )
                    voice_client.play(source, after=after_playing)
                    await self.transition_effects.smart_fade_in(voice_client, guild_id, volume, fade_duration)
                elif transition_type == "CROSSFADE":
                    if voice_client.is_playing():
                        await self.transition_effects.smart_crossfade(voice_client, guild_id, song, fade_duration, volume_steps, smooth_curves)
                    else:
                        ffmpeg_before_options = f"{self.ffmpeg_options['before_options']} -ss 0"
                        ffmpeg_options = f"{self.ffmpeg_options['options']} -af \"volume={volume}\""
                        source = discord.FFmpegPCMAudio(
                            audio_source,
                            before_options=ffmpeg_before_options,
                            options=ffmpeg_options,
                            executable=self.config.ffmpeg_executable
                        )
                        voice_client.play(source, after=after_playing)
                else:  # SMOOTH_CUT or DYNAMIC
                    if voice_client.is_playing():
                        voice_client.stop()
                    ffmpeg_before_options = f"{self.ffmpeg_options['before_options']} -ss 0"
                    ffmpeg_options = f"{self.ffmpeg_options['options']} -af \"volume={volume}\""
                    source = discord.FFmpegPCMAudio(
                        audio_source,
                        before_options=ffmpeg_before_options,
                        options=ffmpeg_options,
                        executable=self.config.ffmpeg_executable
                    )
                    voice_client.play(source, after=after_playing)
                logger.info(f"Now playing: {song['title']} in {guild.name}")
                await self._update_status_message(guild_id, song)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to play song after {max_retries} attempts: {e}", exc_info=True)
                logger.warning(f"Play song attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2 ** attempt)

    async def _play_next(self, guild_id: int):
        try:
            if guild_id in self.loop_state and self.loop_state[guild_id]:
                current_song = self.now_playing.get(guild_id)
                if current_song:
                    if guild_id not in self.queues:
                        self.queues[guild_id] = []
                    self.queues[guild_id].insert(0, current_song)
            if guild_id in self.queues and self.queues[guild_id]:
                await self.play_song(guild_id)
            else:
                if guild_id in self.autoplay_state and self.autoplay_state[guild_id]:
                    await self._handle_autoplay(guild_id)
                else:
                    if guild_id in self.now_playing:
                        del self.now_playing[guild_id]
                    guild = self.get_guild(guild_id)
                    if guild and guild.voice_client:
                        await asyncio.sleep(self.config.auto_disconnect_delay)
                        if guild.voice_client and not guild.voice_client.is_playing():
                            await guild.voice_client.disconnect()
                            logger.info(f"Auto-disconnected from {guild.name}")
        except Exception as e:
            logger.error(f"Error in _play_next for guild {guild_id}: {e}")

    async def _handle_autoplay(self, guild_id: int):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                current_song = self.now_playing.get(guild_id)
                if not current_song:
                    return
                search_queries = [
                    f"{current_song.get('uploader', '')} songs",
                    f"{current_song['title']} similar",
                    f"music like {current_song['title']}",
                ]
                for query in search_queries:
                    related_songs = await self.search_media(query, guild_id)
                    if related_songs:
                        for song in related_songs:
                            if song.get('url') != current_song.get('url'):
                                if guild_id not in self.queues:
                                    self.queues[guild_id] = []
                                self.queues[guild_id].append(song)
                                logger.info(f"Autoplay added: {song['title']}")
                                await self.play_song(guild_id)
                                return
                if attempt == max_retries - 1:
                    logger.info("Autoplay could not find related songs after all attempts")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Autoplay failed after {max_retries} attempts for guild {guild_id}: {e}")
                logger.warning(f"Autoplay attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2 ** attempt)

    async def _update_status_message(self, guild_id: int, song: Dict[str, Any]):
        try:
            if guild_id not in self.status_messages:
                return
            message = self.status_messages[guild_id]
            embed = create_embed(
                "🎵 Now Playing",
                f"**{song['title']}**\nBy: {song.get('uploader', 'Unknown')}"
            )
            if song.get('thumbnail'):
                embed.set_thumbnail(url=song['thumbnail'])
            queue_size = len(self.queues.get(guild_id, []))
            if queue_size > 0:
                embed.add_field(name="Queue", value=f"{queue_size} songs", inline=True)
            if await cache_manager.is_song_cached(song.get('url', '')):
                embed.add_field(name="Source", value="💾 Cached", inline=True)
            else:
                embed.add_field(name="Source", value="🌐 Streaming", inline=True)
            view = MusicControlView(self)
            await message.edit(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Error updating status message for guild {guild_id}: {e}")

    async def close(self):
        logger.info("Bot shutting down...")
        max_retries = 3
        for attempt in range(max_retries):
            try:
                for voice_client in self.voice_clients:
                    try:
                        await voice_client.disconnect(force=True)
                    except Exception as e:
                        logger.warning(f"Error disconnecting voice client: {e}")
                await super().close()
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to close bot after {max_retries} attempts: {e}")
                logger.warning(f"Bot close attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(1)

async def main():
    print("🎵 Starting Discord Music Bot...")
    setup_logging()
    logger = logging.getLogger(__name__)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            config = Config()
            intents = discord.Intents.default()
            intents.message_content = True
            intents.voice_states = True
            intents.guilds = True
            bot = MusicBot(config, intents=intents)
            logger.info("🤖 Starting Discord bot...")
            logger.info(f"🔑 Token length: {len(config.discord_token)} characters")
            await bot.start(config.discord_token)
            break
        except KeyboardInterrupt:
            logger.info("🛑 Bot shutdown requested by user")
            break
        except discord.errors.LoginFailure as e:
            logger.error(f"❌ Discord login failed: Invalid bot token")
            logger.info("💡 Please check your Discord bot token and ensure it's valid")
            sys.exit(1)
        except discord.errors.ConnectionClosed as e:
            if e.code == 4004:
                logger.error(f"❌ Discord authentication failed: Invalid or expired token")
                logger.info("💡 Please generate a new Discord bot token")
            else:
                logger.error(f"❌ Discord connection error: {e}")
            if attempt == max_retries - 1:
                sys.exit(1)
            logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(2 ** attempt)
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"❌ Fatal error after {max_retries} attempts: {e}", exc_info=True)
                sys.exit(1)
            logger.warning(f"Startup attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(2 ** attempt)
    else:
        logger.info("👋 Bot shutting down...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        sys.exit(1)