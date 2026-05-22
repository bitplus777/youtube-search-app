"""
유튜브 한국 여행 채널 발굴 앱
"""

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import auth
from db import (
    add_quota, delete_session, get_quota_history, get_today_quota,
    get_total_stats, list_sessions, load_session, rename_session, save_session,
)
from keywords import filter_keywords, get_all_categories, get_all_languages

load_dotenv()

DAILY_QUOTA = 10_000

# ── 등급 ──────────────────────────────────────────────────────────────────────
GRADES = {
    "S": {"label":"S급","icon":"🏆","color":"#FFD700","bg":"#1a1200","border":"#FFD700",
          "desc":"구독자 1만↓ · 7일↓ · 조회수 1만↓","badge":"background:linear-gradient(135deg,#FFD700,#FFA500);color:#000;",
          "glow":"0 0 18px rgba(255,215,0,0.35)","badge_text_color":"#000"},
    "A": {"label":"A급","icon":"⭐","color":"#00CFFF","bg":"#001520","border":"#00CFFF",
          "desc":"구독자 5만↓ · 30일↓ · 조회수 5만↓","badge":"background:linear-gradient(135deg,#00CFFF,#0090CC);color:#000;",
          "glow":"0 0 18px rgba(0,207,255,0.25)","badge_text_color":"#000"},
    "B": {"label":"B급","icon":"🌱","color":"#4CAF50","bg":"#071507","border":"#4CAF50",
          "desc":"구독자 20만↓ · 90일↓","badge":"background:linear-gradient(135deg,#4CAF50,#2E7D32);color:#fff;",
          "glow":"0 0 18px rgba(76,175,80,0.2)","badge_text_color":"#fff"},
    "C": {"label":"C급","icon":"📺","color":"#B0BEC5","bg":"#101418","border":"#546E7A",
          "desc":"대형 채널 또는 오래된 영상","badge":"background:linear-gradient(135deg,#546E7A,#37474F);color:#fff;",
          "glow":"0 0 14px rgba(84,110,122,0.35)","badge_text_color":"#fff"},
}

DURATION_FILTERS = {"전체":None,"짧은 영상 (4분 미만)":"short","중간 영상 (4~20분)":"medium","긴 영상 (20분 초과)":"long"}
SORT_OPTIONS     = {"관련성":"relevance","최신순":"date","조회수":"viewCount"}

# ── Microsoft Fluent Emoji 3D ──────────────────────────────────────────────────
_FE = "https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets"
EMOJI_3D = {
    "🔍": f"{_FE}/Magnifying%20glass%20tilted%20right/3D/magnifying_glass_tilted_right_3d.png",
    "📝": f"{_FE}/Memo/3D/memo_3d.png",
    "🗂": f"{_FE}/Card%20index%20dividers/3D/card_index_dividers_3d.png",
    "📚": f"{_FE}/Books/3D/books_3d.png",
    "👤": f"{_FE}/Bust%20in%20silhouette/3D/bust_in_silhouette_3d.png",
    "🔑": f"{_FE}/Key/3D/key_3d.png",
    "🏆": f"{_FE}/Trophy/3D/trophy_3d.png",
    "⭐": f"{_FE}/Star/3D/star_3d.png",
    "🌱": f"{_FE}/Seedling/3D/seedling_3d.png",
    "📺": f"{_FE}/Television/3D/television_3d.png",
    "💾": f"{_FE}/Floppy%20disk/3D/floppy_disk_3d.png",
    "🚀": f"{_FE}/Rocket/3D/rocket_3d.png",
    "🎬": f"{_FE}/Clapper%20board/3D/clapper_board_3d.png",
    "📊": f"{_FE}/Bar%20chart/3D/bar_chart_3d.png",
    "📅": f"{_FE}/Calendar/3D/calendar_3d.png",
    "👥": f"{_FE}/Busts%20in%20silhouette/3D/busts_in_silhouette_3d.png",
    "👍": f"{_FE}/Thumbs%20up/3D/thumbs_up_3d.png",
    "💬": f"{_FE}/Speech%20balloon/3D/speech_balloon_3d.png",
    "📂": f"{_FE}/Open%20file%20folder/3D/open_file_folder_3d.png",
    "🗑": f"{_FE}/Wastebasket/3D/wastebasket_3d.png",
    "🔒": f"{_FE}/Locked/3D/locked_3d.png",
    "✅": f"{_FE}/Check%20mark%20button/3D/check_mark_button_3d.png",
    "⚡": f"{_FE}/High%20voltage/3D/high_voltage_3d.png",
    "🎯": f"{_FE}/Direct%20hit/3D/direct_hit_3d.png",
    "🩳": f"{_FE}/Shorts/3D/shorts_3d.png",
}


def e3d(emoji: str, size: int = 22, style: str = "") -> str:
    """이모지 문자를 Microsoft Fluent Emoji 3D <img> 태그로 변환."""
    url = EMOJI_3D.get(emoji)
    if url:
        return (f'<img src="{url}" width="{size}" height="{size}" '
                f'style="vertical-align:middle;object-fit:contain;{style}" loading="lazy">')
    return emoji


# ── CSS ───────────────────────────────────────────────────────────────────────
GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');
*, *::before, *::after{box-sizing:border-box}

/* ── 전체 ── */
.stApp,.main,.block-container{
  background:#0d0d0d!important;
  color:#f0f0f0!important;
  font-family:'Noto Sans KR',sans-serif!important;
}
.block-container{padding-top:.6rem!important;max-width:1380px!important}

/* ── 사이드바 ── */
section[data-testid="stSidebar"]{
  background:#111!important;
  border-right:1px solid #1e1e1e!important;
  min-width:220px!important;
}
section[data-testid="stSidebar"] *{color:#f0f0f0!important}
section[data-testid="stSidebar"] .stButton>button{
  background:transparent!important;
  border:none!important;
  text-align:left!important;
  padding:8px 14px!important;
  font-size:13px!important;
  font-weight:500!important;
  color:#aaa!important;
  border-radius:8px!important;
  width:100%!important;
  transition:all .15s!important;
}
section[data-testid="stSidebar"] .stButton>button:hover{
  background:#1e1e1e!important;
  color:#fff!important;
}

/* ── 입력 ── */
.stTextInput input,.stSelectbox select,.stNumberInput input{
  background:#1a1a1a!important;color:#f0f0f0!important;
  border:1px solid #2a2a2a!important;border-radius:8px!important;
}
.stTextInput input:focus{border-color:#e53935!important;box-shadow:0 0 0 2px rgba(229,57,53,.15)!important}
div[data-baseweb="select"]>div{
  background:#1a1a1a!important;border:1px solid #2a2a2a!important;border-radius:8px!important;
}

/* ── 탭 ── */
.stTabs [data-baseweb="tab-list"]{
  background:#161616!important;border-bottom:2px solid #222!important;
  border-radius:10px 10px 0 0;padding:4px 4px 0;gap:4px;
}
.stTabs [data-baseweb="tab"]{
  color:#888!important;font-weight:600;font-size:13px;
  border-radius:8px 8px 0 0;padding:9px 18px!important;
}
.stTabs [aria-selected="true"]{
  color:#e53935!important;
  border-bottom:3px solid #e53935!important;
  background:rgba(229,57,53,.07)!important;
}

/* ── 빛이 버튼 위를 좌→우로 흘러가는 keyframes ── */
@keyframes fire-sweep {
  0%   { background-position: -100% center; }
  100% { background-position: 200% center; }
}

/* 주변 글로우만 살살 깜박 */
@keyframes red-glow-pulse {
  0%,100% { box-shadow:0 0 14px rgba(229,57,53,.55), 0 4px 18px rgba(229,57,53,.25); }
  50%      { box-shadow:0 0 28px rgba(229,57,53,.85), 0 4px 28px rgba(229,57,53,.45); }
}

@keyframes gold-pulse {
  0%,100% { box-shadow:0 0 12px rgba(255,215,0,.35),0 0 0 1px rgba(255,215,0,.15); }
  50%      { box-shadow:0 0 35px rgba(255,215,0,.85),0 0 70px rgba(255,165,0,.35),inset 0 0 20px rgba(255,215,0,.06); }
}
@keyframes cyan-pulse {
  0%,100% { box-shadow:0 0 12px rgba(0,207,255,.25); }
  50%      { box-shadow:0 0 30px rgba(0,207,255,.7),0 0 60px rgba(0,144,204,.3); }
}
@keyframes green-pulse {
  0%,100% { box-shadow:0 0 10px rgba(76,175,80,.2); }
  50%      { box-shadow:0 0 26px rgba(76,175,80,.6),0 0 50px rgba(46,125,50,.25); }
}

@keyframes logo-glow {
  0%,100% { text-shadow:0 0 10px rgba(229,57,53,.5); }
  50%      { text-shadow:0 0 25px rgba(229,57,53,.9),0 0 50px rgba(255,107,0,.4); }
}

@keyframes nav-dot-pulse {
  0%,100% { box-shadow:0 0 4px #e53935; }
  50%      { box-shadow:0 0 12px #e53935,0 0 24px rgba(229,57,53,.6); }
}

@keyframes nav-active-glow {
  0%,100% { box-shadow:inset 0 0 20px rgba(229,57,53,.04); }
  50%      { box-shadow:inset 0 0 30px rgba(229,57,53,.12); }
}

/* ── 기본 버튼 ── */
.stButton>button{
  border-radius:9px!important;font-weight:700!important;
  font-size:13px!important;transition:all .18s!important;
  border:1px solid #2a2a2a!important;
  position:relative!important;
}
.stButton>button[kind="primary"]{
  background: linear-gradient(
    90deg,
    #b71c1c 0%,
    #e53935 25%,
    #ff7043 44%,
    #ffe082 50%,
    #ff7043 56%,
    #e53935 75%,
    #b71c1c 100%
  )!important;
  background-size:260% 100%!important;
  color:#fff!important;border:none!important;
  font-size:15px!important;font-weight:900!important;letter-spacing:.5px!important;
  animation:fire-sweep 2.2s ease-in-out infinite,
            red-glow-pulse 2.2s ease-in-out infinite!important;
}
.stButton>button[kind="primary"]:hover{
  transform:translateY(-2px) scale(1.01)!important;
  filter:brightness(1.12)!important;
}
.stButton>button[kind="primary"]:active{
  transform:translateY(1px) scale(.99)!important;
}

/* ── 스크롤바 ── */
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:#0d0d0d}
::-webkit-scrollbar-thumb{background:#333;border-radius:3px}

/* ── 카드 ── */
.app-card{
  background:#161616;border:1px solid #222;
  border-radius:14px;padding:20px 22px;margin-bottom:14px;
  transition:border-color .2s,box-shadow .2s;
}
.app-card:hover{border-color:#333;box-shadow:0 4px 20px rgba(0,0,0,.3)}

/* ── 등급 요약 ── */
/* ── 뱀 빛 흐름 keyframes ── */
@keyframes snake-pulse {
  0%,100%{ filter:brightness(.65) saturate(.6); transform:translateY(2px) scale(.97); }
  30%    { filter:brightness(1.35) saturate(1.6); transform:translateY(-5px) scale(1.04); }
  60%    { filter:brightness(.65) saturate(.6); transform:translateY(2px) scale(.97); }
}
@keyframes snake-shine {
  0%,100%{ background-position:-200% center; }
  30%    { background-position:200% center; }
  60%,99%{ background-position:200% center; }
}

/* ── 등급 요약 ── */
.grade-box{
  border-radius:18px;
  padding:22px 14px 18px;text-align:center;
  border:2px solid;
  position:relative;overflow:hidden;
  cursor:pointer;
  transition:transform .2s,box-shadow .2s;
}
.grade-box::before{
  content:'';position:absolute;inset:0;
  background:linear-gradient(105deg,
    transparent 30%,rgba(255,255,255,.22) 50%,transparent 70%);
  background-size:250% 100%;
  animation:inherit;
  animation-name:snake-shine;
  pointer-events:none;
}
.grade-box:hover{ filter:brightness(1.18); transform:translateY(-5px); }
.grade-count{font-size:36px;font-weight:900;line-height:1}
.grade-label{font-size:15px;font-weight:900;margin-top:7px;letter-spacing:.5px}
.grade-desc{font-size:11px;opacity:.65;margin-top:4px;line-height:1.4}

/* ── 등급 박스 투명 오버레이 버튼 ── */
.gbox-btn-wrap{
  margin-top:-195px!important;   /* 박스 위로 올려서 겹침 */
  position:relative;
  z-index:20;
  height:195px;
}
.gbox-btn-wrap .stButton>button{
  height:195px!important;
  background:transparent!important;
  border:none!important;
  color:transparent!important;
  box-shadow:none!important;
  cursor:pointer!important;
  font-size:0!important;
  padding:0!important;
  border-radius:18px!important;
}
.gbox-btn-wrap .stButton>button:hover{
  background:rgba(255,255,255,.04)!important;
}
.gbox-btn-wrap .stButton>button:active{
  background:rgba(255,255,255,.09)!important;
}

/* ── 비디오 카드 ── */
.video-card{
  border-radius:14px;margin-bottom:14px;overflow:hidden;
  border:1px solid;transition:all .22s;
}
.video-card:hover{transform:translateY(-3px)}
.card-inner{display:flex;align-items:stretch}
.thumb-wrap{
  flex:0 0 240px;min-height:155px;position:relative;overflow:hidden;
  border-radius:14px 0 0 14px;background:#111;
}
.thumb-wrap img{
  width:100%;height:100%;min-height:155px;
  object-fit:cover;display:block;transition:transform .35s;
}
.video-card:hover .thumb-wrap img{transform:scale(1.06)}
.dur-badge{
  position:absolute;bottom:7px;right:7px;
  background:rgba(0,0,0,.82);color:#fff;
  font-size:11px;font-weight:700;padding:2px 7px;
  border-radius:5px;backdrop-filter:blur(3px);
}
.grade-badge{
  position:absolute;top:7px;left:7px;font-size:11px;font-weight:900;
  padding:3px 10px;border-radius:18px;box-shadow:0 2px 8px rgba(0,0,0,.5);
}
.card-info{flex:1;padding:16px 20px;display:flex;flex-direction:column;gap:7px;min-width:0}
.v-title{font-size:14px;font-weight:700;color:#f0f0f0;line-height:1.5;margin:0;word-break:break-word}
.v-title a{color:#f0f0f0;text-decoration:none}
.v-title a:hover{color:#e53935}
.ch-row{font-size:12px;color:#888;font-weight:600}
.stats-row{
  display:flex;flex-wrap:wrap;gap:12px;
  margin-top:8px;padding-top:8px;border-top:1px solid #222;
}
.stat-item{display:flex;flex-direction:column;gap:2px}
.s-label{font-size:9px;color:#666;text-transform:uppercase;letter-spacing:.8px;font-weight:700}
.s-val{font-size:14px;font-weight:800;color:#f0f0f0}
.s-val.red{color:#ff4444}.s-val.gold{color:#FFD700}
.tag-row{display:flex;gap:5px;flex-wrap:wrap;margin-top:3px}
.tag{font-size:11px;color:#666;background:#1e1e1e;border:1px solid #2a2a2a;border-radius:5px;padding:2px 9px}
.watch-btn{
  display:inline-flex;align-items:center;gap:5px;margin-top:8px;align-self:flex-start;
  background:linear-gradient(135deg,#e53935,#b71c1c);color:#fff!important;
  font-size:12px;font-weight:700;padding:7px 18px;border-radius:18px;
  text-decoration:none!important;transition:all .18s;
  box-shadow:0 3px 10px rgba(229,57,53,.3);
}
.watch-btn:hover{transform:translateY(-1px);box-shadow:0 5px 16px rgba(229,57,53,.5)}

/* ── 검색 기록 카드 ── */
.hist-card{
  background:#161616;border:1px solid #222;border-radius:14px;
  padding:16px 18px;margin-bottom:10px;transition:border-color .2s;
}
.hist-card:hover{border-color:#e53935}
.hist-name{font-size:15px;font-weight:800;color:#f0f0f0}
.hist-meta{font-size:12px;color:#666;margin-top:3px}

/* ── 마이페이지 ── */
.profile-card{
  background:linear-gradient(135deg,#1a0000 0%,#161616 100%);
  border:1px solid #2a2a2a;border-radius:16px;padding:28px 24px;
  display:flex;align-items:center;gap:20px;margin-bottom:20px;
}
.avatar{
  width:64px;height:64px;border-radius:50%;
  background:linear-gradient(135deg,#e53935,#b71c1c);
  display:flex;align-items:center;justify-content:center;
  font-size:24px;font-weight:900;color:#fff;flex-shrink:0;
}
.stat-card{
  background:#161616;border:1px solid #222;border-radius:12px;
  padding:16px 18px;text-align:center;
}
.stat-num{font-size:26px;font-weight:900;color:#e53935;line-height:1}
.stat-lbl{font-size:12px;color:#666;margin-top:4px;font-weight:600}

/* ── 쿼타 바 ── */
.quota-bar-wrap{
  background:#1a1a1a;border:1px solid #2a2a2a;border-radius:10px;padding:14px 18px;
}
.quota-bar-bg{background:#222;border-radius:6px;height:10px;margin:8px 0}
.quota-bar-fill{height:10px;border-radius:6px;transition:width .4s}

/* ── 로그인 폼 ── */
.login-wrap{
  max-width:400px;margin:60px auto;
  background:#161616;border:1px solid #2a2a2a;border-radius:18px;padding:36px 32px;
}
.login-logo{text-align:center;margin-bottom:28px}
.login-logo h1{font-size:26px;font-weight:900;color:#f0f0f0;margin:0}
.login-logo h1 span{color:#e53935}
.login-logo p{font-size:13px;color:#666;margin:6px 0 0}

/* ── 네비 섹션 헤더 ── */
.nav-section{
  font-size:10px;font-weight:800;color:#555;
  text-transform:uppercase;letter-spacing:1.2px;
  padding:16px 16px 5px;margin:0;
}

/* ── 사이드바 nav 버튼 강화 ── */
section[data-testid="stSidebar"] .stButton>button{
  background:transparent!important;
  border:none!important;
  text-align:left!important;
  padding:12px 16px!important;
  font-size:16px!important;
  font-weight:700!important;
  color:#bbb!important;
  border-radius:12px!important;
  width:100%!important;
  transition:all .18s!important;
  letter-spacing:.2px;
  line-height:1.4!important;
}
section[data-testid="stSidebar"] .stButton>button:hover{
  background:#1e1e1e!important;
  color:#fff!important;
  transform:translateX(4px)!important;
  border-left:3px solid rgba(229,57,53,.5)!important;
  padding-left:13px!important;
}

/* ── 상단 바 ── */
.topbar{
  display:flex;align-items:center;justify-content:space-between;
  padding:12px 0 16px;border-bottom:1px solid #1e1e1e;margin-bottom:20px;
}
.topbar-title{font-size:22px;font-weight:900;color:#f0f0f0}
.topbar-title span{color:#e53935}
.topbar-right{display:flex;align-items:center;gap:10px}
.quota-chip{
  background:#1a1a1a;border:1px solid #2a2a2a;border-radius:20px;
  padding:6px 16px;font-size:12px;font-weight:700;color:#aaa;
}
.quota-chip b{color:#e53935}
.user-chip{
  background:linear-gradient(135deg,#e53935,#b71c1c);
  border-radius:20px;padding:6px 16px;font-size:13px;font-weight:800;
  color:#fff;cursor:pointer;
  box-shadow:0 3px 12px rgba(229,57,53,.4);
  transition:all .2s;
}
.user-chip:hover{box-shadow:0 5px 18px rgba(229,57,53,.6);transform:translateY(-1px)}

/* ── 팝오버 ── */
div[data-testid="stPopover"] div[data-testid="stPopoverBody"]{
  background:#1a1a1a!important;
  border:1px solid #333!important;
  border-radius:12px!important;
}
div[data-testid="stPopover"] div[data-testid="stPopoverBody"] .stButton>button{
  background:transparent!important;
  border:none!important;
  text-align:left!important;
  color:#ddd!important;
  font-size:14px!important;
  border-radius:8px!important;
  width:100%!important;
}
div[data-testid="stPopover"] div[data-testid="stPopoverBody"] .stButton>button:hover{
  background:#252525!important;
  color:#fff!important;
}
</style>
"""


# ── 유틸 ──────────────────────────────────────────────────────────────────────
def fmt(n: int) -> str:
    if n >= 100_000_000: return f"{n/100_000_000:.1f}억"
    if n >= 10_000:      return f"{n/10_000:.1f}만"
    return f"{n:,}"


def parse_duration(d: str) -> str:
    if not d: return ""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d)
    if not m: return d
    h, mi, s = (int(g or 0) for g in m.groups())
    return f"{h}:{mi:02d}:{s:02d}" if h else f"{mi}:{s:02d}"


def duration_seconds(d: str) -> int:
    if not d: return 0
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d)
    if not m: return 0
    h, mi, s = (int(g or 0) for g in m.groups())
    return h*3600 + mi*60 + s


def is_shorts(raw: str, title: str) -> bool:
    s = duration_seconds(raw)
    tl = title.lower()
    return (0 < s <= 60) or "#shorts" in tl or "#short" in tl


def days_ago(pub: str) -> int:
    try:
        dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 9999


def grade(subs: int, views: int, d: int) -> str:
    if subs < 10_000 and views < 10_000 and d <= 7:  return "S"
    if subs < 50_000 and views < 50_000 and d <= 30: return "A"
    if subs < 200_000 and d <= 90:                   return "B"
    return "C"


# ── API 키 ────────────────────────────────────────────────────────────────────
def _classify(err: str) -> dict:
    e = err.lower()
    if "quotaexceeded" in e or "dailylimitexceeded" in e:
        return {"type":"quota","stop":True,"msg":"🚫 API 할당량이 소진되었습니다. 다른 키로 자동 전환을 시도합니다."}
    if "keyinvalid" in e or "api key not valid" in e:
        return {"type":"key_invalid","stop":True,"msg":"❌ API 키가 올바르지 않습니다."}
    if "accessnotconfigured" in e:
        return {"type":"not_configured","stop":True,
                "msg":"❌ YouTube Data API v3가 비활성화 상태입니다. [Google Cloud Console](https://console.cloud.google.com/apis/library/youtube.googleapis.com)에서 활성화해 주세요."}
    return {"type":"other","stop":False,"msg":f"오류: {err[:80]}"}


def get_valid_keys() -> list[str]:
    saved = auth.load_api_keys()
    env_k = os.getenv("YOUTUBE_API_KEY","").strip()
    try:
        sec_k = st.secrets.get("YOUTUBE_API_KEY","").strip()
    except Exception:
        sec_k = ""
    manual = [k.strip() for k in st.session_state.get("api_keys_raw", saved) if k.strip()]
    seen, out = set(), []
    for k in ([env_k, sec_k] + manual):
        if k and k not in seen:
            seen.add(k); out.append(k)
    return out


def make_client(key: str):
    try: return build("youtube","v3",developerKey=key)
    except Exception: return None


def rotate(idx: int):
    keys = get_valid_keys()
    ni = idx + 1
    if ni < len(keys):
        c = make_client(keys[ni])
        if c: return c, ni
    return None, -1


# ── YouTube API ───────────────────────────────────────────────────────────────
def search_ids(yt, kw, dur_filter, sort, max_res, pub_after=None, max_pages=1):
    base = {"part":"snippet","q":kw,"type":"video",
            "order":SORT_OPTIONS.get(sort,"relevance"),"maxResults":50}
    if pub_after: base["publishedAfter"] = pub_after
    d = DURATION_FILTERS.get(dur_filter)
    if d: base["videoDuration"] = d
    ids, tok = [], None
    for _ in range(max(1, max_pages)):
        p = dict(base)
        if tok: p["pageToken"] = tok
        resp = yt.search().list(**p).execute()
        ids += [i["id"]["videoId"] for i in resp.get("items",[])]
        tok = resp.get("nextPageToken")
        if not tok or len(ids) >= max_res: break
    # 쿼타 로깅: search.list = 100 units/call
    add_quota(100 * min(max_pages, (len(ids)//50)+1), 1)
    return ids[:max_res]


def fetch_subs(yt, ch_ids):
    res = {}
    for i in range(0, len(ch_ids), 50):
        chunk = ch_ids[i:i+50]
        try:
            resp = yt.channels().list(part="statistics", id=",".join(chunk)).execute()
            for item in resp.get("items",[]):
                s = item.get("statistics",{}).get("subscriberCount")
                res[item["id"]] = int(s) if s else 0
            add_quota(1, 1)
        except Exception:
            pass
    return res


def fetch_details(yt, video_ids):
    if not video_ids: return []
    raw, ch_ids, quota_hit = [], [], False
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        try:
            resp = yt.videos().list(
                part="snippet,statistics,contentDetails", id=",".join(chunk)).execute()
            add_quota(1, 1)
        except HttpError as e:
            if "quotaExceeded" in str(e): quota_hit = True; break
            raise
        for item in resp.get("items",[]):
            raw.append(item)
            cid = item["snippet"].get("channelId","")
            if cid and cid not in ch_ids: ch_ids.append(cid)
    if quota_hit and raw:
        st.warning(f"⚠️ 쿼타 초과로 {len(raw)}개까지만 가져왔습니다.")
    subs = fetch_subs(yt, ch_ids)
    rows = []
    for item in raw:
        sn = item["snippet"]
        st_ = item.get("statistics",{})
        cd = item.get("contentDetails",{})
        vid = item["id"]
        pub = sn.get("publishedAt","")
        sub_n = subs.get(sn.get("channelId",""),0)
        views = int(st_.get("viewCount",0))
        d = days_ago(pub)
        raw_dur = cd.get("duration","")
        title = sn.get("title","")
        short = is_shorts(raw_dur, title)
        url = (f"https://www.youtube.com/shorts/{vid}" if short
               else f"https://www.youtube.com/watch?v={vid}")
        rows.append({
            "등급": grade(sub_n, views, d),
            "콘텐츠유형": "🩳 숏폼" if short else "🎬 롱폼",
            "제목": title, "채널명": sn.get("channelTitle",""),
            "구독자수": sub_n, "URL": url,
            "업로드일": pub[:10], "업로드경과일": d,
            "조회수": views,
            "좋아요": int(st_.get("likeCount",0)),
            "댓글수": int(st_.get("commentCount",0)),
            "재생시간": parse_duration(raw_dur),
            "썸네일": (sn.get("thumbnails",{}).get("high",{}).get("url","")
                      or sn.get("thumbnails",{}).get("medium",{}).get("url","")),
            "_is_short": short, "_channel_id": sn.get("channelId",""), "_search_kw":"",
        })
    return rows


# ── 렌더링 ────────────────────────────────────────────────────────────────────
def _video_id(url: str) -> str:
    """URL에서 YouTube 영상 ID 추출"""
    if "shorts/" in url:
        return url.split("shorts/")[-1].split("?")[0]
    if "v=" in url:
        return url.split("v=")[-1].split("&")[0]
    return url.split("/")[-1].split("?")[0]

def render_card(row):
    g = GRADES[row["등급"]]
    short = row.get("_is_short", False)

    # 항상 video ID 로 직접 URL 조합 (API 썸네일 필드가 비어도 작동)
    vid_id = _video_id(row.get("URL", ""))
    thumb_api = row.get("썸네일", "")
    thumb = thumb_api or (f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg" if vid_id else "")
    # maxresdefault → hqdefault 순서로 fallback
    fallback_src = f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"

    ts = "width:100%;height:100%;object-fit:cover;display:block;" + ("aspect-ratio:9/16;" if short else "")
    th = (
        f'<img src="{thumb}" alt="" style="{ts}"'
        f' onerror="this.onerror=null;this.src=\'{fallback_src}\'">'
        if thumb else
        '<div style="background:#1a1a1a;width:100%;height:160px;display:flex;'
        'align-items:center;justify-content:center;font-size:40px;">🎬</div>'
    )
    cb = "background:#FF0076;color:#fff;" if short else "background:#1a73e8;color:#fff;"
    cl = "🩳 숏폼" if short else "🎬 롱폼"
    g_icon = e3d(g["icon"], size=16)
    tv_icon = e3d("📺", size=14)
    subs_icon = e3d("👥", size=15)
    like_icon = e3d("👍", size=15)
    chat_icon = e3d("💬", size=15)
    cal_icon  = e3d("📅", size=13)
    short_icon = e3d("🩳", size=14) if short else e3d("🎬", size=14)

    st.markdown(f"""
<div class="video-card" style="border-color:{g['border']};background:{g['bg']};box-shadow:{g['glow']}">
  <div class="card-inner">
    <div class="thumb-wrap">
      {th}
      <span class="grade-badge" style="{g['badge']}">{g_icon} <b style='color:{g['badge_text_color']}'>{g['label']}</b></span>
      <span class="dur-badge" style="{cb};position:absolute;bottom:7px;left:7px;
        font-size:11px;font-weight:700;padding:3px 8px;border-radius:5px;
        display:flex;align-items:center;gap:4px;">{short_icon}{cl}</span>
      <span class="dur-badge">{row['재생시간']}</span>
    </div>
    <div class="card-info">
      <p class="v-title"><a href="{row['URL']}" target="_blank">{row['제목']}</a></p>
      <div class="ch-row" style="display:flex;align-items:center;gap:5px;">{tv_icon} {row['채널명']}</div>
      <div class="stats-row">
        <div class="stat-item">
          <span class="s-label">구독자</span>
          <span class="s-val gold" style="display:flex;align-items:center;gap:4px;">{subs_icon} {fmt(row['구독자수'])}</span>
        </div>
        <div class="stat-item">
          <span class="s-label">조회수</span>
          <span class="s-val red">▶ {fmt(row['조회수'])}</span>
        </div>
        <div class="stat-item">
          <span class="s-label">좋아요</span>
          <span class="s-val" style="display:flex;align-items:center;gap:4px;">{like_icon} {fmt(row['좋아요'])}</span>
        </div>
        <div class="stat-item">
          <span class="s-label">댓글</span>
          <span class="s-val" style="display:flex;align-items:center;gap:4px;">{chat_icon} {fmt(row['댓글수'])}</span>
        </div>
        <div class="stat-item">
          <span class="s-label">업로드 후</span>
          <span class="s-val" style="display:flex;align-items:center;gap:4px;">{cal_icon} {row['업로드경과일']}일</span>
        </div>
      </div>
      <div class="tag-row">
        <span class="tag">{cal_icon} {row['업로드일']}</span>
        <span class="tag">⏱ {row['재생시간']}</span>
      </div>
      <a class="watch-btn" href="{row['URL']}" target="_blank">▶ 영상 보기</a>
    </div>
  </div>
</div>""", unsafe_allow_html=True)


# S→A→B→C 순서로 빛이 흘러가는 딜레이 (사이클 2.8s, 간격 0.7s)
_SNAKE_CYCLE  = "2.8s"
_SNAKE_DELAYS = {"S": "0s", "A": "0.7s", "B": "1.4s", "C": "2.1s"}
_GRADE_LABEL  = {"S":"🏆 S급","A":"⭐ A급","B":"🌱 B급","C":"📺 C급"}

def render_grade_summary(rows):
    counts  = {g: sum(1 for r in rows if r["등급"]==g) for g in "SABC"}
    cur     = st.session_state.get("gf", "전체")   # 현재 선택된 필터

    # 4열 그리드로 배치
    cols = st.columns(4, gap="small")
    for col, (g, cfg) in zip(cols, GRADES.items()):
        with col:
            is_sel   = (cur == _GRADE_LABEL[g])
            icon_img = e3d(cfg["icon"], size=44)
            delay    = _SNAKE_DELAYS[g]
            anim     = f"snake-pulse {_SNAKE_CYCLE} ease-in-out {delay} infinite"
            sel_ring = (f"outline:3px solid {cfg['color']};"
                        f"outline-offset:3px;"
                        f"box-shadow:0 0 24px {cfg['color']}66;" if is_sel else "")

            # ── 시각적 박스 (HTML) ──
            st.markdown(
                f'<div class="grade-box" style="'
                f'border-color:{cfg["border"]};background:{cfg["bg"]};'
                f'animation:{anim};{sel_ring}cursor:pointer;">'
                f'<div style="line-height:1;margin-bottom:8px;'
                f'filter:drop-shadow(0 0 8px {cfg["color"]}88);">{icon_img}</div>'
                f'<div class="grade-count" style="color:{cfg["color"]}">{counts[g]}</div>'
                f'<div class="grade-label" style="color:{cfg["color"]}">{cfg["label"]}</div>'
                f'<div class="grade-desc">{cfg["desc"]}</div>'
                f'{"<div style=\'font-size:11px;margin-top:6px;color:"+cfg["color"]+";font-weight:900;\'>✓ 선택됨</div>" if is_sel else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )

            # ── 투명 오버레이 버튼 (클릭 감지) ──
            # CSS 로 박스 위로 끌어 올려 겹치게 함
            st.markdown(
                f'<div class="gbox-btn-wrap" data-g="{g}">',
                unsafe_allow_html=True,
            )
            clicked = st.button("　", key=f"gb_{g}",
                                use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

            if clicked:
                # 이미 선택된 등급 클릭 → 전체로 해제
                st.session_state.gf = ("전체" if is_sel
                                       else _GRADE_LABEL[g])
                st.rerun()


# ── 페이지: 로그인 ─────────────────────────────────────────────────────────────
def page_login():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.markdown("""
<div class="login-wrap">
  <div class="login-logo">
    <h1>🔍 채널 <span>발굴기</span></h1>
    <p>한국 여행 채널 분석 · 등급 분류 · 기록 관리</p>
  </div>
</div>""", unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if not auth.has_users():
            st.info("처음 사용하시나요? 아래에서 계정을 만들어 시작하세요.", icon="👋")
            tab_login, tab_reg = st.tabs(["🔑 로그인", "📝 회원가입"])
        else:
            tab_login, tab_reg = st.tabs(["🔑 로그인", "📝 회원가입"])

        with tab_login:
            with st.form("login_form"):
                u = st.text_input("사용자명", placeholder="username")
                p = st.text_input("비밀번호", type="password", placeholder="••••••••")
                ok = st.form_submit_button("로그인", type="primary", use_container_width=True)
            if ok:
                if auth.verify(u, p):
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.rerun()
                else:
                    st.error("사용자명 또는 비밀번호가 틀렸습니다.")

        with tab_reg:
            with st.form("reg_form"):
                nu = st.text_input("사용자명", placeholder="원하는 사용자명", key="reg_u")
                np = st.text_input("비밀번호", type="password", placeholder="••••••••", key="reg_p")
                np2 = st.text_input("비밀번호 확인", type="password", placeholder="••••••••", key="reg_p2")
                ok2 = st.form_submit_button("계정 만들기", type="primary", use_container_width=True)
            if ok2:
                if np != np2:
                    st.error("비밀번호가 일치하지 않습니다.")
                else:
                    ok3, msg = auth.register(nu, np)
                    if ok3:
                        st.success(msg + " 이제 로그인해 주세요.")
                    else:
                        st.error(msg)


# ── 사이드바 내비 ──────────────────────────────────────────────────────────────
def render_sidebar(username: str):
    with st.sidebar:
        search_3d = e3d("🔍", size=26)
        # ── 로고 ──
        st.markdown(
            "<div style='padding:22px 16px 14px;'>"
            f"<div style='font-size:28px;font-weight:900;color:#f0f0f0;letter-spacing:-.5px;"
            f"display:flex;align-items:center;gap:10px;line-height:1.2;'>"
            f"{search_3d}"
            f"채널 <span style='color:#e53935;animation:logo-glow 2s ease-in-out infinite;"
            f"text-shadow:0 0 14px rgba(229,57,53,.7);'>발굴기</span></div>"
            "<div style='font-size:12px;color:#555;margin-top:6px;letter-spacing:2px;"
            "font-weight:800;text-transform:uppercase;'>YOUTUBE CHANNEL FINDER</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='height:1px;background:linear-gradient(90deg,#e53935,#333,transparent);"
            "margin:0 0 8px;box-shadow:0 0 8px rgba(229,57,53,.4);'></div>",
            unsafe_allow_html=True,
        )

        page = st.session_state.get("page", "search")

        def nav(label: str, pg: str, icon: str):
            is_act = page == pg
            icon_img = e3d(icon, size=28)   # 3D 아이콘 크게

            if is_act:
                # 활성: HTML 블록 (빨간 배경 + 글로우)
                st.markdown(
                    f"<div style='"
                    f"background:linear-gradient(90deg,rgba(229,57,53,.25),rgba(229,57,53,.05));"
                    f"border-left:4px solid #e53935;border-radius:0 14px 14px 0;"
                    f"padding:13px 16px;margin:3px 4px 3px 0;"
                    f"display:flex;align-items:center;gap:12px;"
                    f"animation:nav-active-glow 2s ease-in-out infinite;'>"
                    f"<div style='flex-shrink:0;filter:drop-shadow(0 0 6px rgba(229,57,53,.7));'>"
                    f"{icon_img}</div>"
                    f"<span style='font-size:17px;font-weight:900;color:#fff;letter-spacing:.3px;'>"
                    f"{label}</span>"
                    f"<span style='margin-left:auto;width:9px;height:9px;border-radius:50%;"
                    f"background:#e53935;flex-shrink:0;"
                    f"animation:nav-dot-pulse 1.4s ease-in-out infinite;"
                    f"box-shadow:0 0 10px #e53935;'></span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                # 비활성: 3D 아이콘 + 큰 버튼 텍스트
                c_icon, c_btn = st.columns([1, 5])
                with c_icon:
                    st.markdown(
                        f"<div style='display:flex;align-items:center;justify-content:center;"
                        f"height:100%;padding:6px 0 4px;'>"
                        f"<div style='filter:drop-shadow(0 2px 4px rgba(0,0,0,.5));'>"
                        f"{icon_img}</div></div>",
                        unsafe_allow_html=True,
                    )
                with c_btn:
                    if st.button(label, key=f"nav_{pg}", use_container_width=True):
                        st.session_state.page = pg
                        st.rerun()

        def section_header(text: str, color: str):
            st.markdown(
                f"<div style='font-size:13px;font-weight:900;color:{color};"
                f"letter-spacing:1.5px;padding:20px 16px 8px;"
                f"opacity:1;border-top:1px solid rgba(255,255,255,.06);"
                f"margin-top:6px;text-shadow:0 0 10px {color}55;'>"
                f"{text}</div>",
                unsafe_allow_html=True,
            )

        # ── 채널 발굴 ──
        section_header("🔥 채널 발굴", "#e53935")
        nav("빠른 검색",      "search",    "🔎")
        nav("나만의 키워드",  "custom_kw", "📝")
        nav("키워드 DB 검색", "db_search", "🗂")

        # ── 기록 ──
        section_header("📁 기록 & 관리", "#00CFFF")
        nav("저장된 검색 기록", "history", "📚")

        # ── 설정 ──
        section_header("⚙️ 계정 & 설정", "#4CAF50")
        nav("마이페이지",  "mypage",  "👤")
        nav("API 키 관리", "apikeys", "🔑")

        # ── 하단 구분선 ──
        st.markdown(
            "<div style='height:1px;background:linear-gradient(90deg,transparent,#333,transparent);"
            "margin:12px 0 8px;'></div>",
            unsafe_allow_html=True,
        )

        # 하단 쿼타 미니 표시
        q = get_today_quota()
        used = q["units"]
        pct = min(used / DAILY_QUOTA * 100, 100)
        bar_color = "#e53935" if pct > 80 else "#FFD700" if pct > 50 else "#4CAF50"
        st.markdown(
            f"<div style='padding:8px 16px 14px;'>"
            f"<div style='font-size:13px;color:#888;font-weight:900;text-transform:uppercase;"
            f"letter-spacing:1.5px;margin-bottom:7px;'>⚡ 오늘 API 쿼타</div>"
            f"<div style='display:flex;justify-content:space-between;font-size:14px;"
            f"font-weight:800;margin-bottom:6px;'>"
            f"<span style='color:{bar_color};'>{used:,}</span>"
            f"<span style='color:#333;'>{DAILY_QUOTA:,}</span></div>"
            f"<div style='background:#1a1a1a;border-radius:5px;height:6px;'>"
            f"<div style='width:{pct:.1f}%;height:6px;border-radius:5px;"
            f"background:linear-gradient(90deg,{bar_color},{'#ff6b6b' if bar_color=='#e53935' else bar_color});'></div></div>"
            f"</div>",
            unsafe_allow_html=True,
        )


# ── 상단 바 ───────────────────────────────────────────────────────────────────
def render_topbar(title: str, username: str):
    q = get_today_quota()
    used = q["units"]
    remaining = DAILY_QUOTA - used
    pct = min(used / DAILY_QUOTA * 100, 100)
    chip_color = "#e53935" if pct > 80 else "#FFD700" if pct > 50 else "#4CAF50"
    initials = username[:2].upper() if username else "?"
    person_icon = e3d("👤", size=16)
    key_icon    = e3d("🔑", size=15)
    chart_icon  = e3d("📊", size=15)

    tb_left, tb_right = st.columns([6, 4])
    with tb_left:
        st.markdown(
            f"<div style='padding:10px 0 14px;border-bottom:1px solid #1e1e1e;'>"
            f"<div style='font-size:21px;font-weight:900;color:#f0f0f0;'>{title}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with tb_right:
        st.markdown("<div style='padding:6px 0 0;'>", unsafe_allow_html=True)
        rc1, rc2 = st.columns([5, 3])
        with rc1:
            st.markdown(
                f"<div style='background:#1a1a1a;border:1px solid #2a2a2a;border-radius:20px;"
                f"padding:7px 14px;font-size:12px;font-weight:700;color:#aaa;"
                f"display:flex;align-items:center;gap:6px;white-space:nowrap;'>"
                f"{chart_icon} 쿼타 <b style='color:{chip_color}'>{used:,}</b>"
                f"<span style='color:#4CAF50;'>(잔여 {remaining:,})</span></div>",
                unsafe_allow_html=True,
            )
        with rc2:
            with st.popover(
                f"👤 {username}",
                use_container_width=True,
            ):
                st.markdown(
                    f"<div style='padding:4px 0 10px;'>"
                    f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:12px;"
                    f"padding-bottom:10px;border-bottom:1px solid #2a2a2a;'>"
                    f"<div style='width:40px;height:40px;border-radius:50%;"
                    f"background:linear-gradient(135deg,#e53935,#b71c1c);"
                    f"display:flex;align-items:center;justify-content:center;"
                    f"font-size:16px;font-weight:900;color:#fff;flex-shrink:0;'>{initials}</div>"
                    f"<div><div style='font-size:14px;font-weight:800;color:#f0f0f0;'>{username}</div>"
                    f"<div style='font-size:11px;color:#555;'>로그인됨</div></div></div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if st.button(f"{person_icon} 마이페이지", use_container_width=True,
                             key="pop_mypage"):
                    st.session_state.page = "mypage"; st.rerun()
                if st.button(f"{key_icon} API 키 관리", use_container_width=True,
                             key="pop_apikeys"):
                    st.session_state.page = "apikeys"; st.rerun()
                st.markdown("<hr style='border-color:#2a2a2a;margin:6px 0'>", unsafe_allow_html=True)
                if st.button("🚪 로그아웃", use_container_width=True, key="pop_logout"):
                    st.session_state.logged_in = False
                    st.session_state.username = ""
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div style='border-bottom:1px solid #1e1e1e;margin-bottom:18px;'></div>",
                unsafe_allow_html=True)


# ── 페이지: 검색 (공통 결과 표시) ─────────────────────────────────────────────
def _run_search(youtube, keywords_to_search, dur_filter, sort, max_res,
                pub_after, pages_arg, mode_label):
    all_ids: dict[str, str] = {}
    total = len(keywords_to_search)
    prog = st.progress(0, text="검색 준비 중...")
    status = st.empty()
    fatal = None
    key_idx = 0
    keys = get_valid_keys()
    kw_i = 0

    while kw_i < len(keywords_to_search):
        kw = keywords_to_search[kw_i]
        status.markdown(
            f"🔍 **{kw_i+1}/{total}** : `{kw}` | 수집 **{len(all_ids)}개**"
            + (f" | 🔑 키#{key_idx+1}" if len(keys)>1 else "")
        )
        try:
            ids = search_ids(youtube, kw, dur_filter, sort, max_res, pub_after, pages_arg)
            for vid in ids:
                if vid not in all_ids: all_ids[vid] = kw
            kw_i += 1
        except HttpError as e:
            info = _classify(str(e))
            if info["type"] == "quota":
                nc, ni = rotate(key_idx)
                if nc:
                    youtube = nc; key_idx = ni
                    status.warning(f"🔄 키#{key_idx} 소진 → 키#{key_idx+1}로 전환", icon="⚡")
                    time.sleep(0.3); continue
                else:
                    fatal = info; break
            elif info["stop"]:
                fatal = info; break
            else:
                kw_i += 1
        except Exception as e:
            status.empty(); prog.empty()
            st.error(f"예상치 못한 오류: {e}"); st.stop()

        prog.progress(min(kw_i/total,1.0), text=f"진행: {kw_i}/{total} | 수집: {len(all_ids)}개")
        if total > 1: time.sleep(0.05)

    status.empty(); prog.empty()
    return all_ids, fatal, youtube


def page_search(mode: str):
    username = st.session_state.get("username","")
    render_topbar("🔎 채널 발굴 검색", username)

    pub_map = {"7일 이내":7,"30일 이내":30,"90일 이내":90,"1년 이내":365}

    # ── 사이드바 검색 옵션 ──
    with st.sidebar:
        st.markdown("<hr style='border-color:#1e1e1e;margin:4px 0 10px'>", unsafe_allow_html=True)
        st.markdown(
            "<div style='font-size:12px;font-weight:800;color:#666;"
            "text-transform:uppercase;letter-spacing:.8px;padding:0 14px 6px;'>검색 설정</div>",
            unsafe_allow_html=True,
        )

        if mode == "search":
            kw_input = st.text_input("검색어", placeholder="korea hiking vlog", key="sq_kw")
            dur_filter = st.selectbox("영상 길이", list(DURATION_FILTERS.keys()), key="sq_dur")
            sort_by = st.selectbox("정렬", list(SORT_OPTIONS.keys()), key="sq_sort")
            pages = st.slider("페이지 수", 1, 4, 2, key="sq_pg",
                              help="1페이지=50개, 4페이지=200개")
            max_results = pages * 50
            pages_arg = pages
            pub_days = st.selectbox("업로드 기간",
                ["전체","7일 이내","30일 이내","90일 이내","1년 이내"], key="sq_pub")
            pub_after = None
            if pub_days in pub_map:
                dt = datetime.now(timezone.utc) - timedelta(days=pub_map[pub_days])
                pub_after = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            search_clicked = st.button("🔍 검색 시작", type="primary",
                                       use_container_width=True, key="sq_btn")
            keywords_to_search = [kw_input.strip()] if kw_input.strip() else []

        elif mode == "custom_kw":
            with st.form("ck_form", clear_on_submit=True):
                new_kw = st.text_input("키워드 입력", placeholder="vlog in korea",
                                       label_visibility="collapsed", key="ck_input")
                submitted = st.form_submit_button("➕ 키워드 추가", use_container_width=True)
            if submitted:
                kw_c = new_kw.strip()
                if kw_c and kw_c not in st.session_state.my_keywords:
                    st.session_state.my_keywords.append(kw_c)
                st.rerun()

            my_kws = st.session_state.my_keywords
            for i, kw_item in enumerate(my_kws):
                r1, r2 = st.columns([8,1])
                with r1:
                    st.markdown(
                        f"<div style='background:#1a1a1a;border:1px solid #2a2a2a;"
                        f"border-radius:7px;padding:5px 11px;font-size:12px;font-weight:600;"
                        f"color:#ddd;margin-bottom:3px;overflow:hidden;text-overflow:ellipsis;"
                        f"white-space:nowrap;' title='{kw_item}'>🔖 {kw_item}</div>",
                        unsafe_allow_html=True)
                with r2:
                    if st.button("✕", key=f"ck_del_{i}", use_container_width=True):
                        st.session_state.my_keywords.pop(i); st.rerun()

            if my_kws and st.button("🗑 전체 삭제", use_container_width=True, key="ck_clr"):
                st.session_state.my_keywords = []; st.rerun()

            dur_filter = st.selectbox("영상 길이", list(DURATION_FILTERS.keys()), key="ck_dur")
            sort_by = st.selectbox("정렬", list(SORT_OPTIONS.keys()), key="ck_sort")
            pages = st.slider("키워드당 페이지", 1, 4, 1, key="ck_pg")
            max_results = pages * 50
            pages_arg = pages
            pub_days = st.selectbox("업로드 기간",
                ["전체","7일 이내","30일 이내","90일 이내","1년 이내"], key="ck_pub")
            pub_after = None
            if pub_days in pub_map:
                dt = datetime.now(timezone.utc) - timedelta(days=pub_map[pub_days])
                pub_after = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            keywords_to_search = list(st.session_state.my_keywords)
            if keywords_to_search:
                est = len(keywords_to_search) * max_results
                st.markdown(
                    f"<div style='background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;"
                    f"padding:8px 12px;font-size:12px;color:#888;margin:4px 0'>"
                    f"🔍 <b style='color:#f0f0f0'>{len(keywords_to_search)}</b>개 키워드 → "
                    f"최대 <b style='color:#e53935'>~{est}</b>개</div>",
                    unsafe_allow_html=True)
            search_clicked = st.button("🚀 검색 시작", type="primary",
                                       use_container_width=True, key="ck_btn",
                                       disabled=(len(keywords_to_search)==0))

        else:  # db_search
            all_langs = get_all_languages()
            if st.button("⚡ 500+ 자동 설정", use_container_width=True, key="db_preset"):
                st.session_state["db_langs"] = ["🇺🇸 English","🇯🇵 日本語","🇨🇳 中文"]
                st.session_state["db_cats"] = ["가족여행","특수여행유형","K-Food"]
                st.session_state["db_pages"] = 1; st.rerun()

            sel_langs = st.multiselect("언어", all_langs,
                default=st.session_state.get("db_langs",["🇺🇸 English","🇯🇵 日本語","🇨🇳 中文"]),
                key="db_langs_sel")
            sel_cats = st.multiselect("카테고리", get_all_categories(),
                default=st.session_state.get("db_cats",["가족여행","특수여행유형"]),
                key="db_cats_sel")
            selected_kws = filter_keywords(sel_langs or None, sel_cats or None)
            kw_count = len(selected_kws)

            dur_filter = st.selectbox("영상 길이", list(DURATION_FILTERS.keys()), key="db_dur")
            sort_by    = st.selectbox("정렬", list(SORT_OPTIONS.keys()), key="db_sort")
            pages_per_kw = st.slider("키워드당 페이지", 1, 2,
                st.session_state.get("db_pages",1), key="db_pg")
            max_results = pages_per_kw * 50; pages_arg = pages_per_kw

            DAILY_QUOTA_LOCAL = 10_000
            est_quota = kw_count * pages_per_kw * 100 + (kw_count * max_results // 50)
            safe_limit = max(1, int(8_000 / (pages_per_kw * 100)))
            actual_kws = min(kw_count, safe_limit)
            pct = est_quota / DAILY_QUOTA_LOCAL * 100
            color = "#4CAF50" if pct<=50 else "#FFD700" if pct<=80 else "#e53935"
            st.markdown(
                f"<div style='background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;"
                f"padding:8px 12px;font-size:12px;color:#888;margin:4px 0'>"
                f"키워드 <b style='color:#f0f0f0'>{actual_kws}</b>개 | 쿼타 "
                f"<b style='color:{color}'>{est_quota:,}</b> ({pct:.0f}%) | "
                f"예상 결과 <b style='color:#e53935'>~{actual_kws*max_results:,}</b>개</div>",
                unsafe_allow_html=True)

            pub_days = st.selectbox("업로드 기간",
                ["전체","7일 이내","30일 이내","90일 이내","1년 이내"], key="db_pub")
            pub_after = None
            if pub_days in pub_map:
                dt = datetime.now(timezone.utc) - timedelta(days=pub_map[pub_days])
                pub_after = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            keywords_to_search = selected_kws[:safe_limit]
            search_clicked = st.button("🚀 대량 검색 시작", type="primary",
                                       use_container_width=True, key="db_btn",
                                       disabled=(kw_count==0))

        st.markdown("<hr style='border-color:#1e1e1e;margin:8px 0'>", unsafe_allow_html=True)
        content_type = st.radio("콘텐츠", ["전체","🎬 롱폼만","🩳 숏폼만"],
                                horizontal=True, label_visibility="collapsed", key="ct_radio")
        min_v = st.number_input("최소 조회수", 0, value=0, step=1000, key="min_v")
        max_v = st.number_input("최대 조회수", 0, value=0, step=1000, key="max_v")

    # ── 검색 실행 ──
    if search_clicked:
        valid_keys = get_valid_keys()
        if not valid_keys:
            st.error("🔑 API 키를 먼저 등록해 주세요. (사이드바 → API 키 관리)")
            st.stop()
        if not keywords_to_search:
            st.warning("검색어를 입력해 주세요."); st.stop()

        youtube = make_client(valid_keys[0])
        if not youtube:
            st.error("API 키가 유효하지 않습니다."); st.stop()

        all_ids, fatal, youtube = _run_search(
            youtube, keywords_to_search, dur_filter, sort_by,
            max_results, pub_after, pages_arg, mode)

        if fatal:
            if not all_ids: st.error(fatal["msg"]); st.stop()
            else: st.warning(fatal["msg"])

        if not all_ids:
            st.warning("검색 결과가 없습니다."); st.stop()

        with st.spinner(f"📥 {len(all_ids)}개 영상 상세정보 수집 중..."):
            try:
                rows = fetch_details(youtube, list(all_ids.keys()))
                for r in rows:
                    r["_search_kw"] = all_ids.get(
                        r["URL"].split("v=")[-1] if "v=" in r["URL"] else r["URL"].split("/")[-1], "")
            except HttpError as e:
                st.error(_classify(str(e))["msg"]); st.stop()
            except Exception as e:
                st.error(f"상세정보 수집 오류: {e}"); st.stop()

        if content_type == "🎬 롱폼만": rows = [r for r in rows if not r["_is_short"]]
        elif content_type == "🩳 숏폼만": rows = [r for r in rows if r["_is_short"]]
        if min_v > 0: rows = [r for r in rows if r["조회수"] >= min_v]
        if max_v > 0: rows = [r for r in rows if r["조회수"] <= max_v]

        go = {"S":0,"A":1,"B":2,"C":3}
        rows.sort(key=lambda r: (go[r["등급"]], r["업로드경과일"]))
        st.session_state.results = rows

        kw_stat: dict[str,int] = {}
        for r in rows:
            k = r.get("_search_kw","기타")
            kw_stat[k] = kw_stat.get(k,0) + 1
        st.session_state["last_kw_stats"] = kw_stat

    # ── 결과 표시 ──
    rows = st.session_state.get("results", [])

    if not rows:
        st.markdown(
            "<div style='text-align:center;padding:70px 0;'>"
            "<div style='font-size:56px'>🔍</div>"
            "<div style='font-size:16px;color:#555;margin-top:14px;line-height:1.8;'>"
            "사이드바에서 검색 설정 후<br>"
            "<b style='color:#e53935'>검색 시작</b> 버튼을 클릭하세요</div>"
            "<div style='display:flex;justify-content:center;gap:12px;margin-top:24px;flex-wrap:wrap;'>",
            unsafe_allow_html=True)
        for g_key, cfg in GRADES.items():
            st.markdown(
                f"<div style='background:{cfg['bg']};border:1px solid {cfg['border']};"
                f"border-radius:12px;padding:12px 18px;min-width:130px;text-align:center;'>"
                f"<div style='font-size:20px;font-weight:900;color:{cfg['color']}'>{cfg['icon']} {cfg['label']}</div>"
                f"<div style='font-size:10px;color:#555;margin-top:3px'>{cfg['desc']}</div></div>",
                unsafe_allow_html=True)
        st.markdown("</div></div>", unsafe_allow_html=True)
        return

    render_grade_summary(rows)

    # 키워드별 결과 수
    kw_stats = st.session_state.get("last_kw_stats", {})
    if len(kw_stats) > 1:
        badges = "".join([
            f"<span style='background:#1a1a1a;border:1px solid #2a2a2a;border-radius:18px;"
            f"padding:4px 12px;font-size:12px;font-weight:700;color:#aaa;'>"
            f"🔖 {kw} <b style='color:#e53935'>{cnt}</b></span>"
            for kw, cnt in kw_stats.items()
        ])
        st.markdown(f"<div style='display:flex;flex-wrap:wrap;gap:7px;margin-bottom:14px;'>{badges}</div>",
                    unsafe_allow_html=True)

    # 저장 행
    sv1, sv2 = st.columns([3, 7])
    with sv1:
        sname = st.text_input("저장 이름", placeholder="예: 영어 가족여행",
                              label_visibility="collapsed", key="sv_name")
        if st.button("💾 결과 저장", type="primary", use_container_width=True):
            if not sname.strip(): st.warning("저장 이름을 입력해 주세요.")
            else:
                sid = save_session(sname.strip(), rows)
                st.success(f"✅ '{sname}' 저장 완료! — 📚 기록 탭 확인")
    with sv2:
        st.markdown(
            f"<div style='background:#161616;border:1px solid #222;border-radius:10px;"
            f"padding:8px 14px;font-size:13px;color:#888;'>"
            f"총 <b style='color:#f0f0f0'>{len(rows)}</b>개 영상 | 등급순 정렬 | "
            f"이름 입력 후 💾 저장하면 📚 기록 탭에서 언제든 다시 확인</div>",
            unsafe_allow_html=True)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    grade_filter = st.radio("등급", ["전체","🏆 S급","⭐ A급","🌱 B급","📺 C급"],
                            horizontal=True, label_visibility="collapsed", key="gf")
    gmap = {"전체":None,"🏆 S급":"S","⭐ A급":"A","🌱 B급":"B","📺 C급":"C"}
    filtered = [r for r in rows if gmap[grade_filter] is None or r["등급"]==gmap[grade_filter]]
    st.markdown(f"<p style='color:#555;font-size:12px;margin:3px 0 10px'>표시: <b style='color:#f0f0f0'>{len(filtered)}개</b></p>",
                unsafe_allow_html=True)

    t_card, t_table = st.tabs(["🎬 카드 보기","📋 테이블 보기"])
    with t_card:
        for r in filtered: render_card(r)
    with t_table:
        df = pd.DataFrame(filtered).drop(columns=["썸네일","_channel_id","_is_short","_search_kw"], errors="ignore")
        st.dataframe(df, use_container_width=True, hide_index=True,
                     column_config={"URL":st.column_config.LinkColumn("URL"),
                                    "조회수":st.column_config.NumberColumn(format="%d"),
                                    "좋아요":st.column_config.NumberColumn(format="%d"),
                                    "댓글수":st.column_config.NumberColumn(format="%d"),
                                    "구독자수":st.column_config.NumberColumn(format="%d")})
        csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button("📥 CSV 다운로드", csv, "채널발굴결과.csv", "text/csv", use_container_width=True)


# ── 페이지: 검색 기록 ──────────────────────────────────────────────────────────
def page_history():
    username = st.session_state.get("username","")
    render_topbar("📚 저장된 검색 기록", username)

    sessions = list_sessions()
    if not sessions:
        st.markdown(
            "<div style='text-align:center;padding:70px 0;'>"
            "<div style='font-size:52px'>📭</div>"
            "<div style='font-size:16px;color:#555;margin-top:12px;'>"
            "저장된 기록이 없습니다.<br>검색 후 💾 결과 저장 버튼을 눌러보세요.</div>"
            "</div>", unsafe_allow_html=True)
        return

    st.markdown(f"<p style='color:#555;font-size:13px;margin-bottom:16px;'>총 <b style='color:#f0f0f0'>{len(sessions)}건</b></p>",
                unsafe_allow_html=True)
    gc = {"S":"#FFD700","A":"#00CFFF","B":"#4CAF50","C":"#888"}

    for s in sessions:
        sid = s["id"]
        badges = "".join([
            f"<span style='background:{gc[g]}18;color:{gc[g]};border:1px solid {gc[g]}35;"
            f"border-radius:14px;padding:2px 10px;font-size:11px;font-weight:700;'>"
            f"{lb} {s[f'grade_{g.lower()}']}</span>"
            for g, lb in [("S","🏆S"),("A","⭐A"),("B","🌱B"),("C","📺C")]
        ])
        st.markdown(
            f"<div class='hist-card'>"
            f"<div class='hist-name'>{s['name']}</div>"
            f"<div class='hist-meta'>📅 {s['saved_at']} &nbsp;|&nbsp; 🎬 {s['result_count']}개 &nbsp;|&nbsp; ID: {sid}</div>"
            f"<div style='display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;'>{badges}</div>"
            f"</div>", unsafe_allow_html=True)

        bc1, bc2, _, rn1, rn2 = st.columns([1.5, 1.2, 0.5, 3, 1])
        with bc1:
            if st.button("📂 불러오기", key=f"ld_{sid}", use_container_width=True, type="primary"):
                st.session_state.results = load_session(sid)
                st.session_state.page = "search"; st.rerun()
        with bc2:
            if st.button("🗑 삭제", key=f"dl_{sid}", use_container_width=True):
                delete_session(sid); st.rerun()
        with rn1:
            new_n = st.text_input("", key=f"rn_{sid}", placeholder="이름 변경...",
                                  label_visibility="collapsed")
        with rn2:
            if st.button("✏️", key=f"rnb_{sid}", use_container_width=True):
                if new_n.strip(): rename_session(sid, new_n.strip()); st.rerun()

        st.markdown("<hr style='border-color:#1e1e1e;margin:6px 0 12px'>", unsafe_allow_html=True)


# ── 페이지: 마이페이지 ─────────────────────────────────────────────────────────
def page_mypage():
    username = st.session_state.get("username","")
    render_topbar("👤 마이페이지", username)

    stats = get_total_stats()
    q_today = get_today_quota()
    q_hist = get_quota_history(7)
    used_today = q_today["units"]
    remain = DAILY_QUOTA - used_today
    pct = min(used_today / DAILY_QUOTA * 100, 100)
    bar_color = "#e53935" if pct>80 else "#FFD700" if pct>50 else "#4CAF50"
    initials = username[:2].upper() if username else "?"

    # 프로필 카드
    st.markdown(
        f"<div class='profile-card'>"
        f"<div class='avatar'>{initials}</div>"
        f"<div>"
        f"<div style='font-size:20px;font-weight:900;color:#f0f0f0;'>{username}</div>"
        f"<div style='font-size:12px;color:#555;margin-top:4px;'>YouTube 채널 발굴기 사용자</div>"
        f"</div></div>",
        unsafe_allow_html=True)

    # 통계 카드 행
    c1, c2, c3, c4 = st.columns(4)
    for col, num, lbl, clr in [
        (c1, stats["sessions"],          "저장된 검색", "#e53935"),
        (c2, stats["videos"],            "발굴한 영상",  "#FFD700"),
        (c3, stats["quota"],             "총 쿼타 사용", "#00CFFF"),
        (c4, q_today["calls"],           "오늘 API 호출", "#4CAF50"),
    ]:
        col.markdown(
            f"<div class='stat-card'>"
            f"<div class='stat-num' style='color:{clr}'>{num:,}</div>"
            f"<div class='stat-lbl'>{lbl}</div>"
            f"</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # 쿼타 현황
    left_col, right_col = st.columns([3, 2])
    with left_col:
        st.markdown(
            f"<div class='quota-bar-wrap'>"
            f"<div style='font-size:14px;font-weight:800;color:#f0f0f0;margin-bottom:4px;'>📊 오늘 쿼타 현황</div>"
            f"<div style='font-size:24px;font-weight:900;color:{bar_color};'>{used_today:,} "
            f"<span style='font-size:14px;color:#555;'>/ {DAILY_QUOTA:,}</span></div>"
            f"<div class='quota-bar-bg'>"
            f"<div class='quota-bar-fill' style='width:{pct:.1f}%;background:{bar_color};'></div></div>"
            f"<div style='display:flex;justify-content:space-between;font-size:12px;color:#555;margin-top:6px;'>"
            f"<span>사용: <b style='color:{bar_color}'>{used_today:,}</b></span>"
            f"<span>잔여: <b style='color:#4CAF50'>{remain:,}</b></span>"
            f"<span>({pct:.1f}%)</span></div>"
            f"</div>", unsafe_allow_html=True)

    with right_col:
        st.markdown(
            "<div class='app-card' style='padding:16px 18px;'>"
            "<div style='font-size:13px;font-weight:800;color:#f0f0f0;margin-bottom:10px;'>📅 쿼타 이력 (최근 7일)</div>",
            unsafe_allow_html=True)
        if q_hist:
            for h in q_hist:
                h_pct = min(h["units"] / DAILY_QUOTA * 100, 100)
                hc = "#e53935" if h_pct>80 else "#FFD700" if h_pct>50 else "#4CAF50"
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:6px;'>"
                    f"<span style='font-size:11px;color:#555;width:70px;flex-shrink:0;'>{h['date']}</span>"
                    f"<div style='flex:1;background:#1a1a1a;border-radius:4px;height:6px;'>"
                    f"<div style='width:{h_pct:.1f}%;height:6px;border-radius:4px;background:{hc};'></div></div>"
                    f"<span style='font-size:11px;color:{hc};width:50px;text-align:right;'>{h['units']:,}</span>"
                    f"</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:#555;font-size:12px;'>아직 기록이 없습니다.</div>",
                        unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # 비밀번호 변경
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    with st.expander("🔒 비밀번호 변경"):
        with st.form("pw_form"):
            old_pw = st.text_input("현재 비밀번호", type="password")
            new_pw = st.text_input("새 비밀번호", type="password")
            new_pw2 = st.text_input("새 비밀번호 확인", type="password")
            if st.form_submit_button("변경하기", type="primary"):
                if new_pw != new_pw2: st.error("새 비밀번호가 일치하지 않습니다.")
                else:
                    ok, msg = auth.change_password(username, old_pw, new_pw)
                    st.success(msg) if ok else st.error(msg)


# ── 페이지: API 키 관리 ────────────────────────────────────────────────────────
def page_apikeys():
    username = st.session_state.get("username","")
    render_topbar("🔑 API 키 관리", username)

    st.markdown(
        "<div class='app-card'>"
        "<div style='font-size:15px;font-weight:800;color:#f0f0f0;margin-bottom:6px;'>YouTube Data API v3 키 등록</div>"
        "<div style='font-size:12px;color:#555;line-height:1.7;'>"
        "최대 5개의 API 키를 등록할 수 있습니다. 한 키의 쿼타(10,000/일)가 소진되면 자동으로 다음 키로 전환됩니다.<br>"
        "API 키는 로컬 파일(<code>keys.json</code>)에 저장되며 GitHub에 업로드되지 않습니다."
        "</div></div>",
        unsafe_allow_html=True)

    saved_keys = auth.load_api_keys()
    if "api_keys_raw" not in st.session_state:
        st.session_state.api_keys_raw = saved_keys

    changed = False
    for i in range(5):
        cur = st.session_state.api_keys_raw[i]
        has = bool(cur.strip())
        dot = "#4CAF50" if has else "#333"
        c_no, c_in, c_del = st.columns([0.5, 7, 1.5])
        with c_no:
            st.markdown(
                f"<div style='text-align:center;font-size:16px;color:{dot};padding-top:8px;'>●</div>",
                unsafe_allow_html=True)
        with c_in:
            new_val = st.text_input(f"key{i}", value=cur, type="password",
                                    placeholder=f"API 키 #{i+1}  (AIza...)",
                                    label_visibility="collapsed", key=f"ak_{i}")
        with c_del:
            if st.button("✕ 삭제", key=f"akd_{i}", use_container_width=True, disabled=not has):
                st.session_state.api_keys_raw[i] = ""
                auth.save_api_keys(st.session_state.api_keys_raw)
                st.rerun()
        if new_val != cur:
            st.session_state.api_keys_raw[i] = new_val
            changed = True

    if changed:
        auth.save_api_keys(st.session_state.api_keys_raw)

    valid = get_valid_keys()
    if valid:
        st.success(f"✅ 유효한 API 키 {len(valid)}개 저장됨 — 자동으로 폴백합니다", icon="🔑")
    else:
        st.error("⚠️ API 키가 없습니다. 위에서 등록해 주세요.")
        st.markdown("[🔗 Google Cloud Console에서 키 발급받기](https://console.cloud.google.com/)")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    with st.expander("ℹ️ API 키 발급 방법"):
        st.markdown("""
1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 (또는 기존 프로젝트 선택)
3. **API 및 서비스 → 라이브러리** → `YouTube Data API v3` 검색 → **활성화**
4. **사용자 인증 정보 → API 키 만들기**
5. 생성된 키를 위 입력란에 붙여넣기
6. 일일 할당량: **10,000 유닛** (검색 1회 = 100 유닛)
""")


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="한국 여행 채널 발굴기", page_icon="🔍", layout="wide")
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    # 세션 초기화
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "username" not in st.session_state:
        st.session_state.username = ""
    if "page" not in st.session_state:
        st.session_state.page = "search"
    if "results" not in st.session_state:
        st.session_state.results = []
    if "my_keywords" not in st.session_state:
        st.session_state.my_keywords = []
    if "api_keys_raw" not in st.session_state:
        st.session_state.api_keys_raw = auth.load_api_keys()

    # 로그인 확인
    if not st.session_state.logged_in:
        page_login()
        return

    username = st.session_state.username
    page = st.session_state.get("page", "search")

    render_sidebar(username)

    if page in ("search", "custom_kw", "db_search"):
        page_search(page)
    elif page == "history":
        page_history()
    elif page == "mypage":
        page_mypage()
    elif page == "apikeys":
        page_apikeys()


if __name__ == "__main__":
    main()
