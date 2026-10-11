from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseUploader(ABC):
    """Abstract base class for all platform uploaders."""

    def __init__(self, platform: str):
        self.platform = platform

    @abstractmethod
    async def upload(self, video_path: str, title: str, description: str, tags: str = "") -> Dict[str, Any]:
        """
        Uploads the video with provided metadata.
        Returns dict: {"success": bool, "post_url": Optional[str], "error": Optional[str]}
        """
        pass
