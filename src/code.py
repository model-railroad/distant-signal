# Distant Signal
# 2025 (c) ralfoide at gmail
# License: MIT
#
# Target Platform: AdaFruit MatrixPortal CircuitPython ESP32-S3
#
# Hardware:
# - AdaFruit MatrixPortal CircuitPython ESP32-S3
# - AdaFruit 64x32 RGB LED Matrix
#
# Hard limitation: CircuitPython has a 16-deep call stack. Any attempt to
# call more functions generates a "pystack exhausted" exception.

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
_CODE_FATAL = const("fatal")
_CODE_RETRY = const("retry")
_COL_LED_ERROR = {
    _CODE_OK: _COL_GREEN,
    _CODE_RETRY: _COL_YELLOW,
    _CODE_FATAL: _COL_RED,
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
_WIFI_ON_PATH   = CWD + "/wifi_on.bmp"
_WIFI_OFF_PATH  = CWD + "/wifi_off.bmp"
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
_mqtt_pending_script: str = None
_script_parser: ScriptParser = None
_script_loader: ScriptLoader = None
_parser_group: displayio.Group = None
_wifi_off_tile = None
_wifi_on_tile = None
_wifi_icon_state = None
_loading_tile = None
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
        blink_led_error(_CODE_RETRY, num_loop=5)
        return False

def init_mqtt() -> None:
    # Modified the global core state if the MQTT connection succeeds
    global _core_state, _mqtt
    host = os.getenv("MQTT_BROKER_IP", "")
    if not host:
        print("@@ MQTT: disabled")
        # This is a core feature so do we not ignore this error in this project
        # and we'll retry again and again and again
        blink_led_error(_CODE_RETRY, num_loop=5)
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
        blink_led_error(_CODE_RETRY, num_loop=5)
        del _mqtt
        _mqtt = None
        _core_state = _CORE_MQTT_FAILED

def update_script_settings():
    settings = _script_parser.settings()
    icon_info = settings.get("cnx-icon", {})
    x = icon_info.get("x", (_SX - _wifi_on_tile.width) // 2)
    y = icon_info.get("y",  _SY - _wifi_on_tile.height)
    _wifi_on_tile.x = x
    _wifi_on_tile.y = y
    _wifi_off_tile.x = x
    _wifi_off_tile.y = y

def compute_mqtt_topics():
    # Compute all MQTT Topic keys
    _mqtt_topics["script" ] = _MQTT_TOPIC_TURNOUT_SCRIPT % { "T": _MQTT_TURNOUT }
    _mqtt_topics["turnout"] = _MQTT_TOPIC_TURNOUT_STATE  % { "T": _MQTT_TURNOUT }
    for block_name in _script_parser.blocks():
        _mqtt_topics["blocks"][block_name] = _MQTT_TOPIC_BLOCk_STATE % { "B": block_name }

def subscribe_mqtt_topics():
    if _mqtt is None:
        return

    # Unsub all topics
    for topic in _mqtt._subscribed_topics:
        _mqtt.unsubscribe(topic)

    # Subscribe to all changes.
    def _sub(t):
        if t:
            print("@@ MQTT: Subscribe to", t)
            _mqtt.subscribe(t, qos=1)
    _sub(_mqtt_topics["script"])
    _sub(_mqtt_topics["turnout"])
    for block_topic in _mqtt_topics["blocks"].values():
        _sub(block_topic)

def init_display():
    global _matrix, _fonts, _parser_group, _wifi_off_tile, _wifi_on_tile, _loading_tile
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

    root_group = displayio.Group()

    bmp = displayio.OnDiskBitmap(_WIFI_OFF_PATH)
    _wifi_off_tile = displayio.TileGrid(bmp, pixel_shader=bmp.pixel_shader)
    _wifi_off_tile.hidden = True
    bmp = displayio.OnDiskBitmap(_WIFI_ON_PATH)
    _wifi_on_tile = displayio.TileGrid(bmp, pixel_shader=bmp.pixel_shader)
    _wifi_on_tile.hidden = True
    root_group.append(_wifi_on_tile)
    root_group.append(_wifi_off_tile)

    _parser_group = displayio.Group()
    root_group.append(_parser_group)

    _loading_tile = Label(font1)
    _loading_tile.text = "Loading"
    _loading_tile.x = (_SX - len(_loading_tile.text) * 4) // 2
    _loading_tile.y = _SY // 2 - 2 + FONT_Y_OFFSET
    _loading_tile.scale = 1
    _loading_tile.color = 0xFFFF00
    root_group.append(_loading_tile)

    display.root_group = root_group

def _mqtt_on_connected(client, userdata, flags, rc):
    # This function will be called when the client has successfully connected to the broker.
    global _core_state
    _core_state = _CORE_MQTT_CONNECTED
    # Actual subscription is handled by subscribe_mqtt_topics() called from main core state loop.
    print("@Q MQTT: Connected")
    blink_led_error(_CODE_OK, num_loop=0)

def _mqtt_on_disconnected(client, userdata, rc):
    # This method is called when the client is disconnected
    print("@Q MQTT: Disconnected")

def _mqtt_on_message(client, topic, message):
    """Method callled when a client's subscribed feed has a new
    value.
    :param str topic: The topic of the feed with a new value.
    :param str message: The new value
    """
    global _mqtt_pending_script
    print(f"@Q MQTT: New message on topic {topic}: {message}")
    try:
        if topic == _mqtt_topics["script"]:
            # Note that attempts to parse the script right here typically throw a
            # "pystack exhausted" exception due to having too many calls on the
            # very limited (16-deep) call stack.
            # Instead, we keep a reference to the script and process it in the main loop.
            _mqtt_pending_script = message
        elif topic == _mqtt_topics["turnout"]:
            _script_loader.setState(message)
        else:
            for block_name, block_topic in _mqtt_topics["blocks"].items():
                if topic == block_topic:
                    _script_loader.setBlockState(block_name, message.strip().lower() == "active")
                    break
    except Exception as e:
        print(f"@@ MQTT: Failed to process {topic}: {message}", e)
        blink_led_error(_CODE_RETRY, num_loop=0)

_mqtt_retry_ts = 0
def _mqtt_loop():
    global _mqtt, _core_state
    if _mqtt is None:
        return
    try:
        # This call has an integrated timeout and takes either 1 or 2 seconds
        # to complete with the default timeout = 1 value.
        _mqtt.loop()
    except Exception as e:
        print("@@ MQTT: Failed with ", e)
        blink_led_error(_CODE_RETRY, num_loop=1)
        try:
            _mqtt.reconnect()
            blink_led_error(_CODE_OK, num_loop=0)
        except Exception as e:
            print("@@ MQTT: Reconnect failed with ", e)
            blink_led_error(_CODE_RETRY, num_loop=1)
            del _mqtt
            _mqtt = None
            _core_state = _CORE_MQTT_FAILED

_next_blink_wifi_ts = 0
def display_wifi_icon(wifi: bool|None) -> None:
    global _wifi_icon_state, _next_blink_wifi_ts
    _wifi_icon_state = wifi
    _wifi_on_tile.hidden = True
    _wifi_off_tile.hidden = True
    _next_blink_wifi_ts = time.monotonic()

def blink_wifi() -> None:
    global _next_blink_wifi_ts
    if _wifi_icon_state is None:
        return
    now = time.monotonic()
    if _wifi_icon_state:
        # "Wifi OK" blinks for 1 second every 30 seconds
        if now > _next_blink_wifi_ts:
            _wifi_on_tile.hidden = not _wifi_on_tile.hidden
            if _wifi_on_tile.hidden:
                _next_blink_wifi_ts = now + 30
            else:
                _next_blink_wifi_ts = now + 0.75
    else:
        # "Wifi FAIL" blinks 5 seconds on, 2 seconds off
            _wifi_off_tile.hidden = not _wifi_off_tile.hidden
            if _wifi_on_tile.hidden:
                _next_blink_wifi_ts = now + 1
            else:
                _next_blink_wifi_ts = now + 1

def blink_led_error(error_code, num_loop=-1):
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

_last_blink_led_ts = 0
_next_blink_led = 1
def blink_led() -> None:
    global _last_blink_led_ts, _next_blink_led
    _led.brightness = 0.1 if _next_blink_led else 0
    now = time.monotonic()
    if now - _last_blink_led_ts > 1:
        _last_blink_led_ts = now
        _next_blink_led = 1 - _next_blink_led

def init_script():
    global _script_parser, _script_loader

    _script_parser = ScriptParser(_SX, _SY, _fonts)
    _script_loader = ScriptLoader(_script_parser)

    _parser_group.append(_script_parser.root())
    
    # Buttons have a pull-up and values are True when they are not pressed.
    # Reset NVM script if either buttons are pressed at boot.
    if not _button_down.value or not _button_up.value:
        _script_loader.resetNVM()

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
            # The default script _should_ work. Failing to parse it is critical.
            print("@@ InitScript failed to read", _DEFAULT_SCRIPT_PATH, e)
            blink_led_error(_CODE_FATAL)
    del script
    gc.collect()
    update_script_settings()
    compute_mqtt_topics()
    print("@@ Mem free:", gc.mem_free())

if __name__ == "__main__":
    print("@@ loop")

    init()
    init_buttons()
    init_display()

    # # Sleep a few seconds at boot
    _led.fill(_COL_LED_ERROR[_CODE_OK])
    for i in range(0, 3):
        print(i)
        blink_led()
        time.sleep(1)

    blink_led()
    init_script()   
    _script_loader.updateDisplay()
    _loading_tile.hidden = True
    display_wifi_icon(False)

    _old_cs = None
    while True:
        start_ts = time.monotonic()
        blink_led()

        # Handle core state
        if _core_state == _CORE_INIT:
            if init_wifi():
                _core_state = _CORE_WIFI_CONNECTING
        elif _core_state == _CORE_WIFI_CONNECTING:
            if wifi.radio.connected:
                _core_state = _CORE_WIFI_CONNECTED
                display_wifi_icon(True)
        elif _core_state == _CORE_WIFI_CONNECTED or _core_state == _CORE_MQTT_FAILED:
            # This sets the sets to either _CORE_MQTT_FAILED or _CORE_MQTT_CONNECTING
            init_mqtt()
        elif _core_state == _CORE_MQTT_CONNECTING:
            # wait for the _mqtt_on_connected() callback to be invoked
            # which changes state to _CORE_MQTT_CONNECTED
            pass
        elif _core_state == _CORE_MQTT_CONNECTED:
            subscribe_mqtt_topics()
            _core_state = _CORE_MQTT_LOOP
        elif _core_state == _CORE_MQTT_LOOP:
            # The MQTT library loop takes exactly 1 or 2 seconds to complete
            _mqtt_loop()
            # Process any pending script received by _mqtt_on_message()
            if _mqtt_pending_script is not None:
                print("@@ Loop: Process new pending script")
                if _script_loader.newScript(script=_mqtt_pending_script, saveToNVM=True):
                    update_script_settings()
                    compute_mqtt_topics()
                    subscribe_mqtt_topics()
                _mqtt_pending_script = None
                gc.collect()
        if _old_cs != _core_state:
            print("@@ CORE STATE:", _old_cs, "=>", _core_state)
            _old_cs = _core_state

        blink_wifi()
        _matrix.display.refresh(minimum_frames_per_second=0)
        _script_loader.updateDisplay()
        end_ts = time.monotonic()
        delta_ts = end_ts - start_ts
        if delta_ts < 1: time.sleep(0.25)  # prevent busy loop
        print("@@ loop", _core_state, ":", delta_ts)

#~~
