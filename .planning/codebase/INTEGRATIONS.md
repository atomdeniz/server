# External Integrations

**Analysis Date:** 2025-03-22

## APIs & External Services

**DNS Management (Cloudflare):**
- Service: Cloudflare DNS API
- What it's used for: Dynamic DNS record creation and management for all service subdomains
- Implementation: `roles/dns/tasks/main.yml` uses `community.general.cloudflare_dns` module
- Auth: `cloudflare_email` and `cloudflare_api_key` (stored in `secret.yml`)
- Records managed: All service subdomains point to `ansible_host` with proxying configured per service

**Email Notifications (SMTP):**
- Service: Gmail SMTP (or custom SMTP provider)
- What it's used for: System email relay via msmtp, used by CrowdSec and monitoring alerts
- Implementation: `chriswayg.msmtp-mailer` role
- Auth: `email_login` and `email_password` (in `secret.yml`)
- Configuration: `email_smtp_host`, `email_smtp_port` (in `custom.yml`)

**Docker Container Registry (Docker Hub / GHCR):**
- Service: Docker Hub and GitHub Container Registry
- What it's used for: Pulling container images with version pinning
- Special: Immich uses custom PostgreSQL image with pgvectors: `ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0`
- Strategy: `pull: always` in most services to ensure up-to-date images

## Data Storage

**Databases:**

**PostgreSQL (Primary):**
- Type: Relational database (16-alpine)
- Container: `postgres` service via `roles/postgres/`
- Bootstrap user: `spliit`
- Used by:
  - Immich (with pgvectors extension for photo similarity)
  - Supabase (internal PostgreSQL + custom extensions)
  - Spliit (expense tracking)
  - Umami (analytics)
- Connection: Internal Docker network via service DNS
- Data location: `{{ docker_dir }}/postgres`

**Redis:**
- Type: In-memory cache and session store (8.6.1)
- Container: `redis` service
- Used by: Authelia (session storage), Traefik (cache), other services
- Network: `redis_data_network` (isolated internal network)
- Data location: `{{ docker_dir }}/redis`

**File Storage:**

**Hetzner Storage Box (CIFS Mount):**
- Service: Hetzner Storage Box via CIFS/SMB
- What it's used for: Persistent storage for media (Jellyfin, Immich) and backups
- Mount point: `{{ storagebox_mount_path }}` (default `/mnt/storagebox`)
- Authentication: CIFS credentials file at `/etc/storagebox-credentials`
- Host: `{{ storagebox_host }}` (e.g., `uXXXXXX.your-storagebox.de`)
- User: `{{ storagebox_user }}` (stored in `custom.yml`)
- Password: `{{ storagebox_smb_pass }}` (stored in `secret.yml`)
- Subdirectories: `immich/`, `backup/`, `media/`
- Used by:
  - Immich: `{{ storagebox_mount_path }}/immich` for photo/video storage
  - Jellyfin: `{{ storagebox_mount_path }}/media` for media files (bind-mounted to container)
  - Restic: `{{ storagebox_mount_path }}/backup` for backup repository
- Implementation: `roles/storagebox/tasks/main.yml` handles CIFS mount with custom options (rsize, wsize, cache settings)

**Local Docker Storage:**
- Path: `{{ docker_dir }}` (default `/opt/docker`)
- Contains: All container data volumes
- Backed up daily via Restic to Storage Box

**Caching:**
- Redis 8.6.1 - In-memory cache on `redis_data_network`
- Docker volumes for service-specific caching (e.g., Jellyfin transcodes in tmpfs)

## Authentication & Identity

**Authentication Providers:**

**Authelia (Custom SSO):**
- Implementation: 4.39.15 - Self-hosted authentication and authorization
- Used for: Single-sign-on for all private services
- Secrets: `authelia_password` (SHA512 hashed), `authelia_jwt_secret`, `authelia_session_secret`, `authelia_storage_encryption_key`
- Storage: Redis for session management
- Forward auth: Traefik delegates auth checks to Authelia via `traefik.http.middlewares.authelia@file`

**Traefik Middleware Authentication:**
- Basic Auth: `traefik_basic_auth_hash` for Traefik dashboard
- Service Middlewares:
  - `open-external@file` - Public services (no auth required)
  - `secure-vpn@file` - VPN-only services (DNS rewrite in AdGuard)
  - `secure-vpn-with-auth@file` - VPN + Authelia authentication

**API Key Authentication:**
- Jellyfin: API key in media cleanup script and HomepageWidget (`jellyfin_api_key`)
- Immich: API key for external widgets and API access (`immich_api_key`)
- Seedbox services:
  - Radarr: `radarr_api_key`
  - Sonarr: `sonarr_api_key`
  - Prowlarr: `prowlarr_api_key`
  - Bazarr: `bazarr_api_key`

**VPN Authentication:**
- AmneziaWG: User/password-based WireGuard variant
- Password hash: `amnezia_password_hash` (htpasswd)
- Used for VPN client access

## Monitoring & Observability

**Error Tracking & Alerts:**
- CrowdSec v1.7.6 - Behavioral firewall and threat detection
  - Console enrollment: After deploy, enroll with `docker exec crowdsec cscli console enroll -e context <key>`
  - Notifications via email (msmtp relay)
  - Traefik integration for log analysis

**Logging:**
- Traefik logs → CrowdSec acquis.yml
- Docker logs → Dozzle service for log viewer UI
- System logs → Systemd journal
- Alerting: Traefik alerts via email/ntfy to admin

**Metrics & Monitoring:**
- Prometheus v3.10.0 - Metrics collection
- Node Exporter v1.10.2 - System metrics
- cAdvisor v0.55.1 - Container metrics
- Grafana 12.4.1 - Visualization and dashboards
- Network: `ops_network` (isolated internal)

**Uptime Monitoring:**
- Gatus 5.16.0 - Lightweight uptime checks
- Monitors: All public services via internal Docker URLs (http://service:port)
- Configuration: `roles/gatus/templates/config.yml.j2`

## Push Notifications

**Ntfy v2.18.0 (Self-Hosted Push Notifications):**
- Service URL: `https://{{ ntfy_host }}`
- Admin password: `{{ ntfy_admin_password }}`
- Token: `{{ ntfy_token }}` (auto-generated via `docker exec ntfy ntfy token add admin`)
- Upstream integration: `ntfy.sh` for iOS push notifications
- Auth: `{{ ntfy_upstream_access_token }}` (ntfy.sh account token)
- Web push: Public/private key pair for browser push notifications
- Used by:
  - Jellyfin Webhook plugin: Sends notifications to `https://{{ ntfy_host }}/jellyfin` on media events
  - DIUN: Docker image update notifications to `http://ntfy:80/diun`
  - Media Cleanup script: Sends cleanup summaries to `https://{{ ntfy_host }}/media`
  - CrowdSec: Security alerts via ntfy
- Implementation: Jellyfin uses Bearer token authorization, curl-based HTTP POST for custom scripts

## Webhooks & Callbacks

**Jellyfin Webhook Integration:**
- Plugin: Jellyfin.Plugin.Webhook v18.0.0.0
- Configuration: `roles/jellyfin/templates/webhook-config.xml.j2`
- Webhook endpoint: `https://{{ ntfy_host }}/jellyfin`
- Authorization: Bearer token ({{ ntfy_token }})
- Events tracked: ItemAdded (movies and episodes)
- Template: Custom notification format: `New movie: {{Name}} ({{Year}})` or `New episode: {{SeriesName}} - {{Name}}`
- Triggers: Automatically when new media is detected

**DIUN Docker Image Update Notifications:**
- Provider: Docker (via restricted docker_proxy socket)
- Notifier: ntfy
- Topic: `diun`
- Endpoint: `http://ntfy:80`
- Auth: Bearer token
- Notification priority: 3

**Media Cleanup Script Webhooks:**
- Endpoint: `https://{{ ntfy_host }}/media`
- Auth: Bearer token ({{ ntfy_token }})
- Notifications:
  - Cleanup summary with item count
  - Error notifications with priority=high
- Implementation: Bash script in media_cleanup role, curl-based HTTP POST

## Seedbox Integration (Ultra.cc ARR Stack)

**SSH Remote Execution:**
- Host: {{ media_cleanup_seedbox_host }}
- User: {{ media_cleanup_seedbox_user }}
- SSH key: {{ media_cleanup_seedbox_ssh_key }} (SSH private key)
- Used by: Media cleanup script for remote deletion of watched media on seedbox

**Media APIs:**
- Jellyfin API:
  - Base URL: `{{ media_cleanup_jellyfin_url }}`
  - Token: `{{ jellyfin_api_key }}`
  - Endpoints:
    - `/Users` - Get user ID
    - `/Users/{userId}/Items` - Query movies and episodes
    - `/Shows/{seriesId}/Seasons` - Get seasons
    - `/Shows/{seriesId}/Episodes` - Get episodes with watch status
  - Used by: Media cleanup script to identify watched content

- ARR Stack (via Homepage External Widgets):
  - Radarr: `{{ radarr_api_key }}` - Movie requests
  - Sonarr: `{{ sonarr_api_key }}` - TV series requests
  - Prowlarr: `{{ prowlarr_api_key }}` - Torrent/usenet indexing
  - Bazarr: `{{ bazarr_api_key }}` - Subtitle management
  - qBittorrent: `{{ qbittorrent_password }}` - Torrent client WebUI
  - Endpoints: Remote calls from Homepage dashboard for status/stats

## CI/CD & Deployment

**Hosting:**
- Hetzner Cloud (Ubuntu ARM64 VPS)
- IP: 128.140.80.85
- SSH user: ansible
- SSH key: `~/.ssh/ansible`

**Deployment Method:**
- Ansible playbook execution via CLI (no Semaphore UI)
- Manual or cron-based triggering
- Check mode (dry-run): `--check` flag available for testing

## Proxy & Tunneling Services

**Trojan Protocol:**
- Version: 1.16.0
- Used by: `roles/proxy/` for obfuscated proxy access
- Configuration: `roles/proxy/templates/trojan.json.j2`

**V2Ray / V2Fly:**
- Version: v5.41.0
- Protocols:
  - VLESS (VLESS_GUID_1, VLESS_GUID_2)
  - VMess (WMESS_GUID_1, WMESS_GUID_2)
- Configuration: `roles/proxy/templates/config.json.j2`
- Credentials: UUIDs and trojan password stored in `secret.yml`

**Caddy Web Server:**
- Version: 2.11.2
- Used by: Proxy role for additional HTTP/HTTPS handling
- Configuration: `roles/proxy/templates/` (if applicable)

## External Integrations via n8n

**Workflow Automation Platform:**
- Service: n8n 1.123.23
- Purpose: General-purpose workflow automation and API integrations
- Can integrate with: Any external API via n8n's built-in nodes (Webhooks, HTTP, OAuth providers, etc.)
- Subdomains: `n8n.{{ root_host }}`
- Note: Specific integrations would be defined within n8n workflows (not in this Ansible playbook)

## Backend-as-a-Service (Supabase)

**Supabase Stack:**
- Managed via `roles/supabase/`
- Components (docker-compose managed):
  - PostgreSQL (internal)
  - Kong API Gateway
  - GoTrue (authentication)
  - Realtime (WebSocket subscriptions)
  - Storage (S3-compatible backend)
  - Logflare (logging)
  - Pg_meta (metadata API)
- Configuration: Override compose file (`docker-compose.override.yml.j2`) adds Traefik labels
- API endpoints:
  - `supabase.{{ root_host }}` - Dashboard
  - `supabase-api.{{ root_host }}` - REST API endpoint
- S3 Storage:
  - Access key ID: `{{ supabase_s3_access_key_id }}`
  - Secret access key: `{{ supabase_s3_access_key_secret }}`
- Secrets (all in `secret.yml`):
  - `supabase_postgres_password`
  - `supabase_jwt_secret`
  - `supabase_anon_key`
  - `supabase_service_role_key`
  - `supabase_secret_key_base`
  - `supabase_vault_enc_key`
  - `supabase_pg_meta_crypto_key`
  - `supabase_logflare_*_access_token`
  - `supabase_dashboard_password`

## Telegram Integration

**OpenClaw Telegram Bot:**
- Service: openclaw (latest)
- What it's used for: Telegram bot service for notifications and commands
- Bot token: `{{ openclaw_telegram_bot_token }}`
- Gateway token: `{{ openclaw_gateway_token }}`
- Claude Max API Proxy integration: Uses local proxy at `http://10.8.6.1:3456/v1`
- Configuration: `roles/openclaw/templates/openclaw.json.j2`
- OAuth token: `{{ claude_oauth_token }}` (Claude Code OAuth)

**System Telegram Notifications:**
- Telegram user ID: `{{ telegram_user_id }}`
- Bot token: `{{ telegram_api_token }}`
- Used by: Traefik and security monitoring for alerts

## Environment Configuration Variables

**Required in `custom.yml`:**
- `ansible_host` - VPS IP address
- `root_host` - Base domain for all services
- `username` - SSH/container user
- `ansible_ssh_private_key_file` - Path to SSH key
- `email_recipient` - Email for notifications
- `email_smtp_host` - SMTP server
- `email_smtp_port` - SMTP port
- `email_login` - SMTP sender email
- `force_recreate` - Force container recreation on deploy
- `storagebox_host` - Hetzner Storage Box hostname
- `storagebox_user` - Storage Box username

**Required in `secret.yml`:**
- All passwords, API keys, tokens, and cryptographic materials
- Database passwords
- JWT secrets
- API credentials (Cloudflare, services, external APIs)
- SSH keys for remote operations
- Encryption keys

---

*Integration audit: 2025-03-22*
