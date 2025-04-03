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

# from drawing_state import DrawingState
from script_parser import ScriptParser, FONT_Y_OFFSET


_led = None
_mqtt = None
_matrix = None
_fonts = []
# _states = []
_script = None
_boot_btn = None
_button_down = None
_button_up = None
_logger = logging.getLogger("DistantSignal")
_logger.setLevel(logging.INFO)      # INFO or DEBUG

SX = 64
SY = 32

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

MQTT_TOPIC_ROOT          = "distantsignal"
MQTT_TOPIC_SUBSCRIPTION  = "/#"
MQTT_TOPIC_LENGTH        = "/length"
MQTT_TOPIC_BRIGHTNESS    = "/brightness"
MQTT_TOPIC_SCRIPT_INIT   = "/script/init"
MQTT_TOPIC_SCRIPT_EVENT  = "/script/event"
MQTT_TOPIC_EVENT_TRIGGER = "/event/trigger"

# the current working directory (where this file is)
CWD = ("/" + __file__).rsplit("/", 1)[
    0
]

FONT_3x5_PATH1 = CWD + "/tom-thumb.bdf"
FONT_3x5_PATH2 = CWD + "/tom-thumb2.bdf"


def init() -> None:
    print("@@ init")
    global _led, _boot_btn

    try:
        mqtt_topic_root = os.getenv("MQTT_TOPIC_ROOT", "").strip()
        if mqtt_topic_root:
            global MQTT_TOPIC_ROOT
            MQTT_TOPIC_ROOT = mqtt_topic_root
            print("@@ Settings.toml: MQTT_TOPIC_ROOT set to", MQTT_TOPIC_ROOT)
    except Exception as e:
        print("@@ Settings.toml: Invalid MQTT_TOPIC_ROOT variable ", e)

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

def init_display():
    global _matrix, _fonts
    displayio.release_displays()
    _matrix = Matrix(
        width=64,
        height=64,
        bit_depth=3,
        serpentine=True,
        tile_rows=1,
        alt_addr_pins=[
            board.MTX_ADDRA,
            board.MTX_ADDRB,
            board.MTX_ADDRC,
            board.MTX_ADDRD,
            board.MTX_ADDRE
        ],
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
    t.color = 0x202020
    loading_group.append(t)
    display.root_group = loading_group

def _mqtt_on_connected(client, userdata, flags, rc):
    # This function will be called when the client is connected successfully to the broker.
    print("@Q MQTT: Connected")
    # Subscribe to all changes.
    client.subscribe(MQTT_TOPIC_ROOT + MQTT_TOPIC_SUBSCRIPTION)
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
        if topic == MQTT_TOPIC_ROOT + MQTT_TOPIC_LENGTH:
            pass
        elif topic == MQTT_TOPIC_ROOT + MQTT_TOPIC_BRIGHTNESS:
            pass
        elif topic == MQTT_TOPIC_ROOT + MQTT_TOPIC_SCRIPT_INIT:
            pass
        elif topic == MQTT_TOPIC_ROOT + MQTT_TOPIC_SCRIPT_EVENT:
            pass
        elif topic == MQTT_TOPIC_ROOT + MQTT_TOPIC_EVENT_TRIGGER:
            pass
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

def mk_script():
    global _script

    _script = ScriptParser(SX, SY, _fonts)
    _script.parseJson("""
{
    "title":  [
        {"op": "text", "x": 0, "y": 0, "t": "T330", "rgb": "#7F7F7F", "scale": 2, "font": 2 }
    ],
    "block_active": [
        {"op": "rect", "x": -2, "y": -1, "w": "16+3", "h": "7", "rgb": "#222200" },
        {"op": "text", "x":  0, "y":  0, "t": "NAME", "rgb": "#000000" }
    ],
    "block_inactive": [
        {"op": "text", "x":  0, "y": 0, "t": "NAME", "rgb": "#222222" }
    ],
    "blocks": {
        "b321": {
            "active"  : [ { "tmpl": "block_active"  , "vars" : { "NAME": "B321" }, "x": -16, "y":  2 } ],
            "inactive": [ { "tmpl": "block_inactive", "vars" : { "NAME": "B321" }, "x": -16, "y":  2 } ]
        },
        "b320": {
            "active"  : [ { "tmpl": "block_active"  , "vars" : { "NAME": "B320" }, "x": -16, "y": -6 } ],
            "inactive": [ { "tmpl": "block_inactive", "vars" : { "NAME": "B320" }, "x": -16, "y": -6 } ]
        },
        "b330": {
            "active"  : [ { "tmpl": "block_active"  , "vars" : { "NAME": "B330" }, "x":   2, "y": -6 } ],
            "inactive": [ { "tmpl": "block_inactive", "vars" : { "NAME": "B330" }, "x":   2, "y": -6 } ]
        }
    },
    "states": {
        "normal": [
            { "#": "B321 red" },
            { "op": "line", "x1": "26-2", "y1":  20      , "x2": "38-2", "y2": "20-12+1", "rgb": "#220000" },
            { "op": "line", "x1": "38-2", "y1": "20-12+1", "x2":  64   , "y2": "20-12+1", "rgb": "#220000" },
            { "op": "line", "x1": "26+5", "y1":  20      , "x2":  38   , "y2": "20-12+5", "rgb": "#220000" },
            { "op": "line", "x1": "38  ", "y1": "20-12+5", "x2":  64   , "y2": "20-12+5", "rgb": "#220000" },
            { "#": "B320 green" },
            { "op": "rect", "x": 0, "y": "20-1", "w": 64, "h": 6, "rgb": "#007F00" }
        ],
        "reverse": [
            { "#": "B320 red" },
            { "op": "line", "x1": "26", "y1":  20   , "x2": 64, "y2":  20   , "rgb": "#220000" },
            { "op": "line", "x1": "26", "y1": "20+4", "x2": 64, "y2": "20+4", "rgb": "#220000" },
            { "#": "B321 green" },
            { "op": "poly", "rgb": "#007F00", "pts": [
                { "x": 0, "y": "20-1" }, { "x": "26-2", "y": "20-1" },
                { "x": "38-2", "y": "20-12" }, { "x": 64, "y": "20-12" },
                { "x": 64, "y": "20-12+6" },
                { "x": 38, "y": "20-12+6" },
                { "x": 26, "y": "20+5" }, { "x": 0, "y": "20+5" }
             ] }
        ]
    }
}
    """)


def loop() -> None:
    print("@@ loop")

    # # Sleep a few seconds at boot
    _led.fill(COL_LED_ERROR[CODE_OK])
    for i in range(0, 3):
        print(i)
        blink()
        time.sleep(1)

    blink()

    init_display()

    mk_script()
    states = [ "normal", "reverse" ]
    active_blocks = {
        0: [ "b330", "b320" ],
        1: [ "b330", "b321" ],
    }
    state_index = 0 
    _script.display(_matrix.display, states[state_index], active_blocks[state_index])

    while True:
        start_ts = time.monotonic()
        blink()
        _mqtt_loop()    # This takes 1~2 seconds
        _matrix.display.refresh(minimum_frames_per_second=0)
        if not _button_down.value or not _button_up.value:
            state_index = (state_index + 1) % len(states)
            _script.display(_matrix.display, states[state_index], active_blocks[state_index])
        end_ts = time.monotonic()
        delta_ts = end_ts - start_ts
        if delta_ts < 1: time.sleep(0.25)  # prevent busy loop
        print("@@ loop: ", delta_ts)


if __name__ == "__main__":
    init()
    init_buttons()
    init_wifi()
    init_mqtt()
    loop()

#~~
