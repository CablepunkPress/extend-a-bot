# Extend-A-Bot

Curated tool groups for [Bountiful](https://github.com/CablepunkPress/bountiful)'s agents, which run on [Basic Bot](https://github.com/CablepunkPress/basic-bot), its agent engine.

Each group plugs into Basic Bot's tools jack through the `basic_bot.tool_box` entry point, and is read in place, so every agent uses the version installed with Bountiful. An agent turns a group on with a settings file in its own `tools/` folder, and keeps its keys in the system keyring under its id:

    bountiful tools                    the groups available, and which agents use each
    bountiful tools jeden              jeden's groups, and what each still needs
    bountiful add jeden wikipedia      turn a group on for jeden
    bountiful remove jeden wikipedia   turn it off; its settings are kept
    bountiful keys jeden brave         store jeden's keys for a group

## The groups

- **wikipedia**: search Wikipedia and read its articles. No key needed.
- **brave**: search the web with Brave Search. Needs a Brave Search API key, on a plan that charges per search after a monthly free credit.
- **github**: read and propose changes in GitHub repositories through a GitHub App you create.

Every group says, when it's turned on, what it sends beyond your machine.
