# IKEA Obegränsad × Raspberry Pi

Control the IKEA × Swedish House Mafia **Obegränsad** 16×16 LED wall lamp with a
Raspberry Pi and Python — a clock, local weather, scrolling messages, animations,
and countdown/Pomodoro timers, all driven from a web dashboard on your phone.

Most Obegränsad mods run Arduino/ESP firmware. This project takes the same
hardware modification but drives the panel directly from a Pi's GPIO with plain
Python, so there's no toolchain to flash and everything is editable in place.

> **Heads up**
> - The mod is permanent: you unsolder the panel's controller IC and solder wires
>   to the board. Work carefully.
> - The Pi needs a network connection for the web controls and weather.
> - This is a living project — expect regular changes on `main`.

## Contents
- [Features](#features)
- [Hardware](#hardware)
- [Software setup](#software-setup)
- [Run it](#run-it)
- [Run as a service + auto-deploy](#run-as-a-service--auto-deploy)
- [Web dashboard & HTTP API](#web-dashboard--http-api)
- [How it works](#how-it-works)
- [Fonts](#fonts)
- [Developing without the hardware](#developing-without-the-hardware)

## Features
- **Clock** — large HH/MM digits, the default mode.
- **Weather** — cycles after the clock and temperature with animated conditions
  for clear day/night, clouds, rain, thunder, snow, and fog
  from OpenWeatherMap for a configurable city.
- **Messages** — scrolling text in the same large font as the clock, with
  adjustable speed and direction, or static display for 1–2 character messages.
- **Animations** — 15 built-ins: sparkle, wave, swirl, plasma, box, pingpong,
  rain, aurora, life, matrix, rings, tunnel, checker, diamond, lissajous.
- **Timers** — mm:ss countdown, plus a full Pomodoro cycle (work / short break /
  long break across N sessions).
- **Web dashboard** — power, brightness, all modes, and a live pixel preview of
  what the panel is showing right now. Also usable as a plain HTTP API.
- **Hardware button** — the lamp's original button cycles brightness.

## Hardware

You'll need:
1. An IKEA Obegränsad LED wall lamp
2. A Raspberry Pi Zero, 3, or 4 (a 3 was used here)
3. Soldering iron + wires
4. A drill to remove the panel's rivets
5. Double-sided tape or velcro to mount the Pi inside

Open the panel, remove the original controller IC, and solder leads to the pads —
follow the excellent teardown in
[ph1p/ikea-led-obegraensad](https://github.com/ph1p/ikea-led-obegraensad?tab=readme-ov-file#the-panels)
(the physical mod is identical; only the controller differs).

Then wire the panel to the Pi (BCM numbering, as set in `config.py`):

| Panel signal | Purpose                    | Pi GPIO |
|--------------|----------------------------|---------|
| EN           | Brightness (PWM, inverted) | 17      |
| DI           | Serial data                | 2       |
| CLK          | Shift clock                | 3       |
| CLA          | Latch                      | 27      |
| KEY          | Original push button       | 16      |
| GND          | Ground (×2)                | GND     |

## Software setup

On a Pi running Raspberry Pi OS (SSH + Wi-Fi configured):

```bash
sudo apt install python3-flask python3-requests python3-rpi.gpio
git clone https://github.com/gregdchan/Ikea-Obegransad-LED-with-Raspberry-Pi.git
cd Ikea-Obegransad-LED-with-Raspberry-Pi
cp .env.example .env
nano .env    # add your OpenWeatherMap API key and city
```

`.env` holds your [OpenWeatherMap](https://openweathermap.org/api) key and city.
It is gitignored so the key never lands on GitHub. Both values can also be
changed at runtime from the dashboard's settings panel (runtime changes are not
persisted — put permanent values in `.env`).

## Run it

```bash
python3 flask_server.py
```

The panel starts in clock/weather mode and the dashboard is at
`http://<pi-hostname>.local:5000`.

## Run as a service + auto-deploy

The Pi can run the server as a systemd unit (`deploy/obegransad.service`) and
poll this repo once a minute via cron (`deploy/autopull.sh`). Push to `main` and
the display picks up the change and restarts itself within 60 seconds.

One-time setup on the Pi:

```bash
sudo cp deploy/obegransad.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now obegransad
echo 'gdc ALL=(root) NOPASSWD: /usr/bin/systemctl restart obegransad' | sudo tee /etc/sudoers.d/obegransad
(crontab -l 2>/dev/null; echo '* * * * * ~/Documents/ikea-obegransad/deploy/autopull.sh >> ~/autopull.log 2>&1') | crontab -
```

Deploy log: `tail -f ~/autopull.log` · server status: `systemctl status obegransad`.
The pull is `--ff-only`: if you hand-edit files on the Pi, auto-deploy stops
rather than overwriting your work — reconcile with
`git reset --hard origin/main` when ready.

## Web dashboard & HTTP API

Every control on the dashboard is a plain HTTP endpoint, so you can drive the
panel from scripts, Home Assistant, or `curl`. POST bodies are form-encoded.
Send `X-Requested-With: fetch` (or `Accept: application/json`) to get a JSON
state snapshot back; otherwise commands redirect to `/`.

| Endpoint           | Method | Form fields                                                                          |
|--------------------|--------|--------------------------------------------------------------------------------------|
| `/status`          | GET    | — returns full device state (mode, brightness, framebuffer, timers, settings)        |
| `/turn_on`         | POST   | —                                                                                    |
| `/turn_off`        | POST   | —                                                                                    |
| `/set_brightness`  | POST   | `brightness` ∈ 0, 64, 128, 192, 255                                                  |
| `/scroll_text`     | POST   | `text`, `speed` (seconds per pixel step, 0.02–1.0)                                   |
| `/stop_scroll`     | POST   | —                                                                                    |
| `/set_animation`   | POST   | `name` (see [Features](#features)), `speed` (0.01–1.0)                               |
| `/stop_animation`  | POST   | —                                                                                    |
| `/start_countdown` | POST   | `minutes`, `seconds`                                                                 |
| `/start_pomodoro`  | POST   | `work_minutes`, `short_break_minutes`, `long_break_minutes` (1–99), `sessions` (1–12)|
| `/stop_countdown`  | POST   | — (also stops a Pomodoro)                                                            |
| `/show_clock`      | POST   | — stop everything, back to clock                                                     |
| `/update_settings` | POST   | `scroll_direction` (-1 left / 1 right), `transitions_enabled`, `weather_city`, `weather_api_key` |

Example:

```bash
curl -X POST -H 'X-Requested-With: fetch' \
     -d 'text=HELLO&speed=0.12' http://pi.local:5000/scroll_text
```

## How it works

```
flask_server.py          web UI + API, owns the worker threads
├── main.py              clock/weather loop (default mode)
├── scripts/scrolling_text.py   message scroller
├── scripts/animations.py       animation loop + the 15 animations
├── scripts/countdown.py        countdown / Pomodoro loop
├── scripts/clock.py, weather.py  renderers for the default mode
├── config.py            GPIO driver, pixel buffer, fonts glue, shared state
├── fonts.py             glyph data + preview/self-check tool
└── templates/index.html dashboard (live preview polls /status)
```

- **One frame buffer.** Every renderer draws into a shared 256-cell buffer
  (`config.p_buf`); `p_scan()` bit-bangs it to the panel's shift registers under
  a lock. The panel's LEDs are wired in a serpentine order, so `config.lut`
  maps logical (x, y) to physical index — `p_drawPixel()` handles this.
- **One mode at a time.** Renderers run as daemon threads and coordinate
  through `threading.Event` flags (`scrolling_event`, `animation_event`,
  `countdown_event`). The Flask routes stop the active mode before starting
  another (`stop_active_modes()`), so threads never fight over the buffer.
- **Brightness is PWM** on the panel's enable pin (inverted duty cycle), which
  is why on/off is just brightness 0.
- **Weather is cached** — temperature, condition, and day/night data refresh
  at most every 20 minutes. The last snapshot survives network errors, and
  `NA` is shown when there is no temperature data or API key.

## Fonts

Two bitmap fonts live in `fonts.py`, both column-major (each byte is one
column, bit 0 = top row):

- **System6x7** — large 6×7 font: digits, A–Z, punctuation. Used by the clock,
  weather, timers, and scrolling messages.
- **SmallFont4x5** — compact 4×5 font for lowercase, kept as a fallback.

Preview any glyph or string as ASCII art without touching the hardware:

```bash
python3 fonts.py            # dump every glyph in both fonts
python3 fonts.py "HELLO!"   # preview one string
```

The same command runs the font self-checks: every byte within its font's row
range (a 4×5 byte over `0x1F` means the glyph's top rows silently disappear)
and no two characters sharing identical glyph data. If you edit or add glyphs,
run it before pushing.

## Developing without the hardware

`RPi.GPIO` only exists on the Pi, but the whole stack runs anywhere by mocking
it — the tests do exactly that:

```bash
python3 test_web_interface.py   # Flask routes + rendering, mocked GPIO
python3 test_env.py             # .env loading and weather settings plumbing
python3 fonts.py                # font integrity + glyph preview
```

`test_web_interface.py` is the pattern to copy for new tests: inject
`MagicMock()` for `RPi`/`RPi.GPIO` before importing `config`, then drive the
Flask test client and assert on the framebuffer that comes back from `/status`.

## Ideas / not built yet
- Orientation control
- APDS-9960 gesture sensor
