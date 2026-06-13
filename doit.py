#!/usr/bin/env python3
"""
DoIt compatibility entrypoint.
"""
import sys

# Ensure package can be imported if running directly
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from doit.main import main

if __name__ == "__main__":
    sys.exit(main())
