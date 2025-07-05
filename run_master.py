#!/usr/bin/env python3
"""
Discord Music Bot - Master Setup and Run Script
This script handles all dependencies, setup, and runs the Discord bot.
"""

import asyncio
import subprocess
import sys
import os
import logging
import signal
from pathlib import Path
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/master.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

class MasterBotRunner:
    """Master runner for the Discord Music Bot system"""
    
    def __init__(self):
        self.running = True
        
    def setup_directories(self):
        """Create necessary directories"""
        directories = ['logs', 'temp', 'data']
        for directory in directories:
            Path(directory).mkdir(exist_ok=True)
        logger.info("✅ Directories created")
        
    def install_system_dependencies(self):
        """Install system-level dependencies"""
        logger.info("🔧 Installing system dependencies...")
        
        try:
            # Check if we're on Replit (has nix)
            if os.path.exists('/nix'):
                logger.info("🔄 Replit environment detected - dependencies managed by Nix")
                return True
            
            # For local installations
            commands = [
                "apt-get update",
                "apt-get install -y ffmpeg libopus-dev libffi-dev python3-dev"
            ]
            
            for cmd in commands:
                try:
                    subprocess.run(cmd.split(), check=True, capture_output=True)
                    logger.info(f"✅ Executed: {cmd}")
                except subprocess.CalledProcessError as e:
                    logger.warning(f"⚠️ Command failed (may not be needed): {cmd}")
                    
        except Exception as e:
            logger.warning(f"⚠️ System dependency installation warning: {e}")
            
        return True
        
    def install_python_dependencies(self):
        """Install Python dependencies"""
        logger.info("📦 Installing Python dependencies...")
        
        dependencies = [
            "discord.py>=2.3.0",
            "yt-dlp>=2023.7.6",
            "aiohttp>=3.8.0",

            "sqlalchemy>=2.0.0",
            "alembic>=1.11.0",
            "psycopg2-binary>=2.9.0",
            "requests>=2.31.0",
            "PyNaCl>=1.5.0"
        ]
        
        for dep in dependencies:
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", dep], 
                             check=True, capture_output=True)
                logger.info(f"✅ Installed: {dep}")
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Failed to install {dep}: {e}")
                return False
                
        logger.info("✅ All Python dependencies installed")
        return True
        
    def check_environment_variables(self):
        """Check required environment variables"""
        logger.info("🔑 Checking environment variables...")
        
        required_vars = ['DISCORD_BOT_TOKEN']
        optional_vars = ['DATABASE_URL', 'MENU_CHANNEL_ID']
        
        missing_required = []
        for var in required_vars:
            if not os.getenv(var):
                missing_required.append(var)
                
        if missing_required:
            logger.error(f"❌ Missing required environment variables: {missing_required}")
            logger.error("Please set these variables and try again")
            return False
            
        # Log optional variables
        for var in optional_vars:
            if os.getenv(var):
                logger.info(f"✅ {var} is set")
            else:
                logger.info(f"ℹ️ {var} not set (optional)")
                
        logger.info("✅ Environment variables check passed")
        return True
        
    def setup_database(self):
        """Initialize database"""
        logger.info("🗄️ Setting up database...")
        
        try:
            from bot.database import init_database
            init_database()
            logger.info("✅ Database initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Database setup failed: {e}")
            return False
            
    def run_discord_bot(self):
        """Run the Discord bot in a separate process"""
        logger.info("🤖 Starting Discord bot process...")
        
        try:
            # Import and run the main bot
            import main
            asyncio.run(main.main())
        except Exception as e:
            logger.error(f"❌ Discord bot failed: {e}")
            
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Shutdown signal received")
        self.running = False
        sys.exit(0)
        
    def run_bot(self):
        """Run the Discord bot"""
        logger.info("Starting Discord bot...")
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            self.run_discord_bot()
        except KeyboardInterrupt:
            logger.info("Shutdown requested by user")
        except Exception as e:
            logger.error(f"Bot failed: {e}")
            
    def full_setup_and_run(self):
        """Complete setup and run process"""
        logger.info("Discord Music Bot Master Setup")
        logger.info("=" * 50)
        
        # Setup phase
        steps = [
            ("Creating directories", self.setup_directories),
            ("Installing system dependencies", self.install_system_dependencies),
            ("Installing Python dependencies", self.install_python_dependencies),
            ("Checking environment variables", self.check_environment_variables),
            ("Setting up database", self.setup_database)
        ]
        
        for step_name, step_func in steps:
            logger.info(f"Processing {step_name}...")
            if not step_func():
                logger.error(f"{step_name} failed - aborting")
                return False
                
        logger.info("Setup completed successfully!")
        logger.info("Starting Discord bot...")
        
        # Run the bot
        self.run_bot()
        return True

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Discord Music Bot Master Runner')
    parser.add_argument('--skip-deps', action='store_true',
                      help='Skip dependency installation')
    
    args = parser.parse_args()
    
    runner = MasterBotRunner()
    
    if args.skip_deps:
        logger.info("Skipping dependency installation")
        runner.setup_directories()
        runner.check_environment_variables()
        runner.setup_database()
        runner.run_bot()
    else:
        success = runner.full_setup_and_run()
        if not success:
            sys.exit(1)

if __name__ == "__main__":
    main()