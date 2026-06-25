"""DOM extraction helpers for LinkedIn profile posts."""

from __future__ import annotations

import re
from typing import Any

ACTIVITY_ID_RE = re.compile(r"urn:li:activity:(\d+)")
ACTIVITY_URL_RE = re.compile(r"/feed/update/urn:li:activity:(\d+)")


def normalize_post_id(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    match = ACTIVITY_ID_RE.search(text)
    if match:
        return match.group(1)
    match = ACTIVITY_URL_RE.search(text)
    if match:
        return match.group(1)
    if text.isdigit():
        return text
    return text or None


EXPAND_TRUNCATED_POSTS_JS = """
() => {
  const containers = document.querySelectorAll(
    'div.feed-shared-update-v2, div[data-urn*="activity"], div[data-urn*="urn:li:activity"], li.profile-creator-shared-feed-update__container, li.artdeco-list__item'
  );

  const expandPost = (el) => {
    const selectors = [
      'button.feed-shared-inline-show-more-text__see-more-less-toggle',
      'button.inline-show-more-text__button',
      'button.update-components-text__expand-button',
      'button.feed-shared-text-view__see-more-less-toggle',
    ];
    for (const sel of selectors) {
      const btn = el.querySelector(sel);
      if (!btn) continue;
      const label = (btn.getAttribute('aria-label') || btn.innerText || '').toLowerCase();
      if (label.includes('less')) continue;
      btn.click();
      return;
    }
    for (const btn of el.querySelectorAll('button')) {
      const text = (btn.innerText || btn.getAttribute('aria-label') || '').trim().toLowerCase();
      if (
        (text === '…more' || text === '...more' || text === 'more' || text.endsWith(' more')) &&
        !text.includes('less')
      ) {
        btn.click();
        return;
      }
    }
  };

  for (const el of containers) expandPost(el);
}
"""

EXTRACT_POSTS_JS = """
() => {
  const posts = [];
  const seen = new Set();
  const containers = document.querySelectorAll(
    'div.feed-shared-update-v2, div[data-urn*="activity"], div[data-urn*="urn:li:activity"], li.profile-creator-shared-feed-update__container, li.artdeco-list__item'
  );

  for (const el of containers) {
    const urn = el.getAttribute('data-urn') || el.dataset?.urn || '';
    const link = el.querySelector('a[href*="/feed/update/"], a[href*="activity"]');
    const href = link ? link.getAttribute('href') || '' : '';
    let postId = '';
    const urnMatch = urn.match(/activity:(\\d+)/);
    const hrefMatch = href.match(/activity[:/](\\d+)/);
    if (urnMatch) postId = urnMatch[1];
    else if (hrefMatch) postId = hrefMatch[1];
    if (!postId || seen.has(postId)) continue;
    seen.add(postId);

    const textEl = el.querySelector(
      '.feed-shared-update-v2__description, .update-components-text, span.break-words'
    );
    const text = textEl ? (textEl.innerText || '').trim() : '';

    const timeEl = el.querySelector('time');
    const postedAt = timeEl
      ? (timeEl.getAttribute('datetime') || timeEl.innerText || '').trim()
      : '';

    const authorEl = el.querySelector(
      '.update-components-actor__name span, a.update-components-actor__meta-link'
    );
    const authorName = authorEl ? (authorEl.innerText || '').trim() : '';
    const authorLink = el.querySelector('a.update-components-actor__meta-link, a.app-aware-link');
    const authorUrl = authorLink ? (authorLink.getAttribute('href') || '') : '';

    let postUrl = href;
    if (postUrl && !postUrl.startsWith('http')) {
      postUrl = 'https://www.linkedin.com' + postUrl;
    }

    const counts = { likes: null, comments: null, reposts: null };
    const social = el.querySelector('.social-details-social-counts, .feed-shared-social-counts');
    if (social) {
      const t = social.innerText || '';
      const likeM = t.match(/(\\d[\\d,]*)\\s*(reaction|like)/i);
      const commentM = t.match(/(\\d[\\d,]*)\\s*comment/i);
      const repostM = t.match(/(\\d[\\d,]*)\\s*repost/i);
      if (likeM) counts.likes = parseInt(likeM[1].replace(/,/g, ''), 10);
      if (commentM) counts.comments = parseInt(commentM[1].replace(/,/g, ''), 10);
      if (repostM) counts.reposts = parseInt(repostM[1].replace(/,/g, ''), 10);
    }

    const mediaItems = [];
    const mediaSeen = new Set();
    const skipMedia = (url) => {
      if (!url || url.startsWith('data:') || url.startsWith('blob:')) return true;
      const lower = url.toLowerCase();
      return (
        lower.includes('ghost') ||
        lower.includes('profile-displayphoto') ||
        lower.includes('company-logo') ||
        lower.includes('/sc/h/') ||
        lower.includes('licdn.com/collect') ||
        lower.includes('static.licdn.com/aero')
      );
    };
    const classifyUrl = (url) => {
      const lower = url.toLowerCase();
      if (
        /\\.(pdf|pptx?|docx?)(\\?|$)/i.test(url) ||
        lower.includes('feedshare-document') ||
        lower.includes('document-snapshot')
      ) {
        return 'document';
      }
      if (
        /\\.(mp4|webm|mov|m4v)(\\?|$)/i.test(url) ||
        lower.includes('feedshare-video') ||
        lower.includes('/video/') ||
        lower.includes('videoplayback')
      ) {
        return 'video';
      }
      if (lower.includes('videocover') || lower.includes('poster')) {
        return 'poster';
      }
      if (
        /\\.(jpe?g|png|gif|webp|bmp)(\\?|$)/i.test(url) ||
        lower.includes('media.licdn.com') ||
        lower.includes('dms.licdn.com') ||
        lower.includes('feedshare-image') ||
        lower.includes('image-shrink')
      ) {
        return 'image';
      }
      return null;
    };
    const documentLabel = (url) => {
      try {
        const path = new URL(url, 'https://www.linkedin.com').pathname.split('/').pop() || 'Document';
        return decodeURIComponent(path);
      } catch {
        return 'Document';
      }
    };
    const addMedia = (item) => {
      const url = item.url;
      if (!url || mediaSeen.has(url) || skipMedia(url)) return;
      mediaSeen.add(url);
      mediaItems.push(item);
    };
    const addUrl = (url, hint) => {
      if (!url) return;
      const kind = hint || classifyUrl(url);
      if (!kind || kind === 'poster') {
        if (kind === 'poster') {
          addMedia({ kind: 'image', url, role: 'poster' });
        }
        return;
      }
      if (kind === 'document') {
        addMedia({ kind: 'document', url, label: documentLabel(url) });
        return;
      }
      if (kind === 'video') {
        addMedia({ kind: 'video', url });
        return;
      }
      addMedia({ kind: 'image', url });
    };
    const mediaRoots = el.querySelectorAll(
      '.feed-shared-image, .update-components-image, .feed-shared-external-video, .feed-shared-article, .feed-shared-linkedin-video, .document-s-container, .update-components-linkedin-video, .feed-shared-mini-update-v2'
    );
    const collectFromRoot = (root) => {
      for (const img of root.querySelectorAll('img')) {
        for (const src of [
          img.getAttribute('src'),
          img.getAttribute('data-delayed-url'),
          img.getAttribute('data-src'),
          img.currentSrc,
        ]) {
          addUrl(src, 'image');
        }
      }
      for (const video of root.querySelectorAll('video')) {
        const poster = video.getAttribute('poster');
        if (poster) addUrl(poster, 'poster');
        const src = video.getAttribute('src');
        if (src) {
          addMedia({ kind: 'video', url: src, poster: poster || undefined });
        }
        for (const source of video.querySelectorAll('source')) {
          const sourceUrl = source.getAttribute('src');
          if (sourceUrl) {
            addMedia({ kind: 'video', url: sourceUrl, poster: poster || undefined });
          }
        }
      }
      for (const anchor of root.querySelectorAll(
        'a[href*="feedshare-document"], a[href*="feedshare-video"], a[href*="dms.licdn.com"], a[href*="media.licdn.com"]'
      )) {
        const href = anchor.getAttribute('href');
        if (!href) continue;
        if (href.includes('feedshare-document')) {
          addMedia({ kind: 'document', url: href, label: documentLabel(href) });
        } else {
          addUrl(href);
        }
      }
    };
    if (mediaRoots.length) {
      for (const root of mediaRoots) collectFromRoot(root);
    } else {
      const actor = el.querySelector('.update-components-actor, .feed-shared-actor');
      for (const img of el.querySelectorAll('img')) {
        if (actor && actor.contains(img)) continue;
        for (const src of [
          img.getAttribute('src'),
          img.getAttribute('data-delayed-url'),
          img.getAttribute('data-src'),
          img.currentSrc,
        ]) {
          addUrl(src, 'image');
        }
      }
      for (const video of el.querySelectorAll('video')) {
        const poster = video.getAttribute('poster');
        if (poster) addUrl(poster, 'poster');
        const src = video.getAttribute('src');
        if (src) {
          addMedia({ kind: 'video', url: src, poster: poster || undefined });
        }
      }
    }
    const posters = mediaItems.filter((item) => item.role === 'poster');
    const videos = mediaItems.filter((item) => item.kind === 'video');
    if (videos.length > 0 && posters.length > 0) {
      for (let i = 0; i < videos.length; i++) {
        if (!videos[i].poster) {
          videos[i].poster = posters[Math.min(i, posters.length - 1)].url;
        }
      }
    }
    const mediaUrls = mediaItems
      .filter((item) => item.role !== 'poster')
      .map(({ kind, url, poster, label }) => {
        const entry = { kind, url };
        if (poster) entry.poster = poster;
        if (label) entry.label = label;
        return entry;
      });

    posts.push({
      post_id: postId,
      text,
      posted_at: postedAt,
      author_name: authorName,
      author_url: authorUrl,
      post_url: postUrl,
      like_count: counts.likes,
      comment_count: counts.comments,
      repost_count: counts.reposts,
      impression_count: null,
      media_urls: mediaUrls,
    });
  }
  return posts;
}
"""


def parse_posts(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    posts: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        post_id = normalize_post_id(str(item.get("post_id", "")))
        if not post_id:
            continue
        posts.append(
            {
                "post_id": post_id,
                "text": item.get("text") or "",
                "posted_at": item.get("posted_at") or "",
                "author_name": item.get("author_name") or "",
                "author_url": item.get("author_url") or "",
                "post_url": item.get("post_url") or "",
                "like_count": item.get("like_count"),
                "comment_count": item.get("comment_count"),
                "repost_count": item.get("repost_count"),
                "impression_count": item.get("impression_count"),
                "media_urls": item.get("media_urls") or [],
            }
        )
    return posts
