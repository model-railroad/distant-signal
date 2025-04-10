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

# See https://github.com/micropython/micropython/issues/573 for const() details
from micropython import const

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

# Size of the LED Matrix panel to display
_SX = const(64)
_SY = const(32)

# True for a 64x32 panel with an "HUB75-E" interface that actually uses 5 addr pins (A through E)
# instead of just 4 to address 32 lines. We simulate this by creating a 64x64 matrix and only 
# using the top half (i.e. SY=32 but init Matrix with height=64).
# For an AdaFruit 64x32 MatrixPortal-S3 compatible display, set this to False.
# Some non-AdaFruit panels with an HUB75-E need this to True. YMMV.
_HUB75E = const(True)

# Number of MSB bits used in each RGB color.
# 2 means that only RGB colors with #80 or #40 are visible, and anything lower is black.
# 3 means that only RGB colors with #80, #40, or #20 are visible, and anything lower is black.
# The max possible is 5 (the underlying CircuitPython RGBMatrix encodes its framebuffers
# in RGB565) and will produce visible flickering for the low value colors.
_RGB_BIT_DEPTH = const(2)

# Possible colors for the status NeoPixel LED (not for the matrix display).
_COL_OFF    = const( (  0,   0,   0) )
_COL_RED    = const( (255,   0,   0) )
_COL_GREEN  = const( (  0, 255,   0) )
_COL_BLUE   = const( (  0,   0, 255) )
_COL_PURPLE = const( (255,   0, 255) )      # FF00FF
_COL_ORANGE = const( (255,  40,   0) )      # FF2800
_COL_YELLOW = const( (255, 112,   0) )      # FF7000

# We use the LED color to get init status
_CODE_OK = const("ok")
_CODE_WIFI_FAILED = const("wifi_failed")
_CODE_MQTT_FAILED = const("mqtt_failed")
_CODE_MQTT_RETRY  = const("mqtt_retry")
_COL_LED_ERROR = {
    _CODE_OK: _COL_GREEN,
    _CODE_WIFI_FAILED: _COL_PURPLE,
    _CODE_MQTT_FAILED: _COL_BLUE,
    _CODE_MQTT_RETRY: _COL_ORANGE,
}

# Core state machine
_CORE_INIT              = const(0)
_CORE_WIFI_CONNECTING   = const(1)
_CORE_WIFI_CONNECTED    = const(2)
_CORE_MQTT_CONNECTING   = const(3)
_CORE_MQTT_FAILED       = const(4)
_CORE_MQTT_CONNECTED    = const(5)
_CORE_MQTT_LOOP         = const(6)


# MQTT Topics used:
_MQTT_TURNOUT              = "t330"                          # Not constant; overriden in settings.toml
_MQTT_TOPIC_TURNOUT_SCRIPT = "distantsignal/%(T)s/script"    # where T is MQTT_TURNOUT
# Turnout state is a string matching one of the JSON "states" keys.
_MQTT_TOPIC_TURNOUT_STATE  = "turnout/%(T)s/state"           # where T is MQTT_TURNOUT
# Block state is a string matching either "active" or "inactive"
_MQTT_TOPIC_BLOCk_STATE    = "block/%(B)s/state"             # where B is one of the JSON "blocks" keys

# the current working directory (where this file is)
CWD = ("/" + __file__).rsplit("/", 1)[
    0
]

_FONT_3x5_PATH1 = CWD + "/tom-thumb.bdf"
_FONT_3x5_PATH2 = CWD + "/tom-thumb2.bdf"
_DEFAULT_SCRIPT_PATH = CWD + "/default_script.json"

_core_state = _CORE_INIT
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

def init() -> None:
    print("@@ init")
    global _led, _boot_btn

    try:
        mqtt_turnout = os.getenv("MQTT_TURNOUT", "").strip()
        if mqtt_turnout:
            global _MQTT_TURNOUT
            _MQTT_TURNOUT = mqtt_turnout
            print("@@ Settings.toml: MQTT_TURNOUT set to", _MQTT_TURNOUT)
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


def init_wifi() -> bool:
    # Return true if wifi is connecting (which may or may not succeed)
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
        print("@@ WiFI connecting for", wifi_ssid)
        return True
    except ConnectionError:
        print("@@ WiFI Failed to connect to WiFi with provided credentials")
        blink_error(_CODE_WIFI_FAILED, num_loop=5)
        return False

def init_mqtt() -> None:
    # Modified the global core state if the MQTT connection succeeds
    global _core_state, _mqtt
    host = os.getenv("MQTT_BROKER_IP", "")
    if not host:
        print("@@ MQTT: disabled")
        # This is a core feature so we treat this as an error in this project
        blink_error(_CODE_MQTT_FAILED, num_loop=5)
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
        _core_state = _CORE_MQTT_CONNECTING
        _mqtt.connect()
        # Note that on success, the _mqtt_on_connected() callback will have been
        # called before mqtt.connect() returns, which changes the global core state.
    except Exception as e:
        print("@@ MQTT: Failed Connecting with ", e)
        blink_error(_CODE_MQTT_FAILED, num_loop=5)
        del _mqtt
        _mqtt = None
        _core_state = _CORE_MQTT_FAILED

def compute_mqtt_topics():
    # Compute all MQTT Topic keys
    _mqtt_topics["script" ] = _MQTT_TOPIC_TURNOUT_SCRIPT % { "T": _MQTT_TURNOUT }
    _mqtt_topics["turnout"] = _MQTT_TOPIC_TURNOUT_STATE  % { "T": _MQTT_TURNOUT }
    for block_name in _script_parser.blocks():
        _mqtt_topics["blocks"][block_name] = _MQTT_TOPIC_BLOCk_STATE % { "B": block_name }

def init_display():
    global _matrix, _fonts
    displayio.release_displays()
    _matrix = Matrix(
        width=64,
        height=_SY*2 if _HUB75E else _SY,
        bit_depth=_RGB_BIT_DEPTH,
        # serpentine=True,
        # tile_rows=1,
    )
    display = _matrix.display

    font1 = bitmap_font.load_font(_FONT_3x5_PATH1)
    font2 = bitmap_font.load_font(_FONT_3x5_PATH2)
    _fonts.append(font1)
    _fonts.append(font2)

    loading_group = displayio.Group()
    t = Label(font1)
    t.text = "Loading"
    t.x = (_SX - len(t.text) * 4) // 2
    t.y = _SY // 2 - 2 + FONT_Y_OFFSET
    t.scale = 1
    t.color = 0xFFFF00
    loading_group.append(t)
    display.root_group = loading_group

def _mqtt_on_connected(client, userdata, flags, rc):
    # This function will be called when the client is connected successfully to the broker.
    global _core_state
    _core_state = _CORE_MQTT_CONNECTED
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
    blink_error(_CODE_OK, num_loop=0)

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
    global _mqtt, _core_state
    if _mqtt is None:
        return
    try:
        _mqtt.loop()
    except Exception as e:
        print("@@ MQTT: Failed with ", e)
        blink_error(_CODE_MQTT_RETRY, num_loop=1)
        try:
            _mqtt.reconnect()
            blink_error(_CODE_OK, num_loop=0)
        except Exception as e:
            print("@@ MQTT: Reconnect failed with ", e)
            blink_error(_CODE_MQTT_FAILED, num_loop=5)
            del _mqtt
            _core_state = _CORE_MQTT_FAILED


def blink_error(error_code, num_loop=-1):
    _led.fill(_COL_LED_ERROR[error_code])
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

    _script_parser = ScriptParser(_SX, _SY, _fonts)
    _script_loader = ScriptLoader(_script_parser)
    
    script = _script_loader.loadFromNVM()
    if script is not None:
        # Parse the NVM script, and don't save it to the NVM
        _script_loader.newScript(script, saveToNVM=False)
    else:
        # Load a default script, and don't save it to the NVM
        try:
            with open(_DEFAULT_SCRIPT_PATH, "r") as file:
                script = file.read()
                _script_loader.newScript(script, saveToNVM=False)
        except Exception as e:
            print("@@ InitScript failed to read", _DEFAULT_SCRIPT_PATH, e)
            raise
    del script
    gc.collect()
    compute_mqtt_topics()
    print("@@ Mem free:", gc.mem_free())

def loop() -> None:
    global _core_state
    print("@@ loop")

    init_buttons()
    init_display()

    # # Sleep a few seconds at boot
    _led.fill(_COL_LED_ERROR[_CODE_OK])
    for i in range(0, 3):
        print(i)
        blink()
        time.sleep(1)

    blink()
    init_script()   
    _script_loader.updateDisplay(_matrix.display)

    _old_cs = None
    while True:
        start_ts = time.monotonic()
        blink()

        # Handle core state
        if _core_state == _CORE_INIT:
            if init_wifi():
                _core_state = _CORE_WIFI_CONNECTING
        elif _core_state == _CORE_WIFI_CONNECTING:
            if wifi.radio.connected:
                _core_state = _CORE_WIFI_CONNECTED
        elif _core_state == _CORE_WIFI_CONNECTED or _core_state == _CORE_MQTT_FAILED:
            # This sets the sets to either _CORE_MQTT_FAILED or _CORE_MQTT_CONNECTING
            init_mqtt()
        elif _core_state == _CORE_MQTT_CONNECTING:
            # wait for the _mqtt_on_connected() callback to be invoked
            # which changes state to _CORE_MQTT_CONNECTED
            pass
        elif _core_state == _CORE_MQTT_CONNECTED:
            _core_state = _CORE_MQTT_LOOP
        elif _core_state == _CORE_MQTT_LOOP:
            _mqtt_loop()    # This takes 1~2 seconds
        if _old_cs != _core_state:
            print("@@ CORE STATE:", _old_cs, "=>", _core_state)
            _old_cs = _core_state

        _matrix.display.refresh(minimum_frames_per_second=0)
        # if not _button_down.value or not _button_up.value:
        #     state_index = (state_index + 1) % len(states)
        _script_loader.updateDisplay(_matrix.display)
        end_ts = time.monotonic()
        delta_ts = end_ts - start_ts
        if delta_ts < 1: time.sleep(0.25)  # prevent busy loop
        print("@@ loop", _core_state, ":", delta_ts)


if __name__ == "__main__":
    init()
    loop()

#~~
