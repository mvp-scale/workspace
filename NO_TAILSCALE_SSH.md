I only looked and changed nothing, because you're connected through Tailscale SSH right now and a wrong change could lock you out.

What's on the box

┌─────────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│        Item         │                                                                 State                                                                  │
├─────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Normal OpenSSH      │ Already running on port 22. Password login is on, and root can only log in with a key.                                                 │
│ (sshd)              │                                                                                                                                        │
├─────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Tailscale SSH       │ On (RunSSH: true). It intercepts port 22 on the Tailscale IP 100.104.41.45. That's why you get the check prompts, even though sshd is  │
│                     │ also there.                                                                                                                            │
├─────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Users               │ root and ubuntu (uid 1000, in the sudo group). Neither has an authorized_keys file, and ubuntu has no .ssh directory.                  │
├─────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ sudo                │ Not installed.                                                                                                                         │
├─────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Container network   │ Docker bridge at 172.20.0.2, so it isn't reachable from your LAN yet.                                                                  │
└─────────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

So most of this is already in place. You need a key-based user, and a way to reach port 22 that isn't Tailscale.

Guide

1. Create the user (inside the container)

apt-get update && apt-get install -y sudo
adduser --disabled-password --gecos "" corey      # use any username you like
usermod -aG sudo corey
echo 'corey ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/corey && chmod 440 /etc/sudoers.d/corey

2. Add your public key

On your own computer, generate a key if you don't have one:

ssh-keygen -t ed25519 -C "unraid-dev"
cat ~/.ssh/id_ed25519.pub     # copy this line

Then in the container:

install -d -m 700 -o corey -g corey /home/corey/.ssh
echo 'PASTE_PUBLIC_KEY_HERE' > /home/corey/.ssh/authorized_keys
chown corey:corey /home/corey/.ssh/authorized_keys && chmod 600 /home/corey/.ssh/authorized_keys

3. Lock down sshd

cat > /etc/ssh/sshd_config.d/10-hardening.conf <<'EOF'
PasswordAuthentication no
PermitRootLogin no
AllowUsers corey
EOF
sshd -t && systemctl reload ssh

4. Reach it without Tailscale (done on Unraid, not in the container)

In the Unraid Docker tab, edit this container and add a port mapping from host port 2222 to container port 22. Then test from a machine on your LAN:

ssh -p 2222 corey@<unraid-lan-ip>

If you also want access from outside your house, forward a router port to Unraid port 2222. Because that exposes SSH to the internet, keep password login off (step 3) and install fail2ban. Alternatively, a Cloudflare named tunnel can carry SSH. The cloudflared instances already running here only carry HTTP, so that would be a new setup.

5. Optional: stop Tailscale SSH from intercepting port 22

Only do this after step 4 works. Otherwise you'll lose your only way in.

tailscale set --ssh=false

After that, ssh corey@100.104.41.45 goes to the normal sshd with your key and no browser check. It's an alternative to step 4 if you're happy to keep using Tailscale as the network and only drop its SSH layer. It's also the simplest option, since steps 1 to 3 plus this one are all you need.

Recommendation

The simplest option is steps 1 to 3 plus step 5. You keep Tailscale as an encrypted private network, so nothing is exposed to the internet, and you drop only the paid-gated SSH check. Do step 4 only if you really want to avoid Tailscale entirely.

Want me to run steps 1 to 3 now? They're safe, because they don't touch your current session. Steps 4 and 5 I'd leave to you, since step 4 is on Unraid and step 5 would cut the connection you're using. If you want me to run them, tell me your public key and the username you'd like.

✻ Sautéed for 26s · done 12:02 PM