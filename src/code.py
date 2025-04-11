# Distant Signal
# 2025 (c) ralfoide at gmail
# License: MIT
#
# Target Platform: AdaFruit MatrixPortal CircuitPython ESP32-S3
#
# Hardware:
# - AdaFruit MatrixPortal CircuitPython ESP32-S3
# - AdaFruit 64x32 RGB LED Matrix


# CircuitPython built-in libraries
import board
import digitalio
import displayio
import gc
import os
import terminalio
import time
import vectorio
import wifi
from digitalio import DigitalInOut, Direction, Pull

# Bundle libraries
import neopixel
import adafruit_connection_manager
import adafruit_logging as logging
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_matrixportal.matrix import Matrix
from adafruit_display_text.label import Label
from adafruit_bitmap_font import bitmap_font

from script_loader import ScriptLoader
from script_parser import ScriptParser, FONT_Y_OFFSET

_led = None
_mqtt = None
_matrix = None
_fonts = []
_mqtt_topics = {
    "script": "",
    "turnout": "",
    "blocks": {
        # block_name => topic:str
    }
}
_script_parser: ScriptParser = None
_script_loader: ScriptLoader = None
_boot_btn = None
_button_down = None
_button_up = None
_logger = logging.getLogger("DistantSignal")
_logger.setLevel(logging.INFO)      # INFO or DEBUG

# Size of the LED Matrix panel to display
SX = 64
SY = 32

# True for a 64x32 panel with an "HUB75-E" interface that actually uses 5 addr pins (A through E)
# instead of just 4 to address 32 lines. We simulate this by creating a 64x64 matrix and only 
# using the top half (i.e. SY=32 but init Matrix with height=64).
# For an AdaFruit 64x32 MatrixPortal-S3 compatible display, set this to False.
# Some non-AdaFruit panels with an HUB75-E need this to True. YMMV.
HUB75E = True

# Number of MSB bits used in each RGB color.
# 2 means that only RGB colors with #80 or #40 are visible, and anything lower is black.
# 3 means that only RGB colors with #80, #40, or #20 are visible, and anything lower is black.
# The max possible is 5 (the underlying CircuitPython RGBMatrix encodes its framebuffers
# in RGB565) and will produce visible flickering for the low value colors.
RGB_BIT_DEPTH = 2

# Possible colors for the status NeoPixel LED (not for the matrix display).
COL_OFF = (0, 0, 0)
COL_RED = (255, 0, 0)
COL_GREEN = (0, 255, 0)
COL_BLUE = (0, 0, 255)
COL_PURPLE = (255, 0, 255)      # FF00FF
COL_ORANGE = (255, 40, 0)       # FF2800
COL_YELLOW = (255, 112, 0)      # FF7000

# We use the LED color to get init status
CODE_OK = "ok"
CODE_WIFI_FAILED = "wifi_failed"
CODE_MQTT_FAILED = "mqtt_failed"
CODE_MQTT_RETRY  = "mqtt_retry"
COL_LED_ERROR = {
    CODE_OK: COL_GREEN,
    CODE_WIFI_FAILED: COL_PURPLE,
    CODE_MQTT_FAILED: COL_BLUE,
    CODE_MQTT_RETRY: COL_ORANGE,
}

# MQTT Topics used:
MQTT_TURNOUT              = "t330"                          # overriden in settings.toml
MQTT_TOPIC_TURNOUT_SCRIPT = "distantsignal/%(T)s/script"    # where T is MQTT_TURNOUT
# Turnout state is a string matching one of the JSON "states" keys.
MQTT_TOPIC_TURNOUT_STATE  = "turnout/%(T)s/state"           # where T is MQTT_TURNOUT
# Block state is a string matching either "active" or "inactive"
MQTT_TOPIC_BLOCk_STATE    = "block/%(B)s/state"             # where B is one of the JSON "blocks" keys

# the current working directory (where this file is)
CWD = ("/" + __file__).rsplit("/", 1)[
    0
]

FONT_3x5_PATH1 = CWD + "/tom-thumb.bdf"
FONT_3x5_PATH2 = CWD + "/tom-thumb2.bdf"
DEFAULT_SCRIPT_PATH = CWD + "/default_script.json"

def init() -> None:
    print("@@ init")
    global _led, _boot_btn

    try:
        mqtt_turnout = os.getenv("MQTT_TURNOUT", "").strip()
        if mqtt_turnout:
            global MQTT_TURNOUT
            MQTT_TURNOUT = mqtt_turnout
            print("@@ Settings.toml: MQTT_TURNOUT set to", MQTT_TURNOUT)
    except Exception as e:
        print("@@ Settings.toml: Invalid MQTT_TURNOUT variable ", e)

    _led = neopixel.NeoPixel(board.NEOPIXEL, 1)
    _led.brightness = 0.1

def init_buttons():
    global _button_down, _button_up, _boot_btn
    _button_down = DigitalInOut(board.BUTTON_DOWN)
    _button_down.switch_to_input(pull=Pull.UP)
    _button_up = DigitalInOut(board.BUTTON_UP)
    _button_up.switch_to_input(pull=Pull.UP)
    _boot_btn = digitalio.DigitalInOut(board.D0)
    _boot_btn.switch_to_input(pull = digitalio.Pull.UP)


def init_wifi() -> None:
    print("@@ WiFI setup")
    # Get wifi AP credentials from onboard settings.toml file
    wifi_ssid = os.getenv("CIRCUITPY_WIFI_SSID", "")
    wifi_password = os.getenv("CIRCUITPY_WIFI_PASSWORD", "")
    print("@@ WiFI SSID:", wifi_ssid)
    if wifi_ssid is None:
        print("@@ WiFI credentials are kept in settings.toml, please add them there!")
        raise ValueError("WiFI SSID not found in environment variables")

    try:
        wifi.radio.connect(wifi_ssid, wifi_password)
    except ConnectionError:
        print("@@ WiFI Failed to connect to WiFi with provided credentials")
        blink_error(CODE_WIFI_FAILED)
        raise
    print("@@ WiFI OK for", wifi_ssid)

def init_mqtt() -> None:
    global _mqtt
    host = os.getenv("MQTT_BROKER_IP", "")
    if not host:
        print("@@ MQTT: disabled")
        return
    port = int(os.getenv("MQTT_BROKER_PORT", 1883))
    user = os.getenv("MQTT_USERNAME", "")
    pasw = os.getenv("MQTT_PASSWORD", "")
    print("@@ MQTT: connect to", host, ", port", port, ", user", user)

    # Source: https://adafruit-playground.com/u/justmobilize/pages/adafruit-connection-manager
    pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)

    # Source: https://learn.adafruit.com/mqtt-in-circuitpython/advanced-minimqtt-usage
    _mqtt = MQTT.MQTT(
        broker=host,
        port=port,
        username=user,
        password=pasw,
        is_ssl=False,
        socket_pool=pool,
    )
    _mqtt.logger = _logger

    _mqtt.on_connect = _mqtt_on_connected
    _mqtt.on_disconnect = _mqtt_on_disconnected
    _mqtt.on_message = _mqtt_on_message

    try:
        print("@@ MQTT: connecting...")
        _mqtt.connect()
    except Exception as e:
        print("@@ MQTT: Failed Connecting with ", e)
        blink_error(CODE_MQTT_FAILED, num_loop=3)
        _mqtt = "retry"

def compute_mqtt_topics():
    # Compute all MQTT Topic keys
    _mqtt_topics["script" ] = MQTT_TOPIC_TURNOUT_SCRIPT % { "T": MQTT_TURNOUT }
    _mqtt_topics["turnout"] = MQTT_TOPIC_TURNOUT_STATE  % { "T": MQTT_TURNOUT }
    for block_name in _script_parser.blocks():
        _mqtt_topics["blocks"][block_name] = MQTT_TOPIC_BLOCk_STATE % { "B": block_name }

def init_display():
    global _matrix, _fonts
    displayio.release_displays()
    _matrix = Matrix(
        width=64,
        height=SY*2 if HUB75E else SY,
        bit_depth=RGB_BIT_DEPTH,
        # serpentine=True,
        # tile_rows=1,
    )
    display = _matrix.display

    font1 = bitmap_font.load_font(FONT_3x5_PATH1)
    font2 = bitmap_font.load_font(FONT_3x5_PATH2)
    _fonts.append(font1)
    _fonts.append(font2)

    loading_group = displayio.Group()
    t = Label(font1)
    t.text = "Loading"
    t.x = (SX - len(t.text) * 4) // 2
    t.y = SY // 2 - 2 + FONT_Y_OFFSET
    t.scale = 1
    t.color = 0xFFFF00
    loading_group.append(t)
    display.root_group = loading_group

def _mqtt_on_connected(client, userdata, flags, rc):
    # This function will be called when the client is connected successfully to the broker.
    print("@Q MQTT: Connected")
    # Subscribe to all changes.
    def _sub(t):
        if t:
            print("@@ MQTT: Subscribe to", t)
            client.subscribe(t)
    _sub(_mqtt_topics["script"])
    _sub(_mqtt_topics["turnout"])
    for block_topic in _mqtt_topics["blocks"].values():
        _sub(block_topic)
    blink_error(CODE_OK, num_loop=0)

def _mqtt_on_disconnected(client, userdata, rc):
    # This method is called when the client is disconnected
    print("@Q MQTT: Disconnected")

def _mqtt_on_message(client, topic, message):
    """Method callled when a client's subscribed feed has a new
    value.
    :param str topic: The topic of the feed with a new value.
    :param str message: The new value
    """
    print(f"@Q MQTT: New message on topic {topic}: {message}")
    try:
        if topic == _mqtt_topics["script"]:
            if _script_loader.newScript(script=message, saveToNVM=True):
                compute_mqtt_topics()
                # TBD we need to disconnect/reconnect or resubscribe on MQTT topics
        elif topic == _mqtt_topics["turnout"]:
            _script_loader.setState(message)
        else:
            for block_name, block_topic in _mqtt_topics["blocks"].items():
                if topic == block_topic:
                    _script_loader.setBlockState(block_name, message.strip().lower() == "active")
                    break
    except Exception as e:
        print(f"@@ MQTT: Failed to process {topic}: {message}", e)

_mqtt_retry_ts = 0
def _mqtt_loop():
    if not _mqtt:
        return
    if isinstance(_mqtt, str) and _mqtt == "retry":
        global _mqtt_retry_ts
        if time.time() - _mqtt_retry_ts > 5:
            init_mqtt()
            _mqtt_retry_ts = time.time()
        return
    try:
        _mqtt.loop()
    except Exception as e:
        print("@@ MQTT: Failed with ", e)
        blink_error(CODE_MQTT_RETRY, num_loop=1)
        try:
            _mqtt.reconnect()
            blink_error(CODE_OK, num_loop=0)
        except Exception as e:
            print("@@ MQTT: Reconnect failed with ", e)
            blink_error(CODE_MQTT_FAILED, num_loop=2)

def blink_error(error_code, num_loop=-1):
    _led.fill(COL_LED_ERROR[error_code])
    _led.brightness = 0.1
    time.sleep(0.5)
    # For debugging purposes, we can exit the loop by using the boot button to continue
    while num_loop != 0 and _boot_btn.value:
        _led.brightness = 0
        time.sleep(0.25)
        _led.brightness = 0.1
        time.sleep(1)
        num_loop -= 1

_last_blink_ts = 0
_next_blink = 1
def blink() -> None:
    global _last_blink_ts, _next_blink
    _led.brightness = 0.1 if _next_blink else 0
    now = time.time()
    if now - _last_blink_ts > 1:
        _last_blink_ts = now
        _next_blink = 1 - _next_blink

def init_script():
    global _script_parser, _script_loader

    _script_parser = ScriptParser(SX, SY, _fonts)
    _script_loader = ScriptLoader(_script_parser)
    
    script = _script_loader.loadFromNVM()
    if script is not None:
        # Parse the NVM script, and don't save it to the NVM
        _script_loader.newScript(script, saveToNVM=False)
    else:
        # Load a default script, and don't save it to the NVM
        try:
            with open(DEFAULT_SCRIPT_PATH, "r") as file:
                script = file.read()
                _script_loader.newScript(script, saveToNVM=False)
        except Exception as e:
            print("@@ InitScript failed to read", DEFAULT_SCRIPT_PATH, e)
            raise
    del script
    gc.collect()
    print("@@ Mem free:", gc.mem_free())


def loop() -> None:
    print("@@ loop")

    init_buttons()
    init_display()

    # # Sleep a few seconds at boot
    _led.fill(COL_LED_ERROR[CODE_OK])
    for i in range(0, 3):
        print(i)
        blink()
        time.sleep(1)

    blink()
    init_wifi()
    init_script()
    compute_mqtt_topics()
    init_mqtt()
    _script_loader.updateDisplay(_matrix.display)

    while True:
        start_ts = time.monotonic()
        blink()
        _mqtt_loop()    # This takes 1~2 seconds
        _matrix.display.refresh(minimum_frames_per_second=0)
        # if not _button_down.value or not _button_up.value:
        #     state_index = (state_index + 1) % len(states)
        _script_loader.updateDisplay(_matrix.display)
        end_ts = time.monotonic()
        delta_ts = end_ts - start_ts
        if delta_ts < 1: time.sleep(0.25)  # prevent busy loop
        print("@@ loop: ", delta_ts)


if __name__ == "__main__":
    init()
    loop()

#~~
