# Seedbox scripts

Canonical source for the Ultra.cc slot's rclone sync automation. The slot
itself is **not managed by ansible** (shared hosting, no root) — these
files are scp'd to the slot manually after changes here.

Keep this directory as the single source of truth. Do not edit the copy
on the slot in place.

## Files

- `sync-media.sh` — runs on the slot every 30 minutes via cron
- `sync-media.env.example` — template for optional ntfy credentials

## Deploy

Set `SEEDBOX_USER` / `SEEDBOX_HOST` (matching `seedbox_user` / `seedbox_host`
in `custom.yml`) in your shell, then from this repo:

```bash
# Script
scp scripts/seedbox/sync-media.sh $SEEDBOX_USER@$SEEDBOX_HOST:~/bin/sync-media.sh
ssh $SEEDBOX_USER@$SEEDBOX_HOST 'chmod +x ~/bin/sync-media.sh'

# Optional: ntfy failure notifications
scp scripts/seedbox/sync-media.env.example $SEEDBOX_USER@$SEEDBOX_HOST:~/.config/sync-media.env
ssh $SEEDBOX_USER@$SEEDBOX_HOST 'chmod 600 ~/.config/sync-media.env'
# Then edit the remote file to set NTFY_URL and NTFY_TOKEN.
```

On the slot, install the cron entry (`crontab -e`):

```
*/30 * * * * $HOME/bin/sync-media.sh
```

Do not wrap the cron invocation in an outer `flock` — the script
already `flock`s `/tmp/rclone-sync.lock` internally, and wrapping cron
with the same lock file causes the script's own acquire to fail
immediately with "already running, skip".

## Ultra.cc Fair Usage Policy (2026-04-23 incident)

The slot was suspended after 11 parallel rclones accumulated over 26 days
and saturated the shared node's disk I/O. Any rclone automation on this
slot MUST preserve all three guarantees:

- `flock -n /tmp/rclone-sync.lock` at script entry (the script handles this)
- `--bwlimit=30M` — never raise
- `--transfers=2` — never raise

Do not revert to a PID-based lock. PID reuse defeated the original script.

## Logs

`~/.local/log/sync-media.log` on the slot (appended; rotate manually if
it grows, no service-level logrotate available).
