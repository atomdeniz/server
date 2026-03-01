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

- **`custom.yml`** — copy from `.custom.yml`, fill in `ansible_host`, `root_host`, `username`, SSH key path, email settings, `force_recreate`, and Immich storage config.
- **`secret.yml`** — holds secrets like `crowdsecLapiKey`, `crowdsecMachineApiKey`, email password. Must be `chmod 600`.

`inventory.yml` derives all service subdomains from `root_host` (e.g., `auth.{{ root_host }}`, `password.{{ root_host }}`). Docker data lives under `docker_dir` (default `/opt/docker`).

## Architecture

### Role Execution Order

Roles in `playbook.yml` run in this sequence and must be thought of as layers:

1. **Infrastructure base**: `system` → `security` → `dns` → `geerlingguy.docker` → `docker_network` → `docker_proxy`
2. **Security/proxy layer**: `crowdsec` → `traefik` → `authelia`
3. **Applications**: all remaining roles (each has its own tag matching its folder name)

External roles: `geerlingguy.docker`, `geerlingguy.pip`, `chriswayg.msmtp-mailer` (installed to `.ansible/roles/`).

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

`ollama`, `freqtrade`, and `convertx` are commented out in `playbook.yml`. Their role folders still exist and can be re-enabled.

## Adding a New Role

1. Create `roles/<name>/` with the standard structure above.
2. Add version pin in `defaults/main.yml`.
3. Add the role to `playbook.yml` with a matching tag.
4. If the service needs a subdomain, add `<name>_host: "<sub>.{{ root_host }}"` to `inventory.yml`.
5. Join the container to the appropriate Docker network(s) via Compose labels.

## Post-Install Steps

After first CrowdSec deploy, run these on the server:

```bash
# Enroll agent
docker exec crowdsec cscli console enroll -e context <key>

# Add Traefik bouncer (save output key to secret.yml as crowdsecLapiKey)
docker exec crowdsec cscli bouncers add traefik-bouncer

# Add firewall bouncer (save key to /etc/crowdsec/bouncers/crowdsec-firewall-bouncer.yaml)
docker exec crowdsec cscli bouncers add firewall-bouncer
sudo service crowdsec-firewall-bouncer restart
```

Firewall rules: allow 80/tcp, 443/tcp, 51820/udp from any; restrict 22/tcp to your IP.
