# Seven-Day Weather Forecast

A small Python desktop app that retrieves a seven-day forecast from
[Open-Meteo](https://open-meteo.com/) and suggests suitable clothing for each
day. It has weather symbols, an editable location dropdown, and remembers your
10 most recently selected locations. No API key is required.

## Requirements

- Python 3.10 or later
- The `requests` package
- Tkinter and its Tcl/Tk runtime (included with a full Python installation)
- An internet connection

Install the project dependency from the project directory:

```powershell
python -m pip install -r requirements.txt
```

Using the project's Windows virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run the GUI

```powershell
python weather.py
```

Or:

```powershell
.\.venv\Scripts\python.exe weather.py
```

Type a new town or location in the editable **Location** box and click
**Get forecast** (or press Enter). If the search finds multiple matches, select
the right one in the location dialog. You can also pick one of your previous
locations from the dropdown. Each day displays a weather symbol, a description,
high and low temperatures in Celsius, rain probability, and clothing advice.

The most recent 10 selected locations are saved between runs in
`%APPDATA%\Day2TVMaze\recent_locations.json` on Windows. On other systems, the
file is saved as `~/.day2tvmaze/recent_locations.json`.

The program detects the Tcl/Tk folders bundled with the selected Python
installation and configures them if Python's default lookup misses them. If
startup still reports that it cannot find `init.tcl`, repair or reinstall
Python with Tcl/Tk support.

## How it works

- `find_locations()` calls Open-Meteo's geocoding API to turn the typed place
  name into coordinates.
- `get_forecast()` requests seven daily forecasts for the selected coordinates:
  weather code, high and low temperatures, and maximum precipitation
  probability.
- `WEATHER_DESCRIPTIONS` and `WEATHER_SYMBOLS` translate weather codes into
  readable conditions and symbols.
- `recommend_clothing()` applies simple rules to temperatures, rain chance, and
  conditions to suggest layers, waterproofs, an umbrella, or other items.
- `WeatherApp` builds the Tkinter interface, shows the forecast cards, manages
  the editable recent-location dropdown, and persists location history.
- Network requests run on a background thread so the GUI remains responsive.
  `get_json()` uses `requests.get()` with a 15-second timeout, checks HTTP
  status, parses JSON into Python dictionaries/lists, and raises a clear error
  for request or response problems.

The clothing advice uses basic thresholds and is a rule of thumb, not a
guarantee. Check a current local forecast before making plans.

## Data sources

- Location search: [Open-Meteo Geocoding API](https://geocoding-api.open-meteo.com/v1/search)
- Weather forecast: [Open-Meteo Forecast API](https://api.open-meteo.com/v1/forecast)
- Dependency: [`requests`](https://requests.readthedocs.io/)
