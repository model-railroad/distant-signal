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

from drawing_state import DrawingState


_led = None
_mqtt = None
_matrix = None
_fonts = []
_states = []
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
    # glyphs = b"0123456789BCT"
    # font1.load_glyphs(glyphs)
    # font2.load_glyphs(glyphs)

    # gT = displayio.Group()
    # gN = displayio.Group()
    # # root_group.append(self)

    # pal_blue = displayio.Palette(1)
    # pal_blue[0] = 0x0000FF
    # pal_green = displayio.Palette(1)
    # pal_green[0] = 0x00FF00
    # pal_red = displayio.Palette(1)
    # pal_red[0] = 0xFF0000
    # pal_green2 = displayio.Palette(1)
    # pal_green2[0] = 0x002000
    # pal_red2 = displayio.Palette(1)
    # pal_red2[0] = 0x200000
    # pal_gray = displayio.Palette(1)
    # pal_gray[0] = 0x002000

    # # circle = vectorio.Circle(
    # #     pixel_shader=pal_blue,
    # #      radius=12, x=32, y=16)
    # # g.append(circle)

    # r330T = vectorio.Rectangle(
    #     pixel_shader=pal_red,
    #     width=26,
    #     height=4,
    #     x=0,
    #     y=20
    # )
    # r330N = vectorio.Rectangle(
    #     pixel_shader=pal_green,
    #     width=26,
    #     height=4,
    #     x=0,
    #     y=20
    # )
    # gT.append(r330T)
    # gN.append(r330N)

    # r321T = vectorio.Rectangle(
    #     pixel_shader=pal_red,
    #     width=26,
    #     height=4,
    #     x=64-26,
    #     y=20-12
    # )
    # r321N = vectorio.Rectangle(
    #     pixel_shader=pal_red2,
    #     width=26,
    #     height=4,
    #     x=64-26,
    #     y=20-12
    # )
    # gT.append(r321T)
    # gN.append(r321N)

    # r320T = vectorio.Rectangle(
    #     pixel_shader=pal_green2,
    #     width=26,
    #     height=4,
    #     x=64-26,
    #     y=20
    # )
    # r320N = vectorio.Rectangle(
    #     pixel_shader=pal_green,
    #     width=26,
    #     height=4,
    #     x=64-26,
    #     y=20
    # )
    # gT.append(r320T)
    # gN.append(r320N)

    # pT = vectorio.Polygon(
    #     pixel_shader=pal_red,
    #     x=26,
    #     y=20,
    #     points=[ 
    #         (0,0), (0,4), 
    #         (64-26-26, -12+4), (64-26-26, -12),
    #         (64-26-26-1, -12), (0,-1) ]
    # )
    # gT.append(pT)

    # rN = vectorio.Rectangle(
    #     pixel_shader=pal_green,
    #     x=26,
    #     y=20,
    #     width=64-26-26,
    #     height=4
    # )
    # gN.append(rN)

    # for t in [  (0,      0,    "T330", 2, 0x808080, 0x808080, font1), 
    #             (64-4*4, 0,    "B321", 1, 0x808080, 0x202020, font2), 
    #             (64-4*4, 32-5, "B320", 1, 0x202020, 0x808080, font2)]:
    #     text1 = Label(t[6])
    #     text1.x = t[0]
    #     text1.y = t[1]+3*t[3]
    #     text1.text = t[2]
    #     text1.scale = t[3]
    #     text1.color = t[4]        
    #     gT.append(text1)

    #     text1 = Label(t[6])
    #     text1.x = t[0]
    #     text1.y = t[1]+3*t[3]
    #     text1.text = t[2]
    #     text1.scale = t[3]
    #     text1.color = t[5]
    #     gN.append(text1)

    # thrown=False
    # while True:
    #     if thrown:
    #         # r330.pixel_shader = pal_red
    #         # r321.pixel_shader = pal_red
    #         # r320.pixel_shader = pal_gray
    #         display.root_group = gT
    #     else:
    #         # r330.pixel_shader = pal_green
    #         # r321.pixel_shader = pal_gray
    #         # r320.pixel_shader = pal_green
    #         display.root_group = gN
    #     display.refresh(minimum_frames_per_second=0)
    #     time.sleep(0.5)
    #     if not _button_down.value or not _button_up.value:
    #         thrown = not thrown



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
    # Normal state: B320 to B330
    s1 = DrawingState(SX, SY, _fonts)
    s1.parse("""
    T   0  0 "T330" #F0F0F0 font1 scale2 ;
    T -16  2 "B321" #202020 font2 scale1 ;
    T -16 -6 "B320" #F0F0F0 ;
    T   2 -6 "B330" #F0F0F0 ;
    # B321 red ;
    L 26-2 20      38-2 20-12+1 #200000 ;
    L 38-2 20-12+1 64   20-12+1 #200000 ;
    L 26+5 20      38   20-12+5 #200000 ;
    L 38   20-12+5 64   20-12+5 #200000 ;
    # B320 green ;
    R    0 20-1 64  6  #00FF00;
    """)

    # Thrown state: B321 to B330
    s2 = DrawingState(SX, SY, _fonts)
    s2.parse("""
    T   0  0 "T330" #F0F0F0 font1 scale2 ;
    T -16  2 "B321" #F0F0F0 font2 scale1 ;
    T -16 -6 "B320" #202020 ;
    T   2 -6 "B330" #F0F0F0 ;
    # B320 red ;
    L  26 20   64 20    #200000;
    L  26 20+4 64 20+4  #200000;
    # B321 green ;
    P   0 20-1   26-2 20-1   38-2 20-12   64 20-12
                                          64 20-12+6
                             38   20-12+6
                 26   20+5
        0 20+5   #00FF00 ;
    """)
    _states.append(s2)
    _states.append(s1)



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
    state_index = 0
    _states[state_index].display(_matrix.display)

    while True:
        start_ts = time.monotonic()
        blink()
        _mqtt_loop()    # This takes 1~2 seconds
        _matrix.display.refresh(minimum_frames_per_second=0)
        if not _button_down.value or not _button_up.value:
            state_index = (state_index + 1) % len(_states)
            _states[state_index].display(_matrix.display)
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
