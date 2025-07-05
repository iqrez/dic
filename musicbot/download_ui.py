"""
Download UI Components for Discord Music Bot
User interface for one-click song downloads and cache management
"""

import discord
from discord.ext import commands
from typing import Optional, Dict, Any
import asyncio
import logging

from .download_manager import get_download_manager, download_song, is_song_cached

logger = logging.getLogger(__name__)

class DownloadView(discord.ui.View):
    """Interactive view for download controls"""
    
    def __init__(self, song_data: Dict[str, Any], timeout: float = 300):
        super().__init__(timeout=timeout)
        self.song_data = song_data
        self.url = song_data.get('url', '')
        self.title = song_data.get('title', 'Unknown')
        
    @discord.ui.button(label='Download', style=discord.ButtonStyle.green, emoji='📥')
    async def download_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Download button handler"""
        await interaction.response.defer()
        
        try:
            # Check if already cached
            if await is_song_cached(self.url):
                await interaction.followup.send(
                    f"🎵 **{self.title}** is already downloaded and cached!",
                    ephemeral=True
                )
                return
                
            # Create progress message
            progress_embed = discord.Embed(
                title="Download in Progress",
                description=f"Downloading **{self.title}**...",
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
                    pass  # Ignore edit failures
                    
            # Download the song
            result = await download_song(self.url, progress_callback=update_progress)
            
            if result:
                # Success
                success_embed = discord.Embed(
                    title="Download Complete",
                    description=f"**{result['title']}** has been downloaded and cached!",
                    color=discord.Color.green()
                )
                success_embed.add_field(name="Duration", value=f"{result.get('duration', 0)//60}:{result.get('duration', 0)%60:02d}", inline=True)
                success_embed.add_field(name="Size", value=f"{result.get('file_size', 0)/(1024*1024):.1f} MB", inline=True)
                success_embed.add_field(name="Uploader", value=result.get('uploader', 'Unknown'), inline=True)
                
                if result.get('thumbnail'):
                    success_embed.set_thumbnail(url=result['thumbnail'])
                    
                await progress_msg.edit(embed=success_embed)
                
                # Update button state
                button.label = 'Downloaded'
                button.style = discord.ButtonStyle.gray
                button.disabled = True
                await interaction.edit_original_response(view=self)
                
            else:
                # Failure
                error_embed = discord.Embed(
                    title="Download Failed",
                    description=f"Failed to download **{self.title}**. Please try again later.",
                    color=discord.Color.red()
                )
                await progress_msg.edit(embed=error_embed)
                
        except Exception as e:
            logger.error(f"Download button error: {e}")
            await interaction.followup.send(
                f"❌ Download failed: {str(e)}",
                ephemeral=True
            )

class CacheManagementView(discord.ui.View):
    """View for cache management"""
    
    def __init__(self, timeout: float = 300):
        super().__init__(timeout=timeout)
        
    @discord.ui.button(label='Cache Stats', style=discord.ButtonStyle.blurple, emoji='📊')
    async def cache_stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show cache statistics"""
        await interaction.response.defer()
        
        try:
            dm = get_download_manager()
            stats = await dm.get_cache_stats()
            
            embed = discord.Embed(
                title="Download Cache Statistics",
                color=discord.Color.blue()
            )
            embed.add_field(name="Total Songs", value=str(stats['total_files']), inline=True)
            embed.add_field(name="Cache Size", value=f"{stats['total_size_gb']} GB", inline=True)
            embed.add_field(name="Usage", value=f"{stats['usage_percent']}%", inline=True)
            embed.add_field(name="Max Size", value=f"{stats['max_size_gb']} GB", inline=True)
            
            # Add usage bar
            usage_percent = stats['usage_percent']
            bar_length = 20
            filled_length = int(bar_length * usage_percent / 100)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            embed.add_field(name="Usage Bar", value=f"`{bar}` {usage_percent}%", inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            await interaction.followup.send("❌ Failed to get cache statistics", ephemeral=True)
            
    @discord.ui.button(label='View Downloads', style=discord.ButtonStyle.gray, emoji='📋')
    async def view_downloads_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show list of downloaded songs"""
        await interaction.response.defer()
        
        try:
            dm = get_download_manager()
            cached_songs = await dm.get_cached_songs()
            
            if not cached_songs:
                await interaction.followup.send("📭 No songs downloaded yet!", ephemeral=True)
                return
                
            # Create paginated list
            embed = discord.Embed(
                title="Downloaded Songs",
                color=discord.Color.green()
            )
            
            # Show first 10 songs
            for i, song in enumerate(cached_songs[:10]):
                duration = song.get('duration', 0)
                duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
                size_mb = song.get('file_size', 0) / (1024 * 1024)
                
                embed.add_field(
                    name=f"{i+1}. {song.get('title', 'Unknown')}",
                    value=f"👤 {song.get('uploader', 'Unknown')}\n⏰ {duration_str}\n💾 {size_mb:.1f} MB",
                    inline=True
                )
                
            if len(cached_songs) > 10:
                embed.set_footer(text=f"Showing 10 of {len(cached_songs)} songs")
                
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"View downloads error: {e}")
            await interaction.followup.send("❌ Failed to load downloaded songs", ephemeral=True)
            
    @discord.ui.button(label='Clear Cache', style=discord.ButtonStyle.red, emoji='🗑️')
    async def clear_cache_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Clear cache with confirmation"""
        await interaction.response.send_message(
            "⚠️ Are you sure you want to clear the entire download cache? This cannot be undone.",
            view=ConfirmClearView(),
            ephemeral=True
        )

class ConfirmClearView(discord.ui.View):
    """Confirmation view for clearing cache"""
    
    def __init__(self, timeout: float = 60):
        super().__init__(timeout=timeout)
        
    @discord.ui.button(label='Yes, Clear Cache', style=discord.ButtonStyle.red, emoji='✅')
    async def confirm_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm cache clear"""
        await interaction.response.defer()
        
        try:
            dm = get_download_manager()
            await dm.clear_cache()
            
            embed = discord.Embed(
                title="Cache Cleared",
                description="All downloaded songs have been removed from cache.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Clear cache error: {e}")
            await interaction.followup.send("❌ Failed to clear cache", ephemeral=True)
            
        # Disable buttons
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        
    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.gray, emoji='❌')
    async def cancel_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel cache clear"""
        await interaction.response.send_message("Cache clear cancelled.", ephemeral=True)
        
        # Disable buttons
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

class DownloadModal(discord.ui.Modal):
    """Modal for downloading songs by URL"""
    
    def __init__(self):
        super().__init__(title="Download Song")
        
        self.url_input = discord.ui.TextInput(
            label="Song URL",
            placeholder="Enter YouTube, SoundCloud, or other music URL...",
            style=discord.TextStyle.short,
            required=True,
            max_length=500
        )
        self.add_item(self.url_input)
        
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        await interaction.response.defer()
        
        url = self.url_input.value.strip()
        
        try:
            # Check if already cached
            if await is_song_cached(url):
                await interaction.followup.send(
                    f"🎵 This song is already downloaded and cached!",
                    ephemeral=True
                )
                return
                
            # Create progress message
            progress_embed = discord.Embed(
                title="Download in Progress",
                description=f"Downloading from: {url}",
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
                # Success
                success_embed = discord.Embed(
                    title="Download Complete",
                    description=f"**{result['title']}** has been downloaded and cached!",
                    color=discord.Color.green()
                )
                success_embed.add_field(name="Duration", value=f"{result.get('duration', 0)//60}:{result.get('duration', 0)%60:02d}", inline=True)
                success_embed.add_field(name="Size", value=f"{result.get('file_size', 0)/(1024*1024):.1f} MB", inline=True)
                success_embed.add_field(name="Uploader", value=result.get('uploader', 'Unknown'), inline=True)
                
                if result.get('thumbnail'):
                    success_embed.set_thumbnail(url=result['thumbnail'])
                    
                await progress_msg.edit(embed=success_embed)
                
            else:
                # Failure
                error_embed = discord.Embed(
                    title="Download Failed",
                    description=f"Failed to download from the provided URL. Please check the URL and try again.",
                    color=discord.Color.red()
                )
                await progress_msg.edit(embed=error_embed)
                
        except Exception as e:
            logger.error(f"Download modal error: {e}")
            await interaction.followup.send(
                f"❌ Download failed: {str(e)}",
                ephemeral=True
            )

def create_download_embed(song_data: Dict[str, Any], is_cached: bool = False) -> discord.Embed:
    """Create embed for download interface"""
    title = song_data.get('title', 'Unknown')
    uploader = song_data.get('uploader', 'Unknown')
    duration = song_data.get('duration', 0)
    
    if is_cached:
        embed = discord.Embed(
            title="Song Available Offline",
            description=f"**{title}** is already downloaded and cached!",
            color=discord.Color.green()
        )
        embed.add_field(name="Status", value="✅ Downloaded", inline=True)
    else:
        embed = discord.Embed(
            title="Download Song",
            description=f"**{title}**\nby {uploader}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Status", value="📥 Available for download", inline=True)
        
    if duration:
        duration_str = f"{duration//60}:{duration%60:02d}"
        embed.add_field(name="Duration", value=duration_str, inline=True)
        
    if song_data.get('thumbnail'):
        embed.set_thumbnail(url=song_data['thumbnail'])
        
    return embed
