"""
Task cleanup utilities for proper async resource management
"""
import asyncio
import logging
from typing import Set, Union, Any

logger = logging.getLogger(__name__)


async def cancel_tasks_gracefully(
    tasks: Union[Set[asyncio.Task], list[asyncio.Task]], 
    timeout: float = 5.0,
    name: str = "tasks"
) -> None:
    """
    Cancel a set of tasks gracefully with proper error handling
    
    Args:
        tasks: Set or list of asyncio Tasks to cancel
        timeout: Maximum time to wait for tasks to complete
        name: Name for logging purposes
    """
    if not tasks:
        logger.debug(f"No {name} to cancel")
        return
    
    logger.info(f"Cancelling {len(tasks)} {name}")
    
    # Cancel all tasks
    for task in tasks:
        if not task.done():
            task.cancel()
    
    # Wait for tasks to complete or timeout
    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=timeout
        )
        logger.info(f"All {name} cancelled successfully")
    except asyncio.TimeoutError:
        logger.warning(f"Timeout waiting for {name} to cancel after {timeout}s")
        # Force cancel any remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()
                logger.warning(f"Force cancelled task: {task}")
    except Exception as e:
        logger.error(f"Error cancelling {name}: {e}")


async def cleanup_task_set(task_set: Set[asyncio.Task], name: str = "background tasks") -> None:
    """
    Clean up a task set with proper cancellation and clearing
    
    Args:
        task_set: Set of tasks to clean up
        name: Name for logging purposes
    """
    if task_set:
        await cancel_tasks_gracefully(task_set, name=name)
        task_set.clear()


class TaskManager:
    """
    Context manager for managing async tasks with automatic cleanup
    """
    
    def __init__(self, name: str = "TaskManager"):
        self.name = name
        self.tasks: Set[asyncio.Task] = set()
        self._closed = False
    
    def add_task(self, coro_or_task: Union[asyncio.Task, Any]) -> asyncio.Task:
        """Add a task to be managed"""
        if self._closed:
            raise RuntimeError(f"{self.name} is closed")
        
        if isinstance(coro_or_task, asyncio.Task):
            task = coro_or_task
        else:
            task = asyncio.create_task(coro_or_task)
        
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task
    
    async def cancel_all(self, timeout: float = 5.0) -> None:
        """Cancel all managed tasks"""
        if self.tasks:
            await cancel_tasks_gracefully(self.tasks, timeout, f"{self.name} tasks")
            self.tasks.clear()
        self._closed = True
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cancel_all()
        return False
    
    def __len__(self):
        return len(self.tasks)
    
    @property
    def active_count(self) -> int:
        """Number of active (non-done) tasks"""
        return sum(1 for task in self.tasks if not task.done())