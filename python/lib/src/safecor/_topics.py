""" \author Tristan Israël """

class Topics():
    """ This class defines MQTT topics for the API """

    # Groups
    SYSTEM = "system"
    DISKS = f"{SYSTEM}/disks"
    MISC = f"{SYSTEM}/misc"
    EVENTS = f"{SYSTEM}/events"
    DISCOVER = f"{SYSTEM}/discover"
    WORKFLOW = f"{SYSTEM}/workflow"
    ENERGY = f"{SYSTEM}/energy"
    SYS_USB = f"{SYSTEM}/sys-usb"
    SETTINGS = f"{SYSTEM}/settings"

    DEBUGGING = f"{SYSTEM}/debugging"

    # Disks and files management
    LIST_DISKS = f"{DISKS}/list_disks"
    LIST_FILES = f"{DISKS}/list_files"
    READ_FILE = f"{DISKS}/read_file"
    COPY_FILE = f"{DISKS}/copy_file"
    DELETE_FILE = f"{DISKS}/delete_file"
    FILE_FINGERPRINT = f"{DISKS}/file_fingerprint"
    CREATE_FILE = f"{DISKS}/create_file"
    NEW_FILE = f"{DISKS}/new_file"
    DISK_STATE = f"{DISKS}/state"
    MOUNT_FILE = f"{DISKS}/mount_file"
    UNMOUNT = f"{DISKS}/unmount"
    DELETED_FILE = f"{DISKS}/deleted_file"

    # Workflow management
    SHUTDOWN = f"{WORKFLOW}/shutdown"
    RESTART_DOMAIN = f"{WORKFLOW}/restart_domain"
    GUI_READY = f"{WORKFLOW}/gui_ready"

    # Miscellaneous
    DISCOVER_COMPONENTS = f"{DISCOVER}/components"
    KEEPALIVE = f"{MISC}/ping"
    ENERGY_STATE = f"{ENERGY}/state"
    SYSTEM_INFO = f"{SYSTEM}/info"
    BENCHMARK = f"{MISC}/benchmark"
    SYS_USB_CLEAR_QUEUES = f"{SYS_USB}/clear-queues"

    # Logging
    ERROR = f"{EVENTS}/error"
    WARNING = f"{EVENTS}/warning"
    INFO = f"{EVENTS}/info"
    DEBUG = f"{EVENTS}/debug"
    SET_LOG_LEVEL = f"{EVENTS}/set_loglevel"
    SAVE_LOG = f"{EVENTS}/save_log"

    # Debugging
    PING = f"{DEBUGGING}/ping"

    # Settings
    SETTING_CHANGED = f"{SETTINGS}/changed"
    LANGUAGES = f"{SETTINGS}/languages"
    LIST_LANGUAGES = f"{LANGUAGES}/list"
    DEFAULT_LANGUAGE = f"{LANGUAGES}/default"
    CURRENT_LANGUAGE = f"{LANGUAGES}/current"
    SET_LANGUAGE = f"{LANGUAGES}/set"
