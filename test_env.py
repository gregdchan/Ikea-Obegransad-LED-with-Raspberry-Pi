"""Check that .env values reach config and weather. Run: python3 test_env.py
ponytail: MagicMock stands in for RPi.GPIO so this runs off the Pi too."""
import os, sys, tempfile
from unittest.mock import MagicMock

sys.modules['RPi'] = MagicMock()
sys.modules['RPi.GPIO'] = MagicMock()
sys.modules['requests'] = MagicMock()

import config

with tempfile.NamedTemporaryFile('w', suffix='.env', delete=False) as f:
    f.write("# comment\n\nWEATHER_API_KEY=abc123\nWEATHER_CITY=some city\n")
    path = f.name
os.environ.pop('WEATHER_API_KEY', None)
os.environ.pop('WEATHER_CITY', None)
config._load_env(path)
assert os.environ['WEATHER_API_KEY'] == 'abc123', os.environ.get('WEATHER_API_KEY')
assert os.environ['WEATHER_CITY'] == 'some city', os.environ.get('WEATHER_CITY')
os.unlink(path)

# the leaked key must not be anywhere in the source anymore
with open(os.path.join(os.path.dirname(__file__), 'config.py')) as f:
    assert 'af50f219' not in f.read()

# weather reads config late, so a UI/env change is picked up
import scripts.weather as weather
config.update_settings(weather_city='paris', weather_api_key='key2')
assert config.weather_city == 'paris' and weather.config.weather_city == 'paris'

# no key => no request attempted
config.weather_api_key = ''
weather.cached_temperature = None
assert weather.get_weather() is None

print("ok")
