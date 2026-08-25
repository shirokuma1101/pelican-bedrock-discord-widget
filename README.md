# Pelican + Vanilla Bedrock + discord.py Status Widget

A Discord bot that maintains one live-updating Embed for a Pelican-managed Vanilla Minecraft Bedrock server.

## Included

- Pelican Client API server/resource monitoring
- Vanilla Bedrock UDP status monitoring
- CPU, memory and disk usage with limits and percentages when available
- Bedrock online/offline state
- Bedrock version and player count
- MOTD in the Embed title
- Player names from the Wings console WebSocket `list` command
- Server console logs (latest five lines, excluding `list` output)
- Ko-fi support link
- Administrator-managed donor message board
- Discord messages forwarded to Minecraft with the Bedrock `say` command
- Bot presence showing the current Minecraft player count
- Optional Start / Restart / Stop buttons
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
```

The bot creates the widget message automatically if `DISCORD_MESSAGE_ID` is empty.

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

## Pelican token

Use a dedicated Pelican account/API key for the bot.

The monitoring functionality needs access to the target server and its resources. Optional control buttons need power permission. Keep the token secret.

## Discord permissions

The bot needs at least:

- View Channel
- Send Messages
- Embed Links
- Read Message History

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

The bot records cumulative online time from Wings join/leave events and
periodic `list` results. Data is stored in `PLAYTIME_FILE` (default:
`data/playtime.json`) without additional dependencies.

```text
/playtime player:名前
/playtime_ranking
/playtime_reset
```

`/playtime_reset` is restricted to Discord administrators and roles listed in
`CONTROL_ROLE_IDS`.

Set `PLAYTIME_RESET_CRON` to a standard five-field cron expression to reset
the ranking automatically. The default example resets at 00:00 on the first
day of each month in the server's local timezone:

```dotenv
PLAYTIME_RESET_CRON=0 0 1 * *
```

Leave it empty to disable automatic resets. The current statistics start date
is shown in the playtime ranking field of the Embed.

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
