"""
Interactive quality tooltip view for Discord embeds
"""
import discord
import logging
from typing import Optional
from .audio_quality import analyze_track_quality, generate_quality_tooltip

logger = logging.getLogger(__name__)

class QualityTooltipButton(discord.ui.Button):
    """Button that shows audio quality tooltip when clicked"""
    
    def __init__(self, song_url: str, song_title: str = ""):
        super().__init__(
            label="Quality Info",
            emoji="🔍",
            style=discord.ButtonStyle.secondary,
            row=1
        )
        self.song_url = song_url
        self.song_title = song_title
    
    async def callback(self, interaction: discord.Interaction):
        """Show detailed quality information"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Analyze audio quality
            quality_info = await analyze_track_quality(self.song_url)
            
            if not quality_info or quality_info.quality_score is None:
                await interaction.followup.send(
                    "❓ Unable to analyze audio quality for this track.",
                    ephemeral=True
                )
                return
            
            # Generate detailed quality tooltip
            quality_tooltip = generate_quality_tooltip(quality_info, self.song_title)
            
            # Create rich embed
            quality_emojis = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "💎"}
            emoji = quality_emojis.get(quality_info.quality_score, "❓")
            
            color_map = {
                1: discord.Color.red(),
                2: discord.Color.orange(), 
                3: discord.Color.yellow(),
                4: discord.Color.green(),
                5: discord.Color.purple()
            }
            
            embed = discord.Embed(
                title=f"{emoji} Audio Quality Details",
                description=quality_tooltip,
                color=color_map.get(quality_info.quality_score, discord.Color.blue())
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Quality tooltip error: {e}")
            await interaction.followup.send(
                f"❌ Failed to analyze audio quality: {str(e)}",
                ephemeral=True
            )

class QualityTooltipView(discord.ui.View):
    """View containing quality tooltip button"""
    
    def __init__(self, song_url: str, song_title: str = "", timeout: Optional[float] = 300):
        super().__init__(timeout=timeout)
        self.add_item(QualityTooltipButton(song_url, song_title))

def add_quality_tooltip_to_view(view: discord.ui.View, song_url: str, song_title: str = "") -> discord.ui.View:
    """Add quality tooltip button to existing view"""
    if song_url:
        view.add_item(QualityTooltipButton(song_url, song_title))
    return view
