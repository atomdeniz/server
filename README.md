# SelfHosted

Ansible playbook for self-hosted infrastructure on Ubuntu ARM64. Manages reverse proxy, authentication, DNS, security, monitoring, VPN, and application services.

## Prerequisites

### 1. Server Setup

Provision the `ansible` user on a fresh server (generates SSH key, creates user, configures sudo):

```bash
./setup.sh <SERVER_IP>
```

### 2. Configuration Files

Copy and fill in the config templates:

```bash
cp .custom.yml custom.yml    # server connection, email, deploy settings
cp .secret.yml secret.yml    # all secrets (vault encrypted)
chmod 600 secret.yml
```

### 3. Install Dependencies

```bash
ansible-galaxy install -r requirements.yml
```

## Deploy

Full deploy:

```bash
ansible-playbook playbook.yml -i inventory.yml -e @custom.yml -e @secret.yml --vault-password-file ~/.vault_pass
```

Deploy specific role(s):

```bash
ansible-playbook playbook.yml -i inventory.yml -e @custom.yml -e @secret.yml --vault-password-file ~/.vault_pass --tags "traefik,authelia"
```

## Post-Deploy

After first CrowdSec deploy, enroll the agent:

```bash
docker exec crowdsec cscli console enroll -e context <key>
```
