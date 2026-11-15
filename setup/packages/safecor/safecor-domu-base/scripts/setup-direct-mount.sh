#!/bin/sh
# Setup the direct USB mount in a DomU via vchan+sshfs.
# Queries the topology, generates the vchan client script, and mounts /media/usb.
#
# Copyright (c) 2024-2026, Tristan Israël
# Safecor Licence — see python/lib/LICENCE.md

SCRIPT_NAME=$(basename "$0")
MOUNT_POINT="/media/usb"
VCHAN_SFTP_SCRIPT="/usr/local/bin/vchan-sftp"

log() {
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "$1"
}

log_error() {
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.err "$1"
}

# Step 1: Query my_config via MQTT to check if this domain has direct_mount
HAS_DIRECT_MOUNT=$(python3 -c "
import sys
sys.path.insert(0, '/usr/lib/safecor')
import threading
from safecor import Api, MqttFactory, System, Topics

domain_name = System.domain_name()
result = [None]
event = threading.Event()

def on_ready():
    Api().subscribe(f'{Topics.MY_CONFIG}/response')
    Api().publish(f'{Topics.MY_CONFIG}/request', {'domain_name': domain_name})

def on_message(topic, payload):
    if topic == f'{Topics.MY_CONFIG}/response':
        result[0] = payload
        event.set()

mqtt_client = MqttFactory.create_mqtt_client_domu('setup-direct-mount')
Api().add_ready_callback(on_ready)
Api().add_message_callback(on_message)
Api().start(mqtt_client)

if not event.wait(timeout=10):
    sys.exit(1)

response = result[0]
if response:
    for d in response.get('domains', []):
        if d.get('name') == domain_name:
            dm = d.get('direct_mount')
            if dm:
                print(dm.get('mode', 'rw'))
                sys.exit(0)
sys.exit(1)
" 2>/dev/null)

if [ $? -ne 0 ] || [ -z "$HAS_DIRECT_MOUNT" ]; then
    log "This domain does not have direct_mount enabled, skipping"
    exit 0
fi

log "Direct mount enabled (mode: $HAS_DIRECT_MOUNT)"

# Step 2: Get sys-usb's domid from xenstore
SYS_USB_DOMID=""
for i in $(seq 1 30); do
    SYS_USB_DOMID=$(xenstore-read /local/domain/system/domids/sys-usb 2>/dev/null)
    if [ -n "$SYS_USB_DOMID" ]; then
        break
    fi
    sleep 2
done

if [ -z "$SYS_USB_DOMID" ]; then
    log_error "Cannot find sys-usb domid in xenstore"
    exit 1
fi

log "sys-usb domid: $SYS_USB_DOMID"

# Step 3: Generate the vchan-sftp client script
cat > "$VCHAN_SFTP_SCRIPT" << EOF
#!/bin/sh
exec vchan-socket-proxy -m client $SYS_USB_DOMID /local/domain/$SYS_USB_DOMID/data/vchan/sftp -
EOF
chmod +x "$VCHAN_SFTP_SCRIPT"
log "Generated $VCHAN_SFTP_SCRIPT"

# Step 4: Create the mount point
mkdir -p "$MOUNT_POINT"

# Step 5: Build sshfs options
SSHFS_OPTS="ssh_command=$VCHAN_SFTP_SCRIPT,noexec,nosuid,nodev,default_permissions,max_read=131072"
if [ "$HAS_DIRECT_MOUNT" = "ro" ]; then
    SSHFS_OPTS="$SSHFS_OPTS,ro"
fi

# Step 6: Mount
log "Mounting $MOUNT_POINT via sshfs"
sshfs -f -o "$SSHFS_OPTS" none:/ "$MOUNT_POINT" &
SSHFS_PID=$!
echo $SSHFS_PID > /var/run/safecor-direct-mount.pid
log "sshfs started with PID $SSHFS_PID"

# Give it a moment to establish
sleep 2

if kill -0 $SSHFS_PID 2>/dev/null; then
    log "Direct mount is ready at $MOUNT_POINT"
else
    log_error "sshfs process died during mount"
    exit 1
fi
