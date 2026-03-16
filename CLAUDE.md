# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

Ansible playbook for a self-hosted infrastructure on Ubuntu ARM64 VPS.

## Security Rules

- **NEVER** read `secret.yml` or `~/.vault_pass` — these contain sensitive credentials and must not be sent to the cloud.
- If playbook output contains secret values, do not display them.
- The vault password must never appear in conversation.

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
| `proxy` | proxy | `tgo.{{ root_host }}`, `v2ray.{{ root_host }}` | Caddy + Trojan + V2Fly proxy |
| `n8n` | n8n | `n8n.{{ root_host }}` | Workflow automation |
| `whatsupdocker` | whatsupdocker | `whatsupdocker.{{ root_host }}` | Docker image update notifier |
| `web_check` | web_check | `web.{{ root_host }}` | Website analysis tool |
| `convertx` | convertx | `convertx.{{ root_host }}` | File converter |
| `storagebox` | storagebox | — | Hetzner Storage Box CIFS mount |
| `immich` | immich | `photos.{{ root_host }}` | Photo management |
| `openclaw` | openclaw | `openclaw.{{ root_host }}` | Telegram bot service |
| `it_tools` | it_tools | `dev.{{ root_host }}` | Developer utilities |
| `supabase` | supabase | `supabase.{{ root_host }}`, `supabase-api.{{ root_host }}` | Backend-as-a-Service |
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

### Supabase Version Management

Supabase component versions are **not** pinned in Ansible defaults. They are managed by the official Supabase `docker-compose.yml` in `{{ supabase_data_dir }}` with `pull: always`. The override compose file (`docker-compose.override.yml.j2`) only adds Traefik labels and network configuration.

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

## Other Playbooks

- **`migrate-docker-dir.yml`** — Utility playbook for migrating the Docker data directory to a new location.
