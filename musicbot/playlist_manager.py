"""
Playlist management functionality for the Discord Music Bot
"""

import logging
from typing import Dict, List, Optional, Any
import discord
from discord.ext import commands
from .database import get_db_manager
def create_embed(title: str, description: str, color=None, thumbnail=None, footer=None):
    if color is None:
        color = discord.Color.blue()
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

class PlaylistManager:
    """Manages user playlists and queue operations"""

    def __init__(self, bot):
        self.bot = bot
        self.db_manager = None
        try:
            self.db_manager = get_db_manager()
        except Exception as e:
            logger.error(f"Failed to initialize playlist database manager: {e}")

    async def create_playlist(self, user_id: int, guild_id: int, name: str, description: str = None) -> bool:
        """Create a new playlist for a user"""
        if not self.db_manager:
            return False

        try:
            playlist = self.db_manager.create_playlist(user_id, guild_id, name, description)
            logger.info(f"Created playlist '{name}' for user {user_id} in guild {guild_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create playlist: {e}")
            return False

    async def add_song_to_playlist(self, playlist_id: int, song_data: Dict[str, Any]) -> bool:
        """Add a song to an existing playlist"""
        if not self.db_manager:
            return False

        try:
            success = self.db_manager.add_song_to_playlist(playlist_id, song_data)
            if success:
                logger.info(f"Added song '{song_data.get('title')}' to playlist {playlist_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to add song to playlist: {e}")
            return False

    async def get_user_playlists(self, user_id: int, guild_id: int) -> List[Dict[str, Any]]:
        """Get all playlists for a user in a guild"""
        if not self.db_manager:
            return []

        try:
            playlists = self.db_manager.get_user_playlists(user_id, guild_id)
            return [
                {
                    'id': p.id,
                    'name': p.name,
                    'description': p.description,
                    'song_count': len(p.songs) if p.songs else 0,
                    'created_at': p.created_at.isoformat() if p.created_at else None
                }
                for p in playlists
            ]
        except Exception as e:
            logger.error(f"Failed to get user playlists: {e}")
            return []

    async def load_playlist_to_queue(self, playlist_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
        """Load a playlist into the bot's queue"""
        if not self.db_manager:
            return None

        try:
            # Get playlist from database
            session = self.db_manager.get_session()
            try:
                from .database import UserPlaylist
                playlist = session.query(UserPlaylist).filter(UserPlaylist.id == playlist_id).first()

                if not playlist or not playlist.songs:
                    return None

                # Add songs to bot queue
                if guild_id not in self.bot.queues:
                    self.bot.queues[guild_id] = []

                added_count = 0
                for song in playlist.songs:
                    if isinstance(song, dict) and song.get('title') and song.get('url'):
                        self.bot.queues[guild_id].append(song)
                        added_count += 1

                return {
                    'name': playlist.name,
                    'songs_added': added_count,
                    'total_songs': len(playlist.songs)
                }
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to load playlist to queue: {e}")
            return None

    async def save_queue_as_playlist(self, user_id: int, guild_id: int, name: str) -> bool:
        """Save current queue as a new playlist"""
        if not self.db_manager:
            return False

        try:
            queue = self.bot.queues.get(guild_id, [])
            if not queue:
                return False

            # Create playlist
            playlist = self.db_manager.create_playlist(user_id, guild_id, name, f"Saved from queue on {guild_id}")

            # Add all songs from queue
            for song in queue:
                self.db_manager.add_song_to_playlist(playlist.id, song)

            logger.info(f"Saved queue as playlist '{name}' with {len(queue)} songs")
            return True

        except Exception as e:
            logger.error(f"Failed to save queue as playlist: {e}")
            return False

    async def shuffle_queue(self, guild_id: int) -> bool:
        """Shuffle the current queue"""
        try:
            import random
            queue = self.bot.queues.get(guild_id, [])
            if len(queue) < 2:
                return False

            random.shuffle(queue)
            self.bot.queues[guild_id] = queue
            logger.info(f"Shuffled queue for guild {guild_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to shuffle queue: {e}")
            return False

    async def clear_queue(self, guild_id: int) -> int:
        """Clear the current queue and return number of songs removed"""
        try:
            queue_size = len(self.bot.queues.get(guild_id, []))
            self.bot.queues[guild_id] = []
            logger.info(f"Cleared queue for guild {guild_id}, removed {queue_size} songs")
            return queue_size

        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")
            return 0

    async def remove_song_from_queue(self, guild_id: int, position: int) -> Optional[Dict[str, Any]]:
        """Remove a song from the queue at the specified position"""
        try:
            queue = self.bot.queues.get(guild_id, [])
            if position < 1 or position > len(queue):
                return None

            removed_song = queue.pop(position - 1)
            logger.info(f"Removed song '{removed_song.get('title')}' from position {position}")
            return removed_song

        except Exception as e:
            logger.error(f"Failed to remove song from queue: {e}")
            return None

    async def move_song_in_queue(self, guild_id: int, from_pos: int, to_pos: int) -> bool:
        """Move a song in the queue from one position to another"""
        try:
            queue = self.bot.queues.get(guild_id, [])
            if from_pos < 1 or from_pos > len(queue) or to_pos < 1 or to_pos > len(queue):
                return False

            song = queue.pop(from_pos - 1)
            queue.insert(to_pos - 1, song)

            logger.info(f"Moved song from position {from_pos} to {to_pos}")
            return True

        except Exception as e:
            logger.error(f"Failed to move song in queue: {e}")
            return False

def setup_playlist_commands(bot):
    """Setup playlist-related slash commands"""

    playlist_manager = PlaylistManager(bot)

    @bot.tree.command(name="create_playlist", description="Create a new playlist")
    async def create_playlist_cmd(interaction: discord.Interaction, name: str, description: str = None):
        await interaction.response.defer()

        try:
            # Check if command is used in a guild
            if not interaction.guild:
                embed = create_error_embed("❌ Error", "This command can only be used in servers!")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            success = await playlist_manager.create_playlist(
                interaction.user.id, 
                interaction.guild.id, 
                name, 
                description
            )

            if success:
                embed = create_success_embed(
                    "📜 Playlist Created",
                    f"Created playlist: **{name}**"
                )
            else:
                embed = create_error_embed(
                    "❌ Error",
                    "Failed to create playlist. Database may not be available."
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Create playlist command error: {e}")
            embed = create_error_embed("❌ Error", f"Failed to create playlist: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="my_playlists", description="Show your playlists")
    async def my_playlists_cmd(interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            # Check if command is used in a guild
            if not interaction.guild:
                embed = create_error_embed("❌ Error", "This command can only be used in servers!")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            playlists = await playlist_manager.get_user_playlists(
                interaction.user.id, 
                interaction.guild.id
            )

            if not playlists:
                embed = create_embed(
                    "📜 Your Playlists",
                    "You don't have any playlists yet. Use `/create_playlist` to create one!"
                )
            else:
                description = "\n".join([
                    f"**{p['name']}** - {p['song_count']} songs"
                    for p in playlists[:10]  # Limit to 10 for display
                ])

                embed = create_embed(
                    "📜 Your Playlists",
                    description
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"My playlists command error: {e}")
            embed = create_error_embed("❌ Error", f"Failed to get playlists: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="save_queue", description="Save current queue as a playlist")
    async def save_queue_cmd(interaction: discord.Interaction, playlist_name: str):
        await interaction.response.defer()

        try:
            # Check if command is used in a guild
            if not interaction.guild:
                embed = create_error_embed("❌ Error", "This command can only be used in servers!")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            success = await playlist_manager.save_queue_as_playlist(
                interaction.user.id,
                interaction.guild.id,
                playlist_name
            )

            if success:
                queue_size = len(bot.queues.get(interaction.guild.id, []))
                embed = create_success_embed(
                    "💾 Queue Saved",
                    f"Saved {queue_size} songs as playlist: **{playlist_name}**"
                )
            else:
                embed = create_error_embed(
                    "❌ Error",
                    "Failed to save queue. Make sure there are songs in the queue."
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Save queue command error: {e}")
            embed = create_error_embed("❌ Error", f"Failed to save queue: {str(e)}")
            await interaction.followup.send(embed=embed, ephemeral=True)

    return playlist_manager
