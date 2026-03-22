# Technology Stack

**Analysis Date:** 2025-03-22

## Languages

**Primary:**
- YAML - Ansible playbook and configuration files
- Jinja2 - Template rendering for containerized services and configurations
- Bash - Shell scripts for system operations and media cleanup
- Go - Used in some upstream projects (Traefik, Docker tools)

## Runtime

**Environment:**
- Ubuntu ARM64 (target platform for VPS deployment)
- Linux kernel (AppArmor for container security)

**Package Manager:**
- `apt` - Ubuntu system package manager
- Python pip - Via `geerlingguy.pip` role for Python packages (docker client)

## Frameworks & Core Tools

**Orchestration:**
- Ansible - Infrastructure as Code automation framework
- Ansible version: specified in requirements via Galaxy roles

**Container Runtime:**
- Docker - Primary containerization platform
- Docker Compose - Service orchestration via templates (`.j2` files)
- Docker API - Controlled through restricted socket proxy (`docker_proxy` role)

**External Ansible Roles:**
- `geerlingguy.docker` - Docker installation and configuration
- `geerlingguy.pip` - Python package management
- `chriswayg.msmtp-mailer` - System email relay via SMTP

**External Ansible Collections:**
- `community.docker` (>=5.0.0) - Docker container management modules
- `community.general` - General-purpose community modules
- `community.crypto` - Cryptographic utilities
- `ansible.posix` - POSIX system administration

## Key Dependencies by Role

**Reverse Proxy & Routing:**
- Traefik v3.6.10 - HTTP reverse proxy and load balancer
- TraefIKShaper latest - Traffic shaping middleware
- CertsDump v2.11.0 - Certificate monitoring

**Security & Authentication:**
- CrowdSec v1.7.6 - IPS/behavioral firewall
- Authelia 4.39.15 - Authentication and authorization server
- AppArmor - Mandatory access control framework (system)

**DNS & VPN:**
- Unbound 1.22.0 - Recursive DNS resolver
- AdGuard Home v0.108.0-b.82 - DNS ad blocker and filtering
- AmneziaWG v1 - WireGuard-based obfuscated VPN

**Data Storage:**
- PostgreSQL 16-alpine - Primary relational database
- Redis 8.6.1 - In-memory cache and session store
- Restic - Backup tool (system package via apt)

**Monitoring & Observability:**
- Prometheus v3.10.0 - Metrics collection
- Grafana 12.4.1 - Metrics visualization
- Node Exporter v1.10.2 - System metrics exporter
- cAdvisor v0.55.1 - Container metrics exporter
- Gatus 5.16.0 - Lightweight uptime monitoring

**Applications:**
- Jellyfin (latest) - Media server with webhook plugin 18.0.0.0
- Immich v2.5.6 - Photo management with pgvectors integration
- Vaultwarden 1.35.4 - Bitwarden-compatible password manager
- Supabase - Backend-as-a-Service (docker-compose managed)
- n8n 1.123.23 - Workflow automation
- Umami (postgresql-latest) - Web analytics
- Spliit 1.19.0 - Expense splitting
- Pingvin v1.13.0 - File sharing
- Wallos - Subscription tracker
- FileBrowser v2.32.0 - Web file manager
- ChangeDetection 0.54.5 - Website change monitoring
- Dozzle - Docker log viewer
- Web-Check - Website analysis tool
- Convertx - File converter
- IT Tools - Developer utilities
- Homepage - Dashboard/homepage aggregator
- Whoami - HTTP request debugging service
- OpenClaw (latest) - Telegram bot service
- Ntfy v2.18.0 - Self-hosted push notifications

**Media Proxy & Streaming:**
- Caddy 2.11.2 - HTTP proxy and file server
- Trojan 1.16.0 - Proxy protocol
- V2Fly v5.41.0 - V2Ray compatible proxy

**DevOps Tools:**
- DIUN (Docker Image Update Notifier) 4.29.0 - Image update monitoring

## Configuration Management

**Environment Configuration:**
- `custom.yml` (gitignored) - Local deployment variables (hosts, domains, email settings, storage paths)
- `secret.yml` (vault-encrypted, gitignored) - Sensitive credentials (API keys, passwords, tokens)
- `ansible.cfg` - Ansible runtime settings (roles_path, collections_path, callbacks, SSH multiplexing)

**Key Config Files:**
- `playbook.yml` - Main orchestration file defining role execution order
- `inventory.yml` - Host inventory with service subdomains derived from `root_host` variable
- `requirements.yml` - External role and collection dependencies

**Encryption:**
- Ansible Vault - For encrypting `secret.yml` containing sensitive data
- Vault password file: `~/.vault_pass` (never committed, never read by Claude)

## Build & Deployment

**Build System:**
- Ansible playbook execution via CLI
- Docker image pulling (`pull: always` for most services, version pinned in defaults)
- Volume and network creation via `docker_network` role

**Networking:**
- Five isolated Docker bridge networks:
  - `edge_network` (10.8.1.0/24) - External Traefik entry
  - `redis_data_network` (10.8.2.0/24) - Redis internal
  - `ops_network` (10.8.3.0/24) - Monitoring (Grafana, Prometheus, cAdvisor)
  - `dns_network` (10.8.4.0/24) - DNS services (AdGuard 10.8.4.2, Unbound 10.8.4.3)
  - `app_network` (10.8.6.0/24) - Application services

**Volume Management:**
- Docker data directory: `{{ docker_dir }}` (default `/opt/docker`)
- Storage Box mount: `{{ storagebox_mount_path }}` (default `/mnt/storagebox`)
- Per-service volumes defined in role templates (docker-compose.yml.j2)

## Platform Requirements

**Development/Deployment:**
- Ansible 2.9+ (via ansible-galaxy install)
- Python 3 (interpreter_python = python3 in ansible.cfg)
- SSH access to Ubuntu ARM64 target
- CIFS utilities (`cifs-utils` package) for Storage Box mounting
- jq - JSON query tool (for email notifications, media cleanup scripts)

**Production (Target Host):**
- Ubuntu ARM64 VPS
- Docker and docker-compose (installed by geerlingguy.docker role)
- Systemd for service management and timers
- Swap configured (2GB default via system role)
- Firewall rules (iptables managed by security role)

## Secrets Management

**Stored in `secret.yml` (vault-encrypted):**
- Cloudflare API credentials (email, API key)
- Traefik dashboard authentication (htpasswd hash)
- JWT secrets (Authelia, Supabase, Freqtrade)
- Database passwords (Supabase PostgreSQL, Immich, Spliit, Umami)
- API keys (multiple services: Jellyfin, Immich, seedbox arr stack)
- OAuth tokens (Claude Max API proxy)
- Exchange API keys (Freqtrade: Binance, KuCoin)
- Storage Box credentials (CIFS mount)
- Email relay credentials (SMTP via msmtp)
- Restic backup password
- Telegram bot tokens

---

*Stack analysis: 2025-03-22*
