"""
Animated song transition effects for Discord music bot
"""
import asyncio
import discord
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class TransitionEffects:
    """Handles animated transitions between songs with visual effects."""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_transitions = {}  # guild_id -> transition_task
        
        # Transition animation frames
        self.loading_frames = [
            "🎵 ●○○○○",
            "🎵 ○●○○○", 
            "🎵 ○○●○○",
            "🎵 ○○○●○",
            "🎵 ○○○○●",
            "🎵 ○○○●○",
            "🎵 ○○●○○",
            "🎵 ○●○○○"
        ]
        
        self.music_notes = ["🎵", "🎶", "🎼", "🔊", "🎤"]
        self.sparkle_frames = ["✨", "⭐", "🌟", "💫", "⚡"]
        
    async def play_transition_animation(self, guild_id: int, from_song: Optional[Dict], to_song: Dict):
        """Play animated transition between songs."""
        try:
            # Cancel any existing transition
            if guild_id in self.active_transitions:
                self.active_transitions[guild_id].cancel()
                
            # Start new transition animation
            task = asyncio.create_task(self._animate_transition(guild_id, from_song, to_song))
            self.active_transitions[guild_id] = task
            await task
            
        except asyncio.CancelledError:
            logger.debug(f"Transition animation cancelled for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error in transition animation: {e}")
        finally:
            self.active_transitions.pop(guild_id, None)
    
    async def _animate_transition(self, guild_id: int, from_song: Optional[Dict], to_song: Dict):
        """Execute the transition animation sequence."""
        channel_id = self.bot.menu_channels.get(guild_id)
        if not channel_id:
            return
            
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
            
        # Phase 1: Fade out current song (if exists)
        if from_song:
            await self._fade_out_animation(channel, from_song)
            await asyncio.sleep(0.8)
        
        # Phase 2: Loading animation
        await self._loading_animation(channel, to_song)
        await asyncio.sleep(1.0)
        
        # Phase 3: Fade in new song
        await self._fade_in_animation(channel, to_song)
        
    async def _fade_out_animation(self, channel: discord.TextChannel, song: Dict):
        """Animate fading out the current song."""
        from .ui_components import create_embed, MusicControlView
        
        fade_levels = ["🔊", "🔉", "🔈", "🔇"]
        
        for i, volume_icon in enumerate(fade_levels):
            embed = create_embed(
                title=f"{volume_icon} Finishing...",
                description=f"~~{song['title']}~~\n\n*Preparing next song...*",
                color=0x808080,  # Gray color for fading
                thumbnail=song.get('thumbnail')
            )
            
            try:
                if channel.guild.id in self.bot.status_messages:
                    await self.bot.status_messages[channel.guild.id].edit(
                        embed=embed, 
                        view=MusicControlView(self.bot)
                    )
                await asyncio.sleep(0.3)
            except discord.HTTPException:
                pass  # Ignore rate limit errors during animation
                
    async def _loading_animation(self, channel: discord.TextChannel, song: Dict):
        """Animate loading the next song."""
        from .ui_components import create_embed, MusicControlView
        
        for i, frame in enumerate(self.loading_frames * 2):  # Repeat twice
            sparkle = self.sparkle_frames[i % len(self.sparkle_frames)]
            
            embed = create_embed(
                title=f"{frame} Loading Next Song {sparkle}",
                description=f"**{song['title']}**\n\n🎧 *Getting ready to play...*",
                color=0xFFD700,  # Gold color for loading
                thumbnail=song.get('thumbnail')
            )
            
            # Add animated footer
            embed.set_footer(text=f"{'●' * (i % 3 + 1)}{'○' * (3 - (i % 3 + 1))} Buffering...")
            
            try:
                if channel.guild.id in self.bot.status_messages:
                    await self.bot.status_messages[channel.guild.id].edit(
                        embed=embed,
                        view=MusicControlView(self.bot)
                    )
                await asyncio.sleep(0.2)
            except discord.HTTPException:
                pass
                
    async def _fade_in_animation(self, channel: discord.TextChannel, song: Dict):
        """Animate fading in the new song."""
        from .ui_components import create_embed, MusicControlView
        
        fade_levels = ["🔇", "🔈", "🔉", "🔊"]
        colors = [0x404040, 0x808080, 0x40C040, 0x00FF00]  # Gray to green
        
        for i, (volume_icon, color) in enumerate(zip(fade_levels, colors)):
            note = self.music_notes[i % len(self.music_notes)]
            
            embed = create_embed(
                title=f"{volume_icon} {note} Now Playing",
                description=f"**{song['title']}**\n\n🎤 {song.get('uploader', 'Unknown Artist')}",
                color=color,
                thumbnail=song.get('thumbnail')
            )
            
            # Add queue info if available
            queue = self.bot.queues.get(channel.guild.id, [])
            if queue:
                queue_text = "\n".join([f"{j+1}. {s['title'][:40]}{'...' if len(s['title']) > 40 else ''}" 
                                      for j, s in enumerate(queue[:3])])
                if len(queue) > 3:
                    queue_text += f"\n... and {len(queue) - 3} more"
                embed.add_field(name="🎵 Up Next", value=f"```\n{queue_text}\n```", inline=False)
            
            # Add settings info
            settings = []
            if self.bot.loop_state.get(channel.guild.id):
                settings.append("🔁 Loop")
            if self.bot.autoplay_state.get(channel.guild.id):
                settings.append("🎲 Autoplay")
            
            volume = int(self.bot.volume_levels.get(channel.guild.id, 0.5) * 100)
            settings.append(f"🔊 {volume}%")
            
            if settings:
                embed.add_field(name="⚙️ Settings", value=" | ".join(settings), inline=True)
            
            embed.set_footer(
                text=f"✨ Started at {datetime.now().strftime('%H:%M:%S')} ✨",
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
            )
            
            try:
                if channel.guild.id in self.bot.status_messages:
                    await self.bot.status_messages[channel.guild.id].edit(
                        embed=embed,
                        view=MusicControlView(self.bot)
                    )
                await asyncio.sleep(0.4)
            except discord.HTTPException:
                pass
    
    async def play_skip_animation(self, guild_id: int, skipped_song: Dict, next_song: Dict):
        """Play animation for skipping songs."""
        channel_id = self.bot.menu_channels.get(guild_id)
        if not channel_id:
            return
            
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
            
        from .ui_components import create_embed, MusicControlView
        
        # Quick skip animation
        skip_frames = ["⏭️", "⚡", "🎵"]
        
        for frame in skip_frames:
            embed = create_embed(
                title=f"{frame} Skipping to Next Song",
                description=f"~~{skipped_song['title']}~~\n\n**➤ {next_song['title']}**",
                color=0xFF6B35,  # Orange color for skip
                thumbnail=next_song.get('thumbnail')
            )
            
            try:
                if guild_id in self.bot.status_messages:
                    await self.bot.status_messages[guild_id].edit(
                        embed=embed,
                        view=MusicControlView(self.bot)
                    )
                await asyncio.sleep(0.3)
            except discord.HTTPException:
                pass
                
        # Then play normal transition
        await self.play_transition_animation(guild_id, skipped_song, next_song)
    
    async def play_pause_animation(self, guild_id: int, song: Dict, paused: bool):
        """Play animation for pause/resume."""
        channel_id = self.bot.menu_channels.get(guild_id)
        if not channel_id:
            return
            
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
            
        from .ui_components import create_embed, MusicControlView
        
        if paused:
            icon = "⏸️"
            title = "Paused"
            color = 0xFFA500  # Orange
            description = f"**{song['title']}**\n\n*Playback paused*"
        else:
            icon = "▶️"
            title = "Resumed"
            color = 0x00FF00  # Green
            description = f"**{song['title']}**\n\n*Playback resumed*"
        
        # Quick pause/resume flash
        embed = create_embed(
            title=f"{icon} {title}",
            description=description,
            color=color,
            thumbnail=song.get('thumbnail')
        )
        
        try:
            if guild_id in self.bot.status_messages:
                await self.bot.status_messages[guild_id].edit(
                    embed=embed,
                    view=MusicControlView(self.bot)
                )
        except discord.HTTPException:
            pass
    
    def cancel_transition(self, guild_id: int):
        """Cancel any active transition for a guild."""
        if guild_id in self.active_transitions:
            self.active_transitions[guild_id].cancel()
            self.active_transitions.pop(guild_id, None)
