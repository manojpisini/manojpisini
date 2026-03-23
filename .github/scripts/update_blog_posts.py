import feedparser
import re
import requests
import urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# --- RSS sources ---
RSS_FEEDS = [
    {
        "name": "Hashnode",
        "url": "https://manojpisini.hashnode.dev/rss.xml",
        "badge": "![Hashnode](https://img.shields.io/badge/Hashnode-18181B?style=flat-square&logo=hashnode&logoColor=2962FF)",
    },
    {
        "name": "Medium",
        "url": "https://manojpisini.medium.com/feed",
        "badge": "![Medium](https://img.shields.io/badge/Medium-18181B?style=flat-square&logo=medium&logoColor=white)",
    },
    {
        "name": "Substack",
        "url": "https://manojpisini.substack.com/feed",
        "badge": "![Substack](https://img.shields.io/badge/Substack-18181B?style=flat-square&logo=substack&logoColor=FF6719)",
    },
    {
        "name": "Dev.to",
        "url": "https://dev.to/feed/manojpisini",
        "badge": "![Dev.to](https://img.shields.io/badge/Dev.to-18181B?style=flat-square&logo=devdotto&logoColor=white)",
    },
]

# --- GitHub Blog JSON manifest ---
GITHUB_BLOG = {
    "name": "GitHub Blog",
    "manifest_url": "https://manojpisini.github.io/blog/manifest.json",
    "base_url": "https://manojpisini.github.io/blog/",
    "badge": "![GitHub Blog](https://img.shields.io/badge/GitHub_Blog-18181B?style=flat-square&logo=github&logoColor=white)",
}

MAX_POSTS = 5

# Fixed banner dimensions rendered in the README
BANNER_WIDTH  = "100%"
BANNER_HEIGHT = "200"


def parse_rss_date(entry):
    for field in ("published", "updated"):
        val = entry.get(field)
        if val:
            try:
                return parsedate_to_datetime(val).replace(tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.min.replace(tzinfo=timezone.utc)


def parse_manifest_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def get_rss_banner(entry):
    """Try to extract a cover/thumbnail image from an RSS entry."""
    # 1. media:thumbnail or media:content (Medium, Substack, Dev.to)
    media = entry.get("media_thumbnail") or entry.get("media_content")
    if media and isinstance(media, list) and media[0].get("url"):
        return media[0]["url"]
    # 2. enclosures
    for enc in entry.get("enclosures", []):
        if enc.get("type", "").startswith("image/"):
            return enc.get("url")
    # 3. First <img> in summary or content body
    for field in ("summary", "content"):
        val = entry.get(field)
        if isinstance(val, list):
            val = val[0].get("value", "")
        if val:
            match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', val)
            if match:
                return match.group(1)
    return None


def build_capsule_banner(title, source, date_str):
    """Fallback: flat rectangle AMOLED banner via capsule-render."""
    short_title = title if len(title) <= 44 else title[:41] + "..."
    desc = f"{source}  ·  {date_str}"
    params = {
        "type": "rect",
        "color": "0:18181B,100:27272A",
        "height": BANNER_HEIGHT,
        "text": short_title,
        "fontSize": "24",
        "fontColor": "ffffff",
        "fontAlignY": "42",
        "fontAlign": "50",
        "desc": desc,
        "descSize": "14",
        "descColor": "a1a1aa",
        "descAlignY": "65",
        "descAlign": "50",
    }
    return "https://capsule-render.vercel.app/api?" + urllib.parse.urlencode(params)


def fetch_rss_posts():
    posts = []
    for source in RSS_FEEDS:
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries:
                date = parse_rss_date(entry)
                posts.append({
                    "title":       entry.get("title", "Untitled").strip(),
                    "url":         entry.get("link", "#"),
                    "date":        date,
                    "date_str":    date.strftime("%b %d, %Y"),
                    "source_name": source["name"],
                    "source_badge": source["badge"],
                    "banner":      get_rss_banner(entry),
                })
        except Exception as e:
            print(f"Failed to fetch {source['name']}: {e}")
    return posts


def fetch_github_blog_posts():
    posts = []
    try:
        resp = requests.get(GITHUB_BLOG["manifest_url"], timeout=10)
        resp.raise_for_status()
        entries = resp.json()
        for entry in entries:
            slug  = entry.get("file", "").replace(".md", "")
            url   = f"{GITHUB_BLOG['base_url']}{slug}"
            date  = parse_manifest_date(entry.get("date", ""))
            title = entry.get("title", "Untitled").strip()
            posts.append({
                "title":        title,
                "url":          url,
                "date":         date,
                "date_str":     date.strftime("%b %d, %Y"),
                "source_name":  GITHUB_BLOG["name"],
                "source_badge": GITHUB_BLOG["badge"],
                # Use "banner" key in manifest.json if present
                "banner":       entry.get("banner") or None,
            })
    except Exception as e:
        print(f"Failed to fetch GitHub Blog manifest: {e}")
    return posts


def fetch_all_posts():
    posts = fetch_rss_posts() + fetch_github_blog_posts()
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts[:MAX_POSTS]


def build_markdown(posts):
    if not posts:
        return "> _No posts yet. Check back soon!_\n"

    blocks = []
    for p in posts:
        title = p["title"]
        url   = p["url"]
        badge = p["source_badge"]
        date  = p["date_str"]

        if p.get("banner"):
            # Post's own cover image — fixed width + height so all banners
            # are uniform regardless of the original image dimensions.
            # object-fit:cover crops rather than squishes.
            img_tag = (
                f'<img src="{p["banner"]}" '
                f'width="{BANNER_WIDTH}" height="{BANNER_HEIGHT}" '
                f'style="object-fit:cover;border-radius:6px" '
                f'alt="{title}">'
            )
        else:
            # Capsule-render fallback — capsule already outputs at the
            # correct height, so no object-fit needed.
            capsule_url = build_capsule_banner(title, p["source_name"], date)
            img_tag = (
                f'<img src="{capsule_url}" '
                f'width="{BANNER_WIDTH}" height="{BANNER_HEIGHT}" '
                f'alt="{title}">'
            )

        # Wrap image in a link so clicking opens the post
        banner_block = f'<a href="{url}">{img_tag}</a>'

        block = banner_block
        blocks.append(block)

    return "\n\n&nbsp;\n\n".join(blocks) + "\n"


def update_readme(content):
    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()

    new_section = (
        f"<!-- BLOG-POST-LIST:START -->\n{content}<!-- BLOG-POST-LIST:END -->"
    )

    updated = re.sub(
        r"<!-- BLOG-POST-LIST:START -->.*?<!-- BLOG-POST-LIST:END -->",
        new_section,
        readme,
        flags=re.DOTALL,
    )

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(updated)

    print("README.md updated successfully.")


if __name__ == "__main__":
    posts = fetch_all_posts()
    print(f"Fetched {len(posts)} posts total.")
    for p in posts:
        src = "post banner" if p.get("banner") else "capsule-render"
        print(f"  [{p['source_name']}] {p['title']} ({p['date_str']}) — {src}")
    markdown = build_markdown(posts)
    update_readme(markdown)
