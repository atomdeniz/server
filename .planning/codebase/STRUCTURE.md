# Codebase Structure

**Analysis Date:** 2026-03-22

## Directory Layout

```
/Users/deniz/repos/personal/server/
├── playbook.yml                  # Main Ansible playbook entry point
├── inventory.yml                 # Host and variables inventory
├── custom.yml                    # User-provided deployment config (gitignored)
├── secret.yml                    # Vault-encrypted secrets (gitignored)
├── requirements.yml              # External roles and collections dependencies
├── ansible.cfg                   # Ansible configuration
├── handlers/                     # Global notification handlers
│   └── main.yml                  # Container restart handlers (notify targets)
├── roles/                        # Ansible roles organized by function
│   ├── system/                   # System setup: packages, updates, swap, firewall
│   ├── security/                 # AppArmor, SSH PAM security
│   ├── dns/                      # Cloudflare DNS record management
│   ├── docker_network/           # Create isolated Docker bridge networks
│   ├── docker_proxy/             # Restricted Docker socket proxy for Traefik
│   ├── crowdsec/                 # WAF/IDS security service
│   ├── traefik/                  # Reverse proxy and load balancer
│   ├── redis/                    # Session storage cache
│   ├── authelia/                 # SSO and 2FA authentication
│   ├── geerlingguy.docker/       # External: Docker installation role
│   ├── geerlingguy.pip/          # External: Python pip installation role
│   ├── chriswayg.msmtp-mailer/   # External: Email relay role
│   │
│   ├── [APPLICATION ROLES - in execution order]
│   ├── whoami/                   # Debug HTTP service
│   ├── unbound/                  # Recursive DNS resolver
│   ├── adguardhome/              # DNS ad blocker
│   ├── amnezia_wg/               # WireGuard VPN
│   ├── mywebsite/                # Personal website
│   ├── vaultwarden/              # Password manager
│   ├── homepage/                 # Dashboard
│   ├── grafana/                  # Monitoring frontend
│   ├── gatus/                    # Uptime monitoring
│   ├── proxy/                    # Caddy + Trojan + V2Fly proxy
│   ├── n8n/                      # Workflow automation
│   ├── diun/                     # Docker image update notifier
│   ├── web_check/                # Website analysis
│   ├── convertx/                 # File converter
│   ├── storagebox/               # Hetzner Storage Box CIFS mount
│   ├── immich/                   # Photo management
│   ├── openclaw/                 # Telegram bot
│   ├── it_tools/                 # Developer utilities
│   ├── supabase/                 # Backend-as-a-Service
│   ├── changedetection/          # Website change monitor
│   ├── dozzle/                   # Docker log viewer
│   ├── postgres/                 # PostgreSQL database
│   ├── spliit/                   # Expense splitter
│   ├── umami/                    # Web analytics
│   ├── pingvin/                  # File sharing
│   ├── wallos/                   # Subscription tracker
│   ├── filebrowser/              # Web file manager
│   ├── ntfy/                     # Push notification server
│   ├── jellyfin/                 # Media server
│   ├── media_cleanup/            # Cleanup utility (disabled)
│   ├── freqtrade/                # Crypto trading bot (disabled)
│   │
│   └── backup/                   # Restic backup to Storage Box
│
├── .planning/
│   └── codebase/                 # GSD codebase analysis documents
│       ├── ARCHITECTURE.md
│       └── STRUCTURE.md
├── .ansible/                     # Ansible dependencies (from requirements.yml)
│   ├── roles/                    # Installed external roles
│   └── collections/              # Installed collections
├── .ansible-lint                 # ansible-lint configuration
├── .yamllint                     # yamllint configuration
├── .gitignore                    # Git ignore rules
├── CLAUDE.md                     # Claude Code guidance and instructions
├── README.md                     # Project overview and quick start
└── docs/                         # Documentation directory
```

## Directory Purposes

**Root Directory:**
- Purpose: Playbook entry point, configuration, and orchestration
- Contains: Main playbook, inventory, Ansible config, external dependencies manifest
- Key files: `playbook.yml`, `inventory.yml`, `ansible.cfg`

**handlers/:**
- Purpose: Global notification handlers shared across all roles
- Contains: Container restart tasks (notify targets)
- Key files: `handlers/main.yml` - defines handlers like "Restart traefik", "Restart homepage"
- Usage: Roles use `notify: Restart <service>` to trigger idempotent restarts

**roles/:**
- Purpose: Ansible roles organized by infrastructure layer and application
- Contains: 50+ roles, each with standard structure
- Organization: First 6 roles (system → docker_proxy) are infrastructure; remaining are applications
- Execution order: Strictly enforced in `playbook.yml` from lines 15-184

**roles/<name>/ (Role Internal Structure):**

Each custom role follows this structure:

```
roles/<name>/
  defaults/main.yml             # Version pins, image names, config defaults
  tasks/main.yml                # Task logic: create dirs, render templates, start containers
  templates/                    # Jinja2 template files (.j2 extension)
    docker-compose.yml.j2       # Docker Compose service definition
    config.yml                  # Service configuration file
    [other configs]
  handlers/                     # (Optional) Role-specific handlers
    main.yml
  files/                        # (Optional) Static files to copy
  clients/                      # (Optional) Client configs (e.g., roles/proxy/clients/)
```

**External roles (in .ansible/roles/):**
- `geerlingguy.docker` - Installs Docker daemon (from Ansible Galaxy)
- `geerlingguy.pip` - Installs Python packages (from Ansible Galaxy)
- `chriswayg.msmtp-mailer` - System email relay (from Ansible Galaxy)

## Key File Locations

**Entry Points:**

- `playbook.yml`: Main orchestration file, defines role order and tags. Loads `custom.yml`, imports handlers.
- `inventory.yml`: Host inventory and service hostname variables (all subdomains derived from `root_host`)
- `handlers/main.yml`: Global restart handlers for all services

**Configuration:**

- `custom.yml`: User config (copied from `.custom.yml`). Contains: server IP, domain, username, email settings, Docker path, storage paths
- `secret.yml`: Vault-encrypted secrets (copied from `.secret.yml`, encrypted with `ansible-vault`). Contains: API keys, passwords, Cloudflare credentials
- `requirements.yml`: External dependencies - roles and collections to install via `ansible-galaxy`
- `ansible.cfg`: Ansible settings: roles_path, collections_path, callback plugins, SSH multiplexing

**Core Logic:**

- `roles/system/tasks/main.yml`: Install system packages, setup firewall, configure auto-updates
- `roles/security/tasks/main.yml`: AppArmor, SSH PAM configuration
- `roles/dns/tasks/main.yml`: Cloudflare DNS registration via API
- `roles/docker_network/tasks/main.yml`: Create 5 isolated Docker bridge networks
- `roles/docker_proxy/tasks/main.yml`: Deploy restricted Docker socket proxy
- `roles/traefik/tasks/main.yml`: Render Traefik config, setup certificate ACME, create routes
- `roles/traefik/templates/traefik.yml`: Traefik static configuration (entry points, API, plugins)
- `roles/traefik/templates/config.yml`: Traefik dynamic config (routers, middlewares, services)

**Monitoring/Dashboard:**

- `roles/homepage/tasks/main.yml`: Deploy Homepage dashboard
- `roles/homepage/templates/services.yaml`: Service card definitions for dashboard
- `roles/grafana/tasks/main.yml`: Deploy Grafana + Prometheus stack
- `roles/gatus/tasks/main.yml`: Deploy uptime monitor

**Application Examples:**

- `roles/jellyfin/tasks/main.yml`: Create directories, bind mount storage, render compose, start container
- `roles/jellyfin/templates/docker-compose.yml`: Jellyfin + PostgreSQL compose definition
- `roles/immich/tasks/main.yml`: Create directories, bind mount external storage, start containers
- `roles/immich/templates/docker-compose.yml`: Immich microservices compose definition
- `roles/vaultwarden/tasks/main.yml`: Password manager setup
- `roles/supabase/tasks/main.yml`: Backend-as-a-Service with PostgreSQL

**Storage/Backup:**

- `roles/storagebox/tasks/main.yml`: Mount Hetzner Storage Box via CIFS
- `roles/backup/tasks/main.yml`: Restic backup schedule to Storage Box
- `roles/backup/templates/`: Backup scripts and cron job configs

**Testing/Linting:**

- `.ansible-lint`: ansible-lint rules configuration
- `.yamllint`: YAML syntax rules

## Naming Conventions

**Files:**

- Playbook: `playbook.yml` (main orchestration)
- Inventory: `inventory.yml` (hosts and variables)
- Config: `custom.yml`, `secret.yml` (deployment config)
- Roles: `<name>/` in `roles/` (e.g., `roles/jellyfin/`)
- Tasks: `tasks/main.yml` (role logic)
- Handlers: `handlers/main.yml` (restart handlers)
- Templates: `templates/<service>.<ext>.j2` (e.g., `docker-compose.yml.j2`, `traefik.yml`)
- Defaults: `defaults/main.yml` (variables: versions, image names, paths)

**Directories:**

- Infrastructure roles: `roles/system/`, `roles/docker_network/`, `roles/traefik/` (lowercase, underscore-separated)
- Application roles: `roles/jellyfin/`, `roles/homepage/`, `roles/immich/` (lowercase, underscore-separated)
- Config mounts: `{{ docker_dir }}/<service>/` (e.g., `/opt/docker/jellyfin/`, `/opt/docker/traefik/`)
- Data mounts: `{{ docker_dir }}/<service>/data/` or service-specific (e.g., `/opt/docker/jellyfin/config/`)
- Storage Box mount: `{{ storagebox_mount_path }}/` (default: `/mnt/storagebox/`)

**Variables:**

- Service versions: `<service>_version` (e.g., `jellyfin_version: "10.8.0"`)
- Service hosts: `<service>_host: "<subdomain>.{{ root_host }}"` (e.g., `jellyfin_host: "media.{{ root_host }}"`)
- Passwords/keys: `<service>_password`, `<service>_api_key` (stored in `secret.yml`)
- Paths: `<service>_data_dir`, `<service>_config_dir`, `<service>_mount_path`
- Flags: `<service>_enabled`, `<service>_storage_box_mount_enabled` (boolean conditions)

**Docker Resources:**

- Container names: Match role name (e.g., container `jellyfin`, role `roles/jellyfin/`)
- Network names: Standard set - `edge_network`, `app_network`, `redis_data_network`, `ops_network`, `dns_network`
- Volume mounts: `{{ docker_dir }}/<service>/:/app/config` pattern (config) or service-specific paths

## Where to Add New Code

**New Application Role:**

1. Create directory: `roles/<service_name>/`
2. Create structure:
   ```
   roles/<service_name>/
     defaults/main.yml          # Set <service_name>_version, <service_name>_host (if needs subdomain)
     tasks/main.yml             # Create dirs, render templates, start container
     templates/docker-compose.yml.j2  # Service definition
   ```
3. Add to `playbook.yml`: Insert role with tag matching folder name (after infrastructure roles)
4. Add to `inventory.yml`: Add `<service_name>_host: "<subdomain>.{{ root_host }}"` if needs public access
5. Add to `roles/traefik/templates/config.yml`: Router/middleware definitions if needs public access
6. Add to `roles/homepage/templates/services.yaml`: Dashboard card definition
7. Add to `roles/gatus/templates/config.yml.j2`: Uptime monitoring endpoint

**New Configuration File:**

- Template location: `roles/<service>/templates/config.yml`
- Pattern: Use Jinja2 variables for dynamic values (e.g., `{{ service_password }}`, `{{ docker_dir }}`)
- Task pattern:
  ```yaml
  - name: Template config
    ansible.builtin.template:
      src: config.yml
      dest: "{{ docker_dir }}/<service>/config.yml"
    notify: Restart <service>
  ```

**New Docker Compose Service:**

- Location: `roles/<service>/templates/docker-compose.yml.j2`
- Pattern: Include Traefik labels for routing
- Traefik labels example:
  ```yaml
  labels:
    traefik.enable: "true"
    traefik.docker.network: "app_network"
    traefik.http.routers.service.rule: "Host(`{{ service_host }}`)"
    traefik.http.routers.service.middlewares: "open-external@file"
    traefik.http.services.service.loadbalancer.server.port: "8080"
  ```
- Network connections: Join `app_network` (public apps) and/or `edge_network` (security layer)

**New Secret/Credential:**

1. Add to `.secret.yml` template (template file):
   ```yaml
   <service>_api_key: !vault |
     $ANSIBLE_VAULT;...
   ```
2. Add to `secret.yml` (gitignored, vault-encrypted)
3. Reference in role task as `{{ <service>_api_key }}`
4. Pass to container as environment variable:
   ```yaml
   env:
     SERVICE_API_KEY: "{{ <service>_api_key }}"
   ```

**New DNS Record:**

- Location: `roles/dns/defaults/main.yml` under `dns_records:`
- For public services: Add A record (proxied: true for Cloudflare protection)
- For VPN-only: Add rewrite in `roles/adguardhome/templates/AdGuardHome.yaml` under `rewrites:`

**Utilities/Helpers:**

- Shared task files: Not used; each role is self-contained
- Environment-specific config: Handled via `custom.yml` and `secret.yml`
- Version management: Pinned in role `defaults/main.yml`

## Special Directories

**{{ docker_dir }} (default: /opt/docker):**
- Purpose: Central Docker container data and config storage
- Generated: Created by system role, mounted into containers
- Committed: No (gitignored, contains runtime data and secrets)
- Subdirectories: `{{ docker_dir }}/<service>/` for each containerized service
  - `traefik/data/` - Traefik config, certificates, logs
  - `jellyfin/config/` - Jellyfin database and settings
  - `immich/` - Immich uploads and config
  - `homepage/` - Homepage YAML configs and CSS

**{{ storagebox_mount_path }} (default: /mnt/storagebox):**
- Purpose: Hetzner Storage Box CIFS mount for external shared storage
- Generated: Created by storagebox role via CIFS mount
- Committed: No (external mount point)
- Subdirectories: `immich/`, `media/` (used by Jellyfin), `backup/` (Restic backup)

**.planning/codebase/:**
- Purpose: GSD (Claude Code) analysis documents
- Generated: Created by `/gsd:map-codebase` command
- Committed: Yes (gitignored in most repos, but this one commits them)
- Contents: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md, STACK.md, INTEGRATIONS.md

**.ansible/ (hidden):**
- Purpose: External role and collection dependencies
- Generated: Created by `ansible-galaxy install -r requirements.yml`
- Committed: No (gitignored)
- Contents: Installed external roles from Galaxy (`geerlingguy.docker`, etc.), collections (`community.docker`, etc.)

**.vscode/ (hidden):**
- Purpose: VS Code editor settings and extensions recommendations
- Generated: Checked in
- Committed: Yes
- Contents: Ansible extension configuration

**.github/ (hidden):**
- Purpose: GitHub-specific configuration (workflows, issue templates)
- Generated: Checked in
- Committed: Yes

---

*Structure analysis: 2026-03-22*
