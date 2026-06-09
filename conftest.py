"""Put the project root on sys.path so tests/ can `import bot`.

The hashtag tests live in tests/ but import find_hashtags from bot.py in the
project root. This makes that import work no matter where pytest is invoked.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
