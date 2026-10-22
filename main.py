import requests


def search_shows(query):
    url = "https://api.tvmaze.com/search/shows"
    params = {"q": query}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        shows = response.json()
    except requests.exceptions.JSONDecodeError as error:
        print(f"TVMaze returned invalid JSON: {error}")
        return
    except requests.exceptions.HTTPError as error:
        print(f"TVMaze returned an HTTP error: {error}")
        return
    except requests.exceptions.RequestException as error:
        print(f"Could not connect to TVMaze: {error}")
        return

    if not shows:
        print(f"No shows found for {query!r}.")
        return

    for result in shows:
        show = result["show"]
        print(f"{show['name']} ({show.get('premiered') or 'premiere date unknown'})")
        print(f"  URL: {show['url']}")


if __name__ == "__main__":
    search_shows("Slow Horses")
