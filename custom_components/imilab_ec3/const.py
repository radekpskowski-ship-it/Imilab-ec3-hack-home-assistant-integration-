"""Constants for the Imilab EC3 (chuangmi.camera.025b02) integration."""

DOMAIN = "imilab_ec3"
PLATFORMS = ["camera", "binary_sensor", "sensor", "switch", "select", "number", "time", "button"]

CONF_TOKEN = "token"
CONF_STREAM_URL = "stream_url"
CONF_SNAPSHOT_URL = "snapshot_url"
CONF_SNAPSHOT_USER = "snapshot_username"
CONF_SNAPSHOT_PASSWORD = "snapshot_password"

DEFAULT_HOST = "192.168.1.100"
DEFAULT_STREAM_URL = "rtsp://go2rtc.local:8554/imilab_ec3_sub_h264"
DEFAULT_SNAPSHOT_URL = "http://go2rtc.local:1984/api/frame.jpeg?src=imilab_ec3_sub_h264"
TOKEN_FILE = "/config/imilab/token"
# The camera generates a new miio token on every boot. It is fetched over SSH with a key whose
# authorized_keys entry forces hack/bin/ha_cmd.sh (see the repository README).
SSH_KEY = "/config/imilab/ssh_key"

PROPS = [
    "power", "light", "night_mode", "flip", "wdr", "full_color", "watermark", "motion_record", "improve_program",
    "motion_detection_enable", "motion_alarm", "motion_region",
]
SCAN_INTERVAL_S = 30

# NAS / SMB (miio_nas). The camera uses libdsm, which speaks SMB1 (NT LM 0.12) only.
CONF_SMB_ADDR = "smb_addr"
CONF_SMB_NAME = "smb_name"
CONF_SMB_DIR = "smb_dir"
CONF_SMB_GROUP = "smb_group"
CONF_SMB_USER = "smb_user"
CONF_SMB_PASS = "smb_pass"
CONF_SMB_INTERVAL = "smb_sync_interval"
CONF_SMB_RETENTION = "smb_retention"
CONF_SMB_ENABLE = "smb_enable"

NAS_STATE_OFF = 2
NAS_STATE_ON = 3
NAS_STATES = {0: "not_configured", NAS_STATE_OFF: "off", NAS_STATE_ON: "on"}
NAS_INTERVALS = ["300", "3600", "86400"]
NAS_RETENTIONS = ["604800", "2592000", "7776000", "15552000", "31104000"]
# errno values returned by nas_list_dir / nas_set_config (miio_nas, libmiio_samba)
NAS_ERRORS = {
    1: "permission denied",
    2: "no such share or directory",
    11: "cannot connect (server unreachable or no SMB1 support)",
    12: "out of memory on the camera",
    13: "wrong password or no access",
    22: "invalid parameters",
    260: "server rejected the connection (e.g. unknown share)",
}

# Motion: /run/md_event → hack/bin/md2mqtt.sh on the camera → MQTT
MOTION_TOPIC = "imilab_ec3/motion"
MOTION_OFF_DELAY_S = 20

NIGHT_MODES = ["auto", "off", "on"]  # set_night_mode 0/1/2
# set_motion_record: on = record on motion, off = record continuously, stop = no recording
RECORD_MODES = {"off": "continuous", "on": "motion", "stop": "disabled"}
# motion_region: 32 cells, 3 = high, 1 = low (python-miio MotionDetectionSensitivity)
SENSITIVITY = {"high": 3, "low": 1}
# setAlarmConfig / getAlarmConfig: [mode, start_h, start_m, end_h, end_m, notify, interval_min]
ALARM_MODES = {0: "off", 1: "all_day", 2: "schedule"}
# set_favoritelocation: status set/ctrl/del, location 1..6; region "[0,…]" keeps the motion region
PRESET_SLOTS = range(1, 7)
EMPTY_REGION = "[" + ",".join(["0"] * 32) + "]"
