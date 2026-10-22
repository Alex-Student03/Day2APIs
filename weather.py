import json
import os
import queue
import sys
import threading
from datetime import date
from pathlib import Path

if not os.environ.get("TCL_LIBRARY"):
    bundled_tcl = Path(sys.base_prefix) / "tcl" / "tcl8.6"
    if (bundled_tcl / "init.tcl").is_file():
        os.environ["TCL_LIBRARY"] = str(bundled_tcl)

if not os.environ.get("TK_LIBRARY"):
    bundled_tk = Path(sys.base_prefix) / "tcl" / "tk8.6"
    if (bundled_tk / "tk.tcl").is_file():
        os.environ["TK_LIBRARY"] = str(bundled_tk)

import tkinter as tk
from tkinter import ttk

import requests


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 7
MAX_RECENT_LOCATIONS = 10

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

WEATHER_SYMBOLS = {
    0: "☀️",
    1: "🌤️",
    2: "⛅",
    3: "☁️",
    45: "🌫️",
    48: "🌫️",
    51: "🌦️",
    53: "🌦️",
    55: "🌧️",
    56: "🌧️",
    57: "🌧️",
    61: "🌧️",
    63: "🌧️",
    65: "🌧️",
    66: "🌧️",
    67: "🌧️",
    71: "🌨️",
    73: "🌨️",
    75: "❄️",
    77: "🌨️",
    80: "🌦️",
    81: "🌧️",
    82: "🌧️",
    85: "🌨️",
    86: "❄️",
    95: "⛈️",
    96: "⛈️",
    99: "⛈️",
}

WEATHER_PALETTES = {
    "sun": ("#FFF3C4", "#9A6700", "#FFFDF4"),
    "cloud": ("#E5EAF3", "#42526E", "#F7F9FC"),
    "fog": ("#E6E8EF", "#596579", "#F8F8FA"),
    "rain": ("#D8EDFF", "#075985", "#F3FAFF"),
    "snow": ("#E5F6FF", "#0369A1", "#F5FCFF"),
    "storm": ("#E8DFFF", "#6D28D9", "#FAF7FF"),
}


def weather_palette(weather_code):
    if weather_code in (0, 1):
        return WEATHER_PALETTES["sun"]
    if weather_code in (2, 3):
        return WEATHER_PALETTES["cloud"]
    if weather_code in (45, 48):
        return WEATHER_PALETTES["fog"]
    if weather_code in (71, 73, 75, 77, 85, 86):
        return WEATHER_PALETTES["snow"]
    if weather_code in (95, 96, 99):
        return WEATHER_PALETTES["storm"]
    if weather_code in WEATHER_SYMBOLS:
        return WEATHER_PALETTES["rain"]
    return WEATHER_PALETTES["cloud"]


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
                "weather_code": int(code) if code is not None else None,
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


def location_label(location):
    label = location.get("name", "Unknown place")
    for part in (location.get("admin1"), location.get("country")):
        if part and part not in label:
            label += f", {part}"
    return label


def history_file_path():
    app_data = os.getenv("APPDATA")
    base_directory = (
        Path(app_data) / "Day2TVMaze"
        if app_data
        else Path.home() / ".day2tvmaze"
    )
    return base_directory / "recent_locations.json"


class WeatherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Seven-Day Weather Forecast")
        self.root.geometry("1100x700")
        self.root.minsize(800, 570)
        self.history_path = history_file_path()
        self.recent_locations = []
        self.location_by_label = {}
        self.busy = False
        self.worker_results = queue.Queue()

        self.configure_style()
        self.build_interface()
        self.load_recent_locations()
        self.root.after(100, self.process_worker_results)

    def configure_style(self):
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
        style.configure("Day.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Symbol.TLabel", font=("Segoe UI Emoji", 28))
        style.configure("Temperature.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 9))

    def build_interface(self):
        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer, text="Seven-Day Weather Forecast", style="Title.TLabel"
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text="Search any location and get a forecast with practical clothing tips.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 16))

        search_row = ttk.Frame(outer)
        search_row.pack(fill="x", pady=(0, 10))
        ttk.Label(search_row, text="Location:").pack(side="left", padx=(0, 8))
        self.location_var = tk.StringVar()
        self.location_box = ttk.Combobox(
            search_row,
            textvariable=self.location_var,
            state="normal",
            width=48,
        )
        self.location_box.pack(side="left", fill="x", expand=True)
        self.location_box.bind("<Return>", lambda _event: self.on_search())
        self.search_button = ttk.Button(
            search_row, text="Get forecast", command=self.on_search
        )
        self.search_button.pack(side="left", padx=(8, 0))

        self.status_var = tk.StringVar(value="Enter a location or choose a recent one.")
        self.status_label = ttk.Label(
            outer, textvariable=self.status_var, style="Status.TLabel"
        )
        self.status_label.pack(anchor="w", pady=(0, 12))

        self.results_frame = ttk.Frame(outer)
        self.results_frame.pack(fill="both", expand=True)
        for column in range(4):
            self.results_frame.columnconfigure(column, weight=1, uniform="forecast")
        for row in range(2):
            self.results_frame.rowconfigure(row, weight=1, uniform="forecast")

    def load_recent_locations(self):
        if not self.history_path.exists():
            return
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError("The recent locations file must contain a JSON list.")
            self.recent_locations = [
                item for item in data[:MAX_RECENT_LOCATIONS]
                if isinstance(item, dict)
                and isinstance(item.get("name"), str)
                and isinstance(item.get("latitude"), (int, float))
                and isinstance(item.get("longitude"), (int, float))
            ]
        except (OSError, json.JSONDecodeError, ValueError) as error:
            self.set_status(f"Could not load saved locations: {error}", error=True)
            return
        self.refresh_location_choices()

    def save_recent_location(self, location):
        identity = (location["latitude"], location["longitude"])
        self.recent_locations = [
            item for item in self.recent_locations
            if (item["latitude"], item["longitude"]) != identity
        ]
        self.recent_locations.insert(0, location.copy())
        self.recent_locations = self.recent_locations[:MAX_RECENT_LOCATIONS]
        self.refresh_location_choices()
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            self.history_path.write_text(
                json.dumps(self.recent_locations, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return None
        except OSError as error:
            return f"Could not save recent locations: {error}"

    def refresh_location_choices(self):
        self.location_by_label = {
            location_label(item): item for item in self.recent_locations
        }
        self.location_box["values"] = list(self.location_by_label)

    def set_status(self, message, error=False):
        self.status_var.set(message)
        self.status_label.configure(foreground="#a4262c" if error else "#444444")

    def set_busy(self, busy, message):
        self.busy = busy
        self.search_button.configure(state="disabled" if busy else "normal")
        self.set_status(message)

    def run_in_background(self, operation, callback):
        def worker():
            try:
                result = operation()
            except Exception as error:
                self.worker_results.put((callback, None, error))
            else:
                self.worker_results.put((callback, result, None))

        threading.Thread(target=worker, daemon=True).start()

    def process_worker_results(self):
        while True:
            try:
                callback, result, error = self.worker_results.get_nowait()
            except queue.Empty:
                break
            callback(result, error)
        self.root.after(100, self.process_worker_results)

    def on_search(self):
        if self.busy:
            return
        place_name = self.location_var.get().strip()
        if not place_name:
            self.set_status("Enter a location to get its forecast.", error=True)
            return

        recent = self.location_by_label.get(place_name)
        if recent:
            self.use_location(recent)
            return

        self.set_busy(True, f"Searching for {place_name}...")
        self.run_in_background(
            lambda: find_locations(place_name),
            lambda results, error: self.locations_received(place_name, results, error),
        )

    def locations_received(self, place_name, results, error):
        if error:
            self.set_busy(False, "")
            self.set_status(f"Could not find that location: {error}", error=True)
            return
        if len(results) == 1:
            self.use_location(results[0])
            return
        self.set_busy(False, "Choose the matching location.")
        self.show_location_picker(place_name, results)

    def show_location_picker(self, place_name, results):
        dialog = tk.Toplevel(self.root)
        dialog.title("Choose a location")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("430x300")
        ttk.Label(
            dialog, text=f"Select a match for {place_name!r}:"
        ).pack(anchor="w", padx=14, pady=(14, 8))

        listbox = tk.Listbox(dialog, height=8, activestyle="dotbox")
        for location in results:
            listbox.insert("end", location_label(location))
        listbox.pack(fill="both", expand=True, padx=14, pady=4)
        listbox.selection_set(0)

        buttons = ttk.Frame(dialog)
        buttons.pack(fill="x", padx=14, pady=12)

        def select_location(_event=None):
            selected = listbox.curselection()
            if not selected:
                return
            location = results[selected[0]]
            dialog.destroy()
            self.use_location(location)

        ttk.Button(
            buttons, text="Use selected location", command=select_location
        ).pack(side="right")
        ttk.Button(
            buttons,
            text="Cancel",
            command=lambda: (dialog.destroy(), self.set_status("Search cancelled.")),
        ).pack(side="right", padx=(0, 8))
        listbox.bind("<Double-Button-1>", select_location)
        dialog.protocol(
            "WM_DELETE_WINDOW",
            lambda: (dialog.destroy(), self.set_status("Search cancelled.")),
        )

    def use_location(self, location):
        try:
            latitude = location["latitude"]
            longitude = location["longitude"]
            if not isinstance(location.get("name"), str):
                raise KeyError("name")
        except (KeyError, TypeError) as error:
            self.set_status(f"Location data is incomplete: {error}", error=True)
            self.set_busy(False, "")
            return

        save_error = self.save_recent_location(location)
        label = location_label(location)
        self.location_var.set(label)
        self.set_busy(True, f"Loading forecast for {label}...")
        self.run_in_background(
            lambda: get_forecast(latitude, longitude),
            lambda forecast, error: self.forecast_received(
                location, forecast, error, save_error
            ),
        )

    def forecast_received(self, location, forecast, error, save_error):
        self.set_busy(False, "")
        if error:
            self.set_status(f"Could not retrieve the forecast: {error}", error=True)
            return

        upcoming = [
            day for day in forecast if day["date"] >= date.today()
        ][:FORECAST_DAYS]
        if not upcoming:
            self.set_status("No forecasts for today or later were returned.", error=True)
            return

        self.display_forecast(location, upcoming)
        message = f"Showing forecast for {location_label(location)}."
        if len(upcoming) < FORECAST_DAYS:
            message += f" Only {len(upcoming)} days were returned."
        if save_error:
            message += f" {save_error}"
        self.set_status(message, error=bool(save_error))

    def display_forecast(self, location, forecast):
        for child in self.results_frame.winfo_children():
            child.destroy()

        for column in range(4):
            self.results_frame.columnconfigure(column, weight=1, uniform="forecast")
        for row in range(2):
            self.results_frame.rowconfigure(row, weight=1, uniform="forecast")

        for index, day in enumerate(forecast):
            row, column = divmod(index, 4)
            badge_color, accent_color, card_color = weather_palette(
                day["weather_code"]
            )
            card = tk.Frame(
                self.results_frame,
                background=card_color,
                highlightbackground=badge_color,
                highlightthickness=1,
                padx=12,
                pady=12,
            )
            card.grid(
                row=row, column=column, sticky="nsew", padx=5, pady=5
            )
            card.columnconfigure(0, weight=1)

            symbol = WEATHER_SYMBOLS.get(day["weather_code"], "🌡️")
            tk.Label(
                card,
                text=f"{day['date']:%A, %d %b}",
                font=("Segoe UI", 11, "bold"),
                background=card_color,
                foreground="#202938",
                anchor="w",
            ).grid(row=0, column=0, sticky="ew")
            tk.Label(
                card,
                text=symbol,
                font=("Segoe UI Emoji", 32),
                background=badge_color,
                foreground=accent_color,
                padx=8,
                pady=3,
            ).grid(row=1, column=0, sticky="w", pady=(7, 5))
            tk.Label(
                card,
                text=day["description"],
                font=("Segoe UI", 10, "bold"),
                background=card_color,
                foreground=accent_color,
                wraplength=220,
                anchor="w",
                justify="left",
            ).grid(row=2, column=0, sticky="ew", pady=(0, 6))
            tk.Label(
                card,
                text=f"High {format_temperature(day['high'])}  /  "
                f"Low {format_temperature(day['low'])}",
                font=("Segoe UI", 10, "bold"),
                background=card_color,
                foreground="#202938",
                anchor="w",
            ).grid(row=3, column=0, sticky="ew")
            tk.Label(
                card,
                text=f"Rain chance: {format_percentage(day['rain_chance'])}",
                font=("Segoe UI", 9),
                background=card_color,
                foreground="#42526E",
                anchor="w",
            ).grid(row=4, column=0, sticky="ew", pady=(3, 6))
            tk.Label(
                card,
                text=f"Clothing: {recommend_clothing(day)}",
                font=("Segoe UI", 9),
                background=card_color,
                foreground="#344054",
                wraplength=220,
                justify="left",
                anchor="w",
            ).grid(row=5, column=0, sticky="ew")

        self.root.title(f"Weather Forecast - {location_label(location)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = WeatherApp(root)
    root.mainloop()
