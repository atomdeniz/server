# SelfHosted Setup Guide

This document outlines the steps required for installing and configuring SelfHosted with **Semaphore UI** (Ansible is executed from Semaphore, not directly from CLI).

## Project Overview

This project aims to create a secure, efficient, and highly maintainable self-hosting infrastructure. By leveraging modern tools such as Authelia for secure authentication, Traefik for reverse proxy and SSL management, CrowdSec for real-time security protection, and AdGuard combined with Unbound for secure DNS resolution, this setup provides privacy, security, and ease of use for self-hosted services.

I am currently running the whole process only on Ubuntu ARM64.

**Traefik:** Reverse proxy and automatic SSL handling.

**Authelia:** Two-factor authentication for protecting web applications.

**CrowdSec:** Intrusion detection and prevention system, actively blocking malicious activities.

**AdGuard & Unbound:** DNS filtering and secure DNS resolution with DNS-over-HTTPS (DoH).

**Docker Socket Proxy:** Secure Docker socket management.

**Freqtrade:** Open source crypto trading bot with NostalgiaForInfinity strategy.

**WhatsUpDocker:** Tool to get notified when Docker images are updated.

**ConvertX:** Converter

**WhatuspDocker:** Docker image updates notifier

**Web Check:** Web check

**N8N**: MCP

**Grafana, Prometheus, cAdvisor, node_exporter:** Comprehensive monitoring and visualization of infrastructure metrics.

**Homepage & Uptime Kuma:** Easy-to-navigate dashboard and uptime monitoring for hosted services.

**V2ray (vmess/vless on WS), Trojan, AmneziaWG:** Secure VPN and proxy solutions ensuring privacy.

**Vaultwarden:** Self-hosted password management.

**Whoami:** Simple service for testing and debugging HTTP requests.

**Security Enhancements:** AppArmor profiles and iptables rules for further security hardening.

If you use this repository with Semaphore, install role/collection dependencies in the project repository setup (or before first run) so `requirements.yml` is available to jobs.

## 0 Set User

[Set User](https://github.com/atomdeniz/server/blob/main/USER.md)

## 1. Add SSH Key (Semaphore)

Add the SSH private key you use for server access in Semaphore:
- `Key Store` -> `New Key` -> `SSH Key`
- Use this key in your Task Template

## 2. Managing Variables and Secrets (Semaphore)

### Create custom.yml File in Repo

Copy the .custom.yml file as custom.yml and fill it in

### Create and Secure the Secret YAML File in Repo:

```bash
touch secret.yml
chmod 600 secret.yml
```

### Secrets

Because you are running via Semaphore UI, keep secrets in Semaphore `Key Store` / environment variables whenever possible.

If you still use `secret.yml`, prepare it in the repository before running templates (do not run `ansible-vault` manually from CLI unless you explicitly want local vault workflow).

## 3.1 CrowdSec Installation

Run a Semaphore Task Template with:
- `Playbook`: `playbook.yml`
- `Inventory`: `inventory.yml`
- `Limit/Tags`: `system,security,docker,crowdsec`

### CrowdSec Agent Enrollment

After CrowdSec installation, enroll the agent (replace `key` according to crowsec enroll key):

```bash
docker exec crowdsec cscli console enroll -e context key
```

### Add Traefik Bouncer

To add the Traefik bouncer:

```bash
docker exec crowdsec cscli bouncers add traefik-bouncer
```

Add the generated API key (`crowdsecLapiKey`) into your previously created `secret.yml`:

```yaml
crowdsecLapiKey: "your_generated_api_key_here"
```

## 3.2 CrowdSec Firewall Bouncer Installation

### Install CrowdSec Firewall Bouncer:

Execute the CrowdSec firewall installation script:

```bash
curl -s https://install.crowdsec.net | sudo sh
```

Install the firewall bouncer package:

```bash
sudo apt install crowdsec-firewall-bouncer-nftables
```

Add firewall bouncer via CrowdSec:

```bash
docker exec crowdsec cscli bouncers add firewall-bouncer
```

### Configure Firewall Bouncer:

Edit the firewall bouncer configuration:

```bash
sudo nano /etc/crowdsec/bouncers/crowdsec-firewall-bouncer.yaml
```

Lines to update:

```yaml
api_key: "your_generated_firewall_bouncer_api_key_here"
api_url: "http://127.0.0.1:9876/"
```

Restart the CrowdSec firewall bouncer:

```bash
sudo service crowdsec-firewall-bouncer restart
```

## 3.3 Adding a New CrowdSec Machine

To add a new CrowdSec machine:

```bash
docker exec -it crowdsec cscli machines add testMachine --force --password "your_password"
```

Add the generated API key (`crowdsecMachineApiKey`) into your previously created `secret.yml`:

```yaml
crowdsecMachineApiKey: "your_password"
```

## 4 Install SelfHosted

Run a Semaphore Task Template with:
- `Playbook`: `playbook.yml`
- `Inventory`: `inventory.yml`
- `Tags`: empty (full deploy)

---

## 5 Add Firewall

80, 443, 51820 - allow from any
22 (SSH) - only allow from my IP
