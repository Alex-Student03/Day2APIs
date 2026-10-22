# Seven-Day Weather Forecast

This Python program asks for a town or location, looks up matching places, and
retrieves a seven-day forecast from [Open-Meteo](https://open-meteo.com/). It
also recommends clothing for each day using the forecast temperatures, rain
chance, and weather description.

No API key is required. Open-Meteo provides both the geocoding service used to
find the location's coordinates and the weather forecast API.

## Requirements

- Python 3.10 or later
- The `requests` package
- An internet connection

Install the dependency from the project directory:

```powershell
python -m pip install -r requirements.txt
```

If using the project's virtual environment on Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

From the project directory:

```powershell
python weather.py
```

Or, with the project's virtual environment on Windows:

```powershell
.\.venv\Scripts\python.exe weather.py
```

Enter a place name when prompted. If multiple locations match, the program
displays up to five results; enter the number for the desired location.

For each available day, the program prints the weather description, maximum
and minimum temperatures in Celsius, maximum precipitation probability, and
clothing advice.

## How it works

1. `find_locations()` sends the entered place name to Open-Meteo's geocoding
   endpoint and returns matching locations with coordinates.
2. `choose_location()` displays the matches, including region and country when
   available, and asks which one to use.
3. `get_forecast()` requests seven daily forecasts from Open-Meteo using the
   selected latitude and longitude. It asks for the weather code, daily high
   and low temperatures, and maximum precipitation probability.
4. Weather codes are converted into readable descriptions using
   `WEATHER_DESCRIPTIONS`.
5. `recommend_clothing()` applies simple rules to the daily forecast. Cold
   temperatures suggest warmer layers; a higher rain chance suggests a
   waterproof jacket and, when especially likely, an umbrella. Snow, hail,
   sleet, and thunderstorms can add further recommendations.
6. `main()` coordinates the location lookup and forecast request, then prints
   each day's forecast and clothing suggestion.

The forecast API request is made with `requests.get()` in `get_json()`.
`params` passes query parameters, `timeout=15` prevents waiting indefinitely,
`raise_for_status()` detects unsuccessful HTTP responses, and `response.json()`
converts the response body into Python dictionaries and lists.

Request failures, unsuccessful HTTP responses, invalid JSON, and unexpected
response data are reported to the user rather than treated as a forecast.

## Clothing advice

Clothing suggestions are basic rules of thumb, not personalized advice or a
guarantee of conditions. The thresholds and wording are in
`recommend_clothing()` in `weather.py`; change them there if you want different
recommendations. Check a current local forecast before making plans.

## Data sources

- Location search: [Open-Meteo Geocoding API](https://geocoding-api.open-meteo.com/v1/search)
- Weather forecast: [Open-Meteo Forecast API](https://api.open-meteo.com/v1/forecast)
- Project dependency: [`requests`](https://requests.readthedocs.io/)
