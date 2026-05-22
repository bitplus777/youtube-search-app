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
from db import delete_session, list_sessions, load_session, rename_session, save_session

load_dotenv()

# ── 등급 정의 ─────────────────────────────────────────────────────────────────
GRADES = {
    "S": {
        "label": "S급",
        "icon": "🏆",
        "color": "#FFD700",
        "bg": "linear-gradient(135deg,#1a1200 0%,#2a1e00 100%)",
        "border": "#FFD700",
        "desc": "구독자 1만↓ · 업로드 7일↓ · 조회수 1만↓",
        "badge": "background:linear-gradient(135deg,#FFD700,#FFA500);color:#000;",
        "glow": "0 0 20px rgba(255,215,0,0.4)",
    },
    "A": {
        "label": "A급",
        "icon": "⭐",
        "color": "#00CFFF",
        "bg": "linear-gradient(135deg,#001520 0%,#002030 100%)",
        "border": "#00CFFF",
        "desc": "구독자 5만↓ · 업로드 30일↓ · 조회수 5만↓",
        "badge": "background:linear-gradient(135deg,#00CFFF,#0090CC);color:#000;",
        "glow": "0 0 20px rgba(0,207,255,0.3)",
    },
    "B": {
        "label": "B급",
        "icon": "🌱",
        "color": "#4CAF50",
        "bg": "linear-gradient(135deg,#071507 0%,#0d200d 100%)",
        "border": "#4CAF50",
        "desc": "구독자 20만↓ · 업로드 90일↓",
        "badge": "background:linear-gradient(135deg,#4CAF50,#2E7D32);color:#fff;",
        "glow": "0 0 20px rgba(76,175,80,0.25)",
    },
    "C": {
        "label": "C급",
        "icon": "📺",
        "color": "#9E9E9E",
        "bg": "linear-gradient(135deg,#141414 0%,#1e1e1e 100%)",
        "border": "#444",
        "desc": "대형 채널 또는 오래된 영상",
        "badge": "background:linear-gradient(135deg,#555,#333);color:#ccc;",
        "glow": "none",
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
        "bg": "#0d0d0d",
        "card_bg": "#161616",
        "card_border": "#2a2a2a",
        "sidebar_bg": "#111",
        "text": "#f0f0f0",
        "sub": "#888",
        "divider": "#2a2a2a",
        "meta_bg": "#1e1e1e",
        "badge_bg": "rgba(0,0,0,0.85)",
        "input_bg": "#1a1a1a",
        "hero_from": "#1a0000",
        "hero_to": "#0d0d0d",
        "tag_bg": "rgba(255,255,255,0.06)",
    },
    "light": {
        "bg": "#f0f2f5",
        "card_bg": "#ffffff",
        "card_border": "#e0e0e0",
        "sidebar_bg": "#fafafa",
        "text": "#111",
        "sub": "#666",
        "divider": "#e0e0e0",
        "meta_bg": "#f5f5f5",
        "badge_bg": "rgba(0,0,0,0.7)",
        "input_bg": "#fff",
        "hero_from": "#fff0f0",
        "hero_to": "#f0f2f5",
        "tag_bg": "rgba(0,0,0,0.05)",
    },
}


# ── CSS ───────────────────────────────────────────────────────────────────────
def build_css(t: dict) -> str:
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');

/* ── 전체 기반 ── */
.stApp,.main,.block-container{{
  background:{t['bg']}!important;
  color:{t['text']}!important;
  font-family:'Noto Sans KR',sans-serif!important;
}}
.block-container{{padding-top:1rem!important;max-width:1400px!important}}
section[data-testid="stSidebar"]{{
  background:{t['sidebar_bg']}!important;
  border-right:1px solid {t['divider']}!important;
}}
section[data-testid="stSidebar"] *{{color:{t['text']}!important}}

/* ── 입력 컴포넌트 ── */
.stTextInput input,.stSelectbox select,.stNumberInput input{{
  background:{t['input_bg']}!important;
  color:{t['text']}!important;
  border:1px solid {t['divider']}!important;
  border-radius:8px!important;
}}
.stTextInput input:focus,.stSelectbox select:focus{{
  border-color:#ff0000!important;
  box-shadow:0 0 0 2px rgba(255,0,0,0.15)!important;
}}
.stTextArea textarea{{
  background:{t['input_bg']}!important;
  color:{t['text']}!important;
  border:1px solid {t['divider']}!important;
  border-radius:8px!important;
}}
div[data-baseweb="select"] > div{{
  background:{t['input_bg']}!important;
  border:1px solid {t['divider']}!important;
  border-radius:8px!important;
}}

/* ── 탭 ── */
.stTabs [data-baseweb="tab-list"]{{
  background:{t['card_bg']}!important;
  border-bottom:2px solid {t['divider']}!important;
  gap:4px;
  border-radius:12px 12px 0 0;
  padding:4px 4px 0;
}}
.stTabs [data-baseweb="tab"]{{
  color:{t['sub']}!important;
  font-weight:600;
  font-size:14px;
  border-radius:8px 8px 0 0;
  padding:10px 20px!important;
  transition:all .2s;
}}
.stTabs [aria-selected="true"]{{
  color:#ff0000!important;
  border-bottom:3px solid #ff0000!important;
  background:rgba(255,0,0,0.05)!important;
}}
div[data-testid="stMarkdownContainer"] *{{color:{t['text']}!important}}

/* ── 버튼 ── */
.stButton > button{{
  border-radius:10px!important;
  font-weight:700!important;
  font-size:13px!important;
  transition:all .2s!important;
  border:1px solid {t['divider']}!important;
}}
.stButton > button[kind="primary"]{{
  background:linear-gradient(135deg,#ff0000,#cc0000)!important;
  color:#fff!important;
  border:none!important;
  box-shadow:0 4px 15px rgba(255,0,0,0.35)!important;
}}
.stButton > button[kind="primary"]:hover{{
  transform:translateY(-1px);
  box-shadow:0 6px 20px rgba(255,0,0,0.5)!important;
}}

/* ── 히어로 헤더 ── */
.hero-header{{
  background:linear-gradient(135deg,{t['hero_from']} 0%,{t['bg']} 100%);
  border:1px solid {t['divider']};
  border-radius:16px;
  padding:24px 32px;
  margin-bottom:20px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:16px;
}}
.hero-title{{
  font-size:28px;
  font-weight:900;
  color:{t['text']};
  margin:0;
  line-height:1.2;
}}
.hero-title span{{color:#ff0000}}
.hero-sub{{
  font-size:13px;
  color:{t['sub']};
  margin:6px 0 0;
}}

/* ── 등급 요약 카드 ── */
.grade-summary{{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}}
.grade-box{{
  flex:1;min-width:130px;
  border-radius:14px;
  padding:18px 16px;
  text-align:center;
  border:1px solid;
  transition:transform .2s,box-shadow .2s;
}}
.grade-box:hover{{transform:translateY(-3px)}}
.grade-count{{font-size:32px;font-weight:900;line-height:1}}
.grade-label{{font-size:14px;font-weight:800;margin-top:6px;letter-spacing:.5px}}
.grade-desc{{font-size:10px;opacity:.6;margin-top:4px;line-height:1.4}}

/* ── 비디오 카드 ── */
.video-card{{
  border-radius:16px;
  margin-bottom:16px;
  overflow:hidden;
  border:1px solid;
  transition:all .25s;
}}
.video-card:hover{{transform:translateY(-3px)}}
.card-inner{{display:flex;align-items:stretch}}
.thumb-wrap{{
  flex:0 0 260px;
  position:relative;
  overflow:hidden;
  border-radius:16px 0 0 16px;
  background:#000;
}}
.thumb-wrap img{{
  width:100%;height:100%;
  object-fit:cover;display:block;
  transition:transform .4s;
}}
.video-card:hover .thumb-wrap img{{transform:scale(1.06)}}
.dur-badge{{
  position:absolute;bottom:8px;right:8px;
  background:{t['badge_bg']};color:#fff;
  font-size:11px;font-weight:700;
  padding:3px 8px;border-radius:6px;
  backdrop-filter:blur(4px);
}}
.grade-badge{{
  position:absolute;top:8px;left:8px;
  font-size:11px;font-weight:900;
  padding:4px 12px;border-radius:20px;
  letter-spacing:.5px;
  box-shadow:0 2px 8px rgba(0,0,0,.5);
}}
.card-info{{
  flex:1;padding:18px 22px;
  display:flex;flex-direction:column;gap:8px;min-width:0;
}}
.v-title{{
  font-size:15px;font-weight:700;
  color:{t['text']};line-height:1.5;
  margin:0;word-break:break-word;
}}
.v-title a{{color:{t['text']};text-decoration:none}}
.v-title a:hover{{color:#ff0000}}
.ch-row{{
  display:flex;align-items:center;gap:8px;
  font-size:13px;color:{t['sub']};font-weight:600;
}}
.stats-row{{
  display:flex;flex-wrap:wrap;gap:12px;
  margin-top:8px;padding-top:10px;
  border-top:1px solid {t['divider']};
}}
.stat-item{{display:flex;flex-direction:column;gap:2px}}
.s-label{{
  font-size:9px;color:{t['sub']};
  text-transform:uppercase;letter-spacing:.8px;font-weight:700;
}}
.s-val{{font-size:15px;font-weight:800;color:{t['text']}}}
.s-val.red{{color:#ff4444}}
.s-val.gold{{color:#FFD700}}
.tag-row{{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}}
.tag{{
  font-size:11px;color:{t['sub']};
  background:{t['tag_bg']};
  border:1px solid {t['divider']};
  border-radius:6px;padding:2px 10px;
  font-weight:500;
}}
.watch-btn{{
  display:inline-flex;align-items:center;gap:6px;
  margin-top:10px;align-self:flex-start;
  background:linear-gradient(135deg,#ff0000,#cc0000);
  color:#fff!important;
  font-size:12px;font-weight:700;
  padding:8px 20px;border-radius:20px;
  text-decoration:none!important;
  transition:all .2s;
  box-shadow:0 3px 12px rgba(255,0,0,0.3);
}}
.watch-btn:hover{{
  transform:translateY(-1px);
  box-shadow:0 5px 18px rgba(255,0,0,0.5);
}}

/* ── API 키 카드 ── */
.api-key-card{{
  background:{t['card_bg']};
  border:1px solid {t['divider']};
  border-radius:12px;
  padding:12px;
  margin-bottom:8px;
}}
.key-status-ok{{
  display:inline-flex;align-items:center;gap:4px;
  font-size:11px;color:#4CAF50;font-weight:700;
}}
.key-status-empty{{
  display:inline-flex;align-items:center;gap:4px;
  font-size:11px;color:{t['sub']};font-weight:600;
}}

/* ── 검색 기록 ── */
.hist-card{{
  background:{t['card_bg']};
  border:1px solid {t['divider']};
  border-radius:14px;
  padding:16px 20px;
  margin-bottom:12px;
  transition:border-color .2s;
}}
.hist-card:hover{{border-color:#ff0000}}
.hist-name{{font-size:16px;font-weight:800;color:{t['text']}}}
.hist-meta{{font-size:12px;color:{t['sub']};margin-top:4px}}
.hist-grade-row{{
  display:flex;gap:8px;margin-top:10px;flex-wrap:wrap
}}
.hg-badge{{
  font-size:12px;font-weight:700;
  padding:3px 12px;border-radius:20px;
}}

/* ── 스크롤바 ── */
::-webkit-scrollbar{{width:6px;height:6px}}
::-webkit-scrollbar-track{{background:{t['bg']}}}
::-webkit-scrollbar-thumb{{background:#444;border-radius:3px}}
::-webkit-scrollbar-thumb:hover{{background:#666}}

/* ── 알림 박스 ── */
div[data-testid="stNotification"]{{border-radius:12px!important}}
div[data-testid="stInfo"]{{border-radius:10px!important}}
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
    if not d:
        return 0
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d)
    if not m:
        return 0
    h, mi, s = (int(g or 0) for g in m.groups())
    return h * 3600 + mi * 60 + s


def is_shorts(raw_duration: str, title: str) -> bool:
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


# ── YouTube API (멀티 키 지원) ─────────────────────────────────────────────────
def _classify_api_error(err_str: str) -> dict:
    e = err_str.lower()
    if "quotaexceeded" in e or "dailylimitexceeded" in e:
        return {
            "type": "quota",
            "stop": True,
            "msg": (
                "🚫 **API 할당량(10,000 쿼타)이 소진되었습니다.**\n\n"
                "- 쿼타는 **매일 오전 9시(한국 시간)** 에 초기화됩니다.\n"
                "- 사이드바에 **다른 API 키**가 등록되어 있으면 자동으로 전환됩니다.\n"
                "- [🔗 Google Cloud Console](https://console.cloud.google.com/)"
            ),
        }
    if "keyinvalid" in e or "api key not valid" in e or "bad request" in e:
        return {
            "type": "key_invalid",
            "stop": True,
            "msg": "❌ **API 키가 올바르지 않습니다.** 사이드바의 API 키를 확인해 주세요.",
        }
    if "accessnotconfigured" in e or "youtube data api" in e:
        return {
            "type": "not_configured",
            "stop": True,
            "msg": (
                "❌ **YouTube Data API v3가 활성화되지 않았습니다.**\n\n"
                "[Google Cloud Console → API 라이브러리](https://console.cloud.google.com/apis/library/youtube.googleapis.com) "
                "에서 YouTube Data API v3를 활성화해 주세요."
            ),
        }
    return {"type": "other", "stop": False, "msg": f"일부 키워드 검색 실패: {err_str[:80]}"}


def get_client(api_key: str):
    if not api_key:
        return None
    try:
        return build("youtube", "v3", developerKey=api_key)
    except Exception:
        return None


def get_valid_keys() -> list[str]:
    """세션에 등록된 API 키 목록(비어있지 않은 것만)."""
    env_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    secret_key = ""
    try:
        secret_key = st.secrets.get("YOUTUBE_API_KEY", "").strip()
    except Exception:
        pass

    keys_input = st.session_state.get("api_keys_raw", ["", "", "", "", ""])
    manual_keys = [k.strip() for k in keys_input if k.strip()]

    seen, result = set(), []
    for k in ([env_key, secret_key] + manual_keys):
        if k and k not in seen:
            seen.add(k)
            result.append(k)
    return result


def rotate_to_next_key(exhausted_idx: int) -> tuple[object, int]:
    """
    exhausted_idx 다음 키로 전환. 성공하면 (client, new_idx), 없으면 (None, -1).
    """
    keys = get_valid_keys()
    next_idx = exhausted_idx + 1
    if next_idx < len(keys):
        client = get_client(keys[next_idx])
        if client:
            return client, next_idx
    return None, -1


def search_ids(youtube, keyword: str, duration_filter: str,
               sort_by: str, max_results: int,
               published_after: str | None = None,
               max_pages: int = 1) -> list[str]:
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
            pass
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
                break
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
        stat = item.get("statistics", {})
        cd = item.get("contentDetails", {})
        vid = item["id"]
        pub = sn.get("publishedAt", "")
        subs = subs_map.get(sn.get("channelId", ""), 0)
        views = int(stat.get("viewCount", 0))
        d = days_since(pub)
        raw_dur = cd.get("duration", "")
        title = sn.get("title", "")
        short = is_shorts(raw_dur, title)
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
            "좋아요": int(stat.get("likeCount", 0)),
            "댓글수": int(stat.get("commentCount", 0)),
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

    thumb_style = "width:100%;height:100%;object-fit:cover;display:block;"
    if is_short:
        thumb_style += "aspect-ratio:9/16;"
    thumb_html = (f'<img src="{thumb}" alt="썸네일" style="{thumb_style}">' if thumb
                  else f'<div style="background:#1a1a1a;width:100%;height:160px;'
                       f'display:flex;align-items:center;justify-content:center;'
                       f'font-size:40px;">🎬</div>')

    content_badge_style = ("background:#FF0076;color:#fff;" if is_short
                           else "background:#1a73e8;color:#fff;")
    content_label = "🩳 숏폼" if is_short else "🎬 롱폼"

    st.markdown(f"""
<div class="video-card" style="border-color:{g['border']};background:{g['bg']};box-shadow:{g['glow']}">
  <div class="card-inner">
    <div class="thumb-wrap">
      {thumb_html}
      <span class="grade-badge" style="{g['badge']}">{g['icon']} {g['label']}</span>
      <span class="dur-badge" style="{content_badge_style};position:absolute;bottom:8px;left:8px;
        font-size:10px;font-weight:700;padding:2px 8px;border-radius:5px;
        backdrop-filter:blur(4px);">{content_label}</span>
      <span class="dur-badge">{row['재생시간']}</span>
    </div>
    <div class="card-info">
      <p class="v-title"><a href="{row['URL']}" target="_blank">{row['제목']}</a></p>
      <div class="ch-row">
        <span>📺</span>
        <span style="font-size:13px;font-weight:700;color:{t['sub']}">{row['채널명']}</span>
      </div>
      <div class="stats-row">
        <div class="stat-item">
          <span class="s-label">구독자</span>
          <span class="s-val gold">👥 {fmt_num(row['구독자수'])}</span>
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
      <div class="tag-row">
        <span class="tag">📅 {row['업로드일']}</span>
        <span class="tag">⏱ {row['재생시간']}</span>
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
<div class="grade-box" style="border-color:{cfg['border']};background:{cfg['bg']};
     box-shadow:{cfg['glow']};">
  <div class="grade-count" style="color:{cfg['color']}">{cfg['icon']} {counts[g]}</div>
  <div class="grade-label" style="color:{cfg['color']}">{cfg['label']}</div>
  <div class="grade-desc" style="color:{t['sub']}">{cfg['desc']}</div>
</div>"""
    st.markdown(f'<div class="grade-summary">{boxes}</div>', unsafe_allow_html=True)


# ── 검색 기록 탭 ──────────────────────────────────────────────────────────────
def _render_history_tab(t: dict):
    sessions = list_sessions()

    if not sessions:
        st.markdown(
            f"<div style='text-align:center;padding:80px 0;'>"
            "<div style='font-size:56px'>📭</div>"
            f"<div style='font-size:17px;margin-top:14px;color:{t['sub']};line-height:1.8'>"
            "저장된 검색 기록이 없습니다.<br>"
            f"검색 후 <b style='color:{t['text']}'>💾 검색 결과 저장</b> 버튼을 눌러보세요.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"<p style='color:{t['sub']};font-size:14px;margin-bottom:16px;'>"
        f"저장된 검색 기록 <b style='color:{t['text']}'>{len(sessions)}건</b></p>",
        unsafe_allow_html=True,
    )

    grade_colors = {"S": "#FFD700", "A": "#00CFFF", "B": "#4CAF50", "C": "#888"}

    for s in sessions:
        sid = s["id"]
        grade_badges = "".join([
            f"<span class='hg-badge' style='background:{grade_colors[g]}20;"
            f"color:{grade_colors[g]};border:1px solid {grade_colors[g]}40;'>"
            f"{lbl} {s[f'grade_{g.lower()}']}</span>"
            for g, lbl in [("S","🏆S"), ("A","⭐A"), ("B","🌱B"), ("C","📺C")]
        ])

        st.markdown(
            f"""<div class="hist-card">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:8px;">
    <div>
      <div class="hist-name">{s['name']}</div>
      <div class="hist-meta">📅 {s['saved_at']} &nbsp;|&nbsp; 🎬 총 {s['result_count']}개 영상 &nbsp;|&nbsp; ID: {sid}</div>
      <div class="hist-grade-row">{grade_badges}</div>
    </div>
  </div>
</div>""",
            unsafe_allow_html=True,
        )

        btn_col1, btn_col2, btn_col3, _, rename_col = st.columns([1.5, 1.5, 1, 0.5, 3])

        with btn_col1:
            if st.button("📂 불러오기", key=f"load_{sid}", use_container_width=True, type="primary"):
                st.session_state.results = load_session(sid)
                st.success(f"'{s['name']}' 불러왔습니다. 🔍 검색 탭에서 확인하세요.")
                st.rerun()

        with btn_col2:
            if st.button("🗑️ 삭제", key=f"del_{sid}", use_container_width=True):
                delete_session(sid)
                st.rerun()

        with btn_col3:
            pass

        with rename_col:
            rc1, rc2 = st.columns([3, 1])
            with rc1:
                new_name = st.text_input("", key=f"rename_input_{sid}",
                                         placeholder="이름 변경...",
                                         label_visibility="collapsed")
            with rc2:
                if st.button("✏️", key=f"rename_{sid}", use_container_width=True,
                             help="이름 변경"):
                    if new_name.strip():
                        rename_session(sid, new_name.strip())
                        st.rerun()

        st.markdown(
            f"<hr style='border:none;border-top:1px solid {t['divider']};margin:8px 0 16px;'>",
            unsafe_allow_html=True,
        )


# ── 메인 앱 ───────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="한국 여행 채널 발굴기", page_icon="🔍", layout="wide")

    # 세션 초기화
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"
    if "results" not in st.session_state:
        st.session_state.results = []
    if "api_keys_raw" not in st.session_state:
        st.session_state.api_keys_raw = ["", "", "", "", ""]

    t = THEMES[st.session_state.theme]
    st.markdown(build_css(t), unsafe_allow_html=True)

    # ── 히어로 헤더 ──────────────────────────────────────────────────────────
    is_dark = st.session_state.theme == "dark"
    toggle_label = "☀️ 라이트" if is_dark else "🌙 다크"
    col_hero, col_btn = st.columns([10, 1.5])
    with col_hero:
        st.markdown(
            f"<div class='hero-header'>"
            f"<div>"
            f"<h1 class='hero-title'>🔍 한국 여행 채널 <span>발굴기</span></h1>"
            f"<p class='hero-sub'>"
            "전 세계 숨겨진 한국 여행 채널을 &nbsp;"
            "<b style='color:#FFD700'>🏆S</b> &nbsp;"
            "<b style='color:#00CFFF'>⭐A</b> &nbsp;"
            "<b style='color:#4CAF50'>🌱B</b> &nbsp;"
            "<b style='color:#888'>📺C</b> &nbsp;"
            "등급으로 분류합니다</p>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_btn:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button(toggle_label, use_container_width=True):
            st.session_state.theme = "light" if is_dark else "dark"
            st.rerun()

    # ── 메인 탭 ───────────────────────────────────────────────────────────────
    main_tab, history_tab = st.tabs(["🔍 검색", "📚 저장된 검색 기록"])

    with history_tab:
        _render_history_tab(t)

    # ── 사이드바 ──────────────────────────────────────────────────────────────
    with st.sidebar:
        # ── API 키 섹션 ──
        st.markdown(
            f"<div style='font-size:16px;font-weight:800;margin-bottom:10px;'>"
            "🔑 YouTube API 키</div>"
            f"<div style='font-size:11px;color:{t['sub']};margin-bottom:10px;line-height:1.5'>"
            "최대 5개 키를 등록하면 쿼타 소진 시 자동으로 다음 키로 전환됩니다.</div>",
            unsafe_allow_html=True,
        )

        env_key = os.getenv("YOUTUBE_API_KEY", "").strip()
        try:
            secret_key = st.secrets.get("YOUTUBE_API_KEY", "").strip()
        except Exception:
            secret_key = ""

        # .env 또는 secrets에서 키가 있으면 첫 번째 슬롯에 미리 채움
        prefill = env_key or secret_key
        if prefill and not st.session_state.api_keys_raw[0]:
            st.session_state.api_keys_raw[0] = prefill

        new_keys = []
        for i in range(5):
            col_idx, col_input = st.columns([1, 8])
            with col_idx:
                st.markdown(
                    f"<div style='text-align:center;font-size:12px;font-weight:700;"
                    f"color:{t['sub']};padding-top:8px;'>#{i+1}</div>",
                    unsafe_allow_html=True,
                )
            with col_input:
                val = st.text_input(
                    f"API Key {i+1}",
                    value=st.session_state.api_keys_raw[i],
                    type="password",
                    placeholder="AIza...",
                    label_visibility="collapsed",
                    key=f"api_key_slot_{i}",
                )
            new_keys.append(val)
        st.session_state.api_keys_raw = new_keys

        valid_keys = get_valid_keys()
        if valid_keys:
            st.markdown(
                f"<div style='background:#4CAF5015;border:1px solid #4CAF5040;"
                f"border-radius:8px;padding:8px 12px;margin:6px 0;'>"
                f"<span class='key-status-ok'>✅ {len(valid_keys)}개 키 등록됨</span></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div style='background:#ff000015;border:1px solid #ff000040;"
                f"border-radius:8px;padding:8px 12px;margin:6px 0;'>"
                f"<span style='font-size:12px;color:#ff4444;font-weight:700;'>"
                f"⚠️ API 키를 입력해 주세요</span>"
                f"<br><a href='https://console.cloud.google.com/' target='_blank' "
                f"style='font-size:11px;color:#888;'>🔗 키 발급받기</a></div>",
                unsafe_allow_html=True,
            )

        st.markdown("<hr style='border-color:" + t['divider'] + ";margin:12px 0'>",
                    unsafe_allow_html=True)

        # ── 검색 모드 ──
        st.markdown(
            f"<div style='font-size:14px;font-weight:800;margin-bottom:8px;'>"
            "🎯 검색 모드</div>",
            unsafe_allow_html=True,
        )
        mode = st.radio(
            "검색 모드",
            ["🔎 빠른 검색", "🗂 키워드 DB 검색"],
            label_visibility="collapsed",
            help="빠른 검색: 단일 키워드 / DB 검색: 언어·카테고리 선택 후 대량 검색",
        )

        st.markdown("<hr style='border-color:" + t['divider'] + ";margin:12px 0'>",
                    unsafe_allow_html=True)

        pub_map = {"7일 이내": 7, "30일 이내": 30, "90일 이내": 90, "1년 이내": 365}

        if mode == "🔎 빠른 검색":
            st.markdown(
                f"<div style='font-size:14px;font-weight:800;margin-bottom:8px;'>🔍 검색 설정</div>",
                unsafe_allow_html=True,
            )
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
            search_clicked = st.button("🔍 검색 시작", type="primary", use_container_width=True)

        else:
            st.markdown(
                f"<div style='font-size:14px;font-weight:800;margin-bottom:8px;'>🗂 키워드 DB 설정</div>",
                unsafe_allow_html=True,
            )

            all_langs = get_all_languages()
            preset_500 = st.button(
                "⚡ 500+ 결과 자동 설정",
                use_container_width=True,
                help="10개 키워드 × 1페이지 = 약 500개 결과 (쿼타 1,000 소비)",
            )
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

            pages_per_kw = st.slider(
                "키워드당 페이지 수", 1, 2,
                st.session_state.get("db_pages", 1),
                help="페이지당 50개. 1페이지 권장 (쿼타 절약)",
            )
            max_results = pages_per_kw * 50
            pages_arg = pages_per_kw

            DAILY_QUOTA = 10_000
            search_quota = kw_count * pages_per_kw * 100
            detail_quota = (kw_count * max_results // 50) + kw_count
            total_quota = search_quota + detail_quota
            quota_pct = total_quota / DAILY_QUOTA * 100
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
                    f"⚠️ 예상 쿼타: **{total_quota:,}** ({quota_pct:.0f}%)  "
                    f"| 실제 **{actual_kws}개** 키워드로 제한됩니다.",
                    icon="⚠️",
                )
            else:
                st.error(
                    f"🚫 쿼타 초과 위험 ({quota_pct:.0f}%)! 자동으로 **{actual_kws}개** 키워드만 검색합니다."
                )

            published_days = st.selectbox("업로드 기간",
                ["전체", "7일 이내", "30일 이내", "90일 이내", "1년 이내"])
            pub_after = None
            if published_days in pub_map:
                dt = datetime.now(timezone.utc) - timedelta(days=pub_map[published_days])
                pub_after = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            search_clicked = st.button(
                "🚀 대량 검색 시작", type="primary",
                use_container_width=True,
                disabled=(kw_count == 0),
            )
            keyword_input = ""

        st.markdown("<hr style='border-color:" + t['divider'] + ";margin:12px 0'>",
                    unsafe_allow_html=True)

        st.markdown(
            f"<div style='font-size:14px;font-weight:800;margin-bottom:8px;'>🎬 콘텐츠 유형</div>",
            unsafe_allow_html=True,
        )
        content_type = st.radio(
            "콘텐츠 유형",
            ["전체", "🎬 롱폼만", "🩳 숏폼만"],
            horizontal=True,
            label_visibility="collapsed",
        )

        st.markdown("<hr style='border-color:" + t['divider'] + ";margin:12px 0'>",
                    unsafe_allow_html=True)

        st.markdown(
            f"<div style='font-size:14px;font-weight:800;margin-bottom:8px;'>📊 조회수 필터</div>",
            unsafe_allow_html=True,
        )
        min_views = st.number_input("최소 조회수", min_value=0, value=0, step=1000)
        max_views = st.number_input("최대 조회수", min_value=0, value=0, step=1000)

    # ── 검색 실행 ─────────────────────────────────────────────────────────────
    if search_clicked:
        valid_keys = get_valid_keys()
        if not valid_keys:
            st.error("사이드바에 YouTube API 키를 1개 이상 입력해 주세요.")
            st.stop()

        key_idx = 0
        youtube = get_client(valid_keys[key_idx])
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
            safe_limit = max(1, int(8_000 / (pages_arg * 100)))
            keywords_to_search = selected_kws[:safe_limit]
            if len(selected_kws) > safe_limit:
                st.info(
                    f"쿼타 보호: {len(selected_kws)}개 키워드 중 **{safe_limit}개**만 검색합니다.",
                    icon="🛡️",
                )

        all_ids: dict[str, str] = {}
        total = len(keywords_to_search)
        progress_bar = st.progress(0, text="검색 준비 중...")
        status_box = st.empty()
        fatal_error = None

        kw_i = 0
        while kw_i < len(keywords_to_search):
            kw = keywords_to_search[kw_i]
            status_box.markdown(
                f"🔍 **{kw_i+1}/{total}** 검색 중: `{kw}` "
                f"| 수집된 영상: **{len(all_ids)}개**"
                + (f" | 🔑 키 #{key_idx+1} 사용 중" if len(valid_keys) > 1 else "")
            )
            try:
                ids = search_ids(youtube, kw, duration_filter, sort_by,
                                 max_results, pub_after, max_pages=pages_arg)
                for vid in ids:
                    if vid not in all_ids:
                        all_ids[vid] = kw
                kw_i += 1
            except HttpError as e:
                err_info = _classify_api_error(str(e))
                if err_info["type"] == "quota":
                    # 다음 키로 전환 시도
                    next_client, next_idx = rotate_to_next_key(key_idx)
                    if next_client:
                        youtube = next_client
                        key_idx = next_idx
                        status_box.warning(
                            f"🔄 키 #{key_idx}의 쿼타 소진 → 키 #{key_idx+1}로 전환합니다.",
                            icon="⚡",
                        )
                        time.sleep(0.5)
                        # 같은 키워드를 다시 시도 (kw_i 증가 없음)
                        continue
                    else:
                        fatal_error = err_info
                        break  # 모든 키 소진
                elif err_info["stop"]:
                    fatal_error = err_info
                    break
                else:
                    kw_i += 1  # 일시 오류는 건너뜀
            except Exception as e:
                status_box.empty()
                progress_bar.empty()
                st.error(f"예상치 못한 오류: {e}")
                st.stop()

            progress_bar.progress(
                min(kw_i / total, 1.0),
                text=f"진행: {kw_i}/{total} | 수집: {len(all_ids)}개",
            )
            if total > 1:
                time.sleep(0.05)

        status_box.empty()
        progress_bar.empty()

        if fatal_error:
            if len(all_ids) == 0:
                st.error(fatal_error["msg"])
                st.stop()
            else:
                st.warning(fatal_error["msg"] +
                           f"\n\n지금까지 수집된 **{len(all_ids)}개**의 결과를 표시합니다.")

        if len(all_ids) == 0:
            st.warning("검색 결과가 없습니다. 다른 키워드나 필터를 시도해 보세요.")
            st.stop()

        with st.spinner(f"📥 {len(all_ids)}개 영상 상세정보 수집 중..."):
            try:
                rows = fetch_details(youtube, list(all_ids.keys()))
            except HttpError as e:
                err = _classify_api_error(str(e))
                st.error(err["msg"])
                st.stop()
            except Exception as e:
                st.error(f"상세정보 수집 오류: {e}")
                st.stop()

        if content_type == "🎬 롱폼만":
            rows = [r for r in rows if not r["_is_short"]]
        elif content_type == "🩳 숏폼만":
            rows = [r for r in rows if r["_is_short"]]

        if min_views > 0:
            rows = [r for r in rows if r["조회수"] >= min_views]
        if max_views > 0:
            rows = [r for r in rows if r["조회수"] <= max_views]

        grade_order = {"S": 0, "A": 1, "B": 2, "C": 3}
        rows.sort(key=lambda r: (grade_order[r["등급"]], r["업로드경과일"]))

        st.session_state.results = rows

    # ── 결과 표시 ─────────────────────────────────────────────────────────────
    with main_tab:
        rows = st.session_state.results

        if not rows:
            st.markdown(
                f"<div style='text-align:center;padding:80px 0;'>"
                "<div style='font-size:60px'>🔍</div>"
                f"<div style='font-size:18px;margin-top:16px;color:{t['sub']};line-height:1.8'>"
                "사이드바에서 API 키를 입력하고<br>"
                f"검색어 또는 키워드 DB를 선택한 후 "
                f"<b style='color:#ff0000'>검색 시작</b> 버튼을 클릭하세요</div>"
                f"<div style='display:flex;justify-content:center;gap:16px;margin-top:28px;"
                f"flex-wrap:wrap;'>"
                f"<div style='background:{GRADES['S']['bg']};border:1px solid {GRADES['S']['border']};"
                f"border-radius:12px;padding:12px 20px;text-align:center;min-width:120px;'>"
                f"<div style='font-size:22px;font-weight:900;color:{GRADES['S']['color']}'>"
                f"🏆 S급</div>"
                f"<div style='font-size:10px;color:{t['sub']};margin-top:4px'>{GRADES['S']['desc']}</div></div>"
                f"<div style='background:{GRADES['A']['bg']};border:1px solid {GRADES['A']['border']};"
                f"border-radius:12px;padding:12px 20px;text-align:center;min-width:120px;'>"
                f"<div style='font-size:22px;font-weight:900;color:{GRADES['A']['color']}'>"
                f"⭐ A급</div>"
                f"<div style='font-size:10px;color:{t['sub']};margin-top:4px'>{GRADES['A']['desc']}</div></div>"
                f"<div style='background:{GRADES['B']['bg']};border:1px solid {GRADES['B']['border']};"
                f"border-radius:12px;padding:12px 20px;text-align:center;min-width:120px;'>"
                f"<div style='font-size:22px;font-weight:900;color:{GRADES['B']['color']}'>"
                f"🌱 B급</div>"
                f"<div style='font-size:10px;color:{t['sub']};margin-top:4px'>{GRADES['B']['desc']}</div></div>"
                f"<div style='background:{GRADES['C']['bg']};border:1px solid {GRADES['C']['border']};"
                f"border-radius:12px;padding:12px 20px;text-align:center;min-width:120px;'>"
                f"<div style='font-size:22px;font-weight:900;color:{GRADES['C']['color']}'>"
                f"📺 C급</div>"
                f"<div style='font-size:10px;color:{t['sub']};margin-top:4px'>{GRADES['C']['desc']}</div></div>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            render_grade_summary(rows, t)

            total_count = len(rows)

            # 저장 + 정보 행
            save_col, info_col = st.columns([3, 7])
            with save_col:
                save_name = st.text_input(
                    "저장 이름",
                    placeholder="예: 영어 가족여행 검색",
                    label_visibility="collapsed",
                    key="save_name_input",
                )
                if st.button("💾 검색 결과 저장", use_container_width=True, type="primary"):
                    if not save_name.strip():
                        st.warning("저장 이름을 입력해 주세요.")
                    else:
                        sid = save_session(save_name.strip(), rows)
                        st.success(f"✅ '{save_name}' 저장 완료! — 📚 기록 탭에서 확인하세요.")
            with info_col:
                st.markdown(
                    f"<div style='padding:8px 12px;background:{t['card_bg']};"
                    f"border:1px solid {t['divider']};border-radius:10px;'>"
                    f"<span style='font-size:14px;color:{t['text']};font-weight:700;'>"
                    f"총 {total_count}개 영상</span> "
                    f"<span style='color:{t['sub']};font-size:13px;'>&nbsp;|&nbsp; "
                    f"등급순 정렬 (S→A→B→C) &nbsp;|&nbsp; "
                    f"이름 입력 후 저장하면 📚 기록 탭에서 언제든 다시 확인 가능</span></div>",
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            # 등급 필터
            grade_filter = st.radio(
                "등급 필터",
                ["전체", "🏆 S급", "⭐ A급", "🌱 B급", "📺 C급"],
                horizontal=True,
                label_visibility="collapsed",
            )
            grade_map = {
                "전체": None, "🏆 S급": "S", "⭐ A급": "A",
                "🌱 B급": "B", "📺 C급": "C",
            }
            filtered = [r for r in rows if grade_map[grade_filter] is None
                        or r["등급"] == grade_map[grade_filter]]

            st.markdown(
                f"<p style='color:{t['sub']};font-size:13px;margin:4px 0 12px'>"
                f"표시 중: <b style='color:{t['text']}'>{len(filtered)}개</b></p>",
                unsafe_allow_html=True,
            )

            tab1, tab2 = st.tabs(["🎬 카드 보기", "📋 테이블 보기"])

            with tab1:
                for row in filtered:
                    render_card(row, t)

            with tab2:
                df = pd.DataFrame(filtered).drop(
                    columns=["썸네일", "_channel_id", "_is_short"],
                )
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
