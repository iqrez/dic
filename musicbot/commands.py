"""
Slash Commands for the Enhanced Discord Music Bot
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import TYPE_CHECKING, Optional, Literal
import logging
import asyncio

if TYPE_CHECKING:
    from .music_player import MusicBot

from .ui_components import MusicControlView

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

logger = logging.getLogger(__name__)

async def setup_commands(bot: 'MusicBot'):
    """Setup all slash commands for the bot."""

    # Simplified guild check - just ensure we're in a guild
    def guild_check():
        def predicate(interaction: discord.Interaction) -> bool:
            return interaction.guild is not None
        return app_commands.check(predicate)

    @bot.tree.command(name="play", description="Play music from YouTube or SoundCloud")
    @app_commands.describe(
        query="Song name, artist, or URL (prefix with yt: or sc: for specific platforms)",
        playlist="Whether to load entire playlist (for playlist URLs)"
    )
    async def play(interaction: discord.Interaction, query: str, playlist: bool = False):
        """Play music command with enhanced error handling."""
        await interaction.response.defer()

        try:
            # Check if user is in voice channel
            # Check if user is a Member (has voice attribute) and is in voice
            if not hasattr(interaction.user, 'voice') or not interaction.user.voice or not interaction.user.voice.channel:
                embed = create_error_embed("❌ Error", "You need to be in a voice channel to use this command!")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Use robust voice connection utility
            from .voice_utils import robust_voice_connect

            voice_channel = interaction.user.voice.channel
            voice = await robust_voice_connect(voice_channel, bot)

            if not voice:
                # Allow queueing even without voice connection
                logger.warning("Voice connection failed, allowing queue-only mode")
                embed = create_embed(
                    "⚠️ Voice Connection Issue", 
                    "Unable to connect to voice channel due to Discord server issues. Songs will be queued and playback will start automatically when connection is restored.\n\n**This is a known Discord infrastructure issue, not a bot problem.**",
                    color=discord.Color.orange()
                )

            # Search for music with error handling
            songs = await bot.search_media(query, interaction.guild.id, playlist=playlist)
            if not songs:
                embed = create_error_embed("❌ No Results", f"No results found for: `{query}`")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Add to queue
            guild_id = interaction.guild.id
            if guild_id not in bot.queues:
                bot.queues[guild_id] = []

            if playlist:
                bot.queues[guild_id].extend(songs)
                embed = create_success_embed("✅ Playlist Added", f"Added {len(songs)} songs to queue")
            else:
                song = songs[0]
                bot.queues[guild_id].append(song)

                # Analyze audio quality for preview
                from .audio_quality import analyze_track_quality, generate_quality_embed_field

                quality_info = None
                try:
                    if song.get('url'):
                        quality_info = await analyze_track_quality(song['url'])
                except Exception as e:
                    logger.warning(f"Failed to analyze audio quality: {e}")

                embed = create_success_embed("✅ Song Added", f"Added **{song['title']}** to queue")
                if song.get('thumbnail'):
                    embed.set_thumbnail(url=song['thumbnail'])

                # Add quality information to embed
                if quality_info and quality_info.quality_score:
                    quality_field = generate_quality_embed_field(quality_info)
                    embed.add_field(**quality_field)

            await interaction.followup.send(embed=embed)

            # Start playing if voice is connected and nothing is currently playing
            if voice and not voice.is_playing() and not voice.is_paused():
                logger.info(f"🎵 Auto-starting playback for guild {guild_id}")
                await bot.play_song(guild_id)
            elif not voice:
                # Add note about voice connection issue
                embed.add_field(
                    name="📝 Note", 
                    value="Song queued! Playback will start when voice connection is restored.", 
                    inline=False
                )

        except Exception as e:
            logger.error(f"Play command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"An unexpected error occurred: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="search", description="Search for music and preview audio quality")
    @app_commands.describe(query="Song name or artist to search for")
    async def search(interaction: discord.Interaction, query: str):
        """Search music command with quality preview."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in servers!", ephemeral=True)
            return

        # Check if user is a Member (has voice attribute) and is in voice
        if not hasattr(interaction.user, 'voice') or not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ You need to be in a voice channel to use this command!", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            results = await bot.search_media(query, interaction.guild.id)
            if not results:
                embed = create_error_embed("❌ No Results", f"No results found for: {query}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Analyze quality for the first result
            from .audio_quality import analyze_track_quality, generate_quality_embed_field

            song = results[0]
            quality_info = None

            try:
                if song.get('url'):
                    quality_info = await analyze_track_quality(song['url'])
            except Exception as e:
                logger.warning(f"Failed to analyze audio quality: {e}")

            embed = create_success_embed("🔍 Search Results", f"**{song['title']}**\nBy: {song.get('uploader', 'Unknown')}\n\nUse `/play {query}` to add to queue")

            if song.get('thumbnail'):
                embed.set_thumbnail(url=song['thumbnail'])

            # Add quality information
            view = None
            if quality_info and quality_info.quality_score:
                quality_field = generate_quality_embed_field(quality_info)
                embed.add_field(**quality_field)

                # Add quality tooltip button
                from .quality_tooltip_view import QualityTooltipView
                view = QualityTooltipView(song['url'], song['title'])
                embed.set_footer(text="💡 Click 'Quality Info' for detailed analysis")

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Search command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Search failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="skip", description="Skip the current song")
    async def skip(interaction: discord.Interaction):
        """Skip current song with enhanced error handling."""
        try:
            voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)

            if not voice or not voice.is_playing():
                await interaction.response.send_message("❌ Nothing to skip!", ephemeral=True)
                return

            current_song = bot.now_playing.get(interaction.guild.id, {})
            next_song = bot.queues.get(interaction.guild.id, [{}])[0] if bot.queues.get(interaction.guild.id) else None

            # Play skip animation if available
            if hasattr(bot, 'transition_effects') and current_song and next_song:
                asyncio.create_task(bot.transition_effects.play_skip_animation(
                    interaction.guild.id, current_song, next_song
                ))

            voice.stop()

            embed = create_success_embed("⏭️ Skipped", f"Skipped: **{current_song.get('title', 'Unknown')}**")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Skip command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to skip: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="pause", description="Pause the current song")
    async def pause(interaction: discord.Interaction):
        """Pause current song with enhanced error handling."""
        try:
            voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)

            if not voice or not voice.is_playing():
                await interaction.response.send_message("❌ Nothing to pause!", ephemeral=True)
                return

            current_song = bot.now_playing.get(interaction.guild.id, {})

            # Play pause animation if available
            if hasattr(bot, 'transition_effects') and current_song:
                asyncio.create_task(bot.transition_effects.play_pause_animation(
                    interaction.guild.id, current_song, True
                ))

            voice.pause()
            await interaction.response.send_message("⏸️ Paused the music!")

        except Exception as e:
            logger.error(f"Pause command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to pause: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="resume", description="Resume the paused song")
    async def resume(interaction: discord.Interaction):
        """Resume paused song with enhanced error handling."""
        try:
            voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)

            if not voice or not voice.is_paused():
                await interaction.response.send_message("❌ Nothing to resume!", ephemeral=True)
                return

            current_song = bot.now_playing.get(interaction.guild.id, {})

            # Play resume animation if available
            if hasattr(bot, 'transition_effects') and current_song:
                asyncio.create_task(bot.transition_effects.play_pause_animation(
                    interaction.guild.id, current_song, False
                ))

            voice.resume()
            await interaction.response.send_message("▶️ Resumed the music!")

        except Exception as e:
            logger.error(f"Resume command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to resume: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="stop", description="Stop music and clear the queue")
    async def stop(interaction: discord.Interaction):
        """Stop music and clear queue with enhanced error handling."""
        try:
            voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)

            if voice:
                if voice.is_playing() or voice.is_paused():
                    voice.stop()
                await voice.disconnect()

            # Clear queue and state
            guild_id = interaction.guild.id
            bot.queues.pop(guild_id, None)
            bot.now_playing.pop(guild_id, None)
            bot.loop_state.pop(guild_id, None)
            bot.autoplay_state.pop(guild_id, None)

            embed = create_success_embed("⏹️ Stopped", "Music stopped and queue cleared!")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Stop command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to stop: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="queue", description="Show the current music queue")
    async def queue(interaction: discord.Interaction):
        """Show current queue with enhanced error handling."""
        try:
            queue = bot.queues.get(interaction.guild.id, [])
            now_playing = bot.now_playing.get(interaction.guild.id)

            if not now_playing and not queue:
                await interaction.response.send_message("📜 Queue is empty!", ephemeral=True)
                return

            description = ""

            if now_playing:
                description += f"**🎵 Now Playing:**\n[{now_playing['title']}]({now_playing['url']})\n\n"

            if queue:
                description += f"**📜 Queue ({len(queue)} songs):**\n"
                for i, song in enumerate(queue[:10]):  # Show first 10
                    description += f"{i+1}. **{song['title'][:50]}{'...' if len(song['title']) > 50 else ''}**\n"

                if len(queue) > 10:
                    description += f"... and {len(queue) - 10} more songs\n"
            else:
                description += "**📜 Queue:** Empty"

            embed = create_success_embed("🎵 Music Queue", description)
            if now_playing and now_playing.get('thumbnail'):
                embed.set_thumbnail(url=now_playing['thumbnail'])

            view = MusicControlView(bot, interaction.guild.id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Queue command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to show queue: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="loop", description="Toggle loop mode for the current song")
    async def loop(interaction: discord.Interaction):
        """Toggle loop mode with enhanced error handling."""
        try:
            guild_id = interaction.guild.id
            current_state = bot.loop_state.get(guild_id, False)
            bot.loop_state[guild_id] = not current_state

            status = "enabled" if not current_state else "disabled"
            emoji = "🔁" if not current_state else "➡️"

            embed = create_success_embed(f"{emoji} Loop {status.title()}", f"Loop mode is now **{status}**")
            await interaction.response.send_message(embed=embed)

            # Update status message
            await bot._update_status_message(guild_id)

        except Exception as e:
            logger.error(f"Loop command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to toggle loop: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="autoplay", description="Toggle autoplay mode")
    async def autoplay(interaction: discord.Interaction):
        """Toggle autoplay mode with enhanced error handling."""
        try:
            guild_id = interaction.guild.id
            current_state = bot.autoplay_state.get(guild_id, False)
            bot.autoplay_state[guild_id] = not current_state

            status = "enabled" if not current_state else "disabled"
            emoji = "🎲" if not current_state else "🎯"

            description = f"Autoplay mode is now **{status}**"
            if not current_state:
                description += "\nThe bot will automatically add songs when the queue is empty."

            embed = create_success_embed(f"{emoji} Autoplay {status.title()}", description)
            await interaction.response.send_message(embed=embed)

            # Update status message
            await bot._update_status_message(guild_id)

        except Exception as e:
            logger.error(f"Autoplay command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to toggle autoplay: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="volume", description="Set the music volume")
    @app_commands.describe(volume="Volume level (0-100)")
    async def volume(interaction: discord.Interaction, volume: int):
        """Set volume command with enhanced error handling."""
        try:
            if not 0 <= volume <= 100:
                await interaction.response.send_message("❌ Volume must be between 0 and 100!", ephemeral=True)
                return

            guild_id = interaction.guild.id
            # Update volume
            bot.volume_levels[guild_id] = volume / 100.0

            # Apply to current playback
            voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)
            if voice and voice.source and hasattr(voice.source, 'volume'):
                voice.source.volume = volume / 100.0

            embed = create_success_embed("🔊 Volume Changed", f"Volume set to **{volume}%**")
            await interaction.response.send_message(embed=embed)

            # Update status message
            await bot._update_status_message(guild_id)

        except Exception as e:
            logger.error(f"Volume command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to set volume: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="clear", description="Clear the music queue")
    async def clear(interaction: discord.Interaction):
        """Clear the queue with enhanced error handling."""
        try:
            guild_id = interaction.guild.id
            queue = bot.queues.get(guild_id, [])

            if not queue:
                await interaction.response.send_message("📜 Queue is already empty!", ephemeral=True)
                return

            queue_size = len(queue)
            bot.queues[guild_id].clear()

            embed = create_success_embed("🗑️ Queue Cleared", f"Removed **{queue_size} songs** from the queue")
            await interaction.response.send_message(embed=embed)

            # Update status message
            await bot._update_status_message(guild_id)

        except Exception as e:
            logger.error(f"Clear command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to clear queue: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="shuffle", description="Shuffle the current queue")
    async def shuffle(interaction: discord.Interaction):
        """Shuffle the queue with enhanced error handling."""
        try:
            guild_id = interaction.guild.id
            queue = bot.queues.get(guild_id, [])

            if len(queue) < 2:
                await interaction.response.send_message("❌ Need at least 2 songs to shuffle!", ephemeral=True)
                return

            import random
            random.shuffle(queue)

            embed = create_success_embed("🔀 Queue Shuffled", f"Shuffled **{len(queue)} songs** in the queue")
            await interaction.response.send_message(embed=embed)

            # Update status message
            await bot._update_status_message(guild_id)

        except Exception as e:
            logger.error(f"Shuffle command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to shuffle queue: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="nowplaying", description="Show currently playing song")
    async def nowplaying(interaction: discord.Interaction):
        """Show now playing with enhanced error handling."""
        try:
            now_playing = bot.now_playing.get(interaction.guild.id)

            if not now_playing:
                await interaction.response.send_message("❌ Nothing is currently playing!", ephemeral=True)
                return

            voice = discord.utils.get(bot.voice_clients, guild=interaction.guild)
            status = "Playing" if voice and voice.is_playing() else "Paused" if voice and voice.is_paused() else "Stopped"

            description = f"**[{now_playing['title']}]({now_playing['url']})**\n"
            description += f"👤 {now_playing.get('uploader', 'Unknown')}\n"
            description += f"🎵 Status: {status}"

            embed = create_success_embed("🎵 Now Playing", description)
            if now_playing.get('thumbnail'):
                embed.set_thumbnail(url=now_playing['thumbnail'])

            view = MusicControlView(bot)
            await interaction.response.send_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Now playing command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to show current song: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="playlist", description="Manage your playlists")
    async def playlist(interaction: discord.Interaction):
        """Playlist management command with enhanced error handling."""
        try:
            from .ui_components import PlaylistView
            view = PlaylistView(bot, interaction.guild.id, interaction.user.id)

            embed = create_success_embed(
                "📂 Playlist Manager",
                "Manage your personal playlists here!\n\n"
                "💾 **Save Current Queue** - Save the current queue as a playlist\n"
                "📂 **Load Playlist** - Load a saved playlist into the queue"
            )
            embed.set_footer(text="Playlists are saved per user and can be used across servers")

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Playlist command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to load playlist manager: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="history", description="Show your recent searches")
    async def history(interaction: discord.Interaction):
        """Show search history with enhanced error handling."""
        try:
            history = bot.search_history.get(interaction.guild.id, [])

            if not history:
                await interaction.response.send_message("📋 No search history found!", ephemeral=True)
                return

            description = "**Recent Searches:**\n"
            for i, query in enumerate(history[:10], 1):
                description += f"{i}. {query}\n"

            embed = create_success_embed("📋 Search History", description)
            embed.set_footer(text="Use /search or /play to search again")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"History command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to show history: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="help", description="Show help information")
    async def help_command(interaction: discord.Interaction):
        """Help command with enhanced error handling."""
        try:
            if not interaction.guild:
                await interaction.response.send_message("This command can only be used in servers!", ephemeral=True)
                return

            embed = create_success_embed(
                "🎵 Enhanced Music Bot Help",
                "**Music Commands:**\n"
                "`/play <query>` - Play music from YouTube/SoundCloud\n"
                "`/search <query>` - Search and choose from results\n"
                "`/skip` - Skip current song\n"
                "`/pause` - Pause music\n"
                "`/resume` - Resume music\n"
                "`/stop` - Stop and disconnect\n"
                "`/queue` - Show current queue\n"
                "`/nowplaying` - Show current song\n\n"
                "**Queue Management:**\n"
                "`/clear` - Clear the queue\n"
                "`/shuffle` - Shuffle the queue\n"
                "`/loop` - Toggle loop mode\n"
                "`/autoplay` - Toggle autoplay\n"
                "`/volume <0-100>` - Set volume\n\n"
                "**Playlists & History:**\n"
                "`/playlist` - Manage playlists\n"
                "`/history` - Show search history\n\n"
                "**Search Tips:**\n"
                "• Prefix with `yt:` for YouTube-only search\n"
                "• Prefix with `sc:` for SoundCloud-only search\n"
                "• Use direct URLs for specific videos\n"
                "• Add `playlist: true` to load entire playlists"
            )
            embed.set_footer(text="Enhanced Music Bot v2.0 | Use the buttons for quick controls!")

            # Add guild check for help command
            if not interaction.guild:
                await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
                return

            view = MusicControlView(bot, interaction.guild.id)

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Help command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to show help: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="menu", description="Show interactive music control menu")
    async def menu_command(interaction: discord.Interaction):
        """Show main music control interface with enhanced error handling."""
        try:
            from .ui_components import MusicControlView

            embed = create_success_embed(
                "🎵 Music Control Panel",
                "Use the buttons and dropdown below to control music playback:\n\n"
                "🎵 **Available Actions:**\n"
                "• Play/Pause current song\n"
                "• Skip to next track\n"
                "• Shuffle queue\n"
                "• Toggle loop mode\n"
                "• Add new songs\n"
                "• View queue and current song\n"
                "• Save playlists\n"
                "• Volume control\n"
                "• Preview audio quality"
            )

            view = MusicControlView(bot)
            await interaction.response.send_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Menu command error: {e}", exc_info=True)
            embed = create_error_embed("❌ Error", f"Failed to show menu: {str(e)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="join", description="Join a voice channel")
    async def join_channel(interaction: discord.Interaction, channel: discord.VoiceChannel = None):
        """Join a specific voice channel or user's current channel with enhanced error handling."""
        await interaction.response.defer(ephemeral=True)

        try:
            # Check if command is used in a guild
            if not interaction.guild:
                embed = create_error_embed("❌ Error", "This command can only be used in servers!")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            target_channel = None

            if channel:
                # User specified a channel
                target_channel = channel
            elif interaction.user.voice:
                # User is in a voice channel
                target_channel = interaction.user.voice.channel
            else:
                # Show error message
                embed = create_error_embed("🔊 Join Voice Channel", "You need to be in a voice channel or specify one for me to join!")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Check permissions
            if not target_channel.permissions_for(interaction.guild.me).connect:
                embed = create_error_embed("❌ Permission Error", f"I don't have permission to join {target_channel.name}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Use robust voice connection utility
            from .voice_utils import robust_voice_connect

            voice_client = await robust_voice_connect(target_channel, bot)

            if voice_client:
                embed = create_success_embed("🔊 Connected", f"Successfully joined {target_channel.name}")
            else:
                embed = create_error_embed("❌ Connection Failed", "Unable to connect to voice channel after multiple attempts. Please check bot permissions and try again.")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            error_msg = str(e) if str(e) else f"Unknown error: {type(e).__name__}"
            logger.error(f"Join channel error: {error_msg}", exc_info=True)

            embed = create_error_embed("❌ Error", f"Failed to join channel: {error_msg}")
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as followup_error:
                logger.error(f"Failed to send error message: {followup_error}")

    @bot.tree.command(name="test_audio", description="Test complete audio system functionality")
    async def test_audio(interaction: discord.Interaction):
        """Test audio playback functionality with diagnostics and enhanced error handling."""
        await interaction.response.defer()

        try:
            # Auto-join voice if user is in one
            if not interaction.user.voice or not interaction.user.voice.channel:
                embed = create_error_embed("❌ Voice Required", "You need to be in a voice channel for audio testing.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Connect to voice if not connected
            from .voice_utils import robust_voice_connect

            voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
            if not voice_client:
                voice_client = await robust_voice_connect(interaction.user.voice.channel, bot)
                if voice_client:
                    logger.info(f"Auto-joined {interaction.user.voice.channel.name} for testing")
                else:
                    embed = create_error_embed("❌ Connection Failed", "Unable to connect to voice channel for testing.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

            # Run comprehensive audio test
            from .audio_test import run_audio_diagnostics
            diagnostic_report = await run_audio_diagnostics(bot, interaction.guild.id)

            # Test with a simple song
            test_query = "test audio music"
            results = await bot.search_media(test_query, interaction.guild.id)

            if results:
                # Add to queue
                if interaction.guild.id not in bot.queues:
                    bot.queues[interaction.guild.id] = []

                bot.queues[interaction.guild.id].insert(0, results[0])

                # Start playback immediately
                if not voice_client.is_playing():
                    await bot.play_song(interaction.guild.id)

                embed = create_success_embed(
                    "🎵 Audio Test Complete",
                    f"**Test Results:**\n{diagnostic_report}\n\n**Now Playing:** {results[0]['title']}"
                )
            else:
                embed = create_embed(
                    "⚠️ Partial Test",
                    f"**Diagnostic Results:**\n{diagnostic_report}\n\n❌ Could not find test audio for playback",
                    color=discord.Color.orange()
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Audio test error: {e}", exc_info=True)
            embed = create_error_embed("❌ Test Failed", f"Audio test failed: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="playlist_menu", description="Show playlist management interface")
    async def playlist_menu_command(interaction: discord.Interaction):
        """Show playlist management interface with enhanced error handling."""
        try:
            # Get user playlists
            user_playlists = []
            if hasattr(bot, 'db_manager') and bot.db_manager:
                playlists = bot.db_manager.get_user_playlists(interaction.user.id, interaction.guild.id)
                user_playlists = [
                    {
                        'id': p.id,
                        'name': p.name,
                        'song_count': len(p.songs) if p.songs else 0
                    }
                    for p in playlists
                ]

            embed = create_success_embed(
                "📜 Playlist Management",
                f"You have {len(user_playlists)} playlists\n\n"
                "🎵 **Options:**\n"
                "• Load existing playlist\n"
                "• Create new playlist\n"
                "• Save current queue as playlist"
            )

            from .ui_components import PlaylistView
            view = PlaylistView(bot, interaction.guild.id, interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Playlist menu error: {e}")
            embed = create_error_embed("❌ Error", "Failed to load playlist interface")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="download", description="Download and cache songs for offline playback")
    async def download_command(interaction: discord.Interaction, url: str = None):
        """Download songs for offline cache with enhanced error handling."""
        try:
            if url:
                # Direct URL download
                from .download_manager import is_song_cached, download_song

                # Check if already cached
                if await is_song_cached(url):
                    await interaction.response.send_message(
                        "This song is already downloaded and cached!",
                        ephemeral=True
                    )
                    return

                await interaction.response.defer()

                # Create progress message
                progress_embed = create_embed(
                    "Download in Progress",
                    f"Downloading from: {url}",
                    color=discord.Color.orange()
                )
                progress_embed.add_field(name="Status", value="Starting download...", inline=False)

                progress_msg = await interaction.followup.send(embed=progress_embed, ephemeral=True)

                # Progress callback
                async def update_progress(status: str):
                    try:
                        progress_embed.set_field_at(0, name="Status", value=status, inline=False)
                        await progress_msg.edit(embed=progress_embed)
                    except:
                        pass

                # Download the song
                result = await download_song(url, progress_callback=update_progress)

                if result:
                    success_embed = create_success_embed(
                        "Download Complete",
                        f"**{result['title']}** has been downloaded and cached!"
                    )
                    success_embed.add_field(name="Duration", value=f"{result.get('duration', 0)//60}:{result.get('duration', 0)%60:02d}", inline=True)
                    success_embed.add_field(name="Size", value=f"{result.get('file_size', 0)/(1024*1024):.1f} MB", inline=True)
                    success_embed.add_field(name="Uploader", value=result.get('uploader', 'Unknown'), inline=True)

                    if result.get('thumbnail'):
                        success_embed.set_thumbnail(url=result['thumbnail'])

                    await progress_msg.edit(embed=success_embed)
                else:
                    error_embed = create_error_embed(
                        "Download Failed",
                        "Failed to download from the provided URL. Please check the URL and try again."
                    )
                    await progress_msg.edit(embed=error_embed)
            else:
                # Show download interface
                from .download_ui import DownloadModal
                modal = DownloadModal()
                await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Download command error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=create_error_embed("Download Error", f"Failed to process download: {str(e)}"),
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=create_error_embed("Download Error", f"Failed to process download: {str(e)}"),
                    ephemeral=True
                )

    @bot.tree.command(name="cache", description="Manage download cache and view offline songs")
    async def cache_command(interaction: discord.Interaction):
        """Cache management command with enhanced error handling."""
        try:
            from .download_ui import CacheManagementView
            from .download_manager import get_download_manager

            dm = get_download_manager()
            stats = await dm.get_cache_stats()

            embed = create_embed(
                "Download Cache Management",
                "Manage your offline song cache",
                color=discord.Color.blue()
            )
            embed.add_field(name="Total Songs", value=str(stats['total_files']), inline=True)
            embed.add_field(name="Cache Size", value=f"{stats['total_size_gb']} GB", inline=True)
            embed.add_field(name="Usage", value=f"{stats['usage_percent']}%", inline=True)

            # Add usage bar
            usage_percent = stats['usage_percent']
            bar_length = 20
            filled_length = int(bar_length * usage_percent / 100)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            embed.add_field(name="Usage Bar", value=f"`{bar}` {usage_percent}%", inline=False)

            view = CacheManagementView(timeout=300)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Cache command error: {e}")
            await interaction.response.send_message(
                embed=create_error_embed("Cache Error", f"Failed to load cache management: {str(e)}"),
                ephemeral=True
            )

    # Load transition commands
    try:
        from .commands_transitions import setup as setup_transitions
        await setup_transitions(bot)
        logger.info("Loaded transition commands")
    except Exception as e:
        logger.error(f"Failed to load transition commands: {e}")
    
    logger.info("✅ Slash commands setup complete")
