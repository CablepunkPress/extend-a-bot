"""extend-a-bot: curated tool groups for Bountiful's agents.

The groups live in tool_box/, one folder each, read in place by
basic-bot through the basic_bot.tool_box entry point. An agent turns a
group on with a settings file in its own tools/ folder, written by
addons.add(). Each agent's keys are kept in the system keyring under
its id (keys.py).
"""

from pathlib import Path

__version__ = "0.3.0.dev0"

# The folder of tool groups, offered to basic-bot's tools jack
TOOL_BOX = Path(__file__).parent / "tool_box"
