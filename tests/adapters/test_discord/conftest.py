"""Configure pytest for Discord adapter tests."""
import sys
import os

# Fix the discord import issue by ensuring discord.py is loaded first
# before Python tries to import from the local discord directory

# Get the site-packages discord module path
import importlib.util
discord_spec = importlib.util.find_spec("discord")
if discord_spec and discord_spec.origin:
    # Load discord.py from site-packages
    discord_module = importlib.util.module_from_spec(discord_spec)
    sys.modules['discord'] = discord_module
    discord_spec.loader.exec_module(discord_module)