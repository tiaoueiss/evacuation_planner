"""
Entry point for the Building H Alien Evacuation Planner.
Run from the project root with:
    python main.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from gui import main

if __name__ == "__main__":
    main()
