"""Daily YouTube Shorts feed builder — 8 카테고리 × 5 키워드.

GitHub Actions 가 매일 KST 00시 (UTC 15:00) 에 실행:
    1. 8 카테고리 × 5 키워드 = 40개 검색 → 각 8개 쇼츠 수집 (총 320개)
    2. data/feed.json 으로 저장
    3. workflow 가 git commit

API 사용량:
    40 search × 100 units + 40 videos × 1 unit = 4,040 / 10,000 units/일

환경변수:
    YOUTUBE_API_KEY — GitHub Secrets 에서 주입
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = "https://www.googleapis.com/youtube/v3"

CATEGORIES = [
    {
        "key": "home",
        "label": "🛋 가구·홈스타일링",
        "queries": [
            "쿠팡 자취방 꾸미기 필수템",
            "오늘의집 인기 인테리어 소품",
            "옷장 수납 정리 꿀템",
            "가성비 원룸 가구 추천",
            "삶의 질 상승 홈스타일링",
        ],
    },
    {
        "key": "kitchen",
        "label": "🍳 소형가전·주방가전",
        "queries": [
            "쿠팡 주방 꿀템 추천",
            "다이소 자취 가전 리뷰",
            "삶의 질 수직상승 가전",
            "가성비 미니 가전제품",
            "무선 가전 필수템 리뷰",
        ],
    },
    {
        "key": "living",
        "label": "🧴 생활·욕실용품",
        "queries": [
            "다이소 청소 꿀템 추천",
            "쿠팡 욕실 필수템 리뷰",
            "자취생 생활용품 추천",
            "삶의 질 상승 욕실템",
            "안 쓰면 손해인 살림템",
        ],
    },
    {
        "key": "car",
        "label": "🚗 차량용품·자동차",
        "queries": [
            "쿠팡 차량용품 추천",
            "자동차 삶의 질 상승",
            "운전 필수템",
            "자동차 꿀템",
            "차에 두면 무조건 좋은",
        ],
    },
    {
        "key": "pet",
        "label": "🐶 반려동물 케어",
        "queries": [
            "쿠팡 강아지 필수템 추천",
            "고양이 집사 꿀템 리뷰",
            "반려견 삶의 질 상승템",
            "가성비 애완용품 추천",
            "반려동물 추천템",
        ],
    },
    {
        "key": "camping",
        "label": "⛺ 캠핑·아웃도어",
        "queries": [
            "쿠팡 캠핑 꿀템 추천",
            "가성비 캠핑 장비 리뷰",
            "캠핑 필수템 추천",
            "감성 캠핑 용품 추천",
            "차박 필수템",
        ],
    },
    {
        "key": "fitness",
        "label": "💪 운동·홈트레이닝",
        "queries": [
            "다이소 홈트 꿀템",
            "쿠팡 운동기구 추천",
            "홈트레이닝 필수템",
            "다이어트 추천템",
            "삶의 질 상승 운동용품",
        ],
    },
    {
        "key": "food",
        "label": "🍱 가공식품·밀키트",
        "queries": [
            "쿠팡 프레시 추천템",
            "가성비 밀키트 추천",
            "자취생 냉동식품 추천",
            "쟁여두면 좋은 먹거리",
            "쿠팡 대용량 가공식품",
        ],
    },
]


def today_kst() -> str:
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    return now.strftime("%Y-%m-%d")


def now_kst_iso() -> str:
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    return now.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def http_get_json(url: str, timeout: int = 20) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Chronit-StyleFeed/2.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_duration(iso: str) -> int:
    m = re.match(r"PT(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def api_search(query: str, api_key: str, max_results: int = 12) -> list:
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoDuration": "short",
        "regionCode": "KR",
        "relevanceLanguage": "ko",
        "order": "viewCount",
        "maxResults": max_results,
        "key": api_key,
    }
    url = f"{API_BASE}/search?{urllib.parse.urlencode(params)}"
    data = http_get_json(url)
    return [it for it in (data.get("items") or [])
            if it.get("id", {}).get("videoId")]


def api_videos_detail(video_ids: list, api_key: str) -> dict:
    if not video_ids:
        return {}
    params = {
        "part": "snippet,statistics,contentDetails",
        "id": ",".join(video_ids),
        "key": api_key,
    }
    url = f"{API_BASE}/videos?{urllib.parse.urlencode(params)}"
    data = http_get_json(url)
    return {it["id"]: it for it in (data.get("items") or []) if it.get("id")}


def fetch_keyword(query: str, api_key: str, max_results: int = 8) -> list:
    """단일 키워드 → 쇼츠 list."""
    search_items = api_search(query, api_key, max_results=12)
    if not search_items:
        return []
    ids = [it["id"]["videoId"] for it in search_items]
    details = api_videos_detail(ids, api_key)

    items = []
    for s in search_items:
        vid = s["id"]["videoId"]
        d = details.get(vid) or {}
        sn = d.get("snippet") or s.get("snippet") or {}
        stats = d.get("statistics") or {}
        cd = d.get("contentDetails") or {}
        duration = parse_duration(cd.get("duration", ""))
        if duration and duration > 60:
            continue  # 쇼츠 = 60초 이하
        thumbs = sn.get("thumbnails") or {}
        thumb = (thumbs.get("maxres") or thumbs.get("high")
                 or thumbs.get("medium") or thumbs.get("default") or {})
        items.append({
            "id": vid,
            "url": f"https://www.youtube.com/shorts/{vid}",
            "title": sn.get("title", ""),
            "channel": sn.get("channelTitle", ""),
            "channel_id": sn.get("channelId", ""),
            "thumbnail": thumb.get("url", ""),
            "published_at": sn.get("publishedAt", ""),
            "view_count": int(stats.get("viewCount", 0) or 0),
            "duration_sec": duration,
        })
        if len(items) >= max_results:
            break
    return items


def main():
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        print("[X] YOUTUBE_API_KEY 환경변수 없음", file=sys.stderr)
        sys.exit(1)

    feed = {
        "updated_at": now_kst_iso(),
        "date": today_kst(),
        "categories": {},
    }

    total_items = 0
    api_calls = 0
    for cat in CATEGORIES:
        cat_data = {"label": cat["label"], "keywords": {}}
        for q in cat["queries"]:
            try:
                items = fetch_keyword(q, api_key, max_results=8)
                cat_data["keywords"][q] = items
                total_items += len(items)
                api_calls += 2  # search + videos
                print(f"[OK] {cat['key']:>8} · '{q}': {len(items)}개")
                time.sleep(0.3)  # rate limit 여유
            except Exception as e:
                print(f"[X] {cat['key']} · '{q}' 실패: {e}",
                      file=sys.stderr)
                cat_data["keywords"][q] = []
        feed["categories"][cat["key"]] = cat_data

    out = Path("data/feed.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(feed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✓ 완료 — {len(CATEGORIES)} 카테고리, {total_items} 영상")
    print(f"  API 호출: {api_calls}회 (~{api_calls * 50} units)")
    print(f"  파일: {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
