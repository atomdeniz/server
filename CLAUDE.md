# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

Ansible playbook for a self-hosted infrastructure on Ubuntu ARM64 VPS.

## Server Access — ALWAYS Use Ansible (MOST IMPORTANT RULE)

**NEVER use raw `ssh` to run commands on the server. ALWAYS go through Ansible.** Use ad-hoc commands for one-off diagnostics:

```bash
# Run a shell command on the server (becomes root automatically)
ansible server -i inventory.yml -e @custom.yml -e @secret.yml \
  --vault-password-file ~/.vault_pass \
  -m ansible.builtin.shell -a 'docker ps' -b

# Use community.docker.docker_container_exec to run inside a container
ansible server -i inventory.yml -e @custom.yml -e @secret.yml \
  --vault-password-file ~/.vault_pass \
  -m community.docker.docker_container_exec \
  -a 'container=amnezia-wg command="awg show"' -b
```

Why: Ansible enforces consistent become/sudo handling, vault decryption, inventory-driven host resolution, and produces structured/idempotent output. Raw SSH bypasses all of that and creates state drift.

## Security Rules

- **NEVER** read `secret.yml` or `~/.vault_pass` — these contain sensitive credentials and must not be sent to the cloud.
- If playbook output contains secret values, do not display them.
- The vault password must never appear in conversation.

## Security Model

Defense-in-depth is split across two layers that must be kept in sync:

- **Hetzner cloud firewall (external layer, managed in Hetzner console, NOT in this repo):**
  - SSH (`22/tcp`) is IP-allowlisted here — only specific operator IPs can reach the server.
  - This is the authoritative SSH restriction. If the firewall is removed, disabled, or the allowlist is cleared, the server is exposed.

- **Host iptables (internal layer, managed by `roles/system/templates/iptables.conf`):**
  - Intentionally permissive for SSH (`ssh_allow_cidr: 0.0.0.0/0` in `inventory.yml`) because the Hetzner firewall already gates it.
  - Treat this as a fail-open second layer, not a primary defense.

When changing SSH exposure, update **both** layers. If the Hetzner firewall is ever removed, tighten `ssh_allow_cidr` in `inventory.yml` to a real CIDR before redeploying.

### IPv6

IPv6 is disabled at the Hetzner cloud provider layer — the server's Primary
IPv6 has been detached in the console, and all IPv6 sources have been
removed from the cloud firewall rules. As a result:

- No IPv6 traffic is routed to or from the server by Hetzner.
- The VM's OS may still show a stale `inet6 2a01:…` address on `eth0` and a
  v6 link-local default route until the next cloud-init regeneration or
  reboot; this is cosmetic and **not** reachable from the internet.
- Deliberately there is **no `ip6tables` / `ip6tables.conf`** in this repo.
  The `iptables.conf` template covers v4 only. If IPv6 is ever re-attached
  in the Hetzner console, mirror the allowed-ports list to a new
  `ip6tables.conf` drop-in and review `sshd` `AddressFamily` before
  redeploying.

## Running the Playbook

Install dependencies first (once, or when `requirements.yml` changes):

```bash
ansible-galaxy install -r requirements.yml
```

Full deploy:

```bash
ansible-playbook playbook.yml -i inventory.yml -e @custom.yml -e @secret.yml --vault-password-file ~/.vault_pass
```

Deploy specific role(s) by tag:

```bash
ansible-playbook playbook.yml -i inventory.yml -e @custom.yml -e @secret.yml --vault-password-file ~/.vault_pass --tags "traefik,authelia"
```

Lint the project:

```bash
ansible-lint playbook.yml
yamllint .
```

Dry-run (check mode):

```bash
ansible-playbook playbook.yml -i inventory.yml -e @custom.yml -e @secret.yml --vault-password-file ~/.vault_pass --check --tags "<tag>"
```

## Configuration

Before running, two files must exist (both gitignored):

- **`custom.yml`** — copy from `.custom.yml`, fill in `ansible_host`, `root_host`, `username`, SSH key path, email settings, `force_recreate`, and storage config.
- **`secret.yml`** — copy from `.secret.yml`, fill in all secrets. Must be `chmod 600` and encrypted with `ansible-vault`.

`ansible.cfg` sets `roles_path = .ansible/roles`, `collections_path = .ansible/collections`, enables `profile_tasks` callback, YAML output format, SSH connection multiplexing, and disables retry files.

`inventory.yml` derives all service subdomains from `root_host` (e.g., `auth.{{ root_host }}`, `password.{{ root_host }}`). Docker data lives under `docker_dir` (default `/opt/docker`). Storage box mounts go under `storagebox_mount_path` (default `/mnt/storagebox`).

## Architecture

### Role Execution Order

Roles in `playbook.yml` run in this sequence and must be thought of as layers:

1. **Infrastructure base**: `system` → `security` → `dns` → `geerlingguy.docker` → `docker_network` → `docker_proxy`
2. **Security/proxy layer**: `crowdsec` → `traefik` → `redis` → `authelia`
3. **Applications**: all remaining roles (each has its own tag matching its folder name)

External roles (installed to `.ansible/roles/`):

- `geerlingguy.docker`
- `geerlingguy.pip`
- `chriswayg.msmtp-mailer`

External collections (installed to `.ansible/collections/`):

- `community.docker` (>=5.0.0)
- `community.general`
- `community.crypto`
- `ansible.posix`

### Application Roles

All enabled application roles in execution order:

| Role | Tag | Subdomain | Description |
|---|---|---|---|
| `whoami` | whoami | `whoami.{{ root_host }}` | HTTP request debug service |
| `unbound` | unbound | — | Recursive DNS resolver (10.8.4.3) |
| `adguardhome` | adguardhome | `adguard.{{ root_host }}` | DNS ad blocker (10.8.4.2) |
| `amnezia_wg` | amnezia_wg | `vpn.{{ root_host }}` | AmneziaWG VPN |
| `mywebsite` | mywebsite | `www.{{ root_host }}` | Personal website |
| `vaultwarden` | vaultwarden | `password.{{ root_host }}` | Password manager |
| `homepage` | homepage | `home.{{ root_host }}` | Dashboard |
| `grafana` | grafana | `grafana.{{ root_host }}` | Monitoring (Grafana + Prometheus + cAdvisor + Node Exporter) |
| `gatus` | gatus | `uptime.{{ root_host }}` | Uptime monitoring (lightweight) |
| `proxy` | proxy | `proxy.{{ root_host }}` | Xray (VLESS+Vision+Reality, TCP 8443) + Hysteria2 (UDP 443) censorship-resistant proxies |
| `n8n` | n8n | `n8n.{{ root_host }}` | Workflow automation |
| `whatsupdocker` | whatsupdocker | `whatsupdocker.{{ root_host }}` | Docker image update notifier |
| `web_check` | web_check | `web.{{ root_host }}` | Website analysis tool |
| `convertx` | convertx | `convertx.{{ root_host }}` | File converter |
| `storagebox` | storagebox | — | Hetzner Storage Box CIFS mount |
| `immich` | immich | `photos.{{ root_host }}` | Photo management |
| `it_tools` | it_tools | `dev.{{ root_host }}` | Developer utilities |
| `changedetection` | changedetection | `changes.{{ root_host }}` | Website change monitoring |
| `dozzle` | dozzle | `dozzle.{{ root_host }}` | Docker log viewer |
| `postgres` | postgres | — | PostgreSQL with pgvecto.rs (for Immich) |
| `spliit` | spliit | `spliit.{{ root_host }}` | Expense splitting |
| `umami` | umami | `analytics.{{ root_host }}` | Web analytics |
| `pingvin` | pingvin | `share.{{ root_host }}` | File sharing |
| `wallos` | wallos | `wallos.{{ root_host }}` | Subscription tracker |
| `filebrowser` | filebrowser | `files.{{ root_host }}` | Web file manager |
| `ntfy` | ntfy | `ntfy.{{ root_host }}` | Self-hosted push notifications |
| `jellyfin` | jellyfin | `media.{{ root_host }}` | Media server |
| `pr_queue` | pr_queue | `pr.{{ root_host }}` | PR reviewer round-robin queue |
| `backup` | backup | — | Restic backup to Storage Box (daily) |
| `chriswayg.msmtp-mailer` | msmtp | — | System email relay |

### Docker Networking

Five isolated bridge networks are created by the `docker_network` role:

| Network | Subnet | Internal | Purpose |
|---|---|---|---|
| `edge_network` | 10.8.1.0/24 | no | Traefik external entry point |
| `redis_data_network` | 10.8.2.0/24 | yes | Internal Redis |
| `ops_network` | 10.8.3.0/24 | yes | Monitoring (Grafana, Prometheus, cAdvisor) |
| `dns_network` | 10.8.4.0/24 | no | AdGuard (10.8.4.2) + Unbound (10.8.4.3) |
| `app_network` | 10.8.6.0/24 | no | Application services |

Traefik sits on `edge_network` and `app_network`. Most app containers join `app_network`. Security/proxy containers join `edge_network`.

### Traefik Pattern

Every containerized service exposes itself to Traefik via Docker labels in its Compose template. Traefik configuration lives in `roles/traefik/templates/`. Dynamic config files are mounted into the container. The `docker_proxy` role provides a restricted Docker socket proxy that Traefik uses instead of the raw socket.

### Role Structure Convention

Each custom role under `roles/` follows:

```
roles/<name>/
  defaults/main.yml   # version pins, image names, defaults
  tasks/main.yml      # role logic (creates dirs, renders templates, starts containers)
  templates/          # Jinja2 config files / docker-compose.yml.j2
  handlers/           # role-specific restart handlers (if needed)
```

Global handlers (notify targets used across roles) are in `handlers/main.yml`.

### Disabled Roles

`freqtrade` is commented out in `playbook.yml`. Its role folder still exists and can be re-enabled.

## Adding a New Role

1. Create `roles/<name>/` with the standard structure above.
2. Add version pin in `defaults/main.yml`.
3. Add the role to `playbook.yml` with a matching tag.
4. If the service needs a subdomain, add `<name>_host: "<sub>.{{ root_host }}"` to `inventory.yml`.
5. Join the container to the appropriate Docker network(s) via Compose labels.
6. If the service needs secrets, add them to `.secret.yml` (template) and `secret.yml` (actual, vault-encrypted).

### Mandatory Integration Checklist

Every new role with a subdomain **must** also be added to the following:

1. **DNS Registration:**
   - **VPN-only services** (`secure-vpn@file` or `secure-vpn-with-auth@file` middleware) → Add a rewrite entry in `roles/adguardhome/templates/AdGuardHome.yaml` under `rewrites:`.
   - **Public services** (`open-external@file` middleware) → Add a DNS record in `roles/dns/defaults/main.yml` under `dns_records:`.

2. **Gatus Monitoring** → Add an endpoint in `roles/gatus/templates/config.yml.j2` under `endpoints:`. Use internal Docker URL (e.g., `http://<container>:<port>`) when possible.

3. **Homepage Dashboard** → Add a service entry in `roles/homepage/templates/services.yaml` under the appropriate category.

4. **CLAUDE.md Application Table** → Add the role to the Application Roles table above.

## Post-Install Steps

After first CrowdSec deploy, enroll the agent on the server:

```bash
docker exec crowdsec cscli console enroll -e context <key>
```

## Seedbox (Ultra.cc, external)

An Ultra.cc slot (host + user configured in `custom.yml` as `seedbox_host`
/ `seedbox_user`) runs the download side: qBittorrent +
Sonarr/Radarr/Prowlarr/Bazarr. A cron-driven rclone job on the slot
one-way-syncs `~/media/{Movies,TV Shows,Anime}` to the Hetzner Storage
Box, which the VPS Jellyfin reads over CIFS.

The slot is **not managed by ansible** (shared hosting, no root). The
sync script's canonical source lives in `scripts/seedbox/` in this repo;
it is scp'd to the slot manually after changes. Never edit the copy on
the slot in place.

### Ultra.cc Fair Usage Policy (non-negotiable)

The slot was suspended on 2026-04-23 for running 11 parallel rclones
saturating the shared node. Any rclone automation on this slot MUST keep
all three:

- `flock -n /tmp/rclone-sync.lock` — inside the script (cron must NOT wrap with the same lock file; that deadlocks the script's own acquire)
- `--bwlimit=30M` — ceiling specified by Ultra.cc, do not raise
- `--transfers=2` — do not raise

PID-based locking is banned; use `flock` only.

### media_cleanup role

`roles/media_cleanup/` queries the Jellyfin API for watched content,
derives the corresponding paths, and deletes them **on the seedbox only**
via SSH. `rclone sync` propagates the deletion to the Storage Box on the
next run. The role never touches the Storage Box mount directly — doing
so would race with an in-flight sync.

### Redeploying the sync script

See `scripts/seedbox/README.md` for scp + cron install steps.

## Other Playbooks

- **`migrate-docker-dir.yml`** — Utility playbook for migrating the Docker data directory to a new location.
