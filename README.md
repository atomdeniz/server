# SelfHosted Setup Guide

This document outlines the steps required for installing and configuring SelfHosted using Ansible.

## Project Overview

This project aims to create a secure, efficient, and highly maintainable self-hosting infrastructure. By leveraging modern tools such as Authelia for secure authentication, Traefik for reverse proxy and SSL management, CrowdSec for real-time security protection, and AdGuard combined with Unbound for secure DNS resolution, this setup provides privacy, security, and ease of use for self-hosted services.

I am currently running the whole process only on Ubuntu.

**Traefik:** Reverse proxy and automatic SSL handling.

**Authelia:** Two-factor authentication for protecting web applications.

**CrowdSec:** Intrusion detection and prevention system, actively blocking malicious activities.

**AdGuard & Unbound:** DNS filtering and secure DNS resolution with DNS-over-HTTPS (DoH).

**Docker Socket Proxy:** Secure Docker socket management.

**N8N**: MCP

**Grafana, Prometheus, cAdvisor, node_exporter:** Comprehensive monitoring and visualization of infrastructure metrics.

**Homepage & Uptime Kuma:** Easy-to-navigate dashboard and uptime monitoring for hosted services.

**V2ray (vmess/vless on WS), Trojan, WireGuard:** Secure VPN and proxy solutions ensuring privacy.

**Vaultwarden:** Self-hosted password management.

**Watchtower:** Automatic Docker container updates.

**Whoami:** Simple service for testing and debugging HTTP requests.

**Security Enhancements:** AppArmor profiles and iptables rules for further security hardening.

## 0 Set User

[Set User](https://github.com/atomdeniz/server/blob/main/USER.md)


## 1. Load SSH Key

Load the SSH key to use with Ansible connections:

```bash
eval $(ssh-agent)
ssh-add ~/.ssh/ansible
```

## 2. Managing ENV

### Create custom.yml File

Copy the .custom.yml file as custom.yml and fill it in

### Create and Secure the Secret YAML File:

```bash
touch secret.yml
chmod 600 secret.yml
```

### Encrypt the Secret YAML File with Ansible Vault:

```bash
ansible-vault encrypt secret.yml
```

### Edit the Encrypted YAML File:

Example: Using '.secret.yml' as a reference, add your secrets in the following format:
```bash
EDITOR=nano ansible-vault edit secret.yml
```

## 3.1 CrowdSec Installation

Run the Ansible playbook to install CrowdSec:

```bash
ansible-playbook -i inventory.yml playbook.yml --tags "system,security,docker,crowdsec"
```

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

## 4 Install SelfHosted
Then rerun the Ansible playbook:

```bash
ansible-playbook -i inventory.yml playbook.yml
```
---


## 5 Add DNS Record To Cloudflare

You can use a different DNS solution, but you'll need to update Traefik's middleware configuration and adjust your SSL settings accordingly.

Cloudflare:

[cf-dns-records.png](https://github.com/atomdeniz/server/blob/main/cf-dns-records.png)

## 6 Add Firewall

[firewall.png](https://github.com/atomdeniz/server/blob/main/firewall.png)