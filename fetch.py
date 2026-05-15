"""Daily YouTube Shorts feed builder.

GitHub Actions 가 매일 KST 00시 (UTC 15:00) 에 실행:
1. 5개 카테고리 검색 → 각 12개 쇼츠 수집
2. data/feed.json 으로 저장
3. workflow 가 git commit

환경변수:
    YOUTUBE_API_KEY — GitHub Secrets 에서 주입
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = "https://www.googleapis.com/youtube/v3"

CATEGORIES = [
    {"key": "trending", "label": "🔥 인기 쇼츠", "query": "쇼츠 트렌드 #shorts"},
    {"key": "tips", "label": "꿀팁", "query": "쇼츠 꿀팁 #shorts"},
    {"key": "product", "label": "제품 리뷰", "query": "쇼츠 제품 리뷰 #shorts"},
    {"key": "lifestyle", "label": "라이프스타일", "query": "쇼츠 라이프스타일 #shorts"},
    {"key": "food", "label": "푸드/요리", "query": "쇼츠 요리 #shorts"},
    {"key": "tech", "label": "테크/IT", "query": "쇼츠 테크 리뷰 #shorts"},
]


def today_kst() -> str:
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    return now.strftime("%Y-%m-%d")


def now_kst_iso() -> str:
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    return now.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def http_get_json(url: str, timeout: int = 20) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Chronit-StyleFeed/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_duration(iso: str) -> int:
    m = re.match(r"PT(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def api_search(query: str, api_key: str, max_results: int = 15) -> list:
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


def fetch_category(query: str, api_key: str, max_results: int = 12) -> list:
    search_items = api_search(query, api_key, max_results=15)
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
        print("ERROR: YOUTUBE_API_KEY 환경변수가 비어있음", file=sys.stderr)
        sys.exit(1)

    print(f"[fetch] 날짜 (KST): {today_kst()}")
    feed = {
        "updated_at": now_kst_iso(),
        "date": today_kst(),
        "categories": {},
    }
    for cat in CATEGORIES:
        print(f"[fetch] {cat['key']:>10} ← {cat['query']}")
        try:
            items = fetch_category(cat["query"], api_key)
            feed["categories"][cat["key"]] = {
                "label": cat["label"],
                "query": cat["query"],
                "items": items,
            }
            print(f"           → {len(items)}개")
        except Exception as e:
            print(f"           ERROR: {e}", file=sys.stderr)
            feed["categories"][cat["key"]] = {
                "label": cat["label"],
                "query": cat["query"],
                "items": [],
                "error": str(e),
            }

    out = Path(__file__).parent / "data" / "feed.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(feed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    total = sum(len(c.get("items") or [])
                for c in feed["categories"].values())
    print(f"[fetch] 완료: 총 {total}개 → {out}")


if __name__ == "__main__":
    main()
