# Setting Up Passwordless SSH Access for Ansible User

This guide will help you create an `ansible` user on an Ubuntu server and configure it for **key-based SSH login only** (without passwords).

---

## 1. Generate an SSH Key for Ansible
First, generate an SSH key pair on your local machine:

```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/ansible -N ""
```

- `~/.ssh/ansible` → Private key
- `~/.ssh/ansible.pub` → Public key

---

## 2. Create the `ansible` User on the Server
Connect to your server as root and run these commands:

```bash
useradd -m -s /bin/bash ansible  # Create the ansible user
passwd -l ansible  # Disable password-based login

mkdir -p /home/ansible/.ssh
chown -R ansible:ansible /home/ansible/.ssh
chmod 700 /home/ansible/.ssh
```

> `passwd -l ansible`: Disables password login, allowing only SSH key-based authentication.

---

## 3. SSH Authorization
Add your local **ansible.pub** key to the server:

```bash
cat ~/.ssh/ansible.pub | ssh root@SERVER_IP "mkdir -p /home/ansible/.ssh && cat >> /home/ansible/.ssh/authorized_keys && chown -R ansible:ansible /home/ansible/.ssh && chmod 600 /home/ansible/.ssh/authorized_keys"
```

> The `authorized_keys` file stores public keys authorized for SSH access.

---

## 4. Test SSH Connection
Now, you should be able to SSH into the server as the `ansible` user without a password:

```bash
ssh -i ~/.ssh/ansible ansible@SERVER_IP
```

If no password is prompted, the setup was successful. 🎉

---

## 5. Simplify SSH Configuration (Optional)
To simplify the SSH connection, add the following lines to your `~/.ssh/config` file:

```bash
echo -e "Host ansible-server\n  HostName SERVER_IP\n  User ansible\n  IdentityFile ~/.ssh/ansible\n  StrictHostKeyChecking no" >> ~/.ssh/config
chmod 600 ~/.ssh/config
```

From now on, connect to the server simply with:

```bash
ssh ansible-server
```

That's it! You can now log in as the **ansible** user via **passwordless SSH**. 🚀

---

## 6. Grant Sudo Privileges to the Ansible User

### **1. Add Ansible User to the `sudo` Group**
```bash
usermod -aG sudo ansible
```

### **2. Update the `sudoers` File**
```bash
echo "ansible ALL=(ALL) NOPASSWD:ALL" | tee /etc/sudoers.d/ansible
```
This command gives the `ansible` user **passwordless sudo privileges**.

### **3. Verify the Privileges**
Connect as the `ansible` user via SSH and run:
```bash
sudo whoami
```
If the output is `root`, then sudo privileges have been successfully granted. ✅

