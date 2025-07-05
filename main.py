#!/usr/bin/env python3
"""
Discord Music Bot
A comprehensive music bot with YouTube/SoundCloud integration and voice streaming.
"""

import asyncio
import logging
import sys
from pathlib import Path
import discord

from bot.config import setup_environment, get_config
from bot.music_player import MusicBot
from bot.database import init_database

def setup_logging():
    """Configure logging for the Discord bot."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "bot.log", encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce discord.py logging noise
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)

async def main():
    """Main entry point for the Discord music bot."""
    print("🎵 Starting Discord Music Bot...")
    
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Setup environment and dependencies
        await setup_environment()
        
        # Initialize database
        init_database()
        
        config = get_config()
        
        # Configure Discord intents for voice connections
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        # Initialize the music bot
        bot = MusicBot(config, intents=intents)
        
        logger.info("🤖 Starting Discord bot...")
        
        # Debug token information
        if config.discord_token == "demo_token":
            logger.info("🌐 Running in web-only mode - Discord bot disabled")
            logger.info("💡 To enable Discord functionality, set DISCORD_BOT_TOKEN environment variable")
            # Keep the web dashboard running
            while True:
                await asyncio.sleep(60)
        else:
            # Log token format for debugging (safely)
            if config.discord_token:
                token_start = config.discord_token[:10] if len(config.discord_token) > 10 else "short"
                logger.info(f"🔑 Token format check - starts with: {token_start}...")
                logger.info(f"🔑 Token length: {len(config.discord_token)} characters")
            
            await bot.start(config.discord_token)
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot shutdown requested by user")
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
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("👋 Bot shutting down...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        sys.exit(1)
