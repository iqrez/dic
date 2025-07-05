"""
Transition-related slash commands for smart volume effects
"""
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import logging

from .smart_volume_transitions import get_smart_volume_transitions, TransitionType

logger = logging.getLogger(__name__)

class TransitionCommands(commands.Cog):
    """Commands for managing smart volume transitions"""
    
    def __init__(self, bot):
        self.bot = bot
        self.transitions = get_smart_volume_transitions()
    
    @app_commands.command(name="transition_type", description="Set the volume transition effect type")
    @app_commands.describe(
        transition_type="Choose the transition effect for song changes"
    )
    @app_commands.choices(transition_type=[
        app_commands.Choice(name="Smooth Fade (Default)", value=TransitionType.FADE),
        app_commands.Choice(name="Crossfade", value=TransitionType.CROSSFADE),
        app_commands.Choice(name="Quick Fade", value=TransitionType.QUICK_FADE),
        app_commands.Choice(name="Smooth Cut", value=TransitionType.SMOOTH_CUT),
        app_commands.Choice(name="Dynamic (Auto)", value=TransitionType.DYNAMIC)
    ])
    async def set_transition_type(self, interaction: discord.Interaction, transition_type: str):
        """Set the transition effect type for song changes"""
        try:
            guild_id = interaction.guild_id
            
            # Update transition settings
            self.transitions.update_guild_settings(guild_id, transition_type=transition_type)
            
            # Create response embed
            embed = discord.Embed(
                title="🎵 Transition Effect Updated",
                description=f"Volume transition type set to **{transition_type.title()}**",
                color=0x00FF00
            )
            
            # Add description of the selected transition type
            descriptions = {
                TransitionType.FADE: "Smooth fade out → pause → fade in (best for most music)",
                TransitionType.CROSSFADE: "Overlapping audio transition (seamless mixing)",
                TransitionType.QUICK_FADE: "Fast transitions (great for energetic music)",
                TransitionType.SMOOTH_CUT: "Minimal fade to avoid audio pops",
                TransitionType.DYNAMIC: "Automatically adapts based on song characteristics"
            }
            
            embed.add_field(
                name="Effect Description",
                value=descriptions.get(transition_type, "Custom transition effect"),
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Transition type set to {transition_type} for guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Error setting transition type: {e}")
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Error",
                    description="Failed to update transition settings.",
                    color=0xFF0000
                ),
                ephemeral=True
            )
    
    @app_commands.command(name="transition_settings", description="Configure volume transition settings")
    @app_commands.describe(
        fade_duration="Duration of fade effects in seconds (0.5-10.0)",
        volume_steps="Number of volume steps for smoothness (10-50)",
        smooth_curves="Use smooth mathematical curves for transitions"
    )
    async def configure_transitions(
        self, 
        interaction: discord.Interaction,
        fade_duration: Optional[float] = None,
        volume_steps: Optional[int] = None,
        smooth_curves: Optional[bool] = None
    ):
        """Configure detailed transition settings"""
        try:
            guild_id = interaction.guild_id
            settings = {}
            
            # Validate and apply settings
            if fade_duration is not None:
                if 0.5 <= fade_duration <= 10.0:
                    settings['fade_duration'] = fade_duration
                else:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="❌ Invalid Duration",
                            description="Fade duration must be between 0.5 and 10.0 seconds.",
                            color=0xFF0000
                        ),
                        ephemeral=True
                    )
                    return
            
            if volume_steps is not None:
                if 10 <= volume_steps <= 50:
                    settings['volume_steps'] = volume_steps
                else:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="❌ Invalid Steps",
                            description="Volume steps must be between 10 and 50.",
                            color=0xFF0000
                        ),
                        ephemeral=True
                    )
                    return
            
            if smooth_curves is not None:
                settings['smooth_curves'] = smooth_curves
            
            if not settings:
                # Show current settings
                current = self.transitions.get_guild_settings(guild_id)
                embed = discord.Embed(
                    title="🎛️ Current Transition Settings",
                    color=0x0099FF
                )
                embed.add_field(name="Transition Type", value=current['transition_type'].title(), inline=True)
                embed.add_field(name="Fade Duration", value=f"{current['fade_duration']}s", inline=True)
                embed.add_field(name="Volume Steps", value=str(current['volume_steps']), inline=True)
                embed.add_field(name="Smooth Curves", value="✅" if current['smooth_curves'] else "❌", inline=True)
                embed.add_field(name="Adaptive Mode", value="✅" if current['adaptive_mode'] else "❌", inline=True)
                embed.add_field(name="Preserve Volume", value="✅" if current['preserve_volume'] else "❌", inline=True)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Apply settings
            self.transitions.update_guild_settings(guild_id, **settings)
            
            # Create success response
            embed = discord.Embed(
                title="🎛️ Transition Settings Updated",
                description="Your transition settings have been updated successfully.",
                color=0x00FF00
            )
            
            for key, value in settings.items():
                display_name = key.replace('_', ' ').title()
                if key == 'fade_duration':
                    display_value = f"{value}s"
                elif key == 'smooth_curves':
                    display_value = "✅ Enabled" if value else "❌ Disabled"
                else:
                    display_value = str(value)
                
                embed.add_field(name=display_name, value=display_value, inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Transition settings updated for guild {guild_id}: {settings}")
            
        except Exception as e:
            logger.error(f"Error configuring transitions: {e}")
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Error",
                    description="Failed to update transition settings.",
                    color=0xFF0000
                ),
                ephemeral=True
            )
    
    @app_commands.command(name="test_transition", description="Test volume transition effects")
    @app_commands.describe(
        effect_type="Choose a transition effect to test"
    )
    @app_commands.choices(effect_type=[
        app_commands.Choice(name="Current Settings", value="current"),
        app_commands.Choice(name="Smooth Fade", value=TransitionType.FADE),
        app_commands.Choice(name="Quick Fade", value=TransitionType.QUICK_FADE),
        app_commands.Choice(name="Smooth Cut", value=TransitionType.SMOOTH_CUT)
    ])
    async def test_transition(self, interaction: discord.Interaction, effect_type: str = "current"):
        """Test transition effects with current playing song"""
        try:
            guild_id = interaction.guild_id
            voice = interaction.guild.voice_client
            
            if not voice or not voice.is_playing():
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="❌ No Playback",
                        description="No music is currently playing to test transitions.",
                        color=0xFF0000
                    ),
                    ephemeral=True
                )
                return
            
            # Get current volume
            current_volume = getattr(voice.source, 'volume', 0.5)
            
            await interaction.response.defer(ephemeral=True)
            
            if effect_type == "current":
                # Test fade out and back in with current settings
                await self.transitions.smart_fade_out(voice, guild_id, duration=1.5)
                await self.transitions.smart_fade_in(voice, guild_id, target_volume=current_volume, duration=1.5)
                effect_name = "Current Settings"
            else:
                # Test specific transition effect
                if effect_type == TransitionType.FADE:
                    await self.transitions.smart_fade_out(voice, guild_id, duration=2.0)
                    await self.transitions.smart_fade_in(voice, guild_id, target_volume=current_volume, duration=2.0)
                elif effect_type == TransitionType.QUICK_FADE:
                    await self.transitions.smart_fade_out(voice, guild_id, duration=0.8)
                    await self.transitions.smart_fade_in(voice, guild_id, target_volume=current_volume, duration=0.8)
                elif effect_type == TransitionType.SMOOTH_CUT:
                    await self.transitions.smart_fade_out(voice, guild_id, duration=0.3)
                    await self.transitions.smart_fade_in(voice, guild_id, target_volume=current_volume, duration=0.3)
                
                effect_name = effect_type.title()
            
            embed = discord.Embed(
                title="🎵 Transition Test Complete",
                description=f"**{effect_name}** transition effect demonstrated successfully!",
                color=0x00FF00
            )
            embed.set_footer(text="The song volume was faded out and back in to show the transition effect.")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Transition test completed for guild {guild_id}: {effect_type}")
            
        except Exception as e:
            logger.error(f"Error testing transition: {e}")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Test Failed",
                    description="Failed to test transition effects.",
                    color=0xFF0000
                ),
                ephemeral=True
            )

async def setup(bot):
    """Setup function for the transition commands"""
    # Add transition commands directly to the bot's tree
    transition_commands = TransitionCommands(bot)
    
    # Add each command to the bot's command tree
    bot.tree.add_command(transition_commands.set_transition_type)
    bot.tree.add_command(transition_commands.configure_transitions)  
    bot.tree.add_command(transition_commands.test_transition)
    
    logger.info("Added transition commands to bot tree")