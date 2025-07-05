"""
Download Manager for Discord Music Bot
Handles song downloads and offline caching functionality
"""

import asyncio
import os
import hashlib
import json
import aiofiles
import yt_dlp
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class DownloadManager:
    """Manages song downloads and offline cache"""
    
    def __init__(self, cache_dir: str = "cache", max_cache_size_gb: float = 2.0):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        self.audio_dir = self.cache_dir / "audio"
        self.metadata_dir = self.cache_dir / "metadata"
        self.thumbnails_dir = self.cache_dir / "thumbnails"
        
        for directory in [self.audio_dir, self.metadata_dir, self.thumbnails_dir]:
            directory.mkdir(exist_ok=True)
            
        self.max_cache_size_bytes = int(max_cache_size_gb * 1024 * 1024 * 1024)
        self.cache_index_file = self.cache_dir / "cache_index.json"
        self.cache_index = {}
        
        # Load existing cache index
        asyncio.create_task(self._load_cache_index())
        
    async def _load_cache_index(self):
        """Load cache index from file"""
        try:
            if self.cache_index_file.exists():
                async with aiofiles.open(self.cache_index_file, 'r') as f:
                    content = await f.read()
                    self.cache_index = json.loads(content)
                logger.info(f"Loaded cache index with {len(self.cache_index)} entries")
        except Exception as e:
            logger.error(f"Failed to load cache index: {e}")
            self.cache_index = {}
            
    async def _save_cache_index(self):
        """Save cache index to file"""
        try:
            async with aiofiles.open(self.cache_index_file, 'w') as f:
                await f.write(json.dumps(self.cache_index, indent=2))
        except Exception as e:
            logger.error(f"Failed to save cache index: {e}")
            
    def _get_cache_key(self, url: str) -> str:
        """Generate cache key from URL"""
        return hashlib.md5(url.encode()).hexdigest()
        
    async def is_cached(self, url: str) -> bool:
        """Check if a song is already cached"""
        cache_key = self._get_cache_key(url)
        if cache_key not in self.cache_index:
            return False
            
        # Check if files actually exist
        entry = self.cache_index[cache_key]
        audio_path = Path(entry['audio_path'])
        metadata_path = Path(entry['metadata_path'])
        
        return audio_path.exists() and metadata_path.exists()
        
    async def get_cached_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Get cached song info"""
        cache_key = self._get_cache_key(url)
        if not await self.is_cached(url):
            return None
            
        try:
            metadata_path = Path(self.cache_index[cache_key]['metadata_path'])
            async with aiofiles.open(metadata_path, 'r') as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to load cached metadata: {e}")
            return None
            
    async def download_song(self, url: str, progress_callback=None) -> Optional[Dict[str, Any]]:
        """Download a song and cache it"""
        cache_key = self._get_cache_key(url)
        
        # Check if already cached
        if await self.is_cached(url):
            logger.info(f"Song already cached: {cache_key}")
            return await self.get_cached_info(url)
            
        # Prepare file paths
        audio_filename = f"{cache_key}.%(ext)s"
        audio_path = self.audio_dir / audio_filename
        metadata_path = self.metadata_dir / f"{cache_key}.json"
        thumbnail_path = self.thumbnails_dir / f"{cache_key}.%(ext)s"
        
        # Download options
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio',
            'outtmpl': str(audio_path),
            'writeinfojson': False,
            'writethumbnail': True,
            'outtmpl': {
                'default': str(audio_path),
                'thumbnail': str(thumbnail_path)
            },
            'extractaudio': True,
            'audioformat': 'mp3',
            'audioquality': '192',
            'embed_chapters': False,
            'embed_info_json': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
        }
        
        if progress_callback:
            def progress_hook(d):
                if d['status'] == 'downloading':
                    try:
                        progress = d.get('_percent_str', 'N/A')
                        if progress_callback:
                            asyncio.create_task(progress_callback(f"Downloading: {progress}"))
                    except:
                        pass
            ydl_opts['progress_hooks'] = [progress_hook]
            
        try:
            # Download the song
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, ydl.extract_info, url, True)
                
            if not info:
                logger.error(f"Failed to extract info for: {url}")
                return None
                
            # Find the actual downloaded file
            downloaded_files = list(self.audio_dir.glob(f"{cache_key}.*"))
            if not downloaded_files:
                logger.error(f"No audio file found after download: {cache_key}")
                return None
                
            actual_audio_path = downloaded_files[0]
            
            # Find thumbnail file
            thumbnail_files = list(self.thumbnails_dir.glob(f"{cache_key}.*"))
            actual_thumbnail_path = thumbnail_files[0] if thumbnail_files else None
            
            # Prepare metadata
            metadata = {
                'url': url,
                'title': info.get('title', 'Unknown'),
                'uploader': info.get('uploader', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
                'upload_date': info.get('upload_date'),
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'description': info.get('description', ''),
                'cached_at': datetime.now().isoformat(),
                'file_size': actual_audio_path.stat().st_size,
                'audio_path': str(actual_audio_path),
                'thumbnail_path': str(actual_thumbnail_path) if actual_thumbnail_path else None,
                'cache_key': cache_key
            }
            
            # Save metadata
            async with aiofiles.open(metadata_path, 'w') as f:
                await f.write(json.dumps(metadata, indent=2))
                
            # Update cache index
            self.cache_index[cache_key] = {
                'url': url,
                'title': metadata['title'],
                'cached_at': metadata['cached_at'],
                'file_size': metadata['file_size'],
                'audio_path': str(actual_audio_path),
                'metadata_path': str(metadata_path),
                'thumbnail_path': str(actual_thumbnail_path) if actual_thumbnail_path else None
            }
            
            await self._save_cache_index()
            await self._cleanup_cache_if_needed()
            
            logger.info(f"Successfully cached song: {metadata['title']}")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to download song {url}: {e}")
            # Cleanup failed download
            for path in [audio_path.parent.glob(f"{cache_key}.*"), 
                        metadata_path, 
                        thumbnail_path.parent.glob(f"{cache_key}.*")]:
                try:
                    if isinstance(path, Path) and path.exists():
                        path.unlink()
                    elif hasattr(path, '__iter__'):
                        for p in path:
                            if p.exists():
                                p.unlink()
                except:
                    pass
            return None
            
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_size = 0
        total_files = 0
        
        for entry in self.cache_index.values():
            total_size += entry.get('file_size', 0)
            total_files += 1
            
        return {
            'total_files': total_files,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'total_size_gb': round(total_size / (1024 * 1024 * 1024), 3),
            'max_size_gb': self.max_cache_size_bytes / (1024 * 1024 * 1024),
            'usage_percent': round((total_size / self.max_cache_size_bytes) * 100, 1)
        }
        
    async def _cleanup_cache_if_needed(self):
        """Clean up cache if it exceeds size limit"""
        total_size = sum(entry.get('file_size', 0) for entry in self.cache_index.values())
        
        if total_size <= self.max_cache_size_bytes:
            return
            
        logger.info(f"Cache size exceeded limit, cleaning up...")
        
        # Sort by cached_at date (oldest first)
        sorted_entries = sorted(
            self.cache_index.items(),
            key=lambda x: x[1].get('cached_at', ''),
        )
        
        # Remove oldest entries until under limit
        for cache_key, entry in sorted_entries:
            if total_size <= self.max_cache_size_bytes * 0.8:  # Clean to 80% of limit
                break
                
            await self._remove_cache_entry(cache_key)
            total_size -= entry.get('file_size', 0)
            
        await self._save_cache_index()
        
    async def _remove_cache_entry(self, cache_key: str):
        """Remove a cache entry and its files"""
        if cache_key not in self.cache_index:
            return
            
        entry = self.cache_index[cache_key]
        
        # Remove files
        for path_key in ['audio_path', 'metadata_path', 'thumbnail_path']:
            if entry.get(path_key):
                try:
                    Path(entry[path_key]).unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"Failed to remove {path_key}: {e}")
                    
        # Remove from index
        del self.cache_index[cache_key]
        
    async def clear_cache(self):
        """Clear entire cache"""
        logger.info("Clearing entire cache...")
        
        # Remove all files
        for directory in [self.audio_dir, self.metadata_dir, self.thumbnails_dir]:
            for file_path in directory.iterdir():
                try:
                    file_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove {file_path}: {e}")
                    
        # Clear index
        self.cache_index = {}
        await self._save_cache_index()
        
    async def remove_cached_song(self, url: str) -> bool:
        """Remove specific song from cache"""
        cache_key = self._get_cache_key(url)
        if cache_key in self.cache_index:
            await self._remove_cache_entry(cache_key)
            await self._save_cache_index()
            return True
        return False
        
    async def get_cached_songs(self) -> List[Dict[str, Any]]:
        """Get list of all cached songs"""
        cached_songs = []
        
        for cache_key, entry in self.cache_index.items():
            # Load full metadata
            try:
                metadata_path = Path(entry['metadata_path'])
                if metadata_path.exists():
                    async with aiofiles.open(metadata_path, 'r') as f:
                        content = await f.read()
                        metadata = json.loads(content)
                        cached_songs.append(metadata)
            except Exception as e:
                logger.warning(f"Failed to load metadata for {cache_key}: {e}")
                
        return sorted(cached_songs, key=lambda x: x.get('cached_at', ''), reverse=True)

# Global instance
_download_manager = None

def get_download_manager() -> DownloadManager:
    """Get the global download manager instance"""
    global _download_manager
    if _download_manager is None:
        _download_manager = DownloadManager()
    return _download_manager

async def download_song(url: str, progress_callback=None) -> Optional[Dict[str, Any]]:
    """Convenience function to download a song"""
    return await get_download_manager().download_song(url, progress_callback)

async def is_song_cached(url: str) -> bool:
    """Convenience function to check if song is cached"""
    return await get_download_manager().is_cached(url)

async def get_cached_song_info(url: str) -> Optional[Dict[str, Any]]:
    """Convenience function to get cached song info"""
    return await get_download_manager().get_cached_info(url)