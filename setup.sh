#!/usr/bin/env bash
set -euo pipefail

# Setup script for provisioning the ansible user on a fresh Ubuntu server.
# Usage: ./setup.sh <SERVER_IP>

if [ $# -lt 1 ]; then
  echo "Usage: $0 <SERVER_IP>"
  exit 1
fi

SERVER_IP="$1"
SSH_KEY="$HOME/.ssh/ansible"
SSH_USER="ansible"

# 1. Generate SSH key if it doesn't exist
if [ ! -f "$SSH_KEY" ]; then
  echo "Generating SSH key at $SSH_KEY..."
  ssh-keygen -t rsa -b 4096 -f "$SSH_KEY" -N ""
else
  echo "SSH key already exists at $SSH_KEY, skipping."
fi

# 2. Create ansible user, set up SSH auth, and grant sudo on the server
echo "Setting up $SSH_USER user on $SERVER_IP..."
ssh "root@${SERVER_IP}" bash -s <<'REMOTE'
  set -euo pipefail

  USERNAME="ansible"

  # Create user if it doesn't exist
  if ! id "$USERNAME" &>/dev/null; then
    useradd -m -s /bin/bash "$USERNAME"
    passwd -l "$USERNAME"
    echo "Created user $USERNAME."
  else
    echo "User $USERNAME already exists, skipping."
  fi

  # SSH directory
  mkdir -p "/home/${USERNAME}/.ssh"
  chown -R "${USERNAME}:${USERNAME}" "/home/${USERNAME}/.ssh"
  chmod 700 "/home/${USERNAME}/.ssh"

  # Sudo privileges
  if [ ! -f "/etc/sudoers.d/${USERNAME}" ]; then
    usermod -aG sudo "$USERNAME"
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}"
    chmod 440 "/etc/sudoers.d/${USERNAME}"
    echo "Granted passwordless sudo to $USERNAME."
  else
    echo "Sudo already configured, skipping."
  fi
REMOTE

# 3. Copy public key to server
echo "Copying public key to $SERVER_IP..."
ssh-copy-id -i "$SSH_KEY" "${SSH_USER}@${SERVER_IP}" 2>/dev/null || {
  cat "${SSH_KEY}.pub" | ssh "root@${SERVER_IP}" \
    "cat >> /home/${SSH_USER}/.ssh/authorized_keys && chown ${SSH_USER}:${SSH_USER} /home/${SSH_USER}/.ssh/authorized_keys && chmod 600 /home/${SSH_USER}/.ssh/authorized_keys"
}

# 4. Add SSH config entry
if ! grep -q "Host ansible-server" "$HOME/.ssh/config" 2>/dev/null; then
  echo "Adding SSH config entry..."
  cat >> "$HOME/.ssh/config" <<EOF

Host ansible-server
  HostName ${SERVER_IP}
  User ${SSH_USER}
  IdentityFile ${SSH_KEY}
  StrictHostKeyChecking no
EOF
  chmod 600 "$HOME/.ssh/config"
else
  echo "SSH config entry already exists, skipping."
fi

# 5. Verify connection
echo "Verifying SSH connection..."
if ssh -i "$SSH_KEY" "${SSH_USER}@${SERVER_IP}" "sudo whoami" | grep -q "root"; then
  echo "Setup complete. Connect with: ssh ansible-server"
else
  echo "ERROR: SSH connection or sudo verification failed."
  exit 1
fi
