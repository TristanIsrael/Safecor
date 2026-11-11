# Direct USB Mount from sys-usb via vchan

> **Status**: Draft
>
> **Last updated**: 2026-11-11
>
> **Version**: 2
>
> **Context**: Reduce attack surface by eliminating the 9p storage share as the file transfer path.
> Enable DomUs to mount a USB folder directly from sys-usb over a vchan socket with sshfs.

---

## 1. Problem Statement

### 1.1 Current data flow

Today, when a DomU application reads a file from a USB disk:

1. The DomU calls `Api.read_file(disk, filepath)`, which publishes a `READ_FILE/request` on MQTT.
2. The `Dom0Controller` (in Dom0) or `SysUsbController` (in sys-usb) receives the request.
3. The `SysUsbController` in sys-usb:
   - Reads the file from `/media/usb/{disk}/{filepath}`.
   - **Copies it into the repository at `/usr/lib/safecor/storage/{filepath}`** (Dom0 side).
   - The file is thus staged on Dom0 before it can be consumed by antivirus analysis.
4. The DomU accesses the file via its 9p-mounted repository at `/mnt/storage/{filepath}`.

This flow has a **security problem**: the repository lives on Dom0, and a 9p transport exists
between every DomU and Dom0. Any file transferred via USB passes through Dom0's filesystem
before being made available to the requesting DomU. The 9p share is a wide attack surface —
a compromised DomU could potentially access files belonging to other DomUs.

### 1.2 Objectives

| # | Objective | Priority |
|---|-----------|----------|
| 1 | Eliminate the file-copy-to-repository step for USB file access | **P0** |
| 2 | Allow a DomU to mount `/media/usb` from sys-usb directly, over a vchan | **P0** |
| 3 | Deprecate the 9p storage share (`/mnt/storage` via 9p `trans=xen`) | **P1** (future) |
| 4 | Replace the 9p share with a share on an encrypted virtual disk | **P2** (future, backlog) |

**Version 2 scope**: objectives 1 and 2 only. The 9p share and encrypted disk are explicitly
**out of scope** for this version.

### 1.3 Key design constraints

- The vchan data path must bypass Dom0 — no file data passes through Dom0's filesystem.
- Dom0 remains the orchestrator: it creates DomUs via `xl`, writes domids to xenstore,
  and responds to `system/topology/my_config` queries.
- No new network interfaces are required (vchan is a Xen hypervisor channel, not network).

### 1.4 Non-functional requirements (Safecor API)

| # | NFR | Rationale |
|---|-----|-----------|
| NFR-1 | Functions called from MQTT callbacks must be **non-blocking**. | MQTT callbacks run in the event loop; a blocking call (sleep, polling, I/O with timeout) would stall all other message processing. Long-running or retry logic must be delegated to the caller (e.g., `DirectMountManager`) which runs in its own thread/task. |
| NFR-2 | Functions called from MQTT callbacks must have **error handling** (no unhandled exceptions). | An unhandled exception in a callback can crash the MQTT handler or leave the system in an inconsistent state. All public API methods must catch and log exceptions, returning a safe default or raising a typed error. |

---

## 2. Target Architecture

### 2.1 High-level data flow (after implementation)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         sys-usb (DomU)                              │
│                                                                     │
│  USB disk → /media/usb/                                              │
│      │                                                               │
│      ▼                                                               │
│  SFTP server (sftp-server, chroot /media, per-DomU vchan)            │
│      ▲                                                               │
│      │  vchan (XEN pvchan, bidirectional)                            │
└──────┼──────────────────────────────────────────────────────────────┘
       │
       │  vchan-socket-proxy (XEN)  ←→  vchan-socket-proxy
       │
┌──────┼──────────────────────────────────────────────────────────────┐
│                         Business DomU                                │
│                                                                     │
│      ▼                                                               │
│  /usr/local/bin/vchan-sftp                                           │
│  (exec vchan-socket-proxy -m client <domid> ...)                     │
│      ▲                                                               │
│      │  used as sshfs transport (ssh_command option)                 │
│      ▼                                                               │
│  sshfs — mounts remote filesystem (sys-usb's /media/usb)             │
│      │                                                               │
│      ▼                                                               │
│  /media/usb              (local FUSE mount point in DomU)            │
│  Access to all USB disks connected to sys-usb                         │
│      │                                                               │
│      ▼                                                               │
│  Product application reads files directly                            │
└─────────────────────────────────────────────────────────────────────┘

No data passes through Dom0. No 9p storage share is used.
```

### 2.2 Component responsibilities

| Component | Runs in | Responsibility |
|-----------|---------|----------------|
| **vchan-socket-proxy** | sys-usb | Accepts incoming vchan connections from DomUs, creates a UNIX socket that each DomU can connect to. Part of XEN tooling. |
| **sftp-server** | sys-usb | Runs on top of each vchan (via socat), serving files from `/media/usb` in a chroot jail. From `openssh-sftp-server` package. |
| **socat** | sys-usb | Bridges the vchan UNIX socket to `sftp-server` (spawns it per connection in chroot). |
| **vchan-sftp script** | Business DomU | A thin shell script (`/usr/local/bin/vchan-sftp`) that runs `vchan-socket-proxy -m client`. Used as sshfs's `ssh_command` transport. |
| **sshfs** | Business DomU | Mounts the remote filesystem (sys-usb's `/media/usb`) over the vchan transport (via `ssh_command` option). |
| **FUSE** | Business DomU | User-space filesystem kernel module that enables sshfs to mount the remote filesystem in user-space. |
| **Mount manager (new)** | Business DomU | Safecor component that manages the lifecycle: query topology, get domid, generate vchan-sftp script, trigger mount/unmount, handle errors, report mount state. |

---

## 3. Technical Design

### 3.1 End-to-end flow (topology.json → sshfs mount)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  topology.json (on Dom0)                                                    │
│                                                                             │
│  { "usb": { "use": 1 },                                                     │
│    "business": { "domains": [                                              │
│      { "name": "saphir-av-clamav", "direct_mount": {"mode":"ro"} },        │
│      { "name": "saphir-av-eset",   "direct_mount": {"mode":"rw"} }         │
│    ] } }                                                                    │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                    │
                     Orchestrator (Dom0) creates DomUs via xl
                                    │
               ┌────────────────────┴────────────────────┐
               │                                         │
               ▼                                         ▼
┌─────────────────────────────────┐     ┌──────────────────────────────────────┐
│  sys-usb boots                  │     │  saphir-av-clamav boots               │
│                                 │     │                                      │
│  1. Reads topology              │     │  1. Connects to MQTT                 │
│     → list of authorized DomUs  │     │  2. Queries Dom0:                    │
│                                 │     │     system/topology/my_config        │
│  2. Reads xenstore              │     │     → { direct_mount: {mode:"ro"} }  │
│     /local/domain/system/domids │     │  3. Reads xenstore                   │
│     → gets each DomU's domid    │     │     /local/domain/system/domids      │
│                                 │     │     → gets sys-usb's domid           │
│  3. For each authorized DomU:   │     │  4. Writes /usr/local/bin/vchan-sftp:│
│     a. vchan-socket-proxy       │     │     exec vchan-socket-proxy          │
│        -m server <domid_domu>   │     │       -m client <domid_sys_usb>      │
│        /local/domain/<domid>/   │     │       /local/domain/<domid>/         │
│         data/vchan/sftp -       │     │         data/vchan/sftp -            │
│     b. socat ...                │     │  5. Runs:                            │
│        EXEC:"chroot /media      │     │     sshfs -f                         │
│         /usr/lib/ssh/           │     │       -o ssh_command=/usr/local/     │
│         sftp-server"            │     │           bin/vchan-sftp,            │
│                                 │     │           noexec,nosuid,nodev,       │
│  4. Waits for connections       │     │           default_permissions,       │
│                                 │     │           max_read=131072            │
│                                 │     │       none:/ /media/usb              │
└─────────────────────────────────┘     │  6. /media/usb is mounted            │
                                        └──────────┬───────────────────────────┘
                                                   │ vchan (XEN)
                                                   ▼
                                        ┌──────────────────────────┐
                                        │  sys-usb (per-DomU)      │
                                        │  vchan-socket-proxy      │
                                        │    -m server <domid_domu>│
                                        │    /local/domain/<domid> │
                                        │     /data/vchan/sftp -   │
                                        └──────────────────────────┘
```

### 3.2 Domid discovery (synchronization)

`vchan-socket-proxy` requires the peer's `domid` to establish a channel. Both sides need
to discover the other's domid before connecting.

**Problem**: DomUs cannot read xenstore entries of other domains
(`/local/domain/<domid>/name` is restricted to the owning domain and Dom0).

**Solution: `/local/domain/system` shared section** (existing mechanism).

The `/local/domain/system` xenstore section is already readable by all DomUs (permissions
set by `set-xenstore-permissions.sh`: `xenstore-chmod -r /local/domain/system r`).
It is already used by `write-screen-information-to-xenstore.py` to publish screen rotation.

We extend this section with a `domids` subtree:

```
/local/domain/system/
├── screen_rotation          ← existing
└── domids/
    ├── sys-usb              ← "3" (domid of sys-usb)
    ├── saphir-av-clamav     ← "4"
    ├── saphir-av-eset       ← "5"
    └── ...
```

**Writer**: The orchestrator (in Dom0) writes each domain's domid after `xl create`:
```bash
xenstore-write /local/domain/system/domids/<domain_name> <domid>
```

**Timing**:
- Written at **domain creation** by the orchestrator (Dom0) after `xl create` reports the domid.
- **Updated on domain restart** — the orchestrator re-writes the new domid.

**Reader**: Any DomU reads the section to find sys-usb's domid:
```bash
xenstore-read /local/domain/system/domids/sys-usb
# → "3"
```

**Why this works:**
- No new xenstore permissions needed (section already readable by DomUs)
- No MQTT dependency (xenstore is available at boot)
- Follows the existing pattern (`write-screen-information-to-xenstore.py`)
- Dom0 is the single writer (no race conditions)

**Error handling: non-deterministic availability**

The domain boot order is non-deterministic. Two failure cases must be handled:

1. **Initial boot**: when a DomU queries xenstore, sys-usb's domid may not yet be written
   (sys-usb hasn't been created yet by the orchestrator, or the orchestrator hasn't had
   time to write it after `xl create`).
2. **Domain restart**: when a domain is restarted, its domid changes. The xenstore entry
   is transiently inconsistent (old domid or missing) until the orchestrator re-writes it.

**Solution: polling with retry.**

The reader (DomU's `DirectMountManager` or init script) polls xenstore with a timeout,
then attempts the vchan connection. Connection failure itself is the detection mechanism
for stale or invalid domids:

```bash
# Poll until the domid appears (timeout: 60s, interval: 2s)
timeout=60
interval=2
elapsed=0
while [ $elapsed -lt $timeout ]; do
    domid=$(xenstore-read /local/domain/system/domids/sys-usb 2>/dev/null)
    if [ -n "$domid" ]; then
        break
    fi
    sleep $interval
    elapsed=$((elapsed + interval))
done

# Attempt vchan connection with retry (handles stale domid after restart)
max_retries=10
retry_interval=5
attempt=0
while [ $attempt -lt $max_retries ]; do
    # Generate the vchan-sftp script with current domid
    generate_vchan_sftp_script "$domid"
    # Try to mount (this will fail if the domid is stale)
    if sshfs -f -o ssh_command=/usr/local/bin/vchan-sftp,... none:/ /media/usb; then
        break
    fi
    # Re-read domid (may have been updated by orchestrator)
    domid=$(xenstore-read /local/domain/system/domids/sys-usb 2>/dev/null)
    sleep $retry_interval
    attempt=$((attempt + 1))
done
```

**Retry logic** (to detect stale domids after restart):
- If the vchan connection fails (`vchan-socket-proxy` returns an error because the peer
  domain doesn't exist or the channel was never created), the DomU should:
  1. Wait for a retry interval (e.g., 5s).
  2. Re-read the domid from xenstore (it may have been updated by the orchestrator).
  3. Retry the connection (up to N attempts, e.g., 10).
  4. If all retries fail, log the error and stop.

**On the sys-usb side** (server), the same logic applies in reverse:
- The init script reads `/local/domain/system/domids/<domain_name>` for each authorized DomU.
- If a DomU's domid is not yet present, the script polls until it appears (or times out).
- On DomU restart, the server must handle the case where the old vchan channel disappears
  and a new one must be established with the new domid (the init script or a monitoring
  loop re-reads the domid and restarts the proxy).

**Design choice**: simple polling (2s interval, 60s timeout) is preferred over xenstore
watch events because:
- It's easier to implement in shell scripts and Python
- The window of inconsistency is short (seconds, not minutes)
- It avoids the complexity of xenstore watch callbacks and reconnection logic

### 3.3 vchan setup

XEN vchan (pvchan) provides a bidirectional Unix-domain-like socket between two domains.
The `vchan-socket-proxy` tool (from the `xen` package) sits on both sides.

**Prerequisites (both sys-usb and DomU):**
- Install the `xen` package (provides `vchan-socket-proxy` and kernel modules).
- Load kernel modules: `modprobe xen_gntdev xen_gntalloc xen_evtchn`
- DomU additionally needs: `modprobe fuse` (and the `fuse3` package installed)

**Per-DomU vchan channels**: sys-usb must serve multiple DomUs simultaneously. Each DomU
that has access (declared in `topology.json`) gets its own vchan channel.

**Server-side (sys-usb, per authorized DomU):**

```bash
# <domid_client>: the Xen domain ID of the connecting DomU
#   (read from /local/domain/system/domids/<domain_name>)
# <domid_server>: sys-usb's own domain ID
vchan-socket-proxy -m server <domid_client> /local/domain/<domid_server>/data/vchan/sftp -

# socat: spawn sftp-server in a chroot jail for each connection
socat -b 131072 UNIX-LISTEN:/tmp/sftp-{domid_client}.sock,fork \
  EXEC:"chroot /media /usr/lib/ssh/sftp-server"
```

**Client-side (DomU):**

The client side does **not** use socat. Instead, sshfs is configured with the
`ssh_command` option, which replaces the SSH transport with our vchan script.

```bash
# /usr/local/bin/vchan-sftp (generated at boot with the correct domid):
#!/bin/sh
# sshfs adds its own arguments, we ignore them
exec vchan-socket-proxy -m client <domid_sys_usb> /local/domain/<domid_sys_usb>/data/vchan/sftp -

# Mount command:
sshfs -f -o ssh_command=/usr/local/bin/vchan-sftp,noexec,nosuid,nodev,default_permissions,max_read=131072 none:/ /media/usb
```

**Pipeline:**
- **Server (sys-usb)**: vchan → `vchan-socket-proxy` → socat → `chroot /media` → `sftp-server`
- **Client (DomU)**: sshfs → `ssh_command` → `vchan-socket-proxy` → vchan (XEN)

**Key parameters:**
- Per-DomU isolation: each DomU gets its own vchan channel, identified by the DomU's `domid`
- UNIX socket path (sys-usb side): `/tmp/sftp-{domid_client}.sock` (one per DomU)
- The vchan identifier in xenstore: `/local/domain/<domid_server>/data/vchan/sftp`
- Buffer size: 131072 bytes (128 KiB) for the socat tunnel (server side only)
- `sftp-server` is executed directly (no SSH daemon layer) — it speaks the SFTP protocol
  over the raw vchan stream
- **No SSH authentication**: sshfs's `ssh_command` bypasses the SSH protocol entirely;
  the SFTP protocol runs directly over the vchan stream

### 3.4 SFTP server on sys-usb (security)

**Choice: `sftp-server` from `openssh-sftp-server` package (Alpine).**

`sftp-server` is invoked directly by `socat` (via `EXEC`) for each incoming connection.
Security is enforced through **chroot**:

```bash
# The sftp-server runs in a chroot jail rooted at /media
# It can only see files under /media/ (i.e., /media/usb/*)
socat ... EXEC:"chroot /media /usr/lib/ssh/sftp-server"
```

**Chroot jail setup** (performed by the init script at boot):
```
/media/                          ← chroot root
├── usb/                         ← actual USB mounts (visible as /usb/ in the jail)
├── usr/lib/ssh/sftp-server     ← the sftp-server binary (copied or symlinked)
└── lib/                         ← required shared libraries (ldd /usr/lib/ssh/sftp-server)
```

**Security properties:**
- `sftp-server` cannot access any file outside `/media/` (chroot boundary)
- No SSH daemon (`sshd`) — no shell, no port forwarding, no agent forwarding
- No password authentication — the SFTP stream is raw (no SSH layer)
- The vchan channel is point-to-point (only the authorized DomU's domid can connect)
- Package: `openssh-sftp-server` (Alpine)

> **Note**: since we bypass `sshd` entirely, there is no SSH authentication layer.
> The security relies on: (1) Xen vchan isolation (only the specified domid can connect),
> (2) chroot (limits file access), (3) the DomU being a trusted Xen domain.
> If SSH-level encryption is required in the future, an SSH layer can be added
> between the vchan and sftp-server.

### 3.5 Client-side setup (Business DomU)

The DomU needs the following pipeline to bridge vchan → sshfs:

```
sshfs → ssh_command (/usr/local/bin/vchan-sftp) → vchan-socket-proxy → FUSE → /media/usb
```

**Prerequisites (DomU):**
- Install the `xen` package (provides `vchan-socket-proxy` and kernel modules).
- Load kernel modules: `modprobe xen_gntdev xen_gntalloc xen_evtchn`
- Install the `fuse3` package and load the `fuse` module: `modprobe fuse`
- No SSH keys needed (the `ssh_command` option bypasses SSH entirely)

**Boot-time steps (init script or `DirectMountManager`):**
1. Read sys-usb's domid from xenstore: `xenstore-read /local/domain/system/domids/sys-usb`
2. Generate `/usr/local/bin/vchan-sftp` with the correct domid:
   ```sh
   #!/bin/sh
   exec vchan-socket-proxy -m client <domid_sys_usb> /local/domain/<domid_sys_usb>/data/vchan/sftp -
   ```
3. Create mount point: `mkdir -p /media/usb`
4. Mount (adding `ro` to the options if the topology specifies `"mode": "ro"`):
   ```bash
   # Read-write (default):
   sshfs -f -o ssh_command=/usr/local/bin/vchan-sftp,noexec,nosuid,nodev,default_permissions,max_read=131072 none:/ /media/usb

   # Read-only:
   sshfs -f -o ro,ssh_command=/usr/local/bin/vchan-sftp,noexec,nosuid,nodev,default_permissions,max_read=131072 none:/ /media/usb
   ```

**Key considerations:**
- `sshfs` with `ssh_command` replaces the SSH transport — no SSH daemon, no keys, no host key checking
- `noexec,nosuid,nodev` — security flags to restrict the mounted filesystem
- `default_permissions` — enforce file permission checks in the kernel
- `max_read=131072` — 128 KiB read buffer for performance
- Single mount point: `/media/usb` gives access to all USB disks connected to sys-usb

### 3.6 Mount lifecycle management (new Safecor component)

A new component — `DirectMountManager` — will be added to the Safecor library:

**Location**: `python/lib/src/safecor/_direct_mount_manager.py`

**Responsibilities:**
1. **Query topology** — on startup, request the DomU's own configuration from the topology
   (via `system/topology/my_config`). Determine if `direct_mount` is enabled.
2. **Get sys-usb domid** — poll `System.get_domain_domid("sys-usb")` until it returns a value
   (retry logic lives here, not in `System`).
3. **Generate vchan-sftp script** — write `/usr/local/bin/vchan-sftp` with the correct domid.
4. **Mount** — run `sshfs -f -o ssh_command=/usr/local/bin/vchan-sftp,...` to mount `/media/usb`.
5. **Unmount** — handle unmount and cleanup.
6. **Handle** — connection errors, retries, and cleanup.

**New methods on `System` class** (`python/lib/src/safecor/_system.py`):

```python
def get_domain_domid(self, domain_name: str) -> Optional[int]:
    """Return the Xen domain ID of the named domain, or None if not yet available.

    Performs a single non-blocking read from xenstore:
        /local/domain/system/domids/<domain_name>

    Does NOT poll or sleep (NFR-1: non-blocking for MQTT callback context).
    The caller is responsible for retrying if None is returned.

    Args:
        domain_name: The domain name (e.g., "sys-usb").

    Returns:
        The integer domid, or None if the entry is not yet present in xenstore.
    """

def get_current_domid(self) -> int:
    """Return the Xen domain ID of the current domain.

    Non-blocking (NFR-1 compliant). The domid is read from xenstore or
    the Xen hypercall interface at first call, then cached.

    Returns:
        The integer domid of this domain.
    """

def is_usb_mountpoint_ready(self) -> bool:
    """Return True if the USB mount point (Constants.USB_MOUNT_POINT) is available.

    Non-blocking filesystem check (NFR-1 compliant). Usable from any context,
    including product applications that cannot access DirectMountManager
    (which runs in a separate process managed by openrc).

    Returns:
        True if /media/usb is mounted and accessible, False otherwise.
    """

def on_usb_mountpoint_ready(self, callback: Callable[[], None]) -> None:
    """Register a callback to be invoked when the USB mount point becomes ready.

    Event-driven notification: the caller registers a callback and does not need
    to poll. Internally, a background watcher thread in System monitors the mount
    point and invokes the callback when it becomes available.

    The callback is invoked in the watcher thread (not the MQTT event loop),
    so it must be thread-safe.

    Args:
        callback: A callable with no arguments, invoked once when the mount point
                  transitions from unready to ready.

    Note:
        The callback is invoked at most once per mount cycle (i.e., if the mount
        is unmounted and remounted, a new registration is needed for the next
        notification).
    """
```

> **Note**: `DirectMountManager` runs in its own process (started by openrc). Product
> applications cannot call its methods directly. They use `System.is_usb_mountpoint_ready()`
> or `System.on_usb_mountpoint_ready(callback)` to check/wait for mount availability.

**Watcher thread implementation** (inside `System`):
- A single background daemon thread starts lazily on the first `on_usb_mountpoint_ready()` call.
- It polls `is_usb_mountpoint_ready()` every 2 seconds.
- On the first `False → True` transition, it invokes all registered callbacks and stops polling.
- If the mount is unmounted and remounted, the app must re-register (one-shot semantics).
- The thread is daemon (does not prevent process exit) and is stopped if `System` is reset.

**Polling strategy in `DirectMountManager`** (not in `System`):

The retry/poll loop lives in `DirectMountManager` which runs in its own thread/task,
not in the MQTT callback context. This respects NFR-1 (non-blocking API):

```python
def _wait_for_domid(self, domain_name: str, timeout: int = 60, interval: float = 2.0) -> Optional[int]:
    """Poll System.get_domain_domid() until a value is returned or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        domid = self._system.get_domain_domid(domain_name)
        if domid is not None:
            return domid
        time.sleep(interval)
    return None
```

**Auto-connect flow (on DomU boot):**
```
1. DirectMountManager starts
2. Query topology: "Am I allowed to direct-mount?" → system/topology/my_config
   → { direct_mount: { mode: "ro" | "rw" } }
3. If yes → System.get_domain_domid("sys-usb") → get domid (polls xenstore)
4. Write /usr/local/bin/vchan-sftp with the domid
5. mkdir -p /media/usb
6. Run sshfs -f -o [ro,]ssh_command=/usr/local/bin/vchan-sftp,...
   (add "ro" to options if mode is "ro")
```

**Public API (for DomU applications):**

```python
class DirectMountManager:
    def start(self) -> None
        """Initiate the auto-connect flow: query topology, connect vchan, mount."""

    def stop(self) -> None
        """Unmount /media/usb and disconnect the vchan channel."""

    def is_mounted(self) -> bool
        """Check if /media/usb is currently mounted from sys-usb."""

    def get_mount_point(self) -> str
        """Return the local mount path ('/media/usb')."""
```

**MQTT integration:**
- On start: query `system/topology/my_config` to determine if this DomU has direct mount access.
- If yes: call `System.get_domain_domid("sys-usb")` to get the domid.
- Generate `/usr/local/bin/vchan-sftp` and run `sshfs` to mount `/media/usb`.

### 3.7 New MQTT topics

| Topic | Direction | Description |
|-------|-----------|-------------|
| `system/topology/my_config` | Request/Response | DomU queries its own topology configuration. Response includes `direct_mount` object (with `mode`) if enabled. |

> **Note**: Domain ID discovery (domid lookup by name) is handled via **xenstore**
> (`/local/domain/system/domids/<domain_name>`), not via MQTT. No `system/info/domain_id`
> topic is needed. The mount state is observable locally via
> `System.is_usb_mountpoint_ready()` or `System.on_usb_mountpoint_ready(callback)`.

### 3.6 Topology extension

The topology file declares which DomUs have access to sys-usb direct mounts. Each business
domain that needs access gets a `direct_mount` field in its declaration:

```json
{
    "usb": {
        "use": 1
    },
    "repository": {
        "disabled": false
    },
    "business": {
        "domains": [
            {
                "name": "saphir-av-clamav",
                "app-package": "safecor-saphir-av-clamav",
                "memory": 512,
                "direct_mount": { "mode": "ro" }
            },
            {
                "name": "saphir-av-eset",
                "app-package": "safecor-saphir-av-eset",
                "memory": 512,
                "direct_mount": { "mode": "rw" }
            }
        ]
    }
}
```

- `repository.disabled` (boolean, default `false`): set to `true` to disable the 9p
  repository share (`/mnt/storage` in DomUs) for high-security deployments.
  When disabled, DomUs cannot access the repository via 9p; the direct mount is the
  only file access path. Absent or `false` = enabled (backward compatible).
- `business.domains[].direct_mount` — per-DomU object: if present, this DomU gets a vchan
  channel from sys-usb and will auto-mount `/media/usb`.
  - `mode` (string, default `"rw"`): `"ro"` for read-only mount, `"rw"` for read/write.

**sys-usb side**: reads the topology at boot, creates one vchan endpoint per DomU that has
a `direct_mount` entry.

**DomU side**: queries the topology to find out:
1. Whether it has `direct_mount` access.
2. The mount mode (`ro` or `rw`).
3. The sys-usb `domid` (read from xenstore, not from topology).

---

## 4. Package changes

### 4.1 safecor-lib (new Python package)

New file: `python/lib/src/safecor/_direct_mount_manager.py`
New class: `DirectMountManager`

New topic constants in `_topics.py`:
- `MY_CONFIG = f"{SYSTEM}/topology/my_config"`

### 4.2 safecor-sys-usb (new dependencies)

Add to `setup/packages/safecor/safecor-sys-usb/APKBUILD` depends:
- `xen` — provides `vchan-socket-proxy` and vchan kernel modules (`xen_gntdev`, `xen_gntalloc`, `xen_evtchn`)
- `openssh-sftp-server` — provides `/usr/lib/ssh/sftp-server`
- `socat` — for the UNIX socket tunnel (server side only)

### 4.3 safecor-domu-base (new script + dependencies)

Add to `setup/packages/safecor/safecor-domu-base/APKBUILD` depends:
- `xen` — provides `vchan-socket-proxy` and vchan kernel modules
- `sshfs` — for FUSE-based mounting
- `fuse3` — FUSE kernel module (`modprobe fuse`)

New script: `setup/packages/safecor/safecor-domu-base/scripts/setup-direct-mount.sh`
- Runs at DomU boot (via init script or post-start hook).
- Generates `/usr/local/bin/vchan-sftp` with the correct domid.
- Invokes `DirectMountManager.start()` to auto-connect and mount.
- Cleans up on shutdown (unmount).

### 4.4 sys-usb init script

New init script: `setup/packages/safecor/safecor-sys-usb/init/safecor-vchan-sftp.initd`
- Reads topology to find DomUs with a `direct_mount` entry.
- For each such DomU, starts `vchan-socket-proxy` with the DomU's domid.
- Starts the SFTP server connected to each proxy's UNIX socket.
- Stops cleanly on shutdown.

---

## 5. Phases

> **Progress**: Phase 0 — done · Phase 1 — done · Phase 2 — done · Phase 3 — done · Phase 4 — done · Phase 5 — done

### Phase 0 — NFR documentation (prerequisite) — DONE

**Goal**: Formalize the API non-functional requirements so they guide all subsequent implementation.

1. **Add NFR section** to `docs/features.md` (§11):
   - NFR-1: MQTT callback functions must be non-blocking.
   - NFR-2: MQTT callback functions must have error handling.

**Deliverable**: NFRs documented and available as a reference for all phases.

### Phase 1 — Protocol functions + Sys-usb per-DomU vchan server — DONE

**Goal**: Add the new protocol function and have sys-usb serve per-DomU vchan channels with SFTP.

1. **Add protocol function** (safecor-lib):
   - `system/topology/my_config` — Dom0 responds with the requesting DomU's topology config
     (includes `direct_mount` object with `mode`). — **DONE**

2. **Add topic constants** in `_topics.py`: `MY_CONFIG`. — **DONE**

3. **Implement Dom0 handler** in `Dom0Controller`:
   - `__handle_my_config` — returns the requesting DomU's config from the topology.
   - Lazy topology init in `__init__`. — **DONE**

4. **Create chroot jail** for sftp-server at `/media` (copy binary + libraries). — **PENDING** (requires physical system)

5. **Write domids to xenstore** — in `start-business-domain.sh` (and `start-sys-usb.sh`),
   capture the domid after `xl create` via `xl info <name> | grep DOMID` and write it to
   xenstore: `xenstore-write /local/domain/system/domids/<domain_name> <domid>`.
   Similarly in `reboot-domain.sh`: after the domain restarts, re-write the new domid. — **DONE**

6. **Create sys-usb init script** (`safecor-vchan-sftp.initd`):
   - Reads topology to find DomUs with a `direct_mount` entry.
   - Reads `/local/domain/system/domids/` to get each DomU's domid.
   - For each DomU found: starts `vchan-socket-proxy -m server <domid> ...` and
     `socat ... EXEC:"chroot /media /usr/lib/ssh/sftp-server"`. — **DONE**

7. **Unit tests** for new functionality. — **DONE**

**Deliverable**: Protocol function available; sys-usb serves per-DomU vchan+SFTP channels.

### Phase 2 — Client-side sshfs mount — DONE (code)

**Goal**: A DomU can automatically connect to sys-usb via vchan and mount `/media/usb`.

1. **Add dependencies** to `safecor-domu-base` APKBUILD: `sshfs`, `fuse3`, `xen`. — **DONE**

2. **Create `setup-direct-mount.sh`** in `safecor-domu-base/scripts/`:
   - Queries `system/topology/my_config` to check if this DomU has `direct_mount` access.
   - If yes: reads xenstore to find sys-usb's domid.
   - Generates `/usr/local/bin/vchan-sftp` with the correct domid.
   - Creates the mount point at `/media/usb`.
   - Runs: `sshfs -f -o ssh_command=/usr/local/bin/vchan-sftp,noexec,nosuid,nodev,default_permissions,max_read=131072 none:/ /media/usb`
   - Handles unmount on shutdown. — **DONE**

3. **Create DomU init script** to start/stop `setup-direct-mount.sh`. — **DONE**

4. **Test manually**: boot a DomU, verify it auto-connects and mounts `/media/usb`. — **PENDING** (requires physical system)

**Deliverable**: Working auto-mount pipeline in a DomU.

### Phase 3 — DirectMountManager (Safecor library) — DONE (code + tests)

**Goal**: Integrate direct USB mount into the Safecor library as a managed component.

1. **Create `DirectMountManager`** class in `_direct_mount_manager.py`:
   - `start()` — initiates auto-connect flow (query topology → get domid → generate vchan-sftp script → mount via sshfs).
   - `stop()` — unmounts and cleans up.
   - `is_mounted()` — checks if `/media/usb` is mounted.
   - `get_mount_point()` — returns `/media/usb`.
   - `run()` — entry point for standalone process (blocks until SIGTERM).
   — **DONE**

2. **Launcher script** `start-direct-mount.py` for openrc. — **DONE**

3. **Unit tests** for `DirectMountManager` (16 tests). — **DONE**

**Deliverable**: `DirectMountManager` available for use by DomU applications; the
init script launches it as a managed process.

### Phase 4 — Optional 9p repository disablement + integration — DONE (code)

**Goal**: Make the 9p repository share disableable via topology, and complete integration.

1. **Parse `repository.disabled` in topology** (safecor-lib):
   - Add `repository.disabled` (boolean, default `false`) to `Topology` parsing.
   - Expose as `Topology.repository_disabled` property. — **DONE**

2. **Orchestrator** — when `repository.disabled = true`:
   - Do not configure the 9p share (`trans=xen`) in the DomU's device tree / config.
   - DomUs boot without a `/mnt/storage` 9p mount. — **DONE** (`create-domains.py`)

3. **Dom0Controller** — when `repository.disabled = true`:
   - Reject `disks/list_files`, `disks/delete_file`, `disks/file_fingerprint` requests
     targeting `__repository__` with a clear error response. — **DONE**

4. **DomU init** — when `repository.disabled = true`:
   - The 9p mount init script checks the topology and skips mounting `/mnt/storage`. — **PENDING** (requires provisioning script modification)

5. **Product integration tests** — verify end-to-end. — **PENDING** (requires physical system)

6. **Performance & security review**. — **PENDING** (requires physical system)

**Deliverable**: 9p repository is optional (disableable via topology); direct mount is
the primary file access path.

### Phase 5 — End-to-end documentation

**Goal**: Update all project documentation to reflect the direct mount feature.

1. **`docs/features.md`** — add the new functions to the catalogue:
   - `system/topology/my_config` (new topic, section 3 or new section)
   - `System.get_current_domid()`, `System.get_domain_domid(name)`,
     `System.is_usb_mountpoint_ready()`, `System.on_usb_mountpoint_ready(callback)`
   - Update NFR section if needed

2. **`docs/architecture.md`** — update:
   - §2.2 (storage): describe the vchan+SFTP path alongside the existing 9p path
   - §5 (emulatable surface): document the mock direct mount
   - Topology section: document the `direct_mount` object and `mode` field

3. **Safecor Wiki** — update the public documentation:
   - Direct mount feature description (what it is, how it works, security model)
   - Topology reference: `direct_mount` field and `mode`
   - API reference: new `System` methods
   - Operational guide: sys-usb vchan setup, DomU mount lifecycle

4. **`README.md` / `README.fr.md`** — update "Current features" section.

5. **`docs/manual.md`** — document the direct mount for end users/operators.

**Deliverable**: All documentation (internal + Wiki) is consistent with the implemented feature.

---

## 6. Open Questions

| # | Question | Resolution | Status |
|---|----------|------------|--------|
| 1 | What is the fallback if vchan mount fails? | **No retry.** Log the error via the Safecor `Logger` and stop. The DomU has no USB access until the next boot or manual intervention. | Resolved |
| 2 | Should the 9p storage share (Dom0 repository) remain as a fallback in v2? | **Kept but optional.** Enabled by default (backward compat). Can be disabled via `topology.json` for high-security systems. Retained for large file sharing (e.g., databases). | Resolved |
| 3 | Is `system/topology/my_config` already in the GitHub backlog? | No dedicated issue — it will be handled as part of the V2 work stream. | Resolved |

---

## 7. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| sshfs stability over vchan | Low | Medium | Test extensively; add retry logic and keepalive |
| sshfs performance vs. 9p | Low | Low | sshfs is typically comparable to 9p for sequential reads; benchmark for large files |
| Security: untrusted DomU connecting to sys-usb | Medium | High | Per-DomU vchan channels (only authorized DomUs get a channel); no shell, no auth |
| Kernel module loading timing (xen_gntdev, fuse) | Medium | Medium | Ensure `modprobe` runs before `vchan-socket-proxy`/`sshfs` starts (init script ordering) |
| `fuse` module not loaded in DomU | Low | Medium | `fuse3` package dependency; `modprobe fuse` in init script |

---

## 8. Files to be created or modified

### New files

| File | Purpose |
|------|---------|
| `python/lib/src/safecor/_direct_mount_manager.py` | New `DirectMountManager` class (auto-connect, mount, unmount) |
| `setup/packages/safecor/safecor-sys-usb/init/safecor-vchan-sftp.initd` | Init script: per-DomU vchan proxy + SFTP server on sys-usb |
| `setup/packages/safecor/safecor-domu-base/scripts/setup-direct-mount.sh` | DomU script: query topology, generate vchan-sftp script, mount `/media/usb` via sshfs |
| `setup/packages/safecor/safecor-domu-base/init/direct-mount.initd` | DomU init script to start/stop direct mount |

### Modified files

| File | Change |
|------|--------|
| `setup/packages/safecor/safecor-sys-usb/APKBUILD` | Add dependencies (xen, openssh-sftp-server, socat) |
| `setup/packages/safecor/safecor-domu-base/APKBUILD` | Add dependencies (xen, sshfs, fuse3) |
| `setup/packages/safecor/safecor-core/scripts/start-business-domain.sh` | Capture domid after `xl create`, write to xenstore |
| `setup/packages/safecor/safecor-core/scripts/start-sys-usb.sh` | Capture domid after `xl create`, write to xenstore |
| `setup/packages/safecor/safecor-core/scripts/reboot-domain.sh` | Re-write domid to xenstore after domain restart |
| `python/lib/src/safecor/_topics.py` | Add `MY_CONFIG` topic |
| `python/lib/src/safecor/_constants.py` | Add `USB_MOUNT_POINT` constant |
| `python/lib/src/safecor/_dom0_controller.py` | Add `get_topology()` lazy init + `__handle_my_config` handler |
| `python/lib/src/safecor/_topology.py` | Add `direct_mount` (with `mode`) per domain + `repository.disabled` (default `false`) |
| `python/lib/src/safecor/_system.py` | Add `get_current_domid()`, `get_domain_domid(name)`, `is_usb_mountpoint_ready()`, `on_usb_mountpoint_ready(callback)` |
| `docs/features.md` | Add §11 NFR (non-blocking + error handling for MQTT callbacks) |
| `docs/architecture.md` | Update §2.2 (storage), §2.6 (domain lifecycle), §5 (emulatable surface) |

---

## 9. Emulator implications

The emulator (`safecor_emulator`) will need a **mock direct mount manager** that:

1. Simulates the vchan→sshfs pipeline without real hardware.
2. Maps a local directory (chosen by the operator via the console) to a virtual mount point.
3. Responds to `DirectMountManager.mount()` / `unmount()` by creating/removing
   a symbolic link at `/media/usb` in the emulated filesystem namespace.

This is straightforward to implement as an override of the `_perform_*` methods pattern
already used for `MockSysUsbController`.

---

## 10. Future extensions (out of scope for v2)

| Feature | Description |
|---------|-------------|
| Encrypted virtual disk storage | Replace 9p share with an encrypted image shared via 9p (backlog item) |
| Per-disk access control | Restrict which USB disks a DomU can see through its `/media/usb` mount |
| Direct network mount (sys-net) | Analogous vchan+SFTP pipeline for network shares via `sys-net` |
| Direct mount caching | Cache frequently accessed files locally in DomU to reduce vchan load |
| Topology-driven DomU mounts | Replace the static `/etc/fstab` (from apkovl) with runtime mount configuration derived from `topology.json` at DomU boot. Would allow dynamic enable/disable of 9p shares without re-provisioning. |
