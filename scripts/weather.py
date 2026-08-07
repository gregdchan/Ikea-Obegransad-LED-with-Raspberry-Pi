import requests
import config
from config import p_clear, render_char
import time

# Key/city are read off `config` at call time, not imported by value — otherwise
# the .env value and the UI's update_settings() would never reach this module.
CACHE_DURATION = 3600  # 1 hour in seconds

last_request_time = 0
cached_temperature = None
_last_temp_display = None  # Cache last displayed temperature to avoid redraws
_has_drawn_once = False    # Ensure weather draws at least once after a mode switch

def get_weather():
    global last_request_time, cached_temperature

    current_time = time.time()
    if current_time - last_request_time < CACHE_DURATION and cached_temperature is not None:
        return cached_temperature

    if not config.weather_api_key:
        print("[get_weather] No WEATHER_API_KEY set (.env or web UI); skipping fetch.")
        return None

    URL = "http://api.openweathermap.org/data/2.5/weather"
    params = {'q': config.weather_city, 'appid': config.weather_api_key, 'units': 'imperial'}
    try:
        response = requests.get(URL, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        cached_temperature = data['main']['temp']
        last_request_time = current_time
        return cached_temperature
    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data: {e}")
        # Fallback to last known temperature if available
        if cached_temperature is not None:
            return cached_temperature
        return None

def display_temperature(force=False):
    global _last_temp_display, _has_drawn_once
    temperature = get_weather()

    # If temperature is known, render it; otherwise show a fallback so screen isn't blank
    if temperature is not None:
        temp_int = int(temperature)
        temp_str = str(temp_int)

        # Redraw if temp changed OR we haven't drawn any weather frame yet
        if force or temp_str != _last_temp_display or not _has_drawn_once:
            p_clear()
            # Center horizontally; large glyph advance ~7px (6 + 1 spacing)
            # Two-glyph rows center at x0 = (16 - 14) // 2 = 1
            x0 = 1
            if len(temp_str) == 1:
                # One digit + 'F' side-by-side on top row, centered (total width 14)
                render_char(x0 + 0, 0, temp_str[0], size="large")
                render_char(x0 + 8, 0, 'F', size="large")
            elif len(temp_str) == 2:
                # Two digits centered on top; 'F' centered on bottom
                render_char(x0 + 0, 0, temp_str[0], size="large")
                render_char(x0 + 8, 0, temp_str[1], size="large")
                # Center single 'F': (16 - 7) // 2 = 4
                render_char(4, 8, 'F', size="large")
            elif len(temp_str) == 3:
                # Top two digits centered; bottom third digit + 'F' centered as a pair
                render_char(x0 + 0, 0, temp_str[0], size="large")
                render_char(x0 + 8, 0, temp_str[1], size="large")
                render_char(x0 + 0, 8, temp_str[2], size="large")
                render_char(x0 + 8, 8, 'F', size="large")
            _last_temp_display = temp_str
            _has_drawn_once = True
    else:
        # Show fallback once if we haven't drawn weather recently
        if force or _last_temp_display != "__NA__" or not _has_drawn_once:
            p_clear()
            # Render "NA" with F to indicate unavailable
            render_char(0, 0, 'N', size="large")
            render_char(8, 0, 'A', size="large")
            render_char(0, 8, 'F', size="large")
            _last_temp_display = "__NA__"
            _has_drawn_once = True
