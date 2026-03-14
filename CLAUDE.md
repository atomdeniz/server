# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

Ansible playbook for a self-hosted infrastructure on Ubuntu ARM64 VPS. Execution is primarily done via **Semaphore UI**, not the CLI directly.

## Running the Playbook

Install dependencies first (once, or when `requirements.yml` changes):

```bash
ansible-galaxy install -r requirements.yml
```

Full deploy:

```bash
ansible-playbook playbook.yml -i inventory.yml
```

Deploy specific role(s) by tag:

```bash
ansible-playbook playbook.yml -i inventory.yml --tags "traefik,authelia"
```

Lint the project:

```bash
ansible-lint playbook.yml
yamllint .
```

Dry-run (check mode):

```bash
ansible-playbook playbook.yml -i inventory.yml --check --tags "<tag>"
```

## Configuration

Before running, two files must exist (both gitignored):

- **`custom.yml`** — copy from `.custom.yml`, fill in `ansible_host`, `root_host`, `username`, SSH key path, email settings, `force_recreate`, Immich and Seafile storage config.
- **`secret.yml`** — copy from `.secret.yml`, fill in all secrets. Must be `chmod 600`. Includes credentials for: email, Cloudflare, Traefik, CrowdSec, Authelia, AdGuard, Grafana, Amnezia WG, Trojan/V2Ray, Telegram, Freqtrade, Immich, Seafile, and Supabase.

`ansible.cfg` sets `roles_path = .ansible/roles`, `collections_path = .ansible/collections`, enables `profile_tasks` callback, and configures SSH connection multiplexing.

`inventory.yml` derives all service subdomains from `root_host` (e.g., `auth.{{ root_host }}`, `password.{{ root_host }}`). Docker data lives under `docker_dir` (default `/opt/docker`). Storage box mounts go under `storagebox_mount_path` (default `/mnt/storagebox`).

## Architecture

### Role Execution Order

Roles in `playbook.yml` run in this sequence and must be thought of as layers:

1. **Infrastructure base**: `system` → `security` → `dns` → `geerlingguy.docker` → `docker_network` → `docker_proxy`
2. **Security/proxy layer**: `crowdsec` → `traefik` → `authelia`
3. **Applications**: all remaining roles (each has its own tag matching its folder name)

External roles: `geerlingguy.docker`, `geerlingguy.pip`, `chriswayg.msmtp-mailer` (installed to `.ansible/roles/`).

External collections: `community.docker` (>=5.0.0), `community.general`, `community.crypto`, `ansible.posix` (installed to `.ansible/collections/`).

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
| `uptime_kuma` | uptime_kuma | `uptime.{{ root_host }}` | Uptime monitoring |
| `proxy` | proxy | `tgo.{{ root_host }}`, `v2ray.{{ root_host }}` | Caddy + Trojan + V2Fly proxy |
| `n8n` | n8n | `n8n.{{ root_host }}` | Workflow automation |
| `whatsupdocker` | whatsupdocker | `whatsupdocker.{{ root_host }}` | Docker image update notifier |
| `web_check` | web_check | `web.{{ root_host }}` | Website analysis tool |
| `convertx` | convertx | `convertx.{{ root_host }}` | File converter |
| `postgres` | postgres | — | PostgreSQL with pgvecto.rs (for Immich) |
| `immich` | immich | `photos.{{ root_host }}` | Photo management |
| `it_tools` | it_tools | `dev.{{ root_host }}` | Developer utilities |
| `seafile` | seafile | `drive.{{ root_host }}` | File sync & share |
| `supabase` | supabase | `supabase.{{ root_host }}`, `supabase-api.{{ root_host }}` | Backend-as-a-Service |
| `chriswayg.msmtp-mailer` | msmtp | — | System email relay |

### Docker Networking

Six isolated bridge networks are created by `docker_network` role:

| Network | Subnet | Purpose |
|---|---|---|
| `edge_network` | 10.8.1.0/24 | Traefik external entry point |
| `redis_data_network` | 10.8.2.0/24 | Internal Redis |
| `ops_network` | 10.8.3.0/24 | Monitoring (Grafana, Prometheus, cAdvisor) |
| `dns_network` | 10.8.4.0/24 | AdGuard (10.8.4.2) + Unbound (10.8.4.3) |
| `app_network` | 10.8.6.0/24 | Application services |
| `postgres_data_network` | 10.8.7.0/24 | PostgreSQL (used by Immich) |

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

`ollama`, `freqtrade`, and `openclaw` are commented out in `playbook.yml`. Their role folders still exist and can be re-enabled.

### Supabase Version Management

Supabase component versions (db, auth, rest, storage, edge-functions, meta, pooler, analytics, realtime, vector) are **not** pinned in Ansible defaults. They are managed by the official Supabase `docker-compose.yml` in `{{ supabase_data_dir }}` with `pull: always`. The override compose file (`docker-compose.override.yml.j2`) only adds Traefik labels and network configuration.

## Adding a New Role

1. Create `roles/<name>/` with the standard structure above.
2. Add version pin in `defaults/main.yml`.
3. Add the role to `playbook.yml` with a matching tag.
4. If the service needs a subdomain, add `<name>_host: "<sub>.{{ root_host }}"` to `inventory.yml`.
5. Join the container to the appropriate Docker network(s) via Compose labels.

## Post-Install Steps

After first CrowdSec deploy, enroll the agent on the server:

```bash
docker exec crowdsec cscli console enroll -e context <key>
```

Traefik bouncer and firewall bouncer are automatically registered and configured by the `crowdsec` Ansible role.

Firewall rules: allow 80/tcp, 443/tcp, 51820/udp from any; restrict 22/tcp to your IP.

## Other Playbooks

- **`migrate-docker-dir.yml`** — Utility playbook for migrating the Docker data directory to a new location.
