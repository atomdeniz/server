# Disaster Recovery

How to rebuild from nothing. The server's restore path is checked monthly by
`restic-restore-test`; this document covers the parts a script cannot.

## What you need outside this laptop and Hetzner

Keep these somewhere that survives losing both (password manager, paper):

| Item | Why |
|---|---|
| Vault password (`~/.vault_pass`) | Decrypts `secret.yml` |
| `restic_password` | Decrypts every backup |
| R2 Account ID, Access Key ID, Secret Access Key | Reach the offsite repo |
| AWS root login, `archive_crypt_password`, `archive_crypt_salt` | Restore photos from the Deep Archive |
| `~/.ssh/ansible` + passphrase | Optional: a new key can be bootstrapped |

`custom.yml` and the vault-encrypted `secret.yml` are copied into every backup
(`/opt/docker/backup/ansible-config/`), so with the items above they can be
recovered from R2.

## Where the data is

| Data | Location | Offsite copy |
|---|---|---|
| Server `/opt/docker` (configs, app data, DB dumps) | Storage Box `backup` repo + R2 `restic` | yes (R2) |
| Oracle `/opt/docker` (n8n, Grafana, changedetection) | R2 `restic/oracle` | yes (R2 only) |
| Immich originals (`upload`, `incoming`, `library`, `profile`) + FileBrowser | Storage Box | yes (AWS Deep Archive, rclone crypt) |
| Immich thumbs, encoded video | Storage Box | no (Immich regenerates them) |
| Traefik access logs, Grafana plugins | not backed up | — |

DB dumps in `/opt/docker/backup/db-dumps/`: `postgres.sql` (spliit, umami),
`immich.sql`, `vaultwarden.sqlite` (server), `n8n.sqlite`, `grafana.sqlite`
(Oracle). Restore from these, not from the live DB files in the snapshot.

## 0. If the laptop is gone

```bash
git clone https://github.com/atomdeniz/server.git && cd server
printf '%s' '<vault password>' > ~/.vault_pass && chmod 600 ~/.vault_pass
brew install restic ansible   # or your OS equivalent

export AWS_ACCESS_KEY_ID=<R2 key id> AWS_SECRET_ACCESS_KEY=<R2 secret>
export RESTIC_REPOSITORY=s3:https://<account id>.r2.cloudflarestorage.com/restic
restic restore latest --target ./recovered --include /opt/docker/backup/ansible-config
cp recovered/opt/docker/backup/ansible-config/{custom,secret}.yml . && rm -rf recovered
chmod 600 secret.yml
ansible-galaxy install -r requirements.yml
```

Generate a new SSH key if the old one is lost (`ssh-keygen -t ed25519 -f
~/.ssh/ansible`); `bootstrap.yml` installs it.

## 1. Rebuild the server (Hetzner)

1. Create an Ubuntu ARM64 VM. Recreate the cloud firewall (80/443 TCP, 443 UDP,
   8443 TCP, 51820 UDP) and temporarily allow 22/TCP from your IP.
2. Set the new `server_ip` in `custom.yml`. Every command below passes
   `-e server_ssh_host=<new ip>`, because the inventory normally connects over
   the VPN, which does not exist yet.
3. Bootstrap the `ansible` user (Hetzner's default user is `root`):

   ```bash
   ansible-playbook bootstrap.yml -i inventory.yml -e @custom.yml --limit server \
     -e bootstrap_user=root -e server_ssh_host=<new ip>
   ```

4. Base layer, Storage Box mount and restic, without any apps yet:

   ```bash
   ansible-playbook playbook.yml -i inventory.yml -e @custom.yml -e @secret.yml \
     --vault-password-file ~/.vault_pass --limit server -e server_ssh_host=<new ip> \
     --tags system,security,docker,storagebox,backup
   ```

   Then stop the nightly backup until the restore is done, so an empty
   `/opt/docker` does not become the newest snapshot:
   `systemctl stop restic-backup.timer` (via an ad-hoc Ansible shell).

5. Restore `/opt/docker` on the server (ad-hoc Ansible shell, as root). Use the
   Storage Box repo if it survived, otherwise R2:

   ```bash
   # Storage Box
   restic -r /mnt/storagebox/backup -p /etc/restic-password snapshots
   restic -r /mnt/storagebox/backup -p /etc/restic-password restore latest --target /
   # or R2
   set -a; . /etc/restic-r2.env; set +a
   restic -r "$(grep -o 's3:https://[^"]*' /usr/local/bin/restic-backup | head -1)" \
     -p /etc/restic-password restore latest --target /
   ```

6. Full deploy:

   ```bash
   ansible-playbook playbook.yml -i inventory.yml -e @custom.yml -e @secret.yml \
     --vault-password-file ~/.vault_pass --limit server -e server_ssh_host=<new ip>
   ```

   The `dns` role points the Cloudflare records at the new IP.

7. Load the database dumps (ad-hoc Ansible shell; `D=/opt/docker/backup/db-dumps`):

   ```bash
   # spliit + umami
   docker stop spliit umami
   docker exec -i postgres psql -U spliit -d postgres < $D/postgres.sql
   docker start spliit umami

   # Immich: the dump drops and recreates its DB, so stop the app first
   docker stop immich_server
   docker exec -i immich_postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres' < $D/immich.sql
   docker start immich_server

   # Vaultwarden
   docker stop vaultwarden
   rm -f /opt/docker/vw-data/db.sqlite3-wal /opt/docker/vw-data/db.sqlite3-shm
   cp $D/vaultwarden.sqlite /opt/docker/vw-data/db.sqlite3
   docker start vaultwarden
   ```

   Both Postgres dumps are taken with `--clean --if-exists`, so they drop and
   recreate their databases. "already exists" for roles and "current user
   cannot be dropped" are expected; anything else is not.

8. Restart the backup timer (`systemctl start restic-backup.timer`), then run
   `systemctl start restic-backup.service restic-restore-test.service` and
   check Telegram.

## 2. Rebuild Oracle

Same flow, with `--limit oracle`, `bootstrap_user=ubuntu` and the new
`oracle_ip` in `custom.yml`. There is no Storage Box: restore from R2 with the
`restic/oracle` prefix, then replace `n8n/database.sqlite` and
`grafana-data/grafana.db` with the dumps while the containers are stopped. Oracle
has no public ports: its VCN Security List must allow only 22/TCP from
`operator_ip` and `server_ip`.

## 3. Things that point at an IP

After an IP change, update these by hand:

- **Cloudflare R2 token** (`restic` bucket): client IP filter has `server_ip`
  and `oracle_ip`.
- **WireGuard clients**: wg-easy hands out `server_ip` as the endpoint. Change
  the host in the wg-easy UI and re-import the client configs.
- **Oracle**: redeploy `--limit oracle --tags system,tunnel` so its iptables
  allow the new `server_ip`; redeploy `--limit server --tags tunnel` if
  `oracle_ip` changed.
- **Hetzner firewall**: remove the temporary 22/TCP rule.
- **CrowdSec console**: re-enroll (`cscli console enroll`) if the machine was
  not restored.

## 4. Restore photos from the Deep Archive

Only when the Storage Box is gone. Objects are frozen: ask AWS to thaw them
first (Bulk, up to 48 h, ~$0.0025/GB), then download (~$0.09/GB after the first
free 100 GB/month). The `rclone-archive` key cannot restore, so use a session
from `aws login` (root).

```bash
brew install rclone awscli && aws login --region us-east-1
eval "$(aws configure export-credentials --format env)"
export RCLONE_CONFIG_S3_TYPE=s3 RCLONE_CONFIG_S3_PROVIDER=AWS RCLONE_CONFIG_S3_ENV_AUTH=true \
  RCLONE_CONFIG_S3_REGION=us-east-1 RCLONE_CONFIG_ARCHIVE_TYPE=crypt \
  RCLONE_CONFIG_ARCHIVE_REMOTE=s3:<bucket> \
  RCLONE_CONFIG_ARCHIVE_PASSWORD="$(rclone obscure '<archive_crypt_password>')" \
  RCLONE_CONFIG_ARCHIVE_PASSWORD2="$(rclone obscure '<archive_crypt_salt>')"

rclone backend restore s3:<bucket> -o priority=Bulk -o lifetime=14   # then wait
rclone copy archive: /mnt/storagebox --size-only --progress           # after the thaw
```

Paths come back as they were under the Storage Box (`immich/upload/...`,
`filebrowser/...`). Load `immich.sql` from restic afterwards so albums, faces
and metadata match.
