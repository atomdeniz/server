# Architecture

**Analysis Date:** 2026-03-22

## Pattern Overview

**Overall:** Layered Infrastructure-as-Code (IaC) with Docker container orchestration

**Key Characteristics:**
- Ansible-based declarative infrastructure management
- Role-based organization with strict execution order
- Docker containerization with isolated bridge networks
- Traefik reverse proxy as the service gateway
- Multi-tier security through AppArmor, CrowdSec, and Authelia
- Vault-encrypted secret management

## Layers

**Infrastructure Base Layer:**
- Purpose: Foundation system configuration and dependencies
- Location: `roles/system/`, `roles/security/`, `roles/dns/`
- Contains: System packages, firewall rules, AppArmor profiles, SSH configuration, DNS records
- Depends on: Ubuntu OS baseline
- Used by: All other roles

**Docker Layer:**
- Purpose: Docker daemon installation and network setup
- Location: `roles/geerlingguy.docker/`, `roles/docker_network/`, `roles/docker_proxy/`
- Contains: Docker installation, isolated bridge networks (edge_network, redis_data_network, ops_network, dns_network, app_network), restricted Docker socket proxy
- Depends on: System layer
- Used by: All application roles

**Security/Proxy Layer:**
- Purpose: Edge security, DDoS protection, authentication, and ingress routing
- Location: `roles/crowdsec/`, `roles/traefik/`, `roles/redis/`, `roles/authelia/`
- Contains: CrowdSec WAF/IDS, Traefik reverse proxy, Redis for session storage, Authelia SSO
- Depends on: Docker and infrastructure layers
- Used by: All publicly-accessible application roles

**DNS/Network Layer:**
- Purpose: Recursive DNS resolution and ad-blocking
- Location: `roles/unbound/`, `roles/adguardhome/`, `roles/amnezia_wg/`
- Contains: Unbound recursive resolver (10.8.4.3), AdGuard Home ad blocker (10.8.4.2), AmneziaWG VPN
- Depends on: Docker and security layers
- Used by: Client applications and external access

**Application Layer:**
- Purpose: Feature services and user-facing applications
- Location: `roles/*/` (excluding infrastructure roles)
- Contains: Web apps (Homepage, Immich, Jellyfin, Vaultwarden, etc.), automation (n8n), monitoring (Grafana, Gatus), observability (Dozzle, Diun)
- Depends on: All lower layers
- Used by: End users, integrations, backups

## Data Flow

**Request Flow (Public Access):**

1. Client connects to `{{ root_host }}` via HTTPS
2. Cloudflare CDN forwards to server public IP (if proxied)
3. Traefik on `edge_network` (port 443) receives encrypted connection
4. Traefik applies middlewares: CrowdSec rules, Authelia authentication, custom routing
5. Request routes to target container on `app_network` (10.8.6.0/24)
6. Application responds through Traefik back to client

**VPN-Only Access:**

1. Client connects via AmneziaWG VPN (10.8.0.0/24)
2. Client receives internal IP in VPN subnet
3. Client accesses service via internal DNS (AdGuard Home at 10.8.4.2)
4. AdGuard resolves service hostname to internal Docker IP
5. Traffic routes to container on `app_network` or `edge_network` directly
6. Service rejects non-VPN traffic via Traefik `secure-vpn@file` middleware

**State Management:**

- **Session State:** Redis (`redis_data_network`, 10.8.2.0/24) stores Authelia sessions and application caches
- **Configuration State:** Ansible templates render into mounted volumes (`{{ docker_dir }}/*/`)
- **Persistent Data:** PostgreSQL, mounted storage, Storage Box (CIFS mount at `/mnt/storagebox`)
- **Secrets:** Vault-encrypted `secret.yml` loaded at playbook runtime, passed as env vars to containers

## Key Abstractions

**Docker Compose Services:**
- Purpose: Template and manage containerized applications
- Examples: `roles/immich/templates/docker-compose.yml`, `roles/supabase/templates/docker-compose.yml`
- Pattern: Each role has a `docker-compose.yml.j2` template with Jinja2 variables for versions, paths, secrets
- Rendered to: `{{ docker_dir }}/<service>/docker-compose.yml`
- Managed via: `community.docker.docker_container` tasks (pull images, create/restart containers)

**Traefik Labels System:**
- Purpose: Declarative routing and middleware configuration
- Examples: Every application role includes Docker labels for Traefik
- Pattern: Labels define HTTP routers (hostname rules), middleware chains, service port mapping
- Traefik reads labels from Docker API (via docker_proxy) and updates routes dynamically
- Middleware chains: `secure-vpn@file`, `secure-vpn-with-auth@file`, `open-external@file`

**Network Segmentation:**
- Purpose: Isolate traffic by function and trust level
- Examples: `edge_network` for ingress, `ops_network` (internal) for monitoring, `app_network` for applications
- Pattern: Services connect to specific networks via `docker_container` networks parameter
- Isolation: Internal networks have `internal: true` to prevent external egress

**Configuration Templates (Jinja2):**
- Purpose: Render service configs with playbook variables
- Examples: `roles/traefik/templates/traefik.yml`, `roles/adguardhome/templates/AdGuardHome.yaml`
- Pattern: `.j2` templates use `{{ variable }}` syntax, rendered via `ansible.builtin.template` task
- Dynamic values: hostname templates (`{{ root_host }}`), secrets (`{{ api_key }}`), paths (`{{ docker_dir }}`)

**Role Hooks (Notify/Handlers):**
- Purpose: Trigger container restarts when config changes
- Examples: `notify: Restart traefik`, `notify: Restart jellyfin`
- Pattern: Template tasks notify handlers in `handlers/main.yml`
- Global handlers: Defined in `/handlers/main.yml`, restart containers via `community.docker.docker_container` with `restart: yes`

## Entry Points

**Playbook Entry:**
- Location: `playbook.yml`
- Triggers: `ansible-playbook playbook.yml -i inventory.yml -e @custom.yml -e @secret.yml --vault-password-file ~/.vault_pass`
- Responsibilities: Loads all roles in strict order, imports global handlers, applies tags for selective execution

**Inventory Entry:**
- Location: `inventory.yml`
- Triggers: Referenced by playbook as `-i inventory.yml`
- Responsibilities: Defines target host (server), declares all service subdomains as Jinja2 variables, sets global network/port config

**Configuration Entries:**
- `custom.yml`: User-provided deployment config (connection, domains, email, paths)
- `secret.yml`: Vault-encrypted secrets (API keys, passwords, credentials)

**Role Entry Points (by layer):**

**System (Tag: system)**
- Location: `roles/system/tasks/main.yml`
- Triggers: First role executed
- Responsibilities: Install packages, enable auto-updates, configure swap, setup firewall rules

**Security (Tag: security)**
- Location: `roles/security/tasks/main.yml`
- Triggers: Second role, after system
- Responsibilities: Install AppArmor, configure PAM for SSH security

**DNS (Tag: dns)**
- Location: `roles/dns/tasks/main.yml`
- Triggers: Third role, before Docker
- Responsibilities: Register DNS records in Cloudflare via API

**Docker (Tag: docker)**
- Location: `roles/geerlingguy.docker/`, `roles/docker_network/tasks/main.yml`, `roles/docker_proxy/tasks/main.yml`
- Triggers: Fourth, after DNS
- Responsibilities: Install Docker, create bridge networks, setup restricted socket proxy

**Traefik (Tag: traefik)**
- Location: `roles/traefik/tasks/main.yml`
- Triggers: Ninth role, after CrowdSec
- Responsibilities: Render Traefik config, set up ACME certificate management, create router/middleware definitions

**Application Roles (Tag: app name)**
- Location: `roles/<app>/tasks/main.yml`
- Triggers: After security/proxy layer
- Responsibilities: Create service directories, render docker-compose.yml, start container via `community.docker.docker_container`

## Error Handling

**Strategy:** Ansible task-level validation with conditional handlers and container health checks

**Patterns:**

**File Operations:**
```yaml
# Example: Idempotent directory creation
- name: Create service directory
  ansible.builtin.file:
    path: "{{ docker_dir }}/service"
    state: directory
    owner: "{{ username }}"
    mode: "0755"
# Skips if directory exists; errors if permission denied
```

**Docker Pull/Image Errors:**
```yaml
# Example: Pull always, let task fail if image unavailable
- name: Start container
  community.docker.docker_container:
    image: "ghcr.io/app:{{ version }}"
    pull: always  # Always check for new image
    # Task fails if pull fails or container won't start
```

**Conditional Execution:**
```yaml
# Example: Mount only if explicitly enabled
- name: Bind mount storage
  ansible.posix.mount:
    src: "/mnt/storagebox/app"
    path: "/mnt/app"
    state: mounted
  when: app_storage_box_mount_enabled | default(false)
# Task skipped if condition false; error if mount fails
```

**Handler-Based Recovery:**
```yaml
# Example: Detect config change, restart container
- name: Copy service config
  ansible.builtin.template:
    src: config.yml
    dest: "{{ docker_dir }}/service/config.yml"
  notify: Restart service  # Only restart if file changes

# Handler in handlers/main.yml:
- name: Restart service
  community.docker.docker_container:
    name: service
    restart: yes
```

**Vault/Secret Failures:**
```yaml
# Example: Read secret from running container if not provided
- name: Read API key from container
  ansible.builtin.slurp:
    src: "{{ docker_dir }}/service/.api-key"
  register: key_file
  become: true
  failed_when: false  # Don't fail if file doesn't exist

- name: Set fact if available
  ansible.builtin.set_fact:
    service_api_key: "{{ key_file.content | b64decode | trim }}"
  when:
    - service_api_key is not defined
    - key_file is succeeded  # Only set if slurp succeeded
```

## Cross-Cutting Concerns

**Logging:**
- Approach: Docker logs via container stdout/stderr, collected by Dozzle (`roles/dozzle/`)
- Access: Via Traefik reverse proxy at `dozzle.{{ root_host }}`
- Traefik logs: Written to `{{ docker_dir }}/traefik/data/logs/`, rotated via logrotate

**Validation:**
- Approach: Ansible template validation (Jinja2 syntax) + Docker health checks
- Health checks: Defined in docker-compose templates (TCP port checks, HTTP endpoints)
- Container startup: Monitored by `gatus` uptime checker at `gatus.{{ root_host }}`

**Authentication:**
- Approach: Tiered auth via Authelia and Traefik middleware
- Public services: Use `open-external@file` middleware (no auth required)
- VPN-only services: Use `secure-vpn-with-auth@file` (Authelia SSO + VPN check)
- Admin services: Use `secure-vpn-with-auth@file` (Authelia + VPN required)
- Authelia config: Rendered in `roles/authelia/`, manages user DB, OTP, session storage in Redis

**Monitoring:**
- Approach: Prometheus metrics from cAdvisor, Node Exporter, collected by Grafana
- Services: Prometheus scrape targets defined in Grafana role
- Dashboards: Pre-configured Grafana dashboards for Docker containers, system metrics
- Uptime: Gatus monitors HTTP endpoints for each service, alerts via ntfy

**Notifications:**
- Approach: ntfy.sh push notifications (centralized; replaced email/Telegram)
- Services: CrowdSec alerts, Jellyfin webhooks, change detection alerts all post to ntfy
- Config: ntfy role provides self-hosted notification endpoint at `ntfy.{{ root_host }}`

---

*Architecture analysis: 2026-03-22*
