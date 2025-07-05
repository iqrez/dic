"""
Database models and operations for the Discord Music Bot
"""

import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, BigInteger, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import JSON

logger = logging.getLogger(__name__)

Base = declarative_base()

class Guild(Base):
    """Guild (Discord server) settings and preferences"""
    __tablename__ = 'guilds'
    
    id = Column(BigInteger, primary_key=True)  # Discord Guild ID
    name = Column(String(100), nullable=False)
    menu_channel_id = Column(BigInteger, nullable=True)
    default_volume = Column(Float, default=0.5)
    auto_disconnect = Column(Boolean, default=True)
    auto_disconnect_delay = Column(Integer, default=300)  # seconds
    loop_enabled = Column(Boolean, default=False)
    autoplay_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PlayHistory(Base):
    """Track what songs have been played"""
    __tablename__ = 'play_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    title = Column(String(500), nullable=False)
    url = Column(Text, nullable=False)
    platform = Column(String(50), nullable=False)  # youtube, soundcloud, etc.
    duration = Column(Integer, nullable=True)  # seconds
    thumbnail = Column(Text, nullable=True)
    uploader = Column(String(200), nullable=True)
    played_at = Column(DateTime, default=datetime.utcnow)

class UserPlaylist(Base):
    """User-created playlists"""
    __tablename__ = 'user_playlists'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    guild_id = Column(BigInteger, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    songs = Column(JSON, nullable=False, default=list)  # List of song objects
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SearchHistory(Base):
    """Track search queries for recommendations"""
    __tablename__ = 'search_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    query = Column(Text, nullable=False)
    result_count = Column(Integer, default=0)
    searched_at = Column(DateTime, default=datetime.utcnow)

class BotStats(Base):
    """Bot usage statistics"""
    __tablename__ = 'bot_stats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False)
    command_name = Column(String(100), nullable=False)
    user_id = Column(BigInteger, nullable=False)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    execution_time = Column(Float, nullable=True)  # milliseconds
    executed_at = Column(DateTime, default=datetime.utcnow)

class DatabaseManager:
    """Database connection and operations manager"""
    
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        self.engine = create_engine(
            self.database_url,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=False  # Set to True for SQL debugging
        )
        
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create tables
        self.create_tables()
        logger.info("Database manager initialized successfully")
    
    def create_tables(self):
        """Create all database tables"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created/verified successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    def get_session(self) -> Session:
        """Get a database session"""
        return self.SessionLocal()
    
    # Guild operations
    def get_or_create_guild(self, guild_id: int, guild_name: str) -> Guild:
        """Get or create a guild record"""
        session = self.get_session()
        try:
            guild = session.query(Guild).filter(Guild.id == guild_id).first()
            if not guild:
                guild = Guild(id=guild_id, name=guild_name)
                session.add(guild)
                session.commit()
                logger.info(f"Created new guild record: {guild_name} ({guild_id})")
            else:
                # Update name if changed
                if guild.name != guild_name:
                    guild.name = guild_name
                    guild.updated_at = datetime.utcnow()
                    session.commit()
            
            return guild
        finally:
            session.close()
    
    def update_guild_settings(self, guild_id: int, **kwargs) -> bool:
        """Update guild settings"""
        session = self.get_session()
        try:
            guild = session.query(Guild).filter(Guild.id == guild_id).first()
            if guild:
                for key, value in kwargs.items():
                    if hasattr(guild, key):
                        setattr(guild, key, value)
                guild.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False
        finally:
            session.close()
    
    # Play history operations
    def add_play_history(self, guild_id: int, user_id: int, song_data: Dict[str, Any]):
        """Add a song to play history"""
        session = self.get_session()
        try:
            history = PlayHistory(
                guild_id=guild_id,
                user_id=user_id,
                title=song_data.get('title', 'Unknown'),
                url=song_data.get('url', ''),
                platform=song_data.get('platform', 'unknown'),
                duration=song_data.get('duration'),
                thumbnail=song_data.get('thumbnail'),
                uploader=song_data.get('uploader')
            )
            session.add(history)
            session.commit()
        except Exception as e:
            logger.error(f"Failed to add play history: {e}")
        finally:
            session.close()
    
    def get_play_history(self, guild_id: int, limit: int = 50) -> List[PlayHistory]:
        """Get recent play history for a guild"""
        session = self.get_session()
        try:
            return session.query(PlayHistory)\
                .filter(PlayHistory.guild_id == guild_id)\
                .order_by(PlayHistory.played_at.desc())\
                .limit(limit)\
                .all()
        finally:
            session.close()
    
    # Playlist operations
    def create_playlist(self, user_id: int, guild_id: int, name: str, description: str = None) -> UserPlaylist:
        """Create a new user playlist"""
        session = self.get_session()
        try:
            playlist = UserPlaylist(
                user_id=user_id,
                guild_id=guild_id,
                name=name,
                description=description,
                songs=[]
            )
            session.add(playlist)
            session.commit()
            session.refresh(playlist)
            return playlist
        finally:
            session.close()
    
    def add_song_to_playlist(self, playlist_id: int, song_data: Dict[str, Any]) -> bool:
        """Add a song to a playlist"""
        session = self.get_session()
        try:
            playlist = session.query(UserPlaylist).filter(UserPlaylist.id == playlist_id).first()
            if playlist:
                songs = playlist.songs or []
                songs.append(song_data)
                playlist.songs = songs
                playlist.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False
        finally:
            session.close()
    
    def get_user_playlists(self, user_id: int, guild_id: int) -> List[UserPlaylist]:
        """Get all playlists for a user in a guild"""
        session = self.get_session()
        try:
            return session.query(UserPlaylist)\
                .filter(UserPlaylist.user_id == user_id, UserPlaylist.guild_id == guild_id)\
                .order_by(UserPlaylist.created_at.desc())\
                .all()
        finally:
            session.close()
    
    # Search history operations
    def add_search_history(self, guild_id: int, user_id: int, query: str, result_count: int = 0):
        """Add a search query to history"""
        session = self.get_session()
        try:
            search = SearchHistory(
                guild_id=guild_id,
                user_id=user_id,
                query=query,
                result_count=result_count
            )
            session.add(search)
            session.commit()
        except Exception as e:
            logger.error(f"Failed to add search history: {e}")
        finally:
            session.close()
    
    # Statistics operations
    def add_command_stat(self, guild_id: int, user_id: int, command_name: str, 
                        success: bool = True, error_message: str = None, execution_time: float = None):
        """Add command usage statistics"""
        session = self.get_session()
        try:
            stat = BotStats(
                guild_id=guild_id,
                user_id=user_id,
                command_name=command_name,
                success=success,
                error_message=error_message,
                execution_time=execution_time
            )
            session.add(stat)
            session.commit()
        except Exception as e:
            logger.error(f"Failed to add command stat: {e}")
        finally:
            session.close()
    
    def get_guild_stats(self, guild_id: int) -> Dict[str, Any]:
        """Get statistics for a guild"""
        session = self.get_session()
        try:
            total_commands = session.query(BotStats).filter(BotStats.guild_id == guild_id).count()
            total_plays = session.query(PlayHistory).filter(PlayHistory.guild_id == guild_id).count()
            total_searches = session.query(SearchHistory).filter(SearchHistory.guild_id == guild_id).count()
            
            return {
                'total_commands': total_commands,
                'total_plays': total_plays,
                'total_searches': total_searches
            }
        finally:
            session.close()

# Global database manager instance
db_manager: Optional[DatabaseManager] = None

def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance"""
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager

def init_database():
    """Initialize the database connection"""
    global db_manager
    try:
        db_manager = DatabaseManager()
        logger.info("Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False