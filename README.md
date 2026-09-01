# Pelican + Vanilla Bedrock + discord.py Status Widget

A Discord bot that maintains one live-updating Embed for a Pelican-managed Vanilla Minecraft Bedrock server.

## Included

- Pelican Client API server/resource monitoring
- Vanilla Bedrock UDP status monitoring
- CPU, memory and disk usage with limits and percentages when available
- Optional electricity and domain maintenance-cost estimates
- Bedrock online/offline state
- Bedrock version and player count
- MOTD in the Embed title
- Player names from the Wings console WebSocket `list` command
- Administrator-managed custom emoji displayed beside online player names
- Server console logs (latest five lines, excluding `list` output)
- Ko-fi support link
- Administrator-managed donor message board
- Discord messages forwarded to Minecraft with the Bedrock `say` command
- Bot presence showing the current Minecraft player count
- Optional mention-triggered AI chat threads backed by a LAN llama.cpp server
- Optional Start / Restart / Stop buttons
- Slash command or widget reaction-created temporary VC + listener text-channel pairs
- One Discord message that is edited every N seconds
- Docker Compose deployment
- systemd deployment

### Player names

The standard Bedrock status protocol provides the player count, but `mcstatus` does not expose player names. This project obtains names through the Pelican/Wings console WebSocket and periodically runs the Bedrock `list` command.

The parser supports one-name-per-line, comma-separated names, and `name, xuid: ...` lines. The `list` result is treated as the authoritative player snapshot; join/leave messages are only supplemental updates.

## Requirements

- Pelican Panel + Wings
- Vanilla Bedrock server
- Python 3.12+
- Discord bot
- Pelican Client API token

Pelican documents its Client and Application APIs under `/docs/api` on the Panel.

## Configuration

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```dotenv
DISCORD_TOKEN=your_bot_token
DISCORD_GUILD_ID=123456789012345678
DISCORD_CHANNEL_ID=123456789012345678
# Optional; defaults to DISCORD_CHANNEL_ID
DISCORD_TO_MINECRAFT_CHANNEL_ID=123456789012345678

PELICAN_BASE_URL=https://panel.example.com
PELICAN_SERVER_ID=short-server-identifier
PELICAN_CLIENT_API_TOKEN=ptlc_xxxxxxxxx

BEDROCK_HOST=192.168.1.50
BEDROCK_PORT=19132

UPDATE_INTERVAL_SECONDS=15
PRESENCE_ENABLED=true
PUBLIC_ADDRESS=example.com:19132
WEBSITE_URL=https://example.com/

# Optional maintenance-cost estimate (power metric, electricity, and domain)
VICTORIA_METRICS_URL=https://metrics.example.com/api/v1/query
VICTORIA_METRICS_QUERY=ohm_cpu_watts{instance="server",sensor="CPU Package"}
POWER_AVERAGE_WINDOW=7d
ELECTRICITY_YEN_PER_KWH=32.6
DOMAIN_ANNUAL_COST_YEN=0
HDD_COUNT=1
HDD_WATTS_EACH=8
SSD_COUNT=2
SSD_WATTS_EACH=3
OTHER_HARDWARE_WATTS=30

# Optional LAN llama.cpp chat
LLM_ENABLED=false
LLM_BASE_URL=http://192.168.1.50:8080/v1
LLM_MODEL=
LLM_ALLOWED_CHANNEL_ID=123456789012345678
LLM_SYSTEM_PROMPT=You are a friendly community chat bot.
LLM_TIMEOUT_SECONDS=120
LLM_MAX_HISTORY_MESSAGES=20
LLM_MAX_CONCURRENT_REQUESTS=1
LLM_MAX_TOKENS=512
LLM_DATABASE_FILE=data/llm_chat.sqlite3

KO_FI_URL=https://ko-fi.com/yourname
KO_FI_GOAL_TITLE=サポート目標
KO_FI_GOAL_PERCENTAGE=0
KO_FI_GOAL_CURRENT=¥0
KO_FI_GOAL_TARGET=¥0
DONATIONS_FILE=data/donations.json

CONSOLE_ENABLED=true
CONSOLE_LOG_LINES=5
PLAYER_LIST_ENABLED=true
PLAYER_LIST_COMMAND_INTERVAL_SECONDS=30
MAX_PLAYERS_DISPLAYED=20
PLAYER_EMOJI_FILE=data/player_emojis.json

# Optional dynamic voice channels
DYNAMIC_VOICE_CATEGORY_ID=123456789012345678
DYNAMIC_VOICE_EMPTY_MINUTES=10
DYNAMIC_VOICE_DEFAULT_LIMIT=0
DYNAMIC_VOICE_FILE=data/dynamic_voice.json
DYNAMIC_VOICE_REACTIONS_FILE=data/dynamic_voice_reactions.json
```

The bot creates the widget message automatically if `DISCORD_MESSAGE_ID` is empty.
When `WEBSITE_URL` is set, the Embed author links to that website.
The monthly electricity estimate uses the average CPU power over
`POWER_AVERAGE_WINDOW`, adds the configured storage and other hardware estimates,
and assumes that total remains constant for 24 hours a day over 30 days.

Use `/help` in Discord to display an ephemeral overview of the bot's features,
general commands, dynamic voice controls, and administrator commands.

When `PRESENCE_ENABLED=true`, the bot activity shows the current player count,
for example `Minecraft｜2/20人が参加中`. The presence is updated only when the
displayed value changes.

The Ko-fi Goal shown in the support field is read directly from the following
environment variables. The bot does not access or scrape Ko-fi.

```dotenv
KO_FI_GOAL_TITLE=サポート目標
KO_FI_GOAL_PERCENTAGE=0
KO_FI_GOAL_CURRENT=¥0
KO_FI_GOAL_TARGET=¥0
```

## Discord to Minecraft chat

Messages posted in `DISCORD_TO_MINECRAFT_CHANNEL_ID` are forwarded to the
Bedrock server as:

```text
(#チャンネル名) <表示名> メッセージ
```

Discord custom emojis whose names start with `mc_` are converted to Bedrock
emoji shortcodes. For example, `mc_shank` becomes `:shank:`. Both static and
animated Discord emoji formats are supported.

The setting defaults to `DISCORD_CHANNEL_ID`. Direct messages, bot messages,
empty messages, and messages from another guild are ignored. This uses the
existing Wings WebSocket connection, so `CONSOLE_ENABLED=true` is required.
Enable the **Message Content Intent** for the bot in the Discord Developer
Portal, because Discord otherwise does not provide message text to the bot.

## Player custom emoji

Administrators and roles listed in `CONTROL_ROLE_IDS` can associate a Minecraft
player name with a Discord custom emoji:

```text
/player_emoji_add player:PlayerName emoji:<:member:123456789012345678>
/player_emoji_remove player:PlayerName
/player_emoji_list
```

Registered emoji are shown to the left of matching online player names. Player
name matching is case-insensitive, and mappings are stored in
`PLAYER_EMOJI_FILE` (default: `data/player_emojis.json`).

## Pelican token

Use a dedicated Pelican account/API key for the bot.

The monitoring functionality needs access to the target server and its resources. Optional control buttons need power permission. Keep the token secret.

## Discord permissions

The bot needs at least:

- View Channel
- Send Messages
- Embed Links
- Read Message History

The optional AI chat feature also needs **Create Public Threads** and
**Send Messages in Threads**.

## LAN llama.cpp AI chat

Set `LLM_ENABLED=true` and mention the bot in `LLM_ALLOWED_CHANNEL_ID` to
create a public AI chat thread. Messages posted in that thread are sent to the
OpenAI-compatible endpoint at `/v1/chat/completions`. Replying to a bot message
in the configured channel also starts a thread. Threads, messages, user settings,
and long-term memories are stored in SQLite at `LLM_DATABASE_FILE`, so existing
AI threads continue to work after a bot restart. Up to
`LLM_MAX_HISTORY_MESSAGES` recent messages are sent with each request.

The bot registers these AI commands when the feature is enabled:

```text
/ai_reset
/ai_memory
/ai_memory content:紅茶が好き
/ai_memory enabled:false
/ai_forget memory_id:1
/ai_forget
```

`/ai_reset` clears the current thread's short-term conversation history. `/ai_memory`
lists or adds the invoking user's long-term memories and can enable or disable
their use. `/ai_forget` deletes one memory; omitting `memory_id` deletes all memories
for that user. These responses are private except for `/ai_reset`.

Run llama.cpp so the Pelican container can reach it over the LAN, for example:

```bash
llama-server -m /path/to/model.gguf --host 0.0.0.0 --port 8080 -c 8192 -np 2
```

Use the LLM host's LAN address in `LLM_BASE_URL`, not `localhost`, when
the bot runs in a separate container. Do not expose the llama.cpp port to the
Internet; restrict it to trusted LAN hosts with a firewall.

The optional dynamic voice feature also needs **Manage Channels**, **Connect**,
and **Manage Messages**. Manage Messages lets the bot remove a user's `🔊`
reaction so the same person can use it again.

## Dynamic voice channels

Set `DYNAMIC_VOICE_CATEGORY_ID` to enable this feature. Leaving it empty keeps
it disabled. The bot adds a `🔊` reaction to the fixed widget Embed and also
registers the following guild command:

```text
/vc_create
/vc_create limit:5
/vc_create limit:5 name:雑談
```

`limit` accepts 0–99; 0 means unlimited. When omitted, it uses
`DYNAMIC_VOICE_DEFAULT_LIMIT`. The command and reaction create a normal voice
channel plus a matching writable `｜聞き専` text channel. A user who is already
connected to any voice channel cannot create another set.

When the voice channel remains empty for `DYNAMIC_VOICE_EMPTY_MINUTES` (10 by
default), both the voice and text channels are deleted. Managed channel IDs are saved in
`DYNAMIC_VOICE_FILE`, so cleanup continues after a bot restart. The bot cannot
move a disconnected user into a voice channel; the creator joins the new
channel manually.

The listener text channel contains an expiration status message. Discord's
relative timestamp automatically displays the remaining time without repeated
API updates. It changes to a timer-stopped message while the VC is occupied and
starts a new countdown when the VC becomes empty again.

Administrators and members with a role in `CONTROL_ROLE_IDS` can associate
additional Unicode or custom emoji reactions with fixed channel names:

```text
/vc_reaction_add emoji:🎮 channel_name:ゲーム部屋
/vc_reaction_add emoji:<:minecraft:123456789012345678> channel_name:Minecraft
/vc_reaction_remove emoji:🎮
/vc_reaction_list
```

The bot adds registered emoji to the fixed widget message. Reacting creates a
VC using the associated name and its matching listener text channel. These
mappings are persisted in `DYNAMIC_VOICE_REACTIONS_FILE`.

## Run

```bash
source .venv/bin/activate
python -m app
```

## Docker

```bash
cp .env.example .env
# edit .env
docker compose up -d --build
docker compose logs -f
```

## systemd

Copy the project to `/opt/pelican-bedrock-discord-widget`, create a `.venv`, install requirements and `.env`, then:

```bash
sudo cp deploy/pelican-bedrock-widget.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pelican-bedrock-widget
journalctl -u pelican-bedrock-widget -f
```

Edit the service paths/user if necessary.

## Optional controls

Disabled by default.

```dotenv
ENABLE_CONTROL_BUTTONS=true
CONTROL_ROLE_IDS=123456789012345678,987654321098765432
```

Only members having one of those Discord roles can use the buttons.

## Donation message board

The Ko-fi API is not required. Administrators, or members with a role listed
in `CONTROL_ROLE_IDS`, can manage donor messages with these Discord slash
commands:

```text
/donation_add donor:名前 message:メッセージ
/donation_remove item_id:1
/donation_list
/donation_clear
```

Messages are stored in `data/donations.json`, and the latest five entries are
shown at the bottom of the widget. Keep the `data/` directory outside Git.

## Playtime ranking

The bot records online time from Wings join/leave events and periodic `list`
results. It keeps both a resettable period ranking and a permanent lifetime
ranking in `PLAYTIME_FILE` (default: `data/playtime.json`) without additional
dependencies. Existing data is migrated into both counters automatically.

```text
/playtime player:名前
/playtime_ranking
/playtime_reset
```

`/playtime` and `/playtime_ranking` show both period and lifetime totals.
`/playtime_reset` is restricted to Discord administrators and roles listed in
`CONTROL_ROLE_IDS`; it resets only the period ranking and never the lifetime
ranking.

Set `PLAYTIME_RESET_CRON` to a standard five-field cron expression to reset
the ranking automatically. The default example resets at 00:00 on the first
day of each month in the server's local timezone:

```dotenv
PLAYTIME_RESET_CRON=0 0 1 * *
```

Leave it empty to disable automatic resets. Cron also resets only the period
ranking. The Embed shows only the period ranking together with its start date
and next scheduled reset date/time. The lifetime ranking remains available
through commands and permanently accumulated.

## API routes used

The code uses the Pelican/Pterodactyl-compatible Client API:

```text
GET  /api/client/servers/{identifier}
GET  /api/client/servers/{identifier}/resources
POST /api/client/servers/{identifier}/power
```

Pelican is beta software, so if your installed version differs, `app/pelican.py` is the only module that normally needs API changes.

## Project structure

```text
app/
  __main__.py
  bot.py
  config.py
  donations.py
  models.py
  pelican.py
  bedrock.py
  embed.py
  views.py
  widget.py
  wings_ws.py
deploy/
  pelican-bedrock-widget.service
tests/
  test_formatting.py
.env.example
Dockerfile
compose.yml
requirements.txt
pyproject.toml
```


## Wings WebSocket console integration

This version connects directly to the Wings WebSocket using the normal Pelican/Pterodactyl-compatible console flow: obtain temporary WebSocket credentials from the Panel, authenticate to Wings, request the recent console buffer, then consume live `console output` events. The bot also sends the Vanilla Bedrock `list` command periodically and tracks join/leave console lines.

The Panel API key is only used against the Panel to obtain the temporary WebSocket JWT; it is not used as the WebSocket authentication token.
