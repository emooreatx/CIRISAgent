#!/usr/bin/env python3
"""
Setup script for CIRISManager.
This is a lightweight installation that only installs the manager component.
"""

from setuptools import setup, find_packages

setup(
    name="ciris-manager",
    version="0.1.0",
    description="CIRIS Container Manager - Lightweight systemd service for agent lifecycle",
    author="CIRIS AI",
    packages=find_packages(include=["ciris_manager", "ciris_manager.*"]),
    install_requires=[
        "pyyaml>=6.0",
        "asyncio",
        "aiofiles>=23.0",
    ],
    entry_points={
        "console_scripts": [
            "ciris-manager=ciris_manager.cli:main",
        ],
    },
    python_requires=">=3.8",
)