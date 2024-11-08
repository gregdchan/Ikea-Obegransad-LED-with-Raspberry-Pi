import RPi.GPIO as GPIO
from threading import Event, Lock
import time

ROWS = 16
COLS = 16

# Add a flag to track the state of the display (on or off)
display_on = True  # Initially, the display is on

# Disable warnings and setup GPIO mode
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# GPIO pin mappings
P_EN = 17     # Brightness control (PWM pin)
P_DI = 2      # Data pin
P_CLK = 3     # Clock pin
P_CLA = 27    # Latch pin
P_KEY = 16    # Key input pin

# GPIO setup
GPIO.setup(P_EN, GPIO.OUT)
GPIO.setup(P_DI, GPIO.OUT)
GPIO.setup(P_CLK, GPIO.OUT)
GPIO.setup(P_CLA, GPIO.OUT)
GPIO.setup(P_KEY, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Brightness levels (in steps from 0 to 255)
brightness_levels = [0, 64, 128, 192, 255]  # Predefined brightness steps
brightness_index = 0  # Start with the first level

# PWM setup
pwm = GPIO.PWM(P_EN, 1000)  # 1 kHz frequency
pwm.start(brightness_levels[brightness_index] / 255 * 100)

# Shared lock and event to synchronize scrolling with the main display
display_lock = Lock()
scrolling_event = Event()
scrolling_event.set()  # Initially allow time/weather display to run

# Event to signal a clean shutdown
shutdown_event = Event()

def set_brightness(brightness_value):
    inverted_brightness = 255 - brightness_value
    duty_cycle = inverted_brightness / 255 * 100  # Calculate the duty cycle
    pwm.ChangeDutyCycle(duty_cycle)  # Directly set the duty cycle
    print(f"Set brightness to {brightness_value}, duty cycle: {duty_cycle}")

def p_clear():
    global p_buf
    with display_lock:
        p_buf = [0] * 256

def p_scan():
    with display_lock:
        for i in range(256):
            GPIO.output(P_DI, p_buf[i])
            GPIO.output(P_CLK, GPIO.HIGH)
            GPIO.output(P_CLK, GPIO.LOW)
    
        GPIO.output(P_CLA, GPIO.HIGH)
        GPIO.output(P_CLA, GPIO.LOW)

# LUT for OBEGRÄNSAD (pixel index lookup table for the 16x16 matrix)
lut = [
    [23, 22, 21, 20, 19, 18, 17, 16, 7, 6, 5, 4, 3, 2, 1, 0],
    [24, 25, 26, 27, 28, 29, 30, 31, 8, 9, 10, 11, 12, 13, 14, 15],
    [39, 38, 37, 36, 35, 34, 33, 32, 55, 54, 53, 52, 51, 50, 49, 48],
    [40, 41, 42, 43, 44, 45, 46, 47, 56, 57, 58, 59, 60, 61, 62, 63],
    [87, 86, 85, 84, 83, 82, 81, 80, 71, 70, 69, 68, 67, 66, 65, 64],
    [88, 89, 90, 91, 92, 93, 94, 95, 72, 73, 74, 75, 76, 77, 78, 79],
    [103, 102, 101, 100, 99, 98, 97, 96, 119, 118, 117, 116, 115, 114, 113, 112],
    [104, 105, 106, 107, 108, 109, 110, 111, 120, 121, 122, 123, 124, 125, 126, 127],
    [151, 150, 149, 148, 147, 146, 145, 144, 135, 134, 133, 132, 131, 130, 129, 128],
    [152, 153, 154, 155, 156, 157, 158, 159, 136, 137, 138, 139, 140, 141, 142, 143],
    [167, 166, 165, 164, 163, 162, 161, 160, 183, 182, 181, 180, 179, 178, 177, 176],
    [168, 169, 170, 171, 172, 173, 174, 175, 184, 185, 186, 187, 188, 189, 190, 191],
    [215, 214, 213, 212, 211, 210, 209, 208, 199, 198, 197, 196, 195, 194, 193, 192],
    [216, 217, 218, 219, 220, 221, 222, 223, 200, 201, 202, 203, 204, 205, 206, 207],
    [231, 230, 229, 228, 227, 226, 225, 224, 247, 246, 245, 244, 243, 242, 241, 240],
    [232, 233, 234, 235, 236, 237, 238, 239, 248, 249, 250, 251, 252, 253, 254, 255]
]

# Font data for large 6x7 uppercase letters and digits (A-Z, 0-9)
System6x7 = [
    # 0-9
    0x3E, 0x7F, 0x63, 0x63, 0x7F, 0x3E,  # 0
    0x00, 0x00, 0x7F, 0x7F, 0x00, 0x00,  # 1
    0x62, 0x73, 0x7B, 0x6B, 0x6F, 0x66,  # 2
    0x22, 0x63, 0x6B, 0x6B, 0x7F, 0x36,  # 3
    0x0F, 0x0F, 0x08, 0x08, 0x7F, 0x7F,  # 4
    0x2F, 0x6F, 0x6B, 0x6B, 0x7B, 0x3B,  # 5
    0x3E, 0x7F, 0x6B, 0x6B, 0x7B, 0x3A,  # 6
    0x03, 0x03, 0x7B, 0x7B, 0x0F, 0x07,  # 7
    0x36, 0x7F, 0x6B, 0x6B, 0x7F, 0x36,  # 8
    0x26, 0x6F, 0x6B, 0x6B, 0x7F, 0x3E,  # 9
    0x3E, 0x7F, 0x11, 0x11, 0x7F, 0x7F,  # A
    0x7F, 0x7F, 0x49, 0x49, 0x7F, 0x36,  # B
    0x3E, 0x7F, 0x41, 0x41, 0x63, 0x22,  # C
    0x7F, 0x7F, 0x41, 0x41, 0x7F, 0x3E,  # D
    0x7F, 0x7F, 0x49, 0x49, 0x41, 0x41,  # E
    0x7F, 0x7F, 0x09, 0x09, 0x01, 0x01,  # F
    0x3E, 0x7F, 0x41, 0x49, 0x79, 0x7A,  # G
    0x7F, 0x7F, 0x08, 0x08, 0x7F, 0x7F,  # H
    0x00, 0x41, 0x7F, 0x7F, 0x41, 0x00,  # I
    0x20, 0x60, 0x41, 0x7F, 0x3F, 0x01,  # J
    0x7F, 0x7F, 0x08, 0x1C, 0x77, 0x63,  # K
    0x7F, 0x7F, 0x40, 0x40, 0x40, 0x40,  # L
    0x7F, 0x7F, 0x0E, 0x1C, 0x0E, 0x7F,  # M
    0x7F, 0x7F, 0x0E, 0x1C, 0x38, 0x7F,  # N
    0x3E, 0x7F, 0x41, 0x41, 0x7F, 0x3E,  # O
    0x7F, 0x7F, 0x09, 0x09, 0x0F, 0x06,  # P
    0x3E, 0x7F, 0x41, 0x71, 0x3F, 0x5E,  # Q
    0x7F, 0x7F, 0x09, 0x39, 0x7F, 0x46,  # R
    0x26, 0x6F, 0x49, 0x49, 0x7B, 0x32,  # S
    0x01, 0x01, 0x7F, 0x7F, 0x01, 0x01,  # T
    0x3F, 0x7F, 0x40, 0x40, 0x7F, 0x3F,  # U
    0x1F, 0x3F, 0x60, 0x60, 0x3F, 0x1F,  # V
    0x7F, 0x7F, 0x30, 0x18, 0x30, 0x7F,  # W
    0x77, 0x7F, 0x08, 0x08, 0x7F, 0x77,  # X
    0x07, 0x0F, 0x78, 0x78, 0x0F, 0x07,  # Y
    0x71, 0x79, 0x49, 0x4D, 0x47, 0x43,  # Z
    0x00, 0x00, 0x5F, 0x5F, 0x00, 0x00,  # Exclamation mark (!)
    0x02, 0x03, 0x51, 0x59, 0x0F, 0x06,  # Question mark (?)
    0x47, 0x27, 0x18, 0x0C, 0x72, 0x71,  # Percent sign (%)
    0x24, 0x2E, 0x7F, 0x7F, 0x3A, 0x12,  # Dollar sign ($)
    0x14, 0x7F, 0x7F, 0x14, 0x7F, 0x7F,  # Hash (#)
    0x3E, 0x41, 0x5D, 0x55, 0x5E, 0x00,  # At symbol (@)
    0x36, 0x7F, 0x49, 0x5F, 0x76, 0x50,  # Ampersand (&)
    0x08, 0x1C, 0x36, 0x63, 0x41, 0x00,  # Less-than sign (<)
    0x41, 0x63, 0x36, 0x1C, 0x08, 0x00,  # Greater-than sign (>)
    0x00, 0x60, 0x60, 0x00, 0x00, 0x00,  # Period (.)
    0x60, 0x30, 0x18, 0x0C, 0x06, 0x03,  # Forward slash (/)
    0x1C, 0x3E, 0x63, 0x41, 0x00, 0x00,  # Open parenthesis (()
    0x00, 0x41, 0x63, 0x3E, 0x1C, 0x00,  # Close parenthesis ())
    0x22, 0x14, 0x7F, 0x14, 0x22, 0x00,  # Asterisk (*)
    0x04, 0x02, 0x01, 0x02, 0x04, 0x00,  # Caret (^)
    0x30, 0x48, 0x48, 0x30, 0x00, 0x00,  # Tilde (~)
    0x00, 0x36, 0x36, 0x00, 0x00, 0x00,  # Colon (:)
    0x00, 0x56, 0x36, 0x00, 0x00, 0x00,  # Semicolon (;)
    0x00, 0x00, 0x07, 0x07, 0x00, 0x00,   # Apostrophe (')
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # Padding to center the character
    0x00, 0x00, 0x00, 0x60, 0x60, 0x20,  # Comma (,)
    ]

# Mapping of characters to their starting index in the System6x7 font data
char_map = {
    '0': 0, '1': 6, '2': 12, '3': 18, '4': 24, '5': 30, '6': 36, '7': 42, '8': 48, '9': 54,
    'A': 60, 'B': 66, 'C': 72, 'D': 78, 'E': 84, 'F': 90, 'G': 96, 'H': 102, 'I': 108,
    'J': 114, 'K': 120, 'L': 126, 'M': 132, 'N': 138, 'O': 144, 'P': 150, 'Q': 156,
    'R': 162, 'S': 168, 'T': 174, 'U': 180, 'V': 186, 'W': 192, 'X': 198, 'Y': 204,
    'Z': 210, '!': 216, '?': 222, '%': 228, '$': 234, '#': 240, '@': 246, '&': 252,
    '<': 258, '>': 264, '.': 270, '/': 276, '(': 282, ')': 288, '*': 294, '^': 300, 
    '~': 306, ':': 312, ';': 318, "'": 324, ',': 330
}

# SmallFont4x5 font mapping, adjusted for `lut` compatibility and to fix errors.
SmallFont4x5 = [
    # A-Z in 4x5 grid representation
    0x1E, 0x09, 0x09, 0x1E,  # A
    0x1F, 0x15, 0x15, 0x0A,  # B
    0x0E, 0x11, 0x11, 0x0A,  # C
    0x1F, 0x11, 0x11, 0x0E,  # D
    0x1F, 0x15, 0x15, 0x11,  # E
    0x1F, 0x05, 0x05, 0x01,  # F
    0x0E, 0x11, 0x15, 0x1D,  # G
    0x1F, 0x04, 0x04, 0x1F,  # H
    0x11, 0x1F, 0x11, 0x00,  # I
    0x10, 0x11, 0x0F, 0x01,  # J
    0x1F, 0x04, 0x0A, 0x11,  # K
    0x1F, 0x10, 0x10, 0x10,  # L
    0x1F, 0x02, 0x02, 0x1F,  # M
    0x1F, 0x02, 0x04, 0x1F,  # N
    0x0E, 0x11, 0x11, 0x0E,  # O
    0x1F, 0x05, 0x05, 0x02,  # P
    0x0E, 0x11, 0x19, 0x1E,  # Q
    0x1F, 0x05, 0x0D, 0x12,  # R
    0x12, 0x15, 0x15, 0x09,  # S
    0x01, 0x1F, 0x01, 0x01,  # T
    0x0F, 0x10, 0x10, 0x1F,  # U
    0x07, 0x08, 0x10, 0x1F,  # V
    0x1F, 0x08, 0x08, 0x1F,  # W
    0x11, 0x0A, 0x04, 0x0A,  # X     
    0x01, 0x02, 0x1C, 0x02,  # Y
    0x19, 0x15, 0x15, 0x13,  # Z

    # Numbers in 4x5 grid representation
    0x1E, 0x11, 0x11, 0x1E,  # 0
    0x12, 0x1F, 0x10, 0x00,  # 1
    0x1D, 0x15, 0x15, 0x17,  # 2
    0x15, 0x15, 0x15, 0x1F,  # 3
    0x07, 0x04, 0x1F, 0x04,  # 4
    0x17, 0x15, 0x15, 0x1D,  # 5
    0x1E, 0x15, 0x15, 0x1D,  # 6
    0x01, 0x01, 0x1F, 0x00,  # 7
    0x1F, 0x15, 0x15, 0x1F,  # 8
    0x17, 0x15, 0x15, 0x1E,  # 9

    # Additional small symbols
    0x00, 0x00, 0x4F, 0x4F,  # Exclamation mark (!)
    0x02, 0x03, 0x51, 0x59,  # Question mark (?)
    0x47, 0x27, 0x18, 0x0C,  # Percent sign (%)
    0x24, 0x2E, 0x7F, 0x7F,  # Dollar sign ($)
    0x14, 0x7F, 0x7F, 0x14,  # Hash (#)
    0x3E, 0x41, 0x5D, 0x55,  # At symbol (@)
    0x36, 0x7F, 0x49, 0x5F,  # Ampersand (&)
    0x08, 0x1C, 0x36, 0x63,  # Less-than sign (<)
    0x41, 0x63, 0x36, 0x1C,  # Greater-than sign (>)
    0x00, 0x60, 0x60, 0x00,  # Period (.)
    0x60, 0x30, 0x18, 0x0C,  # Forward slash (/)
    0x1C, 0x3E, 0x63, 0x41,  # Open parenthesis (()
    0x00, 0x41, 0x63, 0x3E,  # Close parenthesis ())
    0x22, 0x14, 0x7F, 0x14,  # Asterisk (*)
    0x04, 0x02, 0x01, 0x02,  # Caret (^)
    0x30, 0x48, 0x48, 0x30,  # Tilde (~)
    0x00, 0x36, 0x36, 0x00,  # Colon (:)
    0x00, 0x56, 0x36, 0x00,  # Semicolon (;)
    0x00, 0x00, 0x07, 0x07,  # Apostrophe (')
    0x00, 0x00, 0x00, 0x00,  # Padding for spacing
    0x00, 0x00, 0x00, 0x60   # Comma (,)
]

# Updated mapping for small characters based on their starting index in SmallFont4x5.
small_char_map = {
    'a': 0, 'b': 4, 'c': 8, 'd': 12, 'e': 16, 'f': 20, 'g': 24,
    'h': 28, 'i': 32, 'j': 36, 'k': 40, 'l': 44, 'm': 48, 'n': 52,
    'o': 56, 'p': 60, 'q': 64, 'r': 68, 's': 72, 't': 76, 'u': 80,
    'v': 84, 'w': 88, 'x': 92, 'y': 96, 'z': 100,
    '0': 104, '1': 108, '2': 112, '3': 116, '4': 120, '5': 124,
    '6': 128, '7': 132, '8': 136, '9': 140,
    '!': 144, '?': 148, '%': 152, '$': 156, '#': 160, '@': 164, '&': 168,
    '<': 172, '>': 176, '.': 180, '/': 184, '(': 188, ')': 192, '*': 196,
    '^': 200, '~': 204, ':': 208, ';': 212, "'": 216, ' ': 220, ',': 224
}

def p_drawPixel(x, y, color):
    if 0 <= x < COLS and 0 <= y < ROWS:
        index = lut[y][x]
        p_buf[index] = color

def render_char(xs, ys, ch, size="small"):
    if size == "large" and ch in char_map:
        char_pos = char_map[ch]
        for col in range(6):
            col_data = System6x7[char_pos + col]
            for row in range(7):
                if col_data & (1 << row):
                    p_drawPixel(xs + col, ys + row, 1)
    elif size == "small" and ch.lower() in small_char_map:
        char_pos = small_char_map[ch.lower()]
        for col in range(4):
            col_data = SmallFont4x5[char_pos + col]
            for row in range(5):
                if col_data & (1 << row):
                    p_drawPixel(xs + col, ys + row, 1)
    else:
        print(f"[render_char] Character '{ch}' not found in font data.")

# config.py
def render_word(word, x_start=0, y_start=0, large_numbers=True):
    """
    Renders a word with context-sensitive sizes for numbers and symbols.
    Numbers adjust size based on surrounding text if `large_numbers` is False.
    """
    p_clear()  # Clear the display buffer before rendering the entire word
    x_offset = x_start
    length = len(word)

    for i, ch in enumerate(word):
        # Determine character size based on context or `large_numbers` flag
        if ch.isdigit():
            # Determine size based on context if `large_numbers` is False
            if large_numbers:
                size = "large"
            else:
                # Check if previous or next character is uppercase
                prev_is_large = i > 0 and (word[i - 1].isupper() or word[i - 1].isdigit())
                next_is_large = i < length - 1 and (word[i + 1].isupper() or word[i + 1].isdigit())
                size = "large" if prev_is_large or next_is_large else "small"
        else:
            # For letters and symbols, set size based on uppercase or lowercase
            size = "large" if ch.isupper() else "small"

        render_char(x_offset, y_start, ch, size)  # Render each character with appropriate size
        x_offset += 8 if size == "large" else 6  # Adjust spacing for different font sizes

def handle_key_input():
    global brightness_index
    if GPIO.input(P_KEY) == GPIO.LOW:
        print("Key Pressed!")
        brightness_index = (brightness_index + 1) % len(brightness_levels)
        set_brightness(brightness_levels[brightness_index])
        time.sleep(0.3)
        print("Brightness Level:", brightness_levels[brightness_index])

def pause_display():
    global display_on
    print("[pause_display] Pausing time and weather display for scrolling text.")
    scrolling_event.clear()
    display_on = False

def resume_display():
    global display_on
    print("[resume_display] Resuming time and weather display after scrolling text.")
    scrolling_event.set()
    display_on = True

def shutdown():
    print("[shutdown] Shutting down...")
    shutdown_event.set()
    scrolling_event.set()
    GPIO.cleanup()