import yt_dlp
from dataclasses import dataclass
from typing import Optional, Dict
import asyncio

@dataclass
class AudioQualityInfo:
    bitrate: Optional[int] = None
    codec: Optional[str] = None
    quality_score: Optional[int] = None

async def analyze_track_quality(url: str) -> AudioQualityInfo:
    """Return simple quality info for a track using yt_dlp metadata."""
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    loop = asyncio.get_event_loop()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = await loop.run_in_executor(None, ydl.extract_info, url, False)
        formats = info.get("formats") or []
        abr = None
        codec = None
        for fmt in formats:
            if fmt.get("acodec") != "none" and fmt.get("abr"):
                abr = int(fmt["abr"])
                codec = fmt.get("acodec")
                break
        score = None
        if abr:
            if abr >= 320:
                score = 5
            elif abr >= 256:
                score = 4
            elif abr >= 192:
                score = 3
            elif abr >= 128:
                score = 2
            else:
                score = 1
        return AudioQualityInfo(bitrate=abr, codec=codec, quality_score=score)
    except Exception:
        return AudioQualityInfo()


def generate_quality_embed_field(info: AudioQualityInfo) -> Dict[str, str]:
    if info.quality_score is None:
        return {"name": "Audio Quality", "value": "Unknown"}
    emojis = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "💎"}
    emoji = emojis.get(info.quality_score, "❓")
    text = f"{emoji} {info.bitrate}kbps {info.codec}" if info.bitrate else "Unknown"
    return {"name": "Audio Quality", "value": text}


def generate_quality_tooltip(info: AudioQualityInfo, title: str) -> str:
    if info.quality_score is None:
        return f"Quality information unavailable for {title}"
    return f"Bitrate: {info.bitrate}kbps\nCodec: {info.codec}"
