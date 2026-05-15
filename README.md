# chronit-style-feed

Chronit (한국어 쇼츠 자동 생성 도구) 의 **스타일 찾기 탭** 용 데이터 피드.

GitHub Actions 가 매일 **KST 00시** 에 YouTube Data API 로 인기 쇼츠를 수집해서 `data/feed.json` 으로 commit 합니다. 모든 클라이언트는 이 JSON 을 raw URL 에서 가져와 동일한 트렌드를 봅니다.

## 동작

```
매일 KST 00시 (UTC 15:00)
  ↓ cron trigger
GitHub Actions 실행
  ↓ python fetch.py
YouTube Data API v3 호출 (5개 카테고리 × 12개 쇼츠)
  ↓
data/feed.json 자동 commit
  ↓
클라이언트 (Chronit 앱) 가 raw.githubusercontent.com 에서 GET
```

## 데이터 구조

`data/feed.json`:

```json
{
  "updated_at": "2026-05-15T00:05:23+09:00",
  "date": "2026-05-15",
  "categories": {
    "trending": {
      "label": "🔥 인기 쇼츠",
      "query": "쇼츠 트렌드 #shorts",
      "items": [
        {
          "id": "abc123",
          "url": "https://www.youtube.com/shorts/abc123",
          "title": "...",
          "channel": "...",
          "thumbnail": "https://i.ytimg.com/...",
          "view_count": 1234567,
          "duration_sec": 45
        }
      ]
    }
  }
}
```

## 셋업 (한 번만)

1. **이 repo 를 본인 GitHub 계정에 새로 만들기 (public)**
2. **Secrets 등록**
   - repo Settings → Secrets and variables → Actions → New repository secret
   - Name: `YOUTUBE_API_KEY`
   - Value: Google Cloud Console 에서 발급한 키
3. **Actions 권한 확인**
   - Settings → Actions → General → Workflow permissions → "Read and write permissions"
4. **수동 첫 실행**
   - Actions 탭 → "Daily YouTube Shorts Fetch" → Run workflow
   - 성공하면 `data/feed.json` 생성됨

## Raw URL

클라이언트가 사용하는 URL:

```
https://raw.githubusercontent.com/<USERNAME>/<REPO>/main/data/feed.json
```

(CDN 캐싱 ~5분)

## 비용

- GitHub Actions: public repo 무제한 무료
- YouTube API: 일일 quota ~600 사용 (한도 10,000)
- 클라이언트 fetch: GitHub raw 무료/무제한
