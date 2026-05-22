"""
유튜브 한국 여행 채널 발굴 앱
등급 기준: S급(원석) → A급(신진) → B급(성장) → C급(일반)
"""

import os
import re
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from keywords import (
    filter_keywords,
    get_all_categories,
    get_all_languages,
    keyword_count,
)

load_dotenv()

# ── 등급 정의 ─────────────────────────────────────────────────────────────────
GRADES = {
    "S": {
        "label": "S급",
        "icon": "🏆",
        "color": "#FFD700",
        "bg": "#1a1500",
        "border": "#FFD700",
        "desc": "구독자 1만↓ · 업로드 7일↓ · 조회수 1만↓",
        "badge": "background:#FFD700;color:#000;",
    },
    "A": {
        "label": "A급",
        "icon": "⭐",
        "color": "#00CFFF",
        "bg": "#001a22",
        "border": "#00CFFF",
        "desc": "구독자 5만↓ · 업로드 30일↓ · 조회수 5만↓",
        "badge": "background:#00CFFF;color:#000;",
    },
    "B": {
        "label": "B급",
        "icon": "🌱",
        "color": "#4CAF50",
        "bg": "#0a1a0a",
        "border": "#4CAF50",
        "desc": "구독자 20만↓ · 업로드 90일↓",
        "badge": "background:#4CAF50;color:#fff;",
    },
    "C": {
        "label": "C급",
        "icon": "📺",
        "color": "#888888",
        "bg": "#1a1a1a",
        "border": "#444444",
        "desc": "대형 채널 또는 오래된 영상",
        "badge": "background:#555;color:#ccc;",
    },
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

THEMES = {
    "dark": {
        "bg": "#0a0a0a", "card_bg": "#141414", "card_border": "#2a2a2a",
        "sidebar_bg": "#111", "text": "#f1f1f1", "sub": "#888",
        "divider": "#2a2a2a", "meta_bg": "#222", "badge_bg": "rgba(0,0,0,0.85)",
    },
    "light": {
        "bg": "#f5f5f5", "card_bg": "#ffffff", "card_border": "#e0e0e0",
        "sidebar_bg": "#fafafa", "text": "#111", "sub": "#666",
        "divider": "#e5e5e5", "meta_bg": "#f0f0f0", "badge_bg": "rgba(0,0,0,0.7)",
    },
}


# ── CSS ───────────────────────────────────────────────────────────────────────
def build_css(t: dict) -> str:
    return f"""
<style>
.stApp,.main,.block-container{{background:{t['bg']}!important;color:{t['text']}!important}}
section[data-testid="stSidebar"]{{background:{t['sidebar_bg']}!important}}
section[data-testid="stSidebar"] *{{color:{t['text']}!important}}
.stTextInput input,.stSelectbox select,.stNumberInput input,.stMultiSelect div{{
  background:{t['card_bg']}!important;color:{t['text']}!important;border-color:{t['card_border']}!important}}
.stTabs [data-baseweb="tab-list"]{{background:{t['card_bg']}!important;border-bottom:2px solid {t['divider']}}}
.stTabs [data-baseweb="tab"]{{color:{t['sub']}!important}}
.stTabs [aria-selected="true"]{{color:#ff0000!important;border-bottom:2px solid #ff0000!important}}
div[data-testid="stMarkdownContainer"] *{{color:{t['text']}!important}}

/* ── 등급 요약 카드 ── */
.grade-summary{{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}}
.grade-box{{flex:1;min-width:120px;border-radius:12px;padding:14px 16px;text-align:center;border:1px solid;}}
.grade-count{{font-size:28px;font-weight:900;line-height:1}}
.grade-label{{font-size:13px;font-weight:700;margin-top:4px}}
.grade-desc{{font-size:10px;opacity:.65;margin-top:2px;line-height:1.3}}

/* ── 비디오 카드 ── */
.video-card{{
  border-radius:14px;margin-bottom:14px;overflow:hidden;
  border:1px solid {t['card_border']};background:{t['card_bg']};
  transition:border-color .2s,box-shadow .2s;
  box-shadow:0 2px 8px rgba(0,0,0,.08);
}}
.video-card:hover{{box-shadow:0 6px 20px rgba(255,0,0,.12)}}
.card-inner{{display:flex;align-items:stretch}}
.thumb-wrap{{flex:0 0 250px;position:relative;overflow:hidden;border-radius:14px 0 0 14px;background:#000}}
.thumb-wrap img{{width:100%;height:100%;object-fit:cover;display:block;transition:transform .3s}}
.video-card:hover .thumb-wrap img{{transform:scale(1.04)}}
.dur-badge{{
  position:absolute;bottom:8px;right:8px;
  background:{t['badge_bg']};color:#fff;font-size:11px;font-weight:700;
  padding:2px 7px;border-radius:4px}}
.grade-badge{{
  position:absolute;top:8px;left:8px;
  font-size:12px;font-weight:900;padding:3px 10px;border-radius:20px;
  letter-spacing:.5px}}
.card-info{{flex:1;padding:16px 20px;display:flex;flex-direction:column;gap:7px;min-width:0}}
.v-title{{font-size:15px;font-weight:700;color:{t['text']};line-height:1.45;margin:0 0 2px;word-break:break-word}}
.v-title a{{color:{t['text']};text-decoration:none}}
.v-title a:hover{{color:#ff0000}}
.ch-name{{font-size:13px;color:{t['sub']};font-weight:600;margin:0}}
.stats-row{{display:flex;flex-wrap:wrap;gap:16px;margin-top:6px;padding-top:8px;border-top:1px solid {t['divider']}}}
.stat-item{{display:flex;flex-direction:column}}
.s-label{{font-size:10px;color:{t['sub']};text-transform:uppercase;letter-spacing:.7px;font-weight:600}}
.s-val{{font-size:14px;font-weight:700;color:{t['text']}}}
.s-val.red{{color:#ff4444}}
.meta-row{{display:flex;gap:7px;flex-wrap:wrap;margin-top:4px}}
.meta-tag{{font-size:11px;color:{t['sub']};background:{t['meta_bg']};border-radius:5px;padding:2px 9px}}
.watch-btn{{
  display:inline-block;margin-top:8px;background:#ff0000;color:#fff!important;
  font-size:12px;font-weight:700;padding:7px 18px;border-radius:18px;
  text-decoration:none!important;transition:background .2s}}
.watch-btn:hover{{background:#cc0000}}

/* ── 필터 탭 ── */
.grade-filter{{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}}
.gf-btn{{
  padding:6px 16px;border-radius:20px;border:1px solid;font-size:12px;font-weight:700;
  cursor:pointer;background:transparent;transition:.2s}}
</style>
"""


# ── 유틸리티 ──────────────────────────────────────────────────────────────────
def fmt_num(n: int) -> str:
    if n >= 100_000_000:
        return f"{n/100_000_000:.1f}억"
    if n >= 10_000:
        return f"{n/10_000:.1f}만"
    return f"{n:,}"


def parse_duration(d: str) -> str:
    if not d:
        return ""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d)
    if not m:
        return d
    h, mi, s = (int(g or 0) for g in m.groups())
    return f"{h}:{mi:02d}:{s:02d}" if h else f"{mi}:{s:02d}"


def duration_seconds(d: str) -> int:
    """ISO 8601 duration → 총 초(seconds)"""
    if not d:
        return 0
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d)
    if not m:
        return 0
    h, mi, s = (int(g or 0) for g in m.groups())
    return h * 3600 + mi * 60 + s


def is_shorts(raw_duration: str, title: str) -> bool:
    """숏폼 판별: 60초 이하이거나 제목에 #shorts/#short 포함"""
    secs = duration_seconds(raw_duration)
    title_lower = title.lower()
    has_tag = "#shorts" in title_lower or "#short" in title_lower
    return (0 < secs <= 60) or has_tag


def days_since(published_at: str) -> int:
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 9999


def calculate_grade(subs: int, views: int, days: int) -> str:
    if subs < 10_000 and views < 10_000 and days <= 7:
        return "S"
    if subs < 50_000 and views < 50_000 and days <= 30:
        return "A"
    if subs < 200_000 and days <= 90:
        return "B"
    return "C"


# ── YouTube API ───────────────────────────────────────────────────────────────
def get_client(api_key: str):
    if not api_key:
        return None
    try:
        return build("youtube", "v3", developerKey=api_key)
    except Exception:
        return None


def search_ids(youtube, keyword: str, duration_filter: str,
               sort_by: str, max_results: int,
               published_after: str | None = None,
               max_pages: int = 1) -> list[str]:
    """
    YouTube search.list 호출. max_pages 설정으로 페이지네이션 지원.
    페이지당 최대 50개 → max_pages=4 이면 최대 200개/키워드.
    """
    base_params = {
        "part": "snippet", "q": keyword, "type": "video",
        "order": SORT_OPTIONS.get(sort_by, "relevance"),
        "maxResults": 50,
    }
    if published_after:
        base_params["publishedAfter"] = published_after
    dur = DURATION_FILTERS.get(duration_filter)
    if dur:
        base_params["videoDuration"] = dur

    ids: list[str] = []
    page_token: str | None = None

    for _ in range(max(1, max_pages)):
        params = dict(base_params)
        if page_token:
            params["pageToken"] = page_token
        resp = youtube.search().list(**params).execute()
        ids += [item["id"]["videoId"] for item in resp.get("items", [])]
        page_token = resp.get("nextPageToken")
        if not page_token or len(ids) >= max_results:
            break

    return ids[:max_results]


def fetch_subs(youtube, channel_ids: list[str]) -> dict[str, int]:
    result = {}
    for i in range(0, len(channel_ids), 50):
        chunk = channel_ids[i: i + 50]
        try:
            resp = youtube.channels().list(part="statistics", id=",".join(chunk)).execute()
            for item in resp.get("items", []):
                s = item.get("statistics", {}).get("subscriberCount")
                result[item["id"]] = int(s) if s else 0
        except Exception:
            pass  # 구독자 수 실패 시 0으로 처리하고 계속 진행
    return result


def fetch_details(youtube, video_ids: list[str]) -> list[dict]:
    if not video_ids:
        return []
    raw, ch_ids = [], []
    quota_hit = False
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i: i + 50]
        try:
            resp = (youtube.videos()
                    .list(part="snippet,statistics,contentDetails", id=",".join(chunk))
                    .execute())
        except HttpError as e:
            if "quotaExceeded" in str(e):
                quota_hit = True
                break   # 지금까지 수집된 것만 사용
            raise
        for item in resp.get("items", []):
            raw.append(item)
            cid = item["snippet"].get("channelId", "")
            if cid and cid not in ch_ids:
                ch_ids.append(cid)
    if quota_hit and raw:
        st.warning(f"⚠️ 쿼타 초과로 {len(raw)}개까지만 상세정보를 가져왔습니다.", icon="⚠️")

    subs_map = fetch_subs(youtube, ch_ids)
    rows = []
    for item in raw:
        sn = item["snippet"]
        st = item.get("statistics", {})
        cd = item.get("contentDetails", {})
        vid = item["id"]
        pub = sn.get("publishedAt", "")
        subs = subs_map.get(sn.get("channelId", ""), 0)
        views = int(st.get("viewCount", 0))
        d = days_since(pub)
        raw_dur = cd.get("duration", "")
        title = sn.get("title", "")
        short = is_shorts(raw_dur, title)
        # 숏폼은 Shorts URL 사용
        url = (f"https://www.youtube.com/shorts/{vid}" if short
               else f"https://www.youtube.com/watch?v={vid}")
        rows.append({
            "등급": calculate_grade(subs, views, d),
            "콘텐츠유형": "🩳 숏폼" if short else "🎬 롱폼",
            "제목": title,
            "채널명": sn.get("channelTitle", ""),
            "구독자수": subs,
            "URL": url,
            "업로드일": pub[:10],
            "업로드경과일": d,
            "조회수": views,
            "좋아요": int(st.get("likeCount", 0)),
            "댓글수": int(st.get("commentCount", 0)),
            "재생시간": parse_duration(raw_dur),
            "썸네일": (sn.get("thumbnails", {}).get("high", {}).get("url", "")
                      or sn.get("thumbnails", {}).get("medium", {}).get("url", "")),
            "_is_short": short,
            "_channel_id": sn.get("channelId", ""),
        })
    return rows


# ── 카드 렌더링 ───────────────────────────────────────────────────────────────
def render_card(row: dict, t: dict):
    g = GRADES[row["등급"]]
    thumb = row["썸네일"]
    is_short = row.get("_is_short", False)

    # 숏폼은 세로형 비율로 표시
    thumb_style = ("width:100%;height:100%;object-fit:cover;display:block;"
                   + ("aspect-ratio:9/16;" if is_short else ""))
    thumb_html = (f'<img src="{thumb}" alt="썸네일" style="{thumb_style}">' if thumb
                  else f'<div style="background:#222;width:100%;height:155px;"></div>')

    content_badge_style = ("background:#FF0076;color:#fff;" if is_short
                           else "background:#1a73e8;color:#fff;")
    content_label = "🩳 숏폼" if is_short else "🎬 롱폼"

    st.markdown(f"""
<div class="video-card" style="border-color:{g['border']}">
  <div class="card-inner">
    <div class="thumb-wrap">
      {thumb_html}
      <span class="grade-badge" style="{g['badge']}">{g['icon']} {g['label']}</span>
      <span class="dur-badge" style="{content_badge_style};position:absolute;bottom:8px;left:8px;
        font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;">{content_label}</span>
      <span class="dur-badge">{row['재생시간']}</span>
    </div>
    <div class="card-info">
      <p class="v-title"><a href="{row['URL']}" target="_blank">{row['제목']}</a></p>
      <p class="ch-name">📺 {row['채널명']}</p>
      <div class="stats-row">
        <div class="stat-item">
          <span class="s-label">구독자</span>
          <span class="s-val">👥 {fmt_num(row['구독자수'])}</span>
        </div>
        <div class="stat-item">
          <span class="s-label">조회수</span>
          <span class="s-val red">▶ {fmt_num(row['조회수'])}</span>
        </div>
        <div class="stat-item">
          <span class="s-label">좋아요</span>
          <span class="s-val">👍 {fmt_num(row['좋아요'])}</span>
        </div>
        <div class="stat-item">
          <span class="s-label">댓글</span>
          <span class="s-val">💬 {fmt_num(row['댓글수'])}</span>
        </div>
        <div class="stat-item">
          <span class="s-label">업로드 후</span>
          <span class="s-val">📅 {row['업로드경과일']}일</span>
        </div>
      </div>
      <div class="meta-row">
        <span class="meta-tag">📅 {row['업로드일']}</span>
        <span class="meta-tag">⏱ {row['재생시간']}</span>
      </div>
      <a class="watch-btn" href="{row['URL']}" target="_blank">▶ 영상 보기</a>
    </div>
  </div>
</div>""", unsafe_allow_html=True)


def render_grade_summary(rows: list[dict], t: dict):
    counts = {g: sum(1 for r in rows if r["등급"] == g) for g in "SABC"}
    boxes = ""
    for g, cfg in GRADES.items():
        boxes += f"""
<div class="grade-box" style="border-color:{cfg['border']};background:{cfg['bg']};">
  <div class="grade-count" style="color:{cfg['color']}">{cfg['icon']} {counts[g]}</div>
  <div class="grade-label" style="color:{cfg['color']}">{cfg['label']}</div>
  <div class="grade-desc" style="color:{t['sub']}">{cfg['desc']}</div>
</div>"""
    st.markdown(f'<div class="grade-summary">{boxes}</div>', unsafe_allow_html=True)


# ── 메인 앱 ───────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="한국 여행 채널 발굴기", page_icon="🔍", layout="wide")

    if "theme" not in st.session_state:
        st.session_state.theme = "dark"
    if "results" not in st.session_state:
        st.session_state.results = []
    if "last_keyword" not in st.session_state:
        st.session_state.last_keyword = ""

    t = THEMES[st.session_state.theme]
    st.markdown(build_css(t), unsafe_allow_html=True)

    # ── 헤더 ──────────────────────────────────────────────────────────────────
    col_title, col_toggle = st.columns([9, 1])
    with col_title:
        st.markdown(
            f"<h1 style='color:{t['text']};margin-bottom:2px;font-size:24px;'>"
            "🔍 한국 여행 채널 발굴기</h1>"
            f"<p style='color:{t['sub']};margin:0;font-size:13px;'>"
            "전 세계 숨겨진 한국 여행 채널을 S·A·B·C 등급으로 분류합니다</p>",
            unsafe_allow_html=True,
        )
    with col_toggle:
        is_dark = st.session_state.theme == "dark"
        if st.button("☀️ 낮" if is_dark else "🌙 밤", use_container_width=True):
            st.session_state.theme = "light" if is_dark else "dark"
            st.rerun()

    st.markdown(f"<hr style='border:none;border-top:2px solid {t['divider']};margin:6px 0 16px;'>",
                unsafe_allow_html=True)

    # ── 사이드바 ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🔑 API 키")
        env_key = os.getenv("YOUTUBE_API_KEY", "")
        api_input = st.text_input("YouTube API Key", value=env_key,
                                  type="password", placeholder="AIza...")
        api_key = api_input.strip() or env_key
        if api_key:
            st.success("API 키 설정됨", icon="✅")
        else:
            st.warning("API 키 필요", icon="⚠️")
            st.markdown("[🔗 API 키 발급](https://console.cloud.google.com/)")

        st.divider()

        # ── 검색 모드 선택 ──
        mode = st.radio("검색 모드", ["🔎 빠른 검색", "🗂 키워드 DB 검색"],
                        help="빠른 검색: 단일 키워드 / DB 검색: 언어·카테고리 선택 후 대량 검색")

        st.divider()

        pub_map = {"7일 이내": 7, "30일 이내": 30, "90일 이내": 90, "1년 이내": 365}

        if mode == "🔎 빠른 검색":
            st.markdown("### 🔍 검색")
            keyword_input = st.text_input("검색어", placeholder="예: korea hiking vlog")
            duration_filter = st.selectbox("영상 길이", list(DURATION_FILTERS.keys()))
            sort_by = st.selectbox("정렬", list(SORT_OPTIONS.keys()))
            pages_qs = st.slider("페이지 수 (페이지당 50개)", 1, 4, 2,
                                  help="2페이지 = 최대 100개, 4페이지 = 최대 200개")
            max_results = pages_qs * 50
            published_days = st.selectbox("업로드 기간",
                ["전체", "7일 이내", "30일 이내", "90일 이내", "1년 이내"])
            pub_after = None
            if published_days in pub_map:
                dt = datetime.now(timezone.utc) - timedelta(days=pub_map[published_days])
                pub_after = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            pages_arg = pages_qs
            search_clicked = st.button("🔍 검색", type="primary", use_container_width=True)

        else:
            st.markdown("### 🗂 키워드 DB 검색")

            all_langs = get_all_languages()

            # 500+ 빠른 설정 버튼 (안전한 기본값: 10 키워드 × 1페이지 = 500개, 1,000쿼타)
            preset_500 = st.button("⚡ 500+ 결과 자동 설정", use_container_width=True,
                                   help="10개 키워드 × 1페이지 = 약 500개 결과 (쿼타 1,000 소비)")
            if preset_500:
                st.session_state["db_langs"] = ["🇺🇸 English", "🇯🇵 日本語", "🇨🇳 中文"]
                st.session_state["db_cats"] = ["가족여행", "특수여행유형", "K-Food"]
                st.session_state["db_pages"] = 1
                st.rerun()

            default_langs = st.session_state.get("db_langs",
                                                  ["🇺🇸 English", "🇯🇵 日本語", "🇨🇳 中文"])
            default_cats = st.session_state.get("db_cats", ["가족여행", "특수여행유형"])

            sel_langs = st.multiselect("🌐 언어 선택", all_langs,
                                       default=default_langs,
                                       placeholder="언어를 선택하세요")
            all_cats = get_all_categories()
            sel_cats = st.multiselect("📂 카테고리 선택", all_cats,
                                      default=default_cats,
                                      placeholder="카테고리를 선택하세요")

            selected_kws = filter_keywords(sel_langs or None, sel_cats or None)
            kw_count = len(selected_kws)

            duration_filter = st.selectbox("영상 길이", list(DURATION_FILTERS.keys()))
            sort_by = st.selectbox("정렬", list(SORT_OPTIONS.keys()))

            pages_per_kw = st.slider("키워드당 페이지 수", 1, 2,
                                     st.session_state.get("db_pages", 1),
                                     help="페이지당 50개. 1페이지 권장 (쿼타 절약)")
            max_results = pages_per_kw * 50
            pages_arg = pages_per_kw

            # ── 쿼타 계산기 ──────────────────────────────────────────────
            # search.list = 100 쿼타/호출, videos.list = 1 쿼타/50개, channels.list ≈ 1
            DAILY_QUOTA = 10_000
            search_quota = kw_count * pages_per_kw * 100
            detail_quota = (kw_count * max_results // 50) + kw_count
            total_quota = search_quota + detail_quota
            quota_pct = total_quota / DAILY_QUOTA * 100

            # 실제 검색 가능 키워드 수 (쿼타 한도 내)
            safe_kw_limit = max(1, int((DAILY_QUOTA * 0.8) / (pages_per_kw * 100)))
            actual_kws = min(kw_count, safe_kw_limit)
            est = actual_kws * max_results

            if quota_pct <= 50:
                st.success(
                    f"예상 쿼타: **{total_quota:,} / {DAILY_QUOTA:,}** ({quota_pct:.0f}%) ✅  "
                    f"| 키워드 **{actual_kws}개** → 최대 **~{est:,}개**",
                    icon="📊",
                )
            elif quota_pct <= 85:
                st.warning(
                    f"⚠️ 예상 쿼타: **{total_quota:,} / {DAILY_QUOTA:,}** ({quota_pct:.0f}%)  "
                    f"| 실제 검색은 **{actual_kws}개** 키워드로 제한됩니다.",
                    icon="⚠️",
                )
            else:
                st.error(
                    f"🚫 쿼타 초과 위험 ({quota_pct:.0f}%)! 자동으로 **{actual_kws}개** 키워드만 검색합니다.  "
                    f"키워드 수를 줄이거나 페이지 수를 낮춰주세요.",
                )

            published_days = st.selectbox("업로드 기간",
                ["전체", "7일 이내", "30일 이내", "90일 이내", "1년 이내"])
            pub_after = None
            if published_days in pub_map:
                dt = datetime.now(timezone.utc) - timedelta(days=pub_map[published_days])
                pub_after = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            search_clicked = st.button("🚀 대량 검색 시작", type="primary",
                                       use_container_width=True,
                                       disabled=(kw_count == 0))
            keyword_input = ""

        st.divider()
        st.markdown("### 🎬 콘텐츠 유형")
        content_type = st.radio(
            "콘텐츠 유형",
            ["전체", "🎬 롱폼만", "🩳 숏폼만"],
            horizontal=True,
            label_visibility="collapsed",
            help="숏폼: 60초 이하 또는 #Shorts 태그 포함 영상",
        )

        st.divider()
        st.markdown("### 📊 조회수 필터")
        min_views = st.number_input("최소 조회수", min_value=0, value=0, step=1000)
        max_views = st.number_input("최대 조회수", min_value=0, value=0, step=1000)

    # ── 검색 실행 ─────────────────────────────────────────────────────────────
    if search_clicked:
        if not api_key:
            st.error("사이드바에 YouTube API 키를 입력해 주세요.")
            st.stop()

        youtube = get_client(api_key)
        if not youtube:
            st.error("API 키가 유효하지 않습니다.")
            st.stop()

        if mode == "🔎 빠른 검색":
            if not keyword_input.strip():
                st.warning("검색어를 입력해 주세요.")
                st.stop()
            keywords_to_search = [keyword_input.strip()]
        else:
            if not selected_kws:
                st.warning("언어 또는 카테고리를 선택해 주세요.")
                st.stop()
            # 쿼타 안전 상한 적용 (일일 한도의 80% 이내)
            safe_limit = max(1, int(8_000 / (pages_arg * 100)))
            keywords_to_search = selected_kws[:safe_limit]
            if len(selected_kws) > safe_limit:
                st.info(
                    f"쿼타 보호: {len(selected_kws)}개 키워드 중 "
                    f"**{safe_limit}개**만 검색합니다 (일일 한도 80% 기준).",
                    icon="🛡️",
                )

        all_ids: dict[str, str] = {}  # video_id → search_keyword
        total = len(keywords_to_search)
        errors: list[str] = []

        progress_bar = st.progress(0, text="검색 준비 중...")
        status_box = st.empty()

        for idx, kw in enumerate(keywords_to_search):
            status_box.markdown(
                f"🔍 **{idx+1}/{total}** 검색 중: `{kw}` "
                f"| 수집된 영상: **{len(all_ids)}개**"
            )
            try:
                ids = search_ids(youtube, kw, duration_filter, sort_by,
                                 max_results, pub_after,
                                 max_pages=pages_arg)
                for vid in ids:
                    if vid not in all_ids:
                        all_ids[vid] = kw
            except HttpError as e:
                err_str = str(e)
                if "quotaExceeded" in err_str:
                    st.warning("⚠️ API 일일 할당량 초과. 지금까지 수집된 결과를 표시합니다.")
                    break
                errors.append(f"`{kw}`: {err_str[:120]}")
                # 첫 오류 즉시 표시 (API 키 문제 등 조기 감지)
                if idx == 0 and len(errors) == 1:
                    st.error(f"첫 번째 검색 오류 — API 키를 확인하세요:\n\n{errors[0]}")
                    st.stop()
                continue
            except Exception as e:
                st.error(f"예상치 못한 오류: {e}")
                st.stop()

            progress_bar.progress((idx + 1) / total,
                                  text=f"진행: {idx+1}/{total} | 수집: {len(all_ids)}개")
            if total > 1:
                time.sleep(0.05)

        if errors and len(all_ids) == 0:
            st.error("모든 검색이 실패했습니다. 오류 내용:\n\n" + "\n".join(errors[:5]))
            st.stop()

        status_box.markdown(f"📥 **{len(all_ids)}개** 영상 상세정보 수집 중...")
        progress_bar.progress(1.0, text="영상 정보 수집 중...")

        try:
            rows = fetch_details(youtube, list(all_ids.keys()))
        except HttpError as e:
            st.error(f"YouTube API 오류 (videos.list): {e}")
            st.stop()
        except Exception as e:
            st.error(f"상세정보 수집 오류: {e}")
            st.stop()

        # 콘텐츠 유형 필터
        if content_type == "🎬 롱폼만":
            rows = [r for r in rows if not r["_is_short"]]
        elif content_type == "🩳 숏폼만":
            rows = [r for r in rows if r["_is_short"]]

        # 조회수 필터
        if min_views > 0:
            rows = [r for r in rows if r["조회수"] >= min_views]
        if max_views > 0:
            rows = [r for r in rows if r["조회수"] <= max_views]

        # 등급순 정렬 (S→A→B→C, 같은 등급 내에서는 업로드 최신순)
        grade_order = {"S": 0, "A": 1, "B": 2, "C": 3}
        rows.sort(key=lambda r: (grade_order[r["등급"]], r["업로드경과일"]))

        st.session_state.results = rows
        progress_bar.empty()
        status_box.empty()

    # ── 결과 표시 ─────────────────────────────────────────────────────────────
    rows = st.session_state.results

    if not rows:
        st.markdown(
            f"<div style='text-align:center;padding:80px 0;color:{t['sub']};'>"
            "<div style='font-size:52px'>🔍</div>"
            f"<div style='font-size:18px;margin-top:14px;color:{t['sub']};'>"
            "사이드바에서 검색어 또는 키워드 DB를 선택하고<br>"
            f"<b style='color:#ff0000'>검색</b> 버튼을 클릭하세요</div>"
            f"<div style='margin-top:20px;font-size:13px;color:{t['sub']};line-height:1.8'>"
            "🏆 S급: 구독자 1만↓ · 7일이내 · 조회수 1만↓<br>"
            "⭐ A급: 구독자 5만↓ · 30일이내 · 조회수 5만↓<br>"
            "🌱 B급: 구독자 20만↓ · 90일이내<br>"
            "📺 C급: 대형 채널 / 오래된 영상</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # 등급 요약
    render_grade_summary(rows, t)

    total_count = len(rows)
    st.markdown(
        f"<p style='color:{t['sub']};font-size:14px;margin-bottom:12px'>"
        f"총 <b style='color:{t['text']}'>{total_count}개</b> 영상 | "
        f"등급순 정렬 (S → A → B → C)</p>",
        unsafe_allow_html=True,
    )

    # 등급 필터
    grade_filter = st.radio(
        "등급 필터",
        ["전체", "🏆 S급", "⭐ A급", "🌱 B급", "📺 C급"],
        horizontal=True,
        label_visibility="collapsed",
    )
    grade_map = {"전체": None, "🏆 S급": "S", "⭐ A급": "A", "🌱 B급": "B", "📺 C급": "C"}
    filtered = [r for r in rows if grade_map[grade_filter] is None
                or r["등급"] == grade_map[grade_filter]]

    st.markdown(
        f"<p style='color:{t['sub']};font-size:13px;margin:4px 0 14px'>"
        f"표시 중: <b style='color:{t['text']}'>{len(filtered)}개</b></p>",
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["🎬 카드 보기", "📋 테이블 보기"])

    with tab1:
        for row in filtered:
            render_card(row, t)

    with tab2:
        df = pd.DataFrame(filtered).drop(columns=["썸네일", "_channel_id", "_is_short"])
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "URL": st.column_config.LinkColumn("URL"),
                "조회수": st.column_config.NumberColumn(format="%d"),
                "좋아요": st.column_config.NumberColumn(format="%d"),
                "댓글수": st.column_config.NumberColumn(format="%d"),
                "구독자수": st.column_config.NumberColumn(format="%d"),
            },
        )
        csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "📥 CSV 다운로드",
            data=csv,
            file_name="한국여행채널_발굴결과.csv",
            mime="text/csv",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
