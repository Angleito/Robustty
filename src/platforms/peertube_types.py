"""Type definitions for PeerTube API responses and internal structures."""

from typing import List, Optional, TypedDict, Union


# Channel types
class ChannelInfo(TypedDict):
    """PeerTube channel information."""
    displayName: str
    name: str
    description: Optional[str]
    url: Optional[str]


# Resolution types
class Resolution(TypedDict):
    """Video resolution information."""
    id: int
    label: str


# File types
class VideoFile(TypedDict):
    """PeerTube video file information."""
    fileUrl: str
    resolution: Resolution
    size: int
    torrentUrl: Optional[str]
    magnetUri: Optional[str]


# Video types
class VideoInfo(TypedDict):
    """PeerTube video information from API."""
    uuid: str
    name: str
    description: Optional[str]
    duration: Optional[int]
    views: Optional[int]
    likes: Optional[int]
    dislikes: Optional[int]
    publishedAt: Optional[str]
    channel: Optional[ChannelInfo]
    thumbnailPath: str
    previewPath: Optional[str]
    files: List[VideoFile]


# Search response types
class SearchData(TypedDict):
    """PeerTube search response data."""
    data: List[VideoInfo]
    total: int


# Internal types
class VideoSummary(TypedDict):
    """Video summary for search results."""
    id: str
    title: str
    channel: str
    thumbnail: str
    url: str
    platform: str
    instance: str
    description: str
    duration: Optional[int]
    views: int


class VideoDetails(VideoSummary):
    """Full video details with additional fields."""
    likes: Optional[int]
    dislikes: Optional[int]
    publishedAt: Optional[str]


# Configuration types
class PeerTubeConfig(TypedDict):
    """PeerTube platform configuration."""
    instances: List[str]
    max_results_per_instance: int
    enabled: bool


# Error types
class PeerTubeError(Exception):
    """Base exception for PeerTube-related errors."""
    pass


class PeerTubeAPIError(PeerTubeError):
    """Exception for PeerTube API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, instance: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.instance = instance


class PeerTubeSearchError(PeerTubeError):
    """Exception for search-related errors."""
    pass


# Result types for improved error handling
PeerTubeResult = Union[VideoDetails, PeerTubeError]
SearchResult = Union[List[VideoDetails], PeerTubeError]


# Type aliases for clarity
InstanceURL = str
VideoID = str
SearchQuery = str
