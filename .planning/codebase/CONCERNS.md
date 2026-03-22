# Codebase Concerns

**Analysis Date:** 2026-03-22

## Tech Debt

**Variable Naming Convention Violations:**
- Issue: 36 Ansible lint warnings for variables not using role prefix convention. Backup role uses `restic_*` instead of `backup_restic_*`, changedetection uses `sockpuppetbrowser_*`, etc.
- Files: `roles/backup/defaults/main.yml`, `roles/changedetection/defaults/main.yml`, `roles/amnezia_wg/tasks/main.yml` and others
- Impact: Reduces code consistency, makes variable sources ambiguous, harder to trace dependencies
- Fix approach: Rename all variables to use `<role>_` prefix convention across all roles. Update all references in tasks and templates

**Risky Shell Pipe Patterns:**
- Issue: Three instances of `risky-shell-pipe` violations where piped output could silently fail
- Files: `roles/storagebox/tasks/main.yml` (lines 30, 39), `roles/postgres/tasks/main.yml` (line 76-81)
- Impact: Commands could fail partway through pipe without being caught, leaving system in inconsistent state
- Fix approach: Use `set -o pipefail` in shell blocks or convert to Ansible modules where possible (e.g., replace shell mounts with ansible.posix.mount)

**Missing `changed_when` Declarations:**
- Issue: Two shell/command tasks without `changed_when` declared, causing false "changed" status
- Files: `roles/storagebox/tasks/main.yml` (line 48), `roles/system/tasks/main.yml`
- Impact: Playbook reports changes when none occurred, breaking idempotency
- Fix approach: Add explicit `changed_when: false` or `changed_when: <condition>` to all shell/command tasks

**Shell Instead of Module:**
- Issue: Two instances using `shell` or `command` where Ansible modules would be safer
- Files: `roles/storagebox/tasks/main.yml` (mount operations), `roles/postgres/tasks/main.yml` (user management)
- Impact: Less portable, harder to test, more prone to parsing errors
- Fix approach: Replace with `ansible.posix.mount`, `postgresql_user` modules

## Known Bugs

**Jellyfin "latest" Version Tag:**
- Symptoms: Jellyfin container uses `jellyfin_version: "latest"`, causing unpredictable updates on each deploy
- Files: `roles/jellyfin/defaults/main.yml` (line 2)
- Trigger: Run with `--tags jellyfin` flag or full playbook deploy
- Workaround: Manually specify version in `custom.yml` override
- Severity: Medium - breaking schema changes or API incompatibilities could break Jellyfin integration

**Multiple "latest" Version Tags:**
- Symptoms: Six additional services using `latest` tag (Openclaw, MyWebsite, SockpuppetBrowser, Umami, Traefikshaper, and others)
- Files: `roles/openclaw/defaults/main.yml`, `roles/mywebsite/defaults/main.yml`, `roles/changedetection/defaults/main.yml` and others
- Trigger: Any deploy that pulls fresh images
- Impact: Services may upgrade unexpectedly with breaking changes
- Fix approach: Pin all versions to specific releases

**Missing Media Cleanup Role:**
- Symptoms: `roles/media_cleanup/` exists but is commented out in `playbook.yml` (line 177-180)
- Files: `roles/media_cleanup/tasks/main.yml`, `playbook.yml`
- Workaround: Role can be manually enabled if needed
- Note: Correctly disabled because rclone sync from seedbox would re-copy deleted files

**Orphaned Roles in Filesystem:**
- Symptoms: `roles/uptime_kuma/` exists but is not referenced in `playbook.yml`
- Files: `roles/uptime_kuma/`
- Impact: Dead code, confuses developers about which roles are active
- Fix approach: Either uncomment in playbook or remove from filesystem

**Diun Has No Notifications:**
- Symptoms: `roles/diun/tasks/main.yml` runs diun (image update monitor) but sends no notifications
- Files: `roles/diun/tasks/main.yml` (lines 10-40)
- Impact: Docker image updates are tracked but operator never learns about them
- Fix approach: Add diun notifications config (webhook, email, or ntfy integration)

## Security Considerations

**Storage Box Credentials in Plaintext File:**
- Risk: CIFS credentials written to `/etc/storagebox-credentials` with mode `0600`, but stored on host filesystem
- Files: `roles/storagebox/tasks/main.yml` (lines 17-26)
- Current mitigation: File permissions restrict to root only, not in git
- Recommendations: Consider using systemd-credentials or encrypted credential store; verify vault protection on server

**Traefik CrowdSec LAPI Key Read from Filesystem:**
- Risk: LAPI key is read from `.traefik-bouncer-key` file instead of injected via secret
- Files: `roles/traefik/tasks/main.yml` (lines 26-36)
- Current mitigation: File exists from crowdsec deploy, accessible only to ansible user
- Recommendations: Use Docker Swarm secrets or inject via environment variables from secret.yml

**PostgreSQL Password in Docker Environment:**
- Risk: Postgres user passwords passed via `POSTGRES_PASSWORD` env var (lines 30-32 in postgres/tasks/main.yml)
- Files: `roles/postgres/tasks/main.yml` (lines 30-32)
- Current mitigation: Secrets come from vault-encrypted `secret.yml`
- Recommendations: Use Docker secrets or pass via `.env` file with restricted permissions

**Shell Command Injection Risk in `storagebox/tasks/main.yml`:**
- Risk: Grep patterns and mount paths directly interpolated into shell commands without quoting
- Files: `roles/storagebox/tasks/main.yml` (lines 30, 39, 48, 65-68)
- Example: `mount | grep '{{ storagebox_mount_path }}'` — path not quoted
- Impact: Special characters in mount path could break command or inject shell code
- Recommendations: Quote all variables in shell commands; prefer Ansible modules

**Docker Socket Proxy Not Enforced:**
- Risk: While restricted Docker socket proxy exists (`docker_proxy` role), enforcement is declarative only
- Files: `roles/traefik/tasks/main.yml` uses restricted proxy (good), but other roles may bypass
- Current mitigation: AppArmor profiles enabled in security role
- Recommendations: Verify all containers use restricted socket or no socket access

**CrowdSec Configuration Allows High Resource Consumption:**
- Risk: CrowdSec container has no memory limits defined in compose
- Files: `roles/crowdsec/tasks/main.yml` (no memory constraint)
- Impact: Could OOM-kill on resource-constrained ARM VPS
- Recommendations: Add `memory: "512M"` limit, monitor in production

## Performance Bottlenecks

**Jellyfin Transcode Cache Allocates 4GB tmpfs:**
- Problem: Jellyfin reserves 4GB for transcoding in tmpfs, large for ARM VPS
- Files: `roles/jellyfin/tasks/main.yml` (line 76)
- Cause: Default value doesn't account for VPS memory constraints
- Improvement path: Make configurable; monitor actual usage; consider reducing to 1-2GB

**Immich Photo Reprocessing Without Resource Limits:**
- Problem: Immich microservices have no CPU/memory limits; microservices could consume all server resources during batch operations
- Files: `roles/immich/templates/docker-compose.yml` (no resource limits)
- Cause: Omitted in template; uncommented lines show transcoding settings but no limits
- Improvement path: Add `deploy.resources.limits` in docker-compose; test during heavy photo import

**PostgreSQL No Memory Limit:**
- Problem: Postgres container unbounded, could consume available memory during large queries
- Files: `roles/postgres/tasks/main.yml` (no memory limit)
- Impact: Could trigger OOM-killer under load, losing data
- Recommendation: Add `memory: "2G"` (or appropriate for VPS RAM)

**Mount Operations Using `set -o pipefail` Overhead:**
- Problem: `storagebox/tasks/main.yml` grep + awk chains for mount checks add latency on each deploy
- Files: `roles/storagebox/tasks/main.yml` (lines 30, 39, 57)
- Cause: Repeated parsing of mount table with grep instead of using fact modules
- Improvement path: Cache mount state; use ansible.posix modules; run less frequently

**Backup Restic Operations Not Parallelized:**
- Problem: Restic backup runs serially via cron, single-threaded
- Files: `roles/backup/defaults/main.yml`, backup systemd timer (not shown)
- Impact: Full backup of multi-TB storage could take hours, consuming bandwidth during working hours
- Recommendation: Configure parallel backup paths; run off-peak; enable incremental backups

## Fragile Areas

**Jellyfin Media Mount Bind Mount Dependency:**
- Files: `roles/jellyfin/tasks/main.yml` (lines 15-28)
- Why fragile: Requires storagebox CIFS mount to already be up; if storagebox mount fails silently, bind mount succeeds but points nowhere
- Safe modification: Add health check that validates `/media` has actual files; trigger rebuild if empty
- Test coverage: No validation that media source is accessible

**Storagebox CIFS Mount Unmount-Remount Pattern:**
- Files: `roles/storagebox/tasks/main.yml` (lines 37-53)
- Why fragile: Forcefully unmounts all bind mounts (`umount -l`) then CIFS mount before remounting; if interrupted, filesystem becomes inaccessible
- Safe modification: Use `atomic` operations; ensure timeout protection; add rollback on failure
- Test coverage: No test for partial failure scenarios

**CrowdSec to Traefik Integration:**
- Files: `roles/traefik/tasks/main.yml` (lines 26-36), `roles/crowdsec/tasks/main.yml`
- Why fragile: Traefik reads LAPI key from filesystem that only exists after crowdsec deploy; if crowdsec deploy fails, traefik deploy uses missing key
- Safe modification: Add explicit dependency check; pre-create dummy key if missing; add validation task
- Test coverage: No test that bouncer key format is valid before traefik starts

**Media Cleanup Seedbox SSH Key Generation:**
- Files: `roles/media_cleanup/tasks/main.yml` (lines 14-24)
- Why fragile: Generates SSH key, displays public key, requires manual intervention (copy to seedbox)
- Safe modification: Store public key in git or vault; document required seedbox setup; add playbook that fails with instructions
- Test coverage: No validation that seedbox SSH connection works before cleanup runs

**Postgres Multi-User Password Creation Pattern:**
- Files: `roles/postgres/tasks/main.yml` (lines 61-83)
- Why fragile: Creates user/database via `psql` directly; if container restarts during setup, state could be partially applied
- Safe modification: Use ansible-postgresql module with proper error handling and idempotency guards
- Test coverage: Creates without checking if already exists (though `DO $$ ... IF NOT EXISTS` mitigates)

## Scaling Limits

**ARM64 VPS Memory Constraints:**
- Current capacity: Ubuntu ARM64 VPS (assumed 1-4GB based on typical seedbox tier)
- Limit: With 39 services and 4GB tmpfs reserved by Jellyfin + Postgres unbounded + Immich unbounded, total memory can exceed available
- Scaling path: Reduce tmpfs allocations; add resource limits to all containers; monitor with Grafana (already deployed); consider upgrading VPS tier

**Single Restic Backup to Storage Box:**
- Current capacity: Backup path is `{{ storagebox_mount_path }}/backup` (single repository)
- Limit: If storagebox fills, both live data and backups become unavailable
- Scaling path: Add second backup destination; implement incremental/differential backups; archive old snapshots off-site

**Docker Data Directory on Root Volume:**
- Current capacity: All containers use `{{ docker_dir }}` (default `/opt/docker`), likely on root partition
- Limit: If root partition fills (40-50GB), system becomes unstable and Docker cannot create images
- Scaling path: Mount `/opt/docker` on separate volume; implement cleanup of old images; add monitoring for disk usage

**Network Bandwidth for Seedbox Sync:**
- Current capacity: Jellyfin/Immich mount storagebox via CIFS; seedbox syncs new files via rclone
- Limit: Single CIFS mount saturates 1Gbps link if multiple containers read simultaneously
- Scaling path: Add read-ahead caching; implement prioritization (Jellyfin before others); consider rsync over SSH instead of CIFS

## Dependencies at Risk

**Supabase Version Management Not Pinned:**
- Risk: Supabase components pulled with `pull: always` but versions not managed in ansible defaults
- Files: `roles/supabase/tasks/main.yml` (line 31), supabase docker-compose.yml in `{{ supabase_data_dir }}`
- Impact: Supabase could upgrade database schema, breaking immich, spliit, or other dependent services
- Migration plan: Pin Supabase components in official docker-compose.yml override; document tested versions; use `pull: 'false'` after validation

**Jellyfin Latest Tag:**
- Risk: Jellyfin uses `latest` tag; no pinned version
- Files: `roles/jellyfin/defaults/main.yml`
- Impact: Breaking API changes could break webhook plugin or external integrations
- Migration plan: Pin to 10.8.x or 10.9.x; test plugin compatibility; monitor release notes

**CrowdSec Bouncers Compatibility:**
- Risk: CrowdSec version and Traefik bouncer version not synchronized
- Files: `roles/crowdsec/defaults/main.yml`, `roles/traefik/templates/traefik.yml`
- Impact: Bouncer API incompatibility could disable DDoS protection
- Migration plan: Document tested version pairs; add explicit compatibility check in playbook

**Postgres Database Migrations:**
- Risk: Postgres upgrades could trigger auto-migrations affecting spliit/umami data
- Files: `roles/postgres/defaults/main.yml`
- Impact: Database corruption or data loss if migration fails mid-deploy
- Migration plan: Pin Postgres version; test migrations in staging; add backup before upgrade; add rollback procedure

## Missing Critical Features

**No Automated Backup Verification:**
- Problem: Restic backups run daily but are never tested for restore-ability
- Blocks: Can't guarantee data can be recovered until tested
- Fix approach: Add monthly restore test to random backup snapshot; report results via ntfy

**No Health Check Dashboard for All Services:**
- Problem: Gatus monitors endpoints but Traefik, CrowdSec, Redis have no health checks exposed
- Blocks: Can't detect internal service failures until external effect noticed
- Fix approach: Add health check endpoints to all critical services; include in Gatus config

**No Log Aggregation:**
- Problem: Each service logs to stdout/file; no centralized logging for incident investigation
- Blocks: Debugging multi-service issues requires SSH into server and checking logs manually
- Fix approach: Deploy ELK stack (Elasticsearch + Logstash + Kibana) or Loki; aggregate container logs

**No Certificate Renewal Validation:**
- Problem: Traefik handles ACME certificate renewal, but no monitoring if renewal fails
- Blocks: Certificate could silently expire, breaking HTTPS
- Fix approach: Add certificate expiry check to Gatus; add 30-day renewal alert via ntfy

**No Secrets Rotation Policy:**
- Problem: Database passwords and API keys set at deploy time, never rotated
- Blocks: If credential leaked, no procedure to change without full re-deploy
- Fix approach: Implement rotation policy; add secrets management (e.g., Vault) with periodic rotation

## Test Coverage Gaps

**Storagebox Mount Persistence:**
- What's not tested: Whether bind mounts survive reboot; whether CIFS reconnects after network loss
- Files: `roles/storagebox/tasks/main.yml`, `roles/jellyfin/tasks/main.yml`, `roles/immich/tasks/main.yml`
- Risk: Bind mounts could silently disappear after reboot, breaking Jellyfin/Immich until re-deploy
- Priority: High - affects data availability

**CrowdSec Bouncer Integration:**
- What's not tested: Whether Traefik bouncer actually receives IP bans; whether bans block traffic
- Files: `roles/crowdsec/tasks/main.yml`, `roles/traefik/tasks/main.yml`
- Risk: DDoS protection completely non-functional without validation
- Priority: High - security-critical

**Database Backup Recovery:**
- What's not tested: Whether postgres database can be restored from restic snapshots
- Files: `roles/backup/tasks/main.yml`, `roles/postgres/tasks/main.yml`
- Risk: Data loss if backup is corrupted
- Priority: High - data integrity

**Ansible Idempotency:**
- What's not tested: Whether running playbook twice produces same result (no spurious changes)
- Files: All roles, especially storagebox (mount/unmount), postgres (user/database creation)
- Risk: Deployments fail on second run due to state changes
- Priority: Medium - impacts reliability

**Docker Network Isolation:**
- What's not tested: Whether DNS leaks outside dns_network; whether redis is inaccessible from edge_network
- Files: `roles/docker_network/tasks/main.yml`, all role docker-compose templates
- Risk: Network isolation bypassed, exposing internal services
- Priority: Medium - security hardening

---

*Concerns audit: 2026-03-22*
