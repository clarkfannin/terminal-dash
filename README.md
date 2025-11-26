# terminal-dash

My personal homescreen dashboard, built in the terminal!

![terminal-dash](/images/terminal-dash.png)

## Requirements
- Python
- Ollama running locally (for AI project ideas)
- YouTube Data API v3 credentials
- GitHub personal access token

## Setup

1. **Clone the repository**
```bash
   git clone <your-repo-url>
   cd terminal-dash
```

2. **Install dependencies**
```bash
   pip install -r requirements.txt
```

3. **Configure credentials**
- Create a `.env` file with your GitHub token:
```
DASH_GH_TOKEN=your_github_token_here
```
- Download YouTube API credentials from [Google Cloud Console](https://console.cloud.google.com/) and save as `credentials.json`


4. **Run the dashboard**
```bash
   python main.py
```

## Configuration

Edit these values in `main.py`:
- `REFRESH_INTERVAL` - How often to refresh data (default: 60 seconds)
- Weather coordinates in `get_weather()` function
- GitHub username and repository in `get_workflow_runs()`