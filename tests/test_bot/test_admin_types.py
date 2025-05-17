"""Test type annotations in admin cog"""
import ast
from pathlib import Path


def test_admin_type_annotations():
    """Test that admin cog has proper type annotations by checking the source"""
    # Read the admin.py file
    admin_file = Path(__file__).parent.parent.parent / "src" / "bot" / "cogs" / "admin.py"
    with open(admin_file, 'r') as f:
        content = f.read()
    
    # Check for proper imports
    assert "from typing import Any, Dict, List, Optional, Protocol, Tuple" in content
    assert "import psutil" in content
    assert "from discord.ext.commands import Bot, Cog, Context" in content
    
    # Check Admin class definition
    assert "class Admin(Cog):" in content
    assert "def __init__(self, bot: RobottyBot) -> None:" in content
    
    # Check method signatures
    method_signatures = [
        "async def reload(self, ctx: Context, extension: Optional[str] = None) -> None:",
        "async def shutdown(self, ctx: Context) -> None:",
        "async def set_prefix(self, ctx: Context, new_prefix: str) -> None:",
        "async def status(self, ctx: Context) -> None:",
        "async def clear_cache(self, ctx: Context) -> None:",
    ]
    
    for signature in method_signatures:
        assert signature in content, f"Method signature not found: {signature}"
    
    # Check setup function
    assert "async def setup(bot: RobottyBot) -> None:" in content
    
    # Check type annotations for variables
    assert "reloaded: List[str] = []" in content
    assert "failed: List[Tuple[str, str]] = []" in content
    assert "embed: Embed = create_embed" in content
    assert "failed_text: str = " in content
    assert "platform_text: str = " in content
    assert "memory_mb: float = " in content
    
    # Check Protocol usage
    assert "class PlatformRegistry(Protocol):" in content
    assert "class RobottyBot(Bot):" in content
    
    print("All type annotation checks passed!")


if __name__ == "__main__":
    test_admin_type_annotations()