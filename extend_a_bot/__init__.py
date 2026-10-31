"""extend-a-bot: plugin tools for Bountiful agents.

The groups live in tool_box/, one folder each, read in place by
basic-bot through the basic_bot.tool_box entry point. An agent adds a
group by naming it, with its settings, in its agent.json, which
plugins.add() writes. Each agent's keys are kept in the system keyring
under its id (keys.py).
"""

from pathlib import Path

__version__ = "0.3.0.dev0"

# The folder of tool groups, offered to basic-bot's tools jack
TOOL_BOX = Path(__file__).parent / "tool_box"
