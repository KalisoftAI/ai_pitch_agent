import json
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import (
    IntegrationSetting,
    LinkedInProfile,
    RedditPost,
    SocialMetric,
    SyncRun,
    User,
    WhatsAppMessage,
)
from ..schemas import LinkedInSearchIn, RedditSearchIn, WhatsAppSendIn, YouTubeSearchIn
from ..security import get_current_user, require_roles
from ..services import LinkedInExtractor, RedditScraper, YouTubeExtractor

router = APIRouter(prefix="/social", tags=["social"])


# ---------- LinkedIn ----------
@router.get("/linkedin/profiles")
def list_linkedin(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(LinkedInProfile).filter(LinkedInProfile.user_id == user.id).all()


@router.post("/linkedin/search")
def search_linkedin(
    payload: LinkedInSearchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    extractor = LinkedInExtractor()
    found = extractor.search_by_hiring_alerts(payload.keywords, payload.location)
    added = 0
    for item in found:
        exists = (
            db.query(LinkedInProfile)
            .filter(
                LinkedInProfile.user_id == user.id,
                LinkedInProfile.profile_url == item["profile_url"],
            )
            .first()
        )
        if exists:
            continue
        db.add(
            LinkedInProfile(
                user_id=user.id,
                profile_url=item["profile_url"],
                name=item["name"],
                headline=item["headline"],
                company=item["company"],
                location=item["location"],
                skills=item["skills"],
                source_keyword=item["source_keyword"],
            )
        )
        added += 1
    db.commit()
    return {"found": len(found), "added": added, "api_available": extractor.available}


# ---------- Reddit ----------
@router.get("/reddit/posts")
def list_reddit(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(RedditPost).filter(RedditPost.user_id == user.id).all()


@router.post("/reddit/search")
def search_reddit(
    payload: RedditSearchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scraper = RedditScraper()
    found = scraper.search_hiring_posts(payload.subreddits, payload.keywords)
    added = 0
    for item in found:
        exists = (
            db.query(RedditPost)
            .filter(RedditPost.user_id == user.id, RedditPost.post_url == item["post_url"])
            .first()
        )
        if exists:
            continue
        db.add(
            RedditPost(
                user_id=user.id,
                post_url=item["post_url"],
                title=item["title"],
                content=item["content"],
                subreddit=item["subreddit"],
                alerts_related=item["alerts_related"],
            )
        )
        added += 1
    db.commit()
    return {"found": len(found), "added": added, "api_available": scraper.available}


# ---------- YouTube ----------
@router.post("/youtube/search")
def search_youtube(
    payload: YouTubeSearchIn,
    user: User = Depends(get_current_user),
):
    """Scan YouTube for company/tech signals (Google Data API v3).

    Secured by the workspace Google account (ADC / API key). Without a key the
    extractor returns deterministic stubs so the pipeline remains testable.
    """
    extractor = YouTubeExtractor()
    found = extractor.search_signals(payload.queries, payload.max_results)
    return {"found": len(found), "api_available": extractor.available, "results": found}


# ---------- WhatsApp ----------
@router.post("/whatsapp/messages", status_code=201)
def queue_whatsapp(
    payload: WhatsAppSendIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    message = WhatsAppMessage(
        user_id=user.id,
        phone_number=payload.phone_number,
        message=payload.message,
        status="pending",
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return {"id": message.id, "status": message.status}


@router.get("/whatsapp/messages")
def list_whatsapp(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(WhatsAppMessage).filter(WhatsAppMessage.user_id == user.id).all()


# ---------- Instagram (Meta Graph API) ----------
GRAPH_BASE = "https://graph.facebook.com/v21.0"


def _graph_get(path: str, params: dict) -> dict:
    try:
        response = httpx.get(f"{GRAPH_BASE}/{path}", params=params, timeout=20)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"Instagram request failed: {str(exc)[:200]}"
        ) from exc
    if response.status_code >= 400:
        try:
            error = response.json().get("error", {})
            message = error.get("message") or response.text[:200]
        except ValueError:
            message = response.text[:200]
        raise HTTPException(status_code=502, detail=f"Instagram API error: {message}")
    return response.json()


def _latest_instagram(db: Session) -> SocialMetric | None:
    return (
        db.query(SocialMetric)
        .filter(SocialMetric.platform == "instagram", SocialMetric.metric == "snapshot")
        .order_by(SocialMetric.id.desc())
        .first()
    )


@router.get("/instagram/status")
def instagram_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    snapshot = _latest_instagram(db)
    return {
        "configured": bool(settings.INSTAGRAM_ACCESS_TOKEN and settings.INSTAGRAM_ACCOUNT_ID),
        "account_id_configured": bool(settings.INSTAGRAM_ACCOUNT_ID),
        "access_token_configured": bool(settings.INSTAGRAM_ACCESS_TOKEN),
        "last_sync": str(snapshot.captured_at) if snapshot else None,
        "profile": (snapshot.meta or {}).get("profile", {}) if snapshot else {},
        "metrics": (snapshot.meta or {}).get("insights", {}) if snapshot else {},
        "media_count": len((snapshot.meta or {}).get("media", [])) if snapshot else 0,
    }


@router.post("/instagram/sync")
def sync_instagram(
    user: User = Depends(require_roles("sales", "admin")), db: Session = Depends(get_db)
):
    if not settings.INSTAGRAM_ACCESS_TOKEN or not settings.INSTAGRAM_ACCOUNT_ID:
        return {
            "configured": False,
            "status": "configuration_required",
            "message": "Set INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID to sync real Instagram metrics.",
        }
    account = settings.INSTAGRAM_ACCOUNT_ID
    token = settings.INSTAGRAM_ACCESS_TOKEN
    profile = _graph_get(
        account,
        {
            "fields": "id,username,name,followers_count,follows_count,media_count,profile_picture_url",
            "access_token": token,
        },
    )
    insights = {}
    try:
        data = _graph_get(
            f"{account}/insights",
            {
                "metric": "reach,impressions,profile_views",
                "period": "day",
                "access_token": token,
            },
        )
        for item in data.get("data", []):
            values = item.get("values") or []
            insights[item.get("name", "")] = values[-1].get("value", 0) if values else 0
    except HTTPException:
        insights = {}
    media = []
    try:
        data = _graph_get(
            f"{account}/media",
            {
                "fields": "id,caption,media_type,like_count,comments_count,timestamp,permalink",
                "limit": 25,
                "access_token": token,
            },
        )
        media = data.get("data", [])
    except HTTPException:
        media = []

    likes = sum(int(item.get("like_count") or 0) for item in media)
    comments = sum(int(item.get("comments_count") or 0) for item in media)
    snapshot = SocialMetric(
        user_id=0,
        platform="instagram",
        metric="snapshot",
        value=1,
        period=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        meta={
            "profile": profile,
            "insights": insights,
            "media": media,
            "engagement": {"likes": likes, "comments": comments},
        },
    )
    for metric, value in (
        ("followers", profile.get("followers_count", 0)),
        ("media_count", profile.get("media_count", 0)),
        ("likes", likes),
        ("comments", comments),
        *insights.items(),
    ):
        db.add(
            SocialMetric(
                user_id=0,
                platform="instagram",
                metric=metric,
                value=float(value or 0),
                period=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                meta={"source": "graph_api"},
            )
        )
    db.add(snapshot)
    db.add(
        SyncRun(
            job="instagram_sync",
            status="ok",
            detail=json.dumps({"username": profile.get("username", ""), "media": len(media)}),
            finished_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return {
        "configured": True,
        "status": "synced",
        "profile": profile,
        "insights": insights,
        "media": media,
        "engagement": {"likes": likes, "comments": comments},
    }


@router.get("/instagram/analytics")
def instagram_analytics(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(SocialMetric)
        .filter(
            SocialMetric.platform == "instagram",
            SocialMetric.metric != "snapshot",
            SocialMetric.captured_at >= since,
        )
        .order_by(SocialMetric.captured_at.asc())
        .all()
    )
    series: dict[str, list[dict]] = {}
    latest: dict[str, dict] = {}
    for row in rows:
        series.setdefault(row.metric, []).append({"at": str(row.captured_at), "value": row.value})
        current = latest.get(row.metric)
        if current is None or row.captured_at >= current["at"]:
            latest[row.metric] = {"at": row.captured_at, "value": row.value}
    return {
        "days": days,
        "series": series,
        "latest": {
            key: {"at": str(value["at"]), "value": value["value"]} for key, value in latest.items()
        },
        "configured": bool(settings.INSTAGRAM_ACCESS_TOKEN and settings.INSTAGRAM_ACCOUNT_ID),
    }


@router.get("/overview")
def social_overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    instagram = _latest_instagram(db)
    yt_row = (
        db.query(IntegrationSetting)
        .filter(IntegrationSetting.key == "youtube_channel_stats")
        .first()
    )
    try:
        youtube = json.loads(yt_row.value) if yt_row and yt_row.value else None
    except ValueError:
        youtube = None
    last_instagram_sync = (
        db.query(SyncRun)
        .filter(SyncRun.job == "instagram_sync")
        .order_by(SyncRun.id.desc())
        .first()
    )
    return {
        "instagram": {
            "configured": bool(settings.INSTAGRAM_ACCESS_TOKEN and settings.INSTAGRAM_ACCOUNT_ID),
            "profile": (instagram.meta or {}).get("profile", {}) if instagram else {},
            "insights": (instagram.meta or {}).get("insights", {}) if instagram else {},
            "engagement": (instagram.meta or {}).get("engagement", {}) if instagram else {},
            "media": (instagram.meta or {}).get("media", []) if instagram else [],
            "last_sync": str(last_instagram_sync.finished_at) if last_instagram_sync else None,
        },
        "youtube": {"configured": bool(yt_row), "stats": youtube},
        "linkedin": {
            "configured": bool(settings.LINKEDIN_ACCESS_TOKEN),
            "profiles": db.query(LinkedInProfile)
            .filter(LinkedInProfile.user_id == user.id)
            .count(),
        },
        "reddit": {
            "configured": bool(settings.REDDIT_CLIENT_ID and settings.REDDIT_CLIENT_SECRET),
            "posts": db.query(RedditPost).filter(RedditPost.user_id == user.id).count(),
        },
        "whatsapp": {
            "configured": bool(settings.WHATSAPP_API_KEY and settings.WHATSAPP_PHONE_NUMBER_ID),
            "messages": db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.user_id == user.id)
            .count(),
        },
    }
