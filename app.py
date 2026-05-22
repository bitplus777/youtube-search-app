"""YouTube 동영상 검색 앱 (YouTube Data API v3)"""

import os
import re
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

DATE_FILTERS = {
    "전체": None,
    "오늘": lambda now: now.replace(hour=0, minute=0, second=0, microsecond=0),
    "이번 주": lambda now: now - timedelta(days=7),
    "이번 달": lambda now: now - timedelta(days=30),
    "올해": lambda now: now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
}

DURATION_FILTERS = {
    "전체": None,
    "짧은 영상 (4분 미만)": "short",
    "중간 영상 (4~20분)": "medium",
    "긴 영상 (20분 초과)": "long",
}

SORT_OPTIONS = {
    "관련성": "relevance",
    "최신순": "date",
    "조회수": "viewCount",
}

# ─── 테마 색상 팔레트 ─────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg": "#0f0f0f",
        "sidebar_bg": "#161616",
        "card_bg": "#1a1a1a",
        "card_border": "#2d2d2d",
        "card_hover": "#ff0000",
        "title_color": "#f1f1f1",
        "channel_color": "#aaaaaa",
        "stat_value": "#e0e0e0",
        "stat_label": "#888888",
        "meta_bg": "#2a2a2a",
        "meta_color": "#888888",
        "text_primary": "#f1f1f1",
        "text_secondary": "#888888",
        "divider": "#2a2a2a",
        "badge_bg": "rgba(0,0,0,0.85)",
        "badge_color": "#ffffff",
        "streamlit_bg": "#0f0f0f",
        "streamlit_secondary": "#1a1a1a",
        "streamlit_text": "#f1f1f1",
    },
    "light": {
        "bg": "#ffffff",
        "sidebar_bg": "#f8f8f8",
        "card_bg": "#ffffff",
        "card_border": "#e0e0e0",
        "card_hover": "#ff0000",
        "title_color": "#0f0f0f",
        "channel_color": "#606060",
        "stat_value": "#1a1a1a",
        "stat_label": "#666666",
        "meta_bg": "#f2f2f2",
        "meta_color": "#606060",
        "text_primary": "#0f0f0f",
        "text_secondary": "#606060",
        "divider": "#e5e5e5",
        "badge_bg": "rgba(0,0,0,0.75)",
        "badge_color": "#ffffff",
        "streamlit_bg": "#ffffff",
        "streamlit_secondary": "#f8f8f8",
        "streamlit_text": "#0f0f0f",
    },
}


def build_css(t: dict) -> str:
    return f"""
<style>
/* ── Streamlit 기본 오버라이드 ── */
.stApp, .stApp > .main, .block-container {{
    background-color: {t['bg']} !important;
    color: {t['text_primary']} !important;
}}
section[data-testid="stSidebar"] {{
    background-color: {t['sidebar_bg']} !important;
}}
section[data-testid="stSidebar"] * {{
    color: {t['text_primary']} !important;
}}
.stTextInput input, .stSelectbox select, .stNumberInput input {{
    background-color: {t['card_bg']} !important;
    color: {t['text_primary']} !important;
    border-color: {t['card_border']} !important;
}}
.stTabs [data-baseweb="tab-list"] {{
    background-color: {t['card_bg']} !important;
    border-bottom: 2px solid {t['divider']};
}}
.stTabs [data-baseweb="tab"] {{
    color: {t['text_secondary']} !important;
}}
.stTabs [aria-selected="true"] {{
    color: #ff0000 !important;
    border-bottom: 2px solid #ff0000 !important;
}}
.stDataFrame {{ background: {t['card_bg']} !important; }}
div[data-testid="stMarkdownContainer"] p,
div[data-testid="stMarkdownContainer"] span,
div[data-testid="stMarkdownContainer"] h1,
div[data-testid="stMarkdownContainer"] h2,
div[data-testid="stMarkdownContainer"] h3 {{
    color: {t['text_primary']} !important;
}}

/* ── 비디오 카드 ── */
.video-card {{
    background: {t['card_bg']};
    border: 1px solid {t['card_border']};
    border-radius: 14px;
    margin-bottom: 16px;
    overflow: hidden;
    transition: border-color 0.2s, box-shadow 0.2s;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}}
.video-card:hover {{
    border-color: {t['card_hover']};
    box-shadow: 0 4px 16px rgba(255,0,0,0.12);
}}
.card-inner {{
    display: flex;
    align-items: stretch;
}}
.thumb-wrap {{
    flex: 0 0 260px;
    position: relative;
    overflow: hidden;
    border-radius: 14px 0 0 14px;
    background: #000;
}}
.thumb-wrap img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    transition: transform 0.3s;
}}
.video-card:hover .thumb-wrap img {{ transform: scale(1.03); }}
.duration-badge {{
    position: absolute;
    bottom: 8px;
    right: 8px;
    background: {t['badge_bg']};
    color: {t['badge_color']};
    font-size: 12px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 5px;
    letter-spacing: 0.3px;
}}
.card-info {{
    flex: 1;
    padding: 18px 22px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 0;
}}
.video-title {{
    font-size: 16px;
    font-weight: 700;
    color: {t['title_color']};
    line-height: 1.45;
    margin: 0 0 2px 0;
    word-break: break-word;
}}
.video-title a {{
    color: {t['title_color']};
    text-decoration: none;
}}
.video-title a:hover {{ color: #ff0000; }}
.channel-name {{
    font-size: 13px;
    color: {t['channel_color']};
    font-weight: 600;
    margin: 0;
}}
.stats-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    margin-top: 8px;
    padding-top: 10px;
    border-top: 1px solid {t['divider']};
}}
.stat-item {{
    display: flex;
    flex-direction: column;
    align-items: flex-start;
}}
.stat-label {{
    font-size: 10px;
    color: {t['stat_label']};
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 3px;
    font-weight: 600;
}}
.stat-value {{
    font-size: 15px;
    font-weight: 700;
    color: {t['stat_value']};
}}
.stat-value.red {{ color: #ff4444; }}
.meta-row {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 4px;
}}
.meta-tag {{
    font-size: 12px;
    color: {t['meta_color']};
    background: {t['meta_bg']};
    border-radius: 6px;
    padding: 3px 10px;
    font-weight: 500;
}}
.watch-btn {{
    display: inline-block;
    margin-top: 10px;
    background: #ff0000;
    color: #fff !important;
    font-size: 13px;
    font-weight: 700;
    padding: 8px 22px;
    border-radius: 20px;
    text-decoration: none !important;
    width: fit-content;
    letter-spacing: 0.3px;
    transition: background 0.2s;
}}
.watch-btn:hover {{ background: #cc0000; }}

/* ── 헤더 영역 ── */
.app-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 8px;
    border-bottom: 2px solid {t['divider']};
    margin-bottom: 20px;
}}
.app-title {{
    font-size: 26px;
    font-weight: 800;
    color: {t['text_primary']};
    margin: 0;
}}
.app-subtitle {{
    font-size: 13px;
    color: {t['text_secondary']};
    margin: 2px 0 0 0;
}}

.result-header {{
    color: {t['text_secondary']};
    font-size: 14px;
    margin-bottom: 14px;
}}
.keyword-hl {{ color: #ff0000; font-weight: 700; }}
</style>
"""


def fmt_number(n: int) -> str:
    if n >= 100_000_000:
        return f"{n / 100_000_000:.1f}억"
    if n >= 10_000:
        return f"{n / 10_000:.1f}만"
    return f"{n:,}"


def parse_iso8601_duration(duration: str) -> str:
    if not duration:
        return ""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return duration
    hours, minutes, seconds = (int(g or 0) for g in match.groups())
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def get_youtube_client(api_key: str):
    if not api_key:
        return None
    try:
        return build("youtube", "v3", developerKey=api_key)
    except Exception:
        return None


def published_after_rfc3339(label: str) -> str | None:
    fn = DATE_FILTERS.get(label)
    if fn is None:
        return None
    dt = fn(datetime.now(timezone.utc))
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def search_video_ids(youtube, keyword, date_filter, duration_filter, sort_by, max_results):
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "order": SORT_OPTIONS[sort_by],
        "maxResults": min(max_results, 50),
    }
    published = published_after_rfc3339(date_filter)
    if published:
        params["publishedAfter"] = published
    duration = DURATION_FILTERS.get(duration_filter)
    if duration:
        params["videoDuration"] = duration
    response = youtube.search().list(**params).execute()
    return [item["id"]["videoId"] for item in response.get("items", [])]


def fetch_channel_subscribers(youtube, channel_ids: list[str]) -> dict[str, int]:
    if not channel_ids:
        return {}
    result = {}
    for i in range(0, len(channel_ids), 50):
        chunk = channel_ids[i : i + 50]
        resp = youtube.channels().list(part="statistics", id=",".join(chunk)).execute()
        for item in resp.get("items", []):
            subs = item.get("statistics", {}).get("subscriberCount")
            result[item["id"]] = int(subs) if subs else 0
    return result


def fetch_video_details(youtube, video_ids: list[str]) -> list[dict]:
    if not video_ids:
        return []
    raw_items = []
    channel_ids = []

    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        resp = (
            youtube.videos()
            .list(part="snippet,statistics,contentDetails", id=",".join(chunk))
            .execute()
        )
        for item in resp.get("items", []):
            raw_items.append(item)
            cid = item["snippet"].get("channelId", "")
            if cid and cid not in channel_ids:
                channel_ids.append(cid)

    subs_map = fetch_channel_subscribers(youtube, channel_ids)
    rows = []
    for item in raw_items:
        snippet = item["snippet"]
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})
        video_id = item["id"]
        channel_id = snippet.get("channelId", "")
        rows.append(
            {
                "제목": snippet.get("title", ""),
                "채널명": snippet.get("channelTitle", ""),
                "구독자수": subs_map.get(channel_id, 0),
                "URL": f"https://www.youtube.com/watch?v={video_id}",
                "업로드일": snippet.get("publishedAt", "")[:10],
                "조회수": int(stats.get("viewCount", 0)),
                "좋아요": int(stats.get("likeCount", 0)),
                "댓글수": int(stats.get("commentCount", 0)),
                "재생시간": parse_iso8601_duration(content.get("duration", "")),
                "썸네일": (
                    snippet.get("thumbnails", {}).get("high", {}).get("url", "")
                    or snippet.get("thumbnails", {}).get("medium", {}).get("url", "")
                ),
            }
        )
    return rows


def apply_view_filters(rows, min_views, max_views):
    if min_views and min_views > 0:
        rows = [r for r in rows if r["조회수"] >= min_views]
    if max_views and max_views > 0:
        rows = [r for r in rows if r["조회수"] <= max_views]
    return rows


def render_video_card(row: dict):
    thumb = row["썸네일"]
    thumb_html = (
        f'<img src="{thumb}" alt="썸네일">'
        if thumb
        else '<div style="background:#2a2a2a;width:100%;height:158px;"></div>'
    )
    dur = row["재생시간"]
    dur_badge = f'<span class="duration-badge">{dur}</span>' if dur else ""

    st.markdown(
        f"""
<div class="video-card">
  <div class="card-inner">
    <div class="thumb-wrap">
      {thumb_html}
      {dur_badge}
    </div>
    <div class="card-info">
      <p class="video-title">
        <a href="{row['URL']}" target="_blank">{row['제목']}</a>
      </p>
      <p class="channel-name">📺 {row['채널명']}</p>
      <div class="stats-row">
        <div class="stat-item">
          <span class="stat-label">구독자</span>
          <span class="stat-value">👥 {fmt_number(row['구독자수'])}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">조회수</span>
          <span class="stat-value red">▶ {fmt_number(row['조회수'])}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">좋아요</span>
          <span class="stat-value">👍 {fmt_number(row['좋아요'])}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">댓글</span>
          <span class="stat-value">💬 {fmt_number(row['댓글수'])}</span>
        </div>
      </div>
      <div class="meta-row">
        <span class="meta-tag">📅 {row['업로드일']}</span>
        <span class="meta-tag">⏱ {row['재생시간']}</span>
      </div>
      <a class="watch-btn" href="{row['URL']}" target="_blank">▶ 영상 보기</a>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(page_title="유튜브 검색", page_icon="▶️", layout="wide")

    # ── 테마 초기화 ──────────────────────────────────────────────────────────
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"

    t = THEMES[st.session_state.theme]
    st.markdown(build_css(t), unsafe_allow_html=True)

    # ── 헤더 (제목 + 테마 토글) ─────────────────────────────────────────────
    col_title, col_toggle = st.columns([8, 1])
    with col_title:
        st.markdown(
            f"<p class='app-title'>▶ 유튜브 동영상 검색</p>"
            f"<p class='app-subtitle'>YouTube Data API v3 기반 검색 도구</p>",
            unsafe_allow_html=True,
        )
    with col_toggle:
        is_dark = st.session_state.theme == "dark"
        label = "☀️ 낮 모드" if is_dark else "🌙 밤 모드"
        if st.button(label, use_container_width=True):
            st.session_state.theme = "light" if is_dark else "dark"
            st.rerun()

    st.markdown(f"<hr style='border:none;border-top:2px solid {t['divider']};margin:4px 0 20px 0;'>", unsafe_allow_html=True)

    # ── 사이드바 ─────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🔑 API 설정")
        env_key = os.getenv("YOUTUBE_API_KEY", "")
        api_key_input = st.text_input(
            "YouTube API Key",
            value=env_key,
            type="password",
            placeholder="AIza...",
            help="Google Cloud Console에서 발급한 YouTube Data API v3 키를 입력하세요.",
        )
        api_key = api_key_input.strip() or env_key
        if api_key:
            st.success("API 키 설정 완료", icon="✅")
        else:
            st.warning("API 키를 입력하세요", icon="⚠️")
            st.markdown("[🔗 API 키 발급하기](https://console.cloud.google.com/)")

        st.divider()
        st.markdown("### 🔍 검색 설정")
        keyword = st.text_input("검색어", placeholder="예: 파이썬 강의")
        date_filter = st.selectbox("업로드 날짜", list(DATE_FILTERS.keys()))
        duration_filter = st.selectbox("영상 길이", list(DURATION_FILTERS.keys()))
        sort_by = st.selectbox("정렬 기준", list(SORT_OPTIONS.keys()))

        st.divider()
        st.markdown("### 📊 조회수 필터")
        min_views = st.number_input("최소 조회수", min_value=0, value=0, step=10000, help="0 = 제한 없음")
        max_views = st.number_input("최대 조회수", min_value=0, value=0, step=10000, help="0 = 제한 없음")
        max_results = st.slider("최대 결과 수", 5, 50, 20)

        search_clicked = st.button("🔍 검색", type="primary", use_container_width=True)

    # ── 메인 컨텐츠 ──────────────────────────────────────────────────────────
    if not search_clicked:
        st.markdown(
            f"<div style='text-align:center;padding:80px 0;color:{t['text_secondary']};'>"
            "<div style='font-size:56px;'>▶</div>"
            f"<div style='font-size:18px;margin-top:16px;color:{t['text_secondary']};'>"
            "검색어를 입력하고 <b style='color:#ff0000'>검색</b> 버튼을 클릭하세요</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    if not api_key:
        st.error("사이드바에 YouTube API 키를 입력해 주세요.")
        return
    if not keyword.strip():
        st.warning("검색어를 입력해 주세요.")
        return

    try:
        youtube = get_youtube_client(api_key)
        if youtube is None:
            st.error("API 키가 올바르지 않습니다. 다시 확인해 주세요.")
            return
        with st.spinner("유튜브에서 영상을 검색 중입니다..."):
            video_ids = search_video_ids(
                youtube, keyword.strip(), date_filter, duration_filter, sort_by, max_results
            )
            rows = fetch_video_details(youtube, video_ids)
            rows = apply_view_filters(rows, int(min_views), int(max_views))
    except HttpError as e:
        st.error(f"YouTube API 오류: {e}")
        return
    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
        return

    if not rows:
        st.warning("검색 결과가 없습니다. 다른 키워드나 필터를 사용해 보세요.")
        return

    st.markdown(
        f"<p class='result-header'>검색어 <span class='keyword-hl'>'{keyword}'</span> — "
        f"<b style='color:{t['text_primary']}'>{len(rows)}개</b> 결과</p>",
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["🎬 카드 보기", "📋 테이블 보기"])

    with tab1:
        for row in rows:
            render_video_card(row)

    with tab2:
        df = pd.DataFrame(rows)
        display_df = df.drop(columns=["썸네일"])
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "URL": st.column_config.LinkColumn("URL"),
                "조회수": st.column_config.NumberColumn("조회수", format="%d"),
                "좋아요": st.column_config.NumberColumn("좋아요", format="%d"),
                "댓글수": st.column_config.NumberColumn("댓글수", format="%d"),
                "구독자수": st.column_config.NumberColumn("구독자수", format="%d"),
            },
        )
        csv = display_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="📥 CSV로 다운로드",
            data=csv,
            file_name=f"유튜브검색_{keyword.strip().replace(' ', '_')}.csv",
            mime="text/csv",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
