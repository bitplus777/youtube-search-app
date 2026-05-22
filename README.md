# YouTube Video Search (Streamlit)

A Streamlit web app that searches YouTube videos using the [YouTube Data API v3](https://developers.google.com/youtube/v3).

## Features

- Keyword search
- Upload date filters: today, this week, this month, this year
- Duration filters: short, medium, long
- Sort by relevance, date, or view count
- Minimum and maximum view count filters (applied after fetch)
- Results table with title, channel, URL, published date, views, likes, comments, duration
- Thumbnail preview expander
- Download results as CSV
- API key loaded from `.env`

## Prerequisites

1. A [Google Cloud](https://console.cloud.google.com/) project with **YouTube Data API v3** enabled
2. An API key (Credentials → Create credentials → API key)

## Setup

```bash
cd c:\projectyoutube
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy the example env file and add your key:

```bash
copy .env.example .env
```

Edit `.env`:

```
YOUTUBE_API_KEY=your_actual_api_key
```

## Run

```bash
streamlit run app.py
```

The app opens in your browser (default: http://localhost:8501).

## Usage

1. Enter a keyword in the sidebar.
2. Choose upload date, duration, and sort options.
3. Optionally set minimum/maximum views (use `0` for no limit).
4. Click **Search**.
5. Review the table; expand **Thumbnails preview** if needed.
6. Click **Download results as CSV** to export.

## Project layout

| File | Purpose |
|------|---------|
| `app.py` | Streamlit application |
| `requirements.txt` | Python dependencies |
| `.env` | Your API key (not committed) |
| `.env.example` | Env template |

## API quota

Each search uses quota units (search + video details). The default max is 50 results per search. See [YouTube API quota](https://developers.google.com/youtube/v3/getting-started#quota) for limits.

## License

MIT (or your choice).
