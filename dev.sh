#!/bin/sh
#
# Host-side dev loop for a PillBoy running a pillboy-os -dev image.
# The device runs the app from /mnt/data/pillboy/src/main.py.
#
# Usage:
#   ./dev.sh sync [--restart]   rsync this working tree to the device (and restart the app)
#   ./dev.sh restart|start|stop|status
#                               control the app service on the device
#   ./dev.sh logs [-f]          print (or follow) the app log from the device
#   ./dev.sh screenshot [out]   grab the live screen as a PNG (default: ./screenshot.png)
#   ./dev.sh shell              open an SSH session on the device
#
# Target defaults to root@pillboy.local; override with PILLBOY_HOST / PILLBOY_USER.
#
# ---------------------------------------------------------------------------
# One-time connectivity setup (run on your Mac):
#
# 1. Connect the Pi Zero's *data* micro-USB port (inner one, labeled USB) to
#    your Mac -- one cable powers it and carries a USB-ethernet link. Enable
#    System Settings > Sharing > Internet Sharing for the RNDIS/Ethernet Gadget.
#
# 2. Add an SSH keypair to the device's authorized_keys (default root
#    password is "pillboy"):
#      ssh root@pillboy.local "mkdir -p ~/.ssh && chmod 700 ~/.ssh"
#      cat ~/.ssh/id_ed25519.pub | ssh root@pillboy.local \
#          "cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
#
# 3. (Optional) Add a Host entry to ~/.ssh/config to silence host-key prompts
#    across device re-flashes:
#      Host pillboy pillboy.local
#          HostName pillboy.local
#          User root
#          StrictHostKeyChecking no
#          UserKnownHostsFile /dev/null
#          LogLevel ERROR
# ---------------------------------------------------------------------------

set -eu

HOST="${PILLBOY_HOST:-pillboy.local}"
USER="${PILLBOY_USER:-root}"
DEST_DIR="/mnt/data/pillboy"
LOG_FILE="/mnt/data/logs/pillboy.log"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

usage() {
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
}

[ $# -ge 1 ] || usage
CMD="$1"
shift

case "$CMD" in
    sync)
        RESTART=""
        for arg in "$@"; do
            case "$arg" in
                --restart) RESTART="1" ;;
                *) echo "Unknown option: $arg" >&2; exit 1 ;;
            esac
        done
        rsync -avz --delete \
            --exclude 'dev.sh' \
            --exclude '.git/' \
            --exclude '.DS_Store' \
            --exclude '__pycache__/' \
            --exclude '*.pyc' \
            --exclude 'venv/' \
            --exclude '.venv/' \
            --exclude 'settings.json' \
            "$SCRIPT_DIR/" "$USER@$HOST:$DEST_DIR/"
        if [ -n "$RESTART" ]; then
            ssh "$USER@$HOST" "pillboy restart"
        fi
        ;;
    restart|start|stop|status)
        ssh "$USER@$HOST" "pillboy $CMD"
        ;;
    logs)
        if [ "${1:-}" = "-f" ]; then
            ssh "$USER@$HOST" "tail -n 50 -f $LOG_FILE"
        else
            ssh "$USER@$HOST" "cat $LOG_FILE"
        fi
        ;;
    screenshot)
        OUT="${1:-screenshot.png}"
        # SIGUSR2 makes the app dump its canvas (see src/main.py); the display
        # itself is write-only SPI so this is the only way to capture it.
        ssh "$USER@$HOST" \
            "kill -USR2 \$(cat /var/run/pillboy.pid) && sleep 1 && cat /tmp/pillboy-screenshot.png" > "$OUT"
        echo "saved $OUT"
        ;;
    shell)
        exec ssh "$USER@$HOST"
        ;;
    *)
        echo "Unknown command: $CMD" >&2
        usage
        ;;
esac
