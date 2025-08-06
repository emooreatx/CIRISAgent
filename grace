#!/usr/bin/env python3
"""
Grace - quick access script.
Put this in your PATH or alias it.
"""

import os
import sys

# Add tools directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.grace.__main__ import main

if __name__ == "__main__":
    main()
