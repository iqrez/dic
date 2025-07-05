import asyncio
import logging
from typing import Dict, List, Any

import discord
from discord.ext import commands
import yt_dlp

from config import Config
from database import init_database, get_db_manager
from ui_components import create_embed, MusicControlView
import commands as slash_commands
from voice_utils import robust_voice_connect
from smart_volume_transitions import get_smart_volume_transitions
from download_manager import is_song_cached, get_cached_song_info

logger = logging.getLogger(__name__)

class MusicBot(commands.Bot):
    def __init__(self, config: Config, intents: discord.Intents):
        super().__init__(command_prefix="/", intents=intents)
        self.config = config
        self.queues: Dict[int, List[Dict[str, Any]]] = {}
        self.now_playing: Dict[int, Dict[str, Any]] = {}
        self.volume_levels: Dict[int, float] = {}
        self.loop_state: Dict[int, bool] = {}
        self.autoplay_state: Dict[int, bool] = {}
        self.menu_channels: Dict[int, int] = {}
        self.status_messages: Dict[int, discord.Message] = {}
        self.search_history: Dict[int, List[str]] = {}
        self.db_manager = get_db_manager()
        self.transitions = get_smart_volume_transitions()

    async def setup_hook(self) -> None:
        await slash_commands.setup_commands(self)

    async def on_ready(self):
        logger.info("Bot ready as %s", self.user)
        for guild in self.guilds:
            await self._setup_guild(guild)

    async def _setup_guild(self, guild: discord.Guild):
        channel = guild.system_channel or next(iter(guild.text_channels), None)
        if not channel:
            return
        self.menu_channels[guild.id] = channel.id
        embed = create_embed("🎵 Ready", "Use /play to start playing music!")
        self.status_messages[guild.id] = await channel.send(embed=embed, view=MusicControlView(self, guild.id))

    async def search_media(self, query: str, guild_id: int, playlist: bool = False, user_id: int = 0) -> List[Dict[str, Any]]:
        opts = {
            'format': 'bestaudio/best',
            'noplaylist': not playlist,
            'quiet': True,
            'no_warnings': True,
        }
        loop = asyncio.get_event_loop()
        if not any(domain in query for domain in ["youtube.com", "youtu.be", "soundcloud.com"]):
            query = f"ytsearch:{query}"
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = await loop.run_in_executor(None, ydl.extract_info, query, False)
        entries = info.get('entries', [info])
        results = []
        for e in entries:
            if not e:
                continue
            url = e.get('url') or e.get('webpage_url')
            if not url:
                continue
            results.append({
                'title': e.get('title'),
                'url': e.get('webpage_url', url),
                'audio_url': url,
                'duration': e.get('duration'),
                'uploader': e.get('uploader'),
                'thumbnail': e.get('thumbnail'),
            })
        return results

    async def play_song(self, guild_id: int):
        if guild_id not in self.queues or not self.queues[guild_id]:
            return
        guild = self.get_guild(guild_id)
        if not guild or not guild.voice_client:
            return
        song = self.queues[guild_id].pop(0)
        self.now_playing[guild_id] = song
        source = await self._create_audio_source(song, guild_id)

        if guild.voice_client.is_playing():
            await self.transitions.smart_fade_out(guild.voice_client, guild_id)
            guild.voice_client.stop()

        guild.voice_client.play(source, after=lambda _: asyncio.run_coroutine_threadsafe(self.play_song(guild_id), self.loop))
        await self.transitions.smart_fade_in(guild.voice_client, guild_id, target_volume=self.volume_levels.get(guild_id, self.config.default_volume))

        await self._update_status_message(guild_id)

    async def join_and_play(self, channel: discord.VoiceChannel, song: Dict[str, Any], guild_id: int):
        vc = await robust_voice_connect(channel, self)
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        self.queues[guild_id].insert(0, song)
        await self.play_song(guild_id)
        return vc

    async def _create_audio_source(self, song: Dict[str, Any], guild_id: int) -> discord.PCMVolumeTransformer:
        volume = self.volume_levels.get(guild_id, self.config.default_volume)
        ffmpeg_args = {
            'executable': self.config.ffmpeg_executable,
            'before_options': self.config.ffmpeg_options['before_options'],
            'options': self.config.ffmpeg_options['options'],
        }

        audio_path = song.get('audio_url')
        if await is_song_cached(song.get('url', '')):
            info = await get_cached_song_info(song['url'])
            if info and info.get('audio_path'):
                audio_path = info['audio_path']

        source = discord.FFmpegPCMAudio(audio_path, **ffmpeg_args)
        return discord.PCMVolumeTransformer(source, volume=volume)

    async def _update_status_message(self, guild_id: int):
        if guild_id not in self.status_messages:
            return
        message = self.status_messages[guild_id]
        song = self.now_playing.get(guild_id)
        if not song:
            embed = create_embed("🎵 Ready", "Use /play to start playing music!")
        else:
            embed = create_embed("🎵 Now Playing", f"**{song['title']}**")
            if song.get('thumbnail'):
                embed.set_thumbnail(url=song['thumbnail'])
            queue_size = len(self.queues.get(guild_id, []))
            if queue_size:
                embed.add_field(name="Queue", value=f"{queue_size} songs", inline=True)
            volume_pct = int(self.volume_levels.get(guild_id, self.config.default_volume) * 100)
            embed.add_field(name="Volume", value=f"{volume_pct}%", inline=True)
        await message.edit(embed=embed, view=MusicControlView(self, guild_id))

