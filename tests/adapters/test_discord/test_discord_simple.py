"""Simple test to check Discord imports."""
import pytest


def test_discord_import():
    """Test that discord can be imported."""
    import discord
    # discord.py doesn't expose __version__ directly
    assert hasattr(discord, 'Client')
    

def test_discord_adapter_exists():
    """Test that DiscordAdapter class exists."""
    # Import only the specific module, not through __init__
    import sys
    import os
    
    # Add the project root to path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Now import directly
    from ciris_engine.logic.adapters.discord.discord_adapter import DiscordAdapter
    
    assert DiscordAdapter is not None