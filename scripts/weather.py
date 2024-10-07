import requests
from config import p_clear, render_char
import time

API_KEY = 'af50f219c5524ff5c8971e5761e3e589'
CITY = 'new york city'
CACHE_DURATION = 3600  # 1 hour in seconds

last_request_time = 0
cached_temperature = None

def get_weather():
    global last_request_time, cached_temperature

    current_time = time.time()
    if current_time - last_request_time < CACHE_DURATION and cached_temperature is not None:
        return cached_temperature

    URL = "http://api.openweathermap.org/data/2.5/weather"
    params = {'q': CITY, 'appid': API_KEY, 'units': 'imperial'}
    try:
        response = requests.get(URL, params=params)
        response.raise_for_status()
        data = response.json()
        cached_temperature = data['main']['temp']
        last_request_time = current_time
        return cached_temperature
    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data: {e}")
        return None

def display_temperature():
    p_clear()
    temperature = get_weather()
    
    if temperature is not None:
        temp_str = f"{int(temperature)}F"
        positions = [(0, 0), (8, 0), (4, 8)]
        for i, char in enumerate(temp_str):
            x_pos, y_pos = positions[i] if i < 2 else positions[2]
            render_char(x_pos, y_pos, char)
