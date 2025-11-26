from retry_requests import retry
import requests_cache
import pandas as pd
from PIL import Image
from rich.console import Console
from rich.table import Table
from rich import box
from github import Github, Auth, GithubException
import time
import os
from ollama import chat, ChatResponse
from rich.live import Live
import openmeteo_requests
from youtube_auth import get_youtube_stats
from dotenv import load_dotenv
import humanize
from datetime import datetime, timezone

load_dotenv()


console = Console()

WEATHER_CODE_MAP = {
    0: 'sunny', 1: 'sunny',
    2: 'partly_cloudy',
    3: 'cloudy',
    45: 'fog', 48: 'fog',
    51: 'rain', 53: 'rain', 55: 'rain', 56: 'rain', 57: 'rain',
    61: 'rain', 63: 'rain', 65: 'rain', 66: 'rain', 67: 'rain',
    80: 'rain', 81: 'rain', 82: 'rain',
    71: 'snow', 73: 'snow', 75: 'snow', 77: 'snow', 85: 'snow', 86: 'snow',
    95: 'thunderstorm', 96: 'thunderstorm', 99: 'thunderstorm',
}


def get_weather():
    try:
        cache_session = requests_cache.CachedSession(
            '.cache', expire_after=3600)
        retry_session = retry(cache_session, retries=3, backoff_factor=0.2)
        openmeteo = openmeteo_requests.Client(session=retry_session)

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": 41.9426,
            "longitude": -87.6727,
            "current": ["temperature_2m", "weather_code"],
            "wind_speed_unit": "mph",
            "temperature_unit": "fahrenheit",
            "precipitation_unit": "inch",
        }
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]

        current = response.Current()
        current_temperature_2m = current.Variables(0).Value()
        current_weather_code = int(current.Variables(1).Value())

        return {
            'temperature': f"{current_temperature_2m:.1f}°F",
            'code': current_weather_code
        }
    except Exception as e:
        console.print(f"[yellow]Weather API error: {e}[/yellow]")
        return {'temperature': "N/A", 'code': 0}


def generate_project_idea():
    try:
        response: ChatResponse = chat(
            model='gemma3:1b',
            messages=[{
                'role': 'user',
                'content': (
                    'Give me a one-paragraph idea for a really creative, utility '
                    'python project. Projects should not focus on arbitrary metrics '
                    'like "mood". Return only the project idea, no additional text.'
                )
            }],
        )
        return response.message.content
    except Exception as e:
        console.print(f"[yellow]Ollama error: {e}[/yellow]")
        return "Build a terminal dashboard for monitoring your dev workflow."


def get_workflow_runs():
    try:
        token = os.environ.get("DASH_GH_TOKEN")

        if not token:
            return [("Error", "DASH_GH_TOKEN not set")]

        auth = Auth.Token(token)
        g = Github(auth=auth, timeout=10)

        try:
            user = g.get_user("clarkfannin")
        except GithubException as e:
            if e.status == 403:
                return [("Error", "403 Forbidden - Check token permissions")]
            elif e.status == 401:
                return [("Error", "401 Unauthorized")]
            elif e.status == 404:
                return [("Error", "User not found")]
            else:
                return [("Error", f"{e.status} error")]

        try:
            repo = user.get_repo("chicago-restaurant-inspections")
        except GithubException as e:
            if e.status == 404:
                return [("Error", "Repository not found")]
            else:
                return [("Error", f"Repo error: {e.status}")]

        runs = repo.get_workflow_runs()
        result = []

        now = datetime.now(timezone.utc)

        for run in list(runs)[:5]:
            time_ago = humanize.naturaltime(now - run.created_at)
            conclusion = run.conclusion or 'in progress'
            result.append((time_ago, conclusion))

        return result if result else [("N/A", "No runs found")]

    except GithubException as e:
        return [("Error", f"{e.status}")]
    except Exception as e:
        return [("Error", f"{type(e).__name__}")]


def get_image_string(weather_code, max_width=None, max_height=None):
    try:
        weather_type = WEATHER_CODE_MAP.get(weather_code, 'sunny')
        image_path = f'images/{weather_type}.png'

        im = Image.open(image_path, 'r')
        orig_w, orig_h = im.size

        if max_width is None:
            max_width = console.width // 3
        if max_height is None:
            max_height = console.height // 3

        scale = min(max_width / orig_w, max_height / orig_h)

        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale * 0.5)
        im = im.resize((new_w, new_h))

        pixel_values = list(im.getdata())

        lines = []
        line = []

        for i, pixel in enumerate(pixel_values):
            r, g, b = pixel[:3]
            if i % new_w == 0 and i != 0:
                lines.append("".join(line))
                line = []

            if (r, g, b) == (0, 0, 0):
                line.append(" ")
            else:
                line.append(f"[rgb({r},{g},{b})]█[/rgb({r},{g},{b})]")

        if line:
            lines.append("".join(line))

        return "\n".join(lines)
    except FileNotFoundError:
        return f"[{weather_type.replace('_', ' ').title()}]"
    except Exception as e:
        console.print(f"[yellow]Image error: {e}[/yellow]")
        return "[Weather]"


YOUTUBE_STATS = get_youtube_stats()
PROJECT_IDEA = None
WORKFLOW_INFO = None
WEATHER = None
LAST_REFRESH = 0
REFRESH_INTERVAL = 60


def refresh_data():
    global PROJECT_IDEA, WORKFLOW_INFO, WEATHER, LAST_REFRESH

    console.print("[dim]Refreshing data...[/dim]")

    PROJECT_IDEA = f"\n{generate_project_idea()}\n"
    WORKFLOW_INFO = get_workflow_runs()
    WEATHER = get_weather()

    LAST_REFRESH = time.time()


def generate_table():
    console_width = console.width
    console_height = console.height
    
    table = Table(box=box.ASCII, show_header=False, width=console_width, expand=True)
    table.add_column("Weather")
    table.add_column("Info")

    weather_container = Table(
        show_header=False,
        show_edge=False,
        show_lines=True,
        box=box.ASCII,
        padding=(0, 0),
        expand=True
    )
    weather_container.add_column(justify="center")
    
    weather_image = get_image_string(
        WEATHER['code'],
        max_width=console_width // 3,
        max_height=console_height // 2
    )
    
    weather_container.add_row(weather_image)
    weather_container.add_row(f"Chicago: {WEATHER['temperature']}")

    project_table = Table(
        show_header=False,
        show_edge=False,
        show_lines=False,
        box=None,
        padding=(0, 0),
        expand=True
    )
    project_table.add_column()
    project_table.add_row(
        f"Project Idea:\n{PROJECT_IDEA}",
        style="green"
    )

    workflow_table = Table(
        title="GitHub Workflows",
        show_header=True,
        show_edge=False,
        show_lines=True,
        box=box.ASCII,
        padding=(0, 0),
        expand=True
    )
    workflow_table.add_column("Time", justify="center")
    workflow_table.add_column("Result", justify="center")

    for time_ago, conclusion in WORKFLOW_INFO:
        if conclusion.lower() == "success":
            result_text = f"[green]{conclusion}[/green]"
        elif conclusion.lower() == "failure":
            result_text = f"[red]{conclusion}[/red]"
        else:
            result_text = conclusion

        workflow_table.add_row(time_ago, result_text)

    youtube_table = Table(
        show_header=True,
        show_edge=False,
        show_lines=True,
        box=box.ASCII,
        padding=(0, 0),
        expand=True
    )
    youtube_table.add_column("Subscribers", justify="center")
    youtube_table.add_column("# of Videos", justify="center")
    youtube_table.add_column("Most Viewed", justify="center")
    youtube_table.add_row(
        str(YOUTUBE_STATS['subscribers']),
        str(YOUTUBE_STATS['total_videos']),
        str(YOUTUBE_STATS['top_video_views'])
    )

    youtube_videos_table = Table(
        title="Last 3 Videos:",
        show_header=True,
        show_edge=False,
        show_lines=True,
        box=box.ASCII,
        padding=(0, 0),
        expand=True
    )
    youtube_videos_table.add_column("Title")
    youtube_videos_table.add_column("# of Views", justify="center")
    for title, views in zip(YOUTUBE_STATS['last_3_videos_titles'], YOUTUBE_STATS['last_3_videos_views']):
        youtube_videos_table.add_row(title, str(views))

    youtube_container = Table(
        show_header=False,
        show_edge=False,
        box=None,
        padding=(0, 0),
        expand=True
    )
    youtube_container.add_column()
    youtube_container.add_row(youtube_table)
    youtube_container.add_row(youtube_videos_table)

    table.add_row(weather_container, project_table)
    table.add_row(workflow_table, youtube_container)

    return table


if __name__ == "__main__":
    try:
        refresh_data()

        with Live(generate_table(), refresh_per_second=1, screen=False) as live:
            while True:
                now = time.time()

                if now - LAST_REFRESH >= REFRESH_INTERVAL:
                    refresh_data()

                live.update(generate_table(), refresh=True)
                time.sleep(1)

    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
