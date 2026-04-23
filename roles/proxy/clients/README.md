# Client Share Links

Substitute the placeholders with values from `secret.yml`
(view via `ansible-vault view secret.yml`) and `custom.yml` / `defaults/main.yml`.

## VLESS + XTLS-Vision + Reality (TCP 8443)

```
vless://{VLESS_UUID}@{PROXY_HOST}:8443?security=reality&encryption=none&pbk={REALITY_PUBLIC_KEY}&fp=chrome&type=tcp&flow=xtls-rprx-vision&sni=www.microsoft.com&sid={REALITY_SHORT_ID}#Reality
```

Fields:
- `VLESS_UUID` → `secret.yml::vless_reality_uuid`
- `PROXY_HOST` → `proxy.<root_host>` (or the server IP)
- `REALITY_PUBLIC_KEY` → paired public key of `secret.yml::reality_private_key`
- `REALITY_SHORT_ID` → `secret.yml::reality_short_id`

Supported clients: v2rayN, Nekoray, Streisand, Shadowrocket, V2RayNG, Hiddify.

## Hysteria2 (UDP 443)

```
hy2://{HYSTERIA_PASSWORD}@{PROXY_HOST}:443/?insecure=1&sni=www.microsoft.com&obfs=salamander&obfs-password={HYSTERIA_OBFS_PASSWORD}#Hysteria2
```

Fields:
- `HYSTERIA_PASSWORD` → `secret.yml::hysteria_password`
- `HYSTERIA_OBFS_PASSWORD` → `secret.yml::hysteria_obfs_password`
- `insecure=1` is required because the server uses a self-signed cert.

Supported clients: Nekoray, Hiddify, v2rayN (>= 7.x), Streisand, Shadowrocket, Hysteria native CLI.

## Generating Reality keys

Run once on any machine with Docker:

```
docker run --rm ghcr.io/xtls/xray-core:latest x25519
```

Output gives `Private key` (→ `reality_private_key`) and `Public key` (→ client share link).

Short ID:

```
openssl rand -hex 8
```
