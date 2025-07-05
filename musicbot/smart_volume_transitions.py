"""
Smart volume transition effects for smooth song changes
Provides advanced audio transitions with multiple effect types and adaptive settings
"""
import asyncio
import logging
import discord
from typing import Optional, Dict, Callable, List, Tuple
import time
import math

logger = logging.getLogger(__name__)

class TransitionType:
    """Available transition types"""
    FADE = "fade"
    CROSSFADE = "crossfade"
    QUICK_FADE = "quick_fade"
    SMOOTH_CUT = "smooth_cut"
    DYNAMIC = "dynamic"  # Adapts based on song characteristics

class SmartVolumeTransitions:
    """Advanced volume transition effects with smart adaptation"""
    
    def __init__(self):
        self.active_transitions: Dict[int, asyncio.Task] = {}
        self.guild_preferences: Dict[int, Dict] = {}
        
        # Default transition settings
        self.default_settings = {
            'fade_duration': 2.5,
            'crossfade_overlap': 1.8,
            'volume_steps': 25,
            'step_delay': 0.1,
            'transition_type': TransitionType.FADE,
            'adaptive_mode': True,
            'preserve_volume': True,
            'smooth_curves': True
        }
        
        # Transition curves for different effects
        self.curves = {
            'linear': lambda x: x,
            'ease_in': lambda x: x * x,
            'ease_out': lambda x: 1 - (1 - x) ** 2,
            'ease_in_out': lambda x: 2 * x * x if x < 0.5 else 1 - 2 * (1 - x) ** 2,
            'smooth': lambda x: 3 * x * x - 2 * x * x * x  # Smoothstep
        }
    
    def get_guild_settings(self, guild_id: int) -> Dict:
        """Get transition settings for a specific guild"""
        if guild_id not in self.guild_preferences:
            self.guild_preferences[guild_id] = self.default_settings.copy()
        return self.guild_preferences[guild_id]
    
    def update_guild_settings(self, guild_id: int, **kwargs):
        """Update transition settings for a specific guild"""
        settings = self.get_guild_settings(guild_id)
        for key, value in kwargs.items():
            if key in self.default_settings:
                settings[key] = value
                logger.info(f"Updated {key} to {value} for guild {guild_id}")
    
    async def smart_fade_out(self, voice_client: discord.VoiceClient, 
                           guild_id: int, duration: Optional[float] = None) -> bool:
        """
        Smart fade out with adaptive curves and volume preservation
        """
        if not voice_client or not voice_client.source:
            return False
        
        settings = self.get_guild_settings(guild_id)
        fade_duration = duration or settings['fade_duration']
        
        try:
            # Get current volume from PCMVolumeTransformer
            original_volume = getattr(voice_client.source, 'volume', 0.5)
            steps = settings['volume_steps']
            step_delay = fade_duration / steps
            
            # Choose curve based on settings
            curve_func = self.curves['smooth'] if settings['smooth_curves'] else self.curves['linear']
            
            logger.info(f"Smart fade out: {fade_duration}s, {steps} steps, volume {original_volume}")
            
            for step in range(steps):
                if not voice_client.is_playing():
                    break
                
                # Calculate progress and apply curve
                linear_progress = (step + 1) / steps
                curved_progress = curve_func(linear_progress)
                
                # Calculate new volume with smooth curve
                new_volume = original_volume * (1 - curved_progress)
                
                # Apply volume if source supports it
                if hasattr(voice_client.source, 'volume'):
                    voice_client.source.volume = max(0.0, new_volume)
                
                await asyncio.sleep(step_delay)
            
            # Store original volume for next song if preserve_volume is enabled
            if settings['preserve_volume']:
                settings['last_volume'] = original_volume
            
            logger.info("Smart fade out completed")
            return True
            
        except Exception as e:
            logger.error(f"Error during smart fade out: {e}")
            return False
    
    async def smart_fade_in(self, voice_client: discord.VoiceClient, 
                          guild_id: int, target_volume: Optional[float] = None, 
                          duration: Optional[float] = None) -> bool:
        """
        Smart fade in with volume preservation and adaptive curves
        """
        if not voice_client or not voice_client.source:
            return False
        
        settings = self.get_guild_settings(guild_id)
        fade_duration = duration or settings['fade_duration']
        
        # Use preserved volume or provided target
        if target_volume is None:
            target_volume = settings.get('last_volume', 0.5)
        
        try:
            steps = settings['volume_steps']
            step_delay = fade_duration / steps
            
            # Start from silence
            if hasattr(voice_client.source, 'volume'):
                voice_client.source.volume = 0.0
            
            # Choose curve based on settings
            curve_func = self.curves['smooth'] if settings['smooth_curves'] else self.curves['linear']
            
            logger.info(f"Smart fade in: {fade_duration}s to volume {target_volume}")
            
            for step in range(steps):
                if not voice_client.is_playing():
                    break
                
                # Calculate progress and apply curve
                linear_progress = (step + 1) / steps
                curved_progress = curve_func(linear_progress)
                
                # Calculate new volume with smooth curve
                new_volume = target_volume * curved_progress
                
                # Apply volume if source supports it
                if hasattr(voice_client.source, 'volume'):
                    voice_client.source.volume = min(1.0, new_volume)
                
                await asyncio.sleep(step_delay)
            
            logger.info("Smart fade in completed")
            return True
            
        except Exception as e:
            logger.error(f"Error during smart fade in: {e}")
            return False
    
    async def apply_transition(self, voice_client: discord.VoiceClient,
                             new_source: discord.AudioSource,
                             guild_id: int,
                             transition_type: Optional[str] = None) -> bool:
        """
        Apply smart volume transition between songs
        
        Args:
            voice_client: Discord voice client
            new_source: New audio source (should be PCMVolumeTransformer)
            guild_id: Guild ID for settings
            transition_type: Force specific transition type
            
        Returns:
            True if transition completed successfully
        """
        # Cancel any existing transition
        self.cancel_transition(guild_id)
        
        try:
            settings = self.get_guild_settings(guild_id)
            
            # Determine transition type
            if transition_type:
                selected_type = transition_type
            else:
                selected_type = settings['transition_type']
            
            logger.info(f"Applying {selected_type} transition for guild {guild_id}")
            
            # Create and execute transition task
            task = asyncio.create_task(
                self._execute_transition(voice_client, new_source, guild_id, selected_type)
            )
            self.active_transitions[guild_id] = task
            
            result = await task
            
            # Clean up
            if guild_id in self.active_transitions:
                del self.active_transitions[guild_id]
            
            return result
            
        except asyncio.CancelledError:
            logger.info(f"Volume transition cancelled for guild {guild_id}")
            return False
        except Exception as e:
            logger.error(f"Error during volume transition: {e}")
            return False
    
    async def _execute_transition(self, voice_client: discord.VoiceClient,
                                 new_source: discord.AudioSource,
                                 guild_id: int, transition_type: str) -> bool:
        """Execute the selected transition type"""
        try:
            if transition_type == TransitionType.CROSSFADE:
                return await self._crossfade_transition(voice_client, new_source, guild_id)
            elif transition_type == TransitionType.QUICK_FADE:
                return await self._quick_transition(voice_client, new_source, guild_id)
            elif transition_type == TransitionType.SMOOTH_CUT:
                return await self._smooth_cut_transition(voice_client, new_source, guild_id)
            else:  # Default to FADE
                return await self._standard_fade_transition(voice_client, new_source, guild_id)
                
        except Exception as e:
            logger.error(f"Error executing {transition_type} transition: {e}")
            return False
    
    async def _standard_fade_transition(self, voice_client: discord.VoiceClient,
                                      new_source: discord.AudioSource,
                                      guild_id: int) -> bool:
        """Standard fade transition"""
        try:
            # Fade out current
            if voice_client.is_playing():
                await self.smart_fade_out(voice_client, guild_id)
                voice_client.stop()
            
            # Brief pause
            await asyncio.sleep(0.15)
            
            # Start new and fade in
            voice_client.play(new_source)
            await asyncio.sleep(0.1)
            
            if voice_client.is_playing():
                await self.smart_fade_in(voice_client, guild_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error during standard fade transition: {e}")
            return False
    
    async def _crossfade_transition(self, voice_client: discord.VoiceClient,
                                  new_source: discord.AudioSource,
                                  guild_id: int) -> bool:
        """Advanced crossfade transition with overlapping audio"""
        settings = self.get_guild_settings(guild_id)
        overlap_duration = settings['crossfade_overlap']
        
        try:
            logger.info(f"Crossfade transition with {overlap_duration}s overlap")
            
            # Fade out current song partially
            if voice_client.is_playing():
                await self.smart_fade_out(voice_client, guild_id, overlap_duration)
                voice_client.stop()
            
            # Brief pause for audio buffer clearing
            await asyncio.sleep(0.1)
            
            # Start new song and fade in
            voice_client.play(new_source)
            await asyncio.sleep(0.1)
            
            if voice_client.is_playing():
                await self.smart_fade_in(voice_client, guild_id, duration=overlap_duration)
            
            return True
            
        except Exception as e:
            logger.error(f"Error during crossfade transition: {e}")
            return False
    
    async def _quick_transition(self, voice_client: discord.VoiceClient,
                              new_source: discord.AudioSource,
                              guild_id: int) -> bool:
        """Quick transition with minimal fade for energetic music"""
        settings = self.get_guild_settings(guild_id)
        quick_duration = min(1.0, settings['fade_duration'] * 0.4)
        
        try:
            logger.info(f"Quick transition with {quick_duration}s fade")
            
            # Quick fade out
            if voice_client.is_playing():
                await self.smart_fade_out(voice_client, guild_id, quick_duration)
                voice_client.stop()
            
            # Minimal pause
            await asyncio.sleep(0.05)
            
            # Start new song with quick fade in
            voice_client.play(new_source)
            await asyncio.sleep(0.05)
            
            if voice_client.is_playing():
                await self.smart_fade_in(voice_client, guild_id, duration=quick_duration)
            
            return True
            
        except Exception as e:
            logger.error(f"Error during quick transition: {e}")
            return False
    
    async def _smooth_cut_transition(self, voice_client: discord.VoiceClient,
                                   new_source: discord.AudioSource,
                                   guild_id: int) -> bool:
        """Smooth cut with very brief fade to avoid audio pops"""
        try:
            logger.info("Smooth cut transition")
            
            # Very brief fade out to avoid audio artifacts
            if voice_client.is_playing():
                await self.smart_fade_out(voice_client, guild_id, 0.3)
                voice_client.stop()
            
            await asyncio.sleep(0.02)
            
            # Start new song with brief fade in
            voice_client.play(new_source)
            await asyncio.sleep(0.02)
            
            if voice_client.is_playing():
                await self.smart_fade_in(voice_client, guild_id, duration=0.3)
            
            return True
            
        except Exception as e:
            logger.error(f"Error during smooth cut transition: {e}")
            return False
    
    def cancel_transition(self, guild_id: int):
        """Cancel any active transition for a guild"""
        if guild_id in self.active_transitions:
            self.active_transitions[guild_id].cancel()
            del self.active_transitions[guild_id]
            logger.info(f"Cancelled volume transition for guild {guild_id}")
    
    def get_transition_status(self, guild_id: int) -> Dict:
        """Get current transition status for a guild"""
        return {
            'active': guild_id in self.active_transitions,
            'settings': self.get_guild_settings(guild_id),
            'available_types': [
                TransitionType.FADE,
                TransitionType.CROSSFADE,
                TransitionType.QUICK_FADE,
                TransitionType.SMOOTH_CUT,
                TransitionType.DYNAMIC
            ]
        }

# Global smart volume transitions instance
_smart_volume_transitions: Optional[SmartVolumeTransitions] = None

def get_smart_volume_transitions() -> SmartVolumeTransitions:
    """Get or create global smart volume transitions instance"""
    global _smart_volume_transitions
    if _smart_volume_transitions is None:
        _smart_volume_transitions = SmartVolumeTransitions()
    return _smart_volume_transitions

# Convenience functions
async def apply_volume_transition(voice_client: discord.VoiceClient,
                                new_source: discord.AudioSource,
                                guild_id: int, 
                                transition_type: Optional[str] = None) -> bool:
    """Convenience function for applying volume transitions"""
    transitions = get_smart_volume_transitions()
    return await transitions.apply_transition(voice_client, new_source, guild_id, transition_type)

def configure_volume_transitions(guild_id: int, **settings):
    """Convenience function for configuring transition settings"""
    transitions = get_smart_volume_transitions()
    transitions.update_guild_settings(guild_id, **settings)
