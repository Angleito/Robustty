import json
import logging
from collections import deque
from pathlib import Path
from typing import Dict, List

import aiofiles

logger = logging.getLogger(__name__)


class QueueManager:
    """Manages persistent queue storage"""

    def __init__(self, config: Dict):
        self.config = config
        self.queue_dir = Path("data/queues")
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    async def save_queue(self, guild_id: int, queue: List[Dict]):
        """Save queue to file"""
        if not self.config.get("save_queue", True):
            return

        queue_file = self.queue_dir / f"{guild_id}.json"
        try:
            async with aiofiles.open(queue_file, "w") as f:
                await f.write(json.dumps(queue, indent=2))
            logger.info(f"Saved queue for guild {guild_id}")
        except Exception as e:
            logger.error(f"Failed to save queue for guild {guild_id}: {e}")

    async def load_queue(self, guild_id: int) -> List[Dict]:
        """Load queue from file"""
        if not self.config.get("save_queue", True):
            return []

        queue_file = self.queue_dir / f"{guild_id}.json"
        if not queue_file.exists():
            return []

        try:
            async with aiofiles.open(queue_file, "r") as f:
                content = await f.read()
                queue = json.loads(content)
                logger.info(f"Loaded queue for guild {guild_id}")
                return queue
        except Exception as e:
            logger.error(f"Failed to load queue for guild {guild_id}: {e}")
            return []

    async def delete_queue(self, guild_id: int):
        """Delete saved queue"""
        queue_file = self.queue_dir / f"{guild_id}.json"
        if queue_file.exists():
            try:
                queue_file.unlink()
                logger.info(f"Deleted queue for guild {guild_id}")
            except Exception as e:
                logger.error(f"Failed to delete queue for guild {guild_id}: {e}")

    async def cleanup_old_queues(self, days: int = 7):
        """Clean up old queue files"""
        import time

        current_time = time.time()
        cutoff_time = current_time - (days * 24 * 60 * 60)

        for queue_file in self.queue_dir.glob("*.json"):
            try:
                if queue_file.stat().st_mtime < cutoff_time:
                    queue_file.unlink()
                    logger.info(f"Deleted old queue file: {queue_file}")
            except Exception as e:
                logger.error(f"Failed to delete old queue file {queue_file}: {e}")

    def serialize_queue(self, queue: deque) -> List[Dict]:
        """Convert queue to serializable format"""
        return list(queue)

    def deserialize_queue(self, data: List[Dict], max_size: int) -> deque:
        """Convert serialized data back to queue"""
        queue: deque[Dict] = deque(maxlen=max_size)
        queue.extend(data[:max_size])  # Ensure we don't exceed max size
        return queue
