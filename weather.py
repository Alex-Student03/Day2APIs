from datetime import date

import requests


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 7

WEATHER_DESCRIPTIONS = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherAPIError(Exception):
    """Raised when an API request fails or returns unusable data."""


def get_json(url, *, params=None, headers=None):
    """Request a URL and return its JSON response."""
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as error:
        raise WeatherAPIError(f"HTTP error from {url}: {error}") from error
    except requests.exceptions.JSONDecodeError as error:
        raise WeatherAPIError(f"Invalid JSON from {url}: {error}") from error
    except requests.exceptions.RequestException as error:
        raise WeatherAPIError(f"Request failed for {url}: {error}") from error


def find_locations(place_name):
    """Use Open-Meteo's geocoder to find places matching the user's input."""
    data = get_json(
        GEOCODING_URL,
        params={
            "name": place_name,
            "count": 5,
            "language": "en",
            "format": "json",
        },
    )
    results = data.get("results", []) if isinstance(data, dict) else []
    if not isinstance(results, list) or not results:
        raise WeatherAPIError(f"No locations found for {place_name!r}.")
    return results


def choose_location(results):
    """Display search matches and return the user's selection."""
    print("\nMatching locations:")
    for index, location in enumerate(results, start=1):
        label = location.get("name", "Unknown place")
        region = location.get("admin1")
        country = location.get("country")
        if region:
            label += f", {region}"
        if country:
            label += f", {country}"
        print(f"  {index}. {label}")

    while True:
        answer = input("Choose a location number: ").strip()
        try:
            choice = int(answer)
        except ValueError:
            choice = 0
        if 1 <= choice <= len(results):
            return results[choice - 1]
        print(f"Enter a number from 1 to {len(results)}.")


def as_number(value):
    """Convert an API number to float, or return None for missing/invalid values."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_forecast(latitude, longitude):
    """Return Open-Meteo daily forecasts for the next seven days."""
    data = get_json(
        FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max"
            ),
            "forecast_days": FORECAST_DAYS,
            "timezone": "auto",
        },
    )

    try:
        daily = data["daily"]
        dates = daily["time"]
        weather_codes = daily["weather_code"]
        highs = daily["temperature_2m_max"]
        lows = daily["temperature_2m_min"]
        rain_chances = daily["precipitation_probability_max"]
    except (KeyError, TypeError) as error:
        raise WeatherAPIError(
            "Open-Meteo returned an unexpected daily forecast response."
        ) from error

    forecasts = []
    columns = (dates, weather_codes, highs, lows, rain_chances)
    if not all(isinstance(column, list) for column in columns):
        raise WeatherAPIError("Open-Meteo returned invalid daily forecast data.")
    if not dates:
        raise WeatherAPIError("Open-Meteo returned no daily forecast entries.")
    if any(len(column) != len(dates) for column in columns[1:]):
        raise WeatherAPIError("Open-Meteo returned inconsistent daily forecast data.")

    for values in zip(*columns):
        forecast_date_text, weather_code, high, low, rain_chance = values
        try:
            forecast_date = date.fromisoformat(forecast_date_text)
        except (TypeError, ValueError) as error:
            raise WeatherAPIError(
                "Open-Meteo returned a forecast without a valid date."
            ) from error

        code = as_number(weather_code)
        description = (
            WEATHER_DESCRIPTIONS.get(int(code), "Conditions unavailable")
            if code is not None
            else "Conditions unavailable"
        )
        forecasts.append(
            {
                "date": forecast_date,
                "high": as_number(high),
                "low": as_number(low),
                "rain_chance": as_number(rain_chance),
                "description": description,
            }
        )
    return forecasts


def recommend_clothing(forecast):
    """Give simple clothing suggestions based on temperatures and conditions."""
    suggestions = []
    high = forecast["high"]
    low = forecast["low"]
    rain_chance = forecast["rain_chance"]
    description = forecast["description"].casefold()

    if low is not None and low < 5:
        suggestions.append("warm coat and layers for the cold")
    elif low is not None and low < 12:
        suggestions.append("a jacket or warm layer")
    elif high is not None and high >= 24:
        suggestions.append("light, breathable clothing")
    elif high is not None and high >= 18:
        suggestions.append("comfortable light clothing; consider a light layer")
    elif high is not None:
        suggestions.append("a light-to-warm layer")
    else:
        suggestions.append("layers, as temperatures are unavailable")

    if rain_chance is not None and rain_chance >= 40:
        suggestions.append("waterproof jacket")
        if rain_chance >= 70:
            suggestions.append("umbrella")

    if any(word in description for word in ("snow", "sleet", "hail", "ice")):
        suggestions.append("waterproof shoes; warm gloves for wintry conditions")
    elif "thunder" in description:
        suggestions.append("waterproof clothing and sturdy shoes")
    elif any(word in description for word in ("rain", "shower", "drizzle")):
        if rain_chance is None or rain_chance < 40:
            suggestions.append("a light rain layer may be useful")
    elif any(word in description for word in ("fog", "mist")):
        suggestions.append("a visible outer layer if walking or cycling")

    return "; ".join(suggestions) + "."


def format_temperature(value):
    return f"{value:.0f}°C" if value is not None else "n/a"


def format_percentage(value):
    return f"{value:.0f}%" if value is not None else "n/a"


def main():
    place_name = input("Enter the town or location for the forecast: ").strip()
    if not place_name:
        print("Please enter a location.")
        return

    try:
        location = choose_location(find_locations(place_name))
        latitude = location["latitude"]
        longitude = location["longitude"]
        forecast = get_forecast(latitude, longitude)
    except (WeatherAPIError, KeyError) as error:
        print(f"Could not retrieve the forecast: {error}")
        return

    upcoming = [
        day for day in forecast
        if day["date"] >= date.today()
    ][:FORECAST_DAYS]
    if not upcoming:
        print("Open-Meteo returned no forecasts for today or later.")
        return

    print(
        f"\nOpen-Meteo forecast for {location.get('name', place_name)}, "
        f"{location.get('country', '')}"
    )
    if len(upcoming) < FORECAST_DAYS:
        print(f"Only {len(upcoming)} forecast day(s) were returned.")

    for day in upcoming:
        print(f"\n{day['date']:%A, %d %B}")
        print(
            f"  {day['description']}; high {format_temperature(day['high'])}, "
            f"low {format_temperature(day['low'])}; "
            f"rain chance {format_percentage(day['rain_chance'])}"
        )
        print(f"  Clothing: {recommend_clothing(day)}")


if __name__ == "__main__":
    main()
