#! /usr/bin/env python3
import json
import os
import re
import shutil
from datetime import datetime, timezone

from feedgen.feed import FeedGenerator
from jinja2 import Environment, PackageLoader
from markdown import Markdown
from pygments.formatters import HtmlFormatter

# Optional Ollama integration for auto-generating summaries
# Set these environment variables to enable:
#   OLLAMA_HOST - Ollama server URL (e.g., http://localhost:11434)
#   OLLAMA_MODEL - Model to use (e.g., llama3.2, mistral)
#
# Optional Claude API fallback for auto-generating summaries (used when Ollama is not configured)
# Set this environment variable to enable:
#   ANTHROPIC_API_KEY - Anthropic API key
SITE_URL = os.environ.get("SITE_URL", "https://adair.tech")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Optional LinkedIn integration for auto-posting new blog posts
# Set these environment variables to enable:
#   LINKEDIN_ACCESS_TOKEN - OAuth2 access token (use linkedin_auth.py to obtain)
#   LINKEDIN_PERSON_URN - Your LinkedIn person URN (e.g., urn:li:person:abc123)
LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN")
LINKEDIN_PERSON_URN = os.environ.get("LINKEDIN_PERSON_URN")
LINKEDIN_SHARE_FILE = os.environ.get("LINKEDIN_SHARE_FILE", ".linkedin_shared.json")

# Optional Bluesky integration for auto-posting new blog posts
# Set these environment variables to enable:
#   BLUESKY_HANDLE - Your Bluesky handle (e.g., user.bsky.social)
#   BLUESKY_APP_PASSWORD - App password (generate at Settings > App Passwords)
BLUESKY_HANDLE = os.environ.get("BLUESKY_HANDLE")
BLUESKY_APP_PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD")
BLUESKY_SHARE_FILE = os.environ.get("BLUESKY_SHARE_FILE", ".bluesky_shared.json")

# Theme configuration
DEFAULT_THEME = os.environ.get("DEFAULT_THEME", "default")
DISABLE_THEME_SWITCHING = os.environ.get("DISABLE_THEME_SWITCHING", "").lower() in ("1", "true", "yes")

ollama_client = None
if OLLAMA_HOST and OLLAMA_MODEL:
    try:
        from ollama import Client
        ollama_client = Client(host=OLLAMA_HOST)
    except ImportError:
        print("Warning: ollama package not installed. Auto-summary generation disabled.")
        print("Install with: pip install ollama")

anthropic_client = None
if not ollama_client and ANTHROPIC_API_KEY:
    try:
        import anthropic as _anthropic
        anthropic_client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except ImportError:
        print("Warning: anthropic package not installed. Claude API fallback for summaries disabled.")
        print("Install with: pip install anthropic")

linkedin_client = None
if LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN:
    try:
        from linkedin_api.clients.restli.client import RestliClient
        linkedin_client = RestliClient()
    except ImportError:
        print("Warning: linkedin-api-client not installed. Auto-posting disabled.")
        print("Install with: pip install linkedin-api-client")

bluesky_client = None
bsky_models = None
if BLUESKY_HANDLE and BLUESKY_APP_PASSWORD:
    try:
        from atproto import Client as BlueskyClient, models as _bsky_models
        bsky_models = _bsky_models
        _bsky = BlueskyClient()
        _bsky.login(BLUESKY_HANDLE, BLUESKY_APP_PASSWORD)
        bluesky_client = _bsky
    except ImportError:
        print("Warning: atproto package not installed. Bluesky auto-posting disabled.")
        print("Install with: pip install atproto")
    except Exception as e:
        print(f"Warning: Failed to log in to Bluesky: {e}")
        print("Check your BLUESKY_HANDLE and BLUESKY_APP_PASSWORD environment variables.")


def convert_obsidian_callouts(text):
    """Convert Obsidian-style callouts to HTML with markdown content.

    Converts:
        > [!NOTE] Optional title
        > Content here
        > More content

    To HTML div structure that Python-Markdown can process with md_in_html.
    """
    lines = text.split("\n")
    result = []
    in_callout = False
    callout_type = None
    callout_title = None
    callout_content = []

    for line in lines:
        # Check for callout start: > [!TYPE] or > [!TYPE] title
        callout_match = re.match(r"^>\s*\[!(\w+)\][-+]?\s*(.*)$", line)

        if callout_match:
            # Close previous callout if we were in one
            if in_callout:
                result.append(
                    _render_callout(callout_type, callout_title, callout_content)
                )
                callout_content = []

            in_callout = True
            callout_type = callout_match.group(1).lower()
            title_text = callout_match.group(2).strip()
            callout_title = title_text if title_text else None
        elif in_callout:
            # Check if this line continues the callout
            if line.startswith(">"):
                # Remove the > and optional space
                content = re.sub(r"^>\s?", "", line)
                callout_content.append(content)
            else:
                # End of callout
                result.append(
                    _render_callout(callout_type, callout_title, callout_content)
                )
                callout_content = []
                in_callout = False
                callout_type = None
                callout_title = None
                result.append(line)
        else:
            result.append(line)

    # Handle callout at end of file
    if in_callout:
        result.append(_render_callout(callout_type, callout_title, callout_content))

    return "\n".join(result)


def _render_callout(callout_type, title, content):
    """Render a callout as HTML div structure."""
    display_title = title if title else callout_type.upper()
    content_text = "\n".join(content)
    return f"""<div class="callout callout-{callout_type}" markdown="1">
<div class="callout-title">{display_title}</div>
<div class="callout-content" markdown="1">

{content_text}

</div>
</div>"""


def parse_markdown(text):
    """Parse markdown text with extensions for code highlighting and metadata."""
    # Preprocess Obsidian callouts
    text = convert_obsidian_callouts(text)

    md = Markdown(
        extensions=[
            "meta",
            "fenced_code",
            "codehilite",
            "md_in_html",
        ],
        extension_configs={
            "codehilite": {
                "css_class": "highlight",
                "guess_lang": False,
            },
        },
    )

    html = md.convert(text)
    return html, md.Meta


def get_metadata_value(meta, key):
    """Extract single value from markdown Meta dict (values are lists)."""
    value = meta.get(key, [""])[0]
    return value


def generate_summary(content, title):
    """Generate a 50-60 word summary for a post using Ollama or Claude API."""
    prompt = f"""Write a summary for the following blog post titled "{title}".
The summary must be exactly 50-60 words. Do not include any preamble or explanation,
just output the summary text directly. The summary should be engaging and give readers
a clear idea of what the post covers.

Post content:
{content}

Summary:"""

    if ollama_client:
        response = ollama_client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response["message"]["content"].strip()

    if anthropic_client:
        response = anthropic_client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    return None


def update_post_with_summary(file_path, summary):
    """Update a markdown post file to include the generated summary."""
    with open(file_path, "r") as file:
        content = file.read()

    # Find the frontmatter section (between --- markers)
    frontmatter_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not frontmatter_match:
        return

    frontmatter = frontmatter_match.group(1)
    rest_of_content = content[frontmatter_match.end():]

    # If summary field exists with a non-empty value, leave it alone
    if re.search(r"^summary:[ \t]+\S", frontmatter, re.MULTILINE):
        return

    # Replace empty summary line if present, otherwise insert before slug or append
    if re.search(r"^summary:[ \t]*$", frontmatter, re.MULTILINE):
        new_frontmatter = re.sub(
            r"^summary:[ \t]*$", f"summary: {summary}", frontmatter, flags=re.MULTILINE
        )
    elif re.search(r"^slug:", frontmatter, re.MULTILINE):
        new_frontmatter = re.sub(
            r"^(slug:)", f"summary: {summary}\n\\1", frontmatter, flags=re.MULTILINE
        )
    else:
        new_frontmatter = frontmatter + f"\nsummary: {summary}"

    new_content = f"---\n{new_frontmatter}\n---\n{rest_of_content}"

    with open(file_path, "w") as file:
        file.write(new_content)


def extract_post_content(file_path):
    """Extract the content of a post (without frontmatter) for summary generation."""
    with open(file_path, "r") as file:
        content = file.read()

    # Remove frontmatter
    content_match = re.match(r"^---\n.*?\n---\n(.*)$", content, re.DOTALL)
    if content_match:
        return content_match.group(1).strip()
    return content.strip()


def load_shared_posts():
    """Load the set of post slugs that have already been shared to LinkedIn."""
    try:
        with open(LINKEDIN_SHARE_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_shared_posts(shared):
    """Save the set of shared post slugs to the tracking file."""
    with open(LINKEDIN_SHARE_FILE, "w") as f:
        json.dump(sorted(shared), f, indent=2)


def share_post_to_linkedin(title, summary, slug, site_url):
    """Share a single post to LinkedIn as an article via the UGC API."""
    post_url = f"{site_url}/posts/{slug}.html"
    try:
        linkedin_client.create(
            resource_path="/ugcPosts",
            entity={
                "author": LINKEDIN_PERSON_URN,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": f"{title}\n\n{summary}"},
                        "shareMediaCategory": "ARTICLE",
                        "media": [{
                            "status": "READY",
                            "originalUrl": post_url,
                            "title": {"text": title},
                            "description": {"text": summary},
                        }],
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                },
            },
            access_token=LINKEDIN_ACCESS_TOKEN,
        )
        print(f"  Shared to LinkedIn: {title}")
        return True
    except Exception as e:
        print(f"  Warning: Failed to share to LinkedIn: {e}")
        if "401" in str(e):
            print("  Hint: Your LinkedIn access token may have expired. Run linkedin_auth.py to re-authorize.")
        return False


def share_new_posts_to_linkedin(posts, site_url):
    """Share any new posts marked with 'linkedin: true' to LinkedIn."""
    if not linkedin_client:
        return

    shared = load_shared_posts()
    for post in posts.values():
        meta = post["metadata"]
        linkedin_flag = get_metadata_value(meta, "linkedin")
        if linkedin_flag.lower() != "true":
            continue

        slug = get_metadata_value(meta, "slug")
        if slug in shared:
            continue

        title = get_metadata_value(meta, "title")
        summary = get_metadata_value(meta, "summary")
        if share_post_to_linkedin(title, summary, slug, site_url):
            shared.add(slug)

    save_shared_posts(shared)


def load_bluesky_shared_posts():
    """Load the set of post slugs that have already been shared to Bluesky."""
    try:
        with open(BLUESKY_SHARE_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_bluesky_shared_posts(shared):
    """Save the set of shared post slugs to the Bluesky tracking file."""
    with open(BLUESKY_SHARE_FILE, "w") as f:
        json.dump(sorted(shared), f, indent=2)


def share_post_to_bluesky(title, summary, slug, site_url):
    """Share a single post to Bluesky with an external link embed."""
    post_url = f"{site_url}/posts/{slug}.html"
    try:
        embed_external = bsky_models.AppBskyEmbedExternal.Main(
            external=bsky_models.AppBskyEmbedExternal.External(
                title=title,
                description=summary,
                uri=post_url,
            )
        )
        bluesky_client.send_post(text=f"{title}\n\n{summary}", embed=embed_external)
        print(f"  Shared to Bluesky: {title}")
        return True
    except Exception as e:
        print(f"  Warning: Failed to share to Bluesky: {e}")
        return False


def share_new_posts_to_bluesky(posts, site_url):
    """Share any new posts marked with 'bluesky: true' to Bluesky."""
    if not bluesky_client:
        return

    shared = load_bluesky_shared_posts()
    for post in posts.values():
        meta = post["metadata"]
        bluesky_flag = get_metadata_value(meta, "bluesky")
        if bluesky_flag.lower() != "true":
            continue

        slug = get_metadata_value(meta, "slug")
        if slug in shared:
            continue

        title = get_metadata_value(meta, "title")
        summary = get_metadata_value(meta, "summary")
        if share_post_to_bluesky(title, summary, slug, site_url):
            shared.add(slug)

    save_bluesky_shared_posts(shared)


# Parse posts and generate summaries if missing
POSTS = {}
for post in os.listdir("posts"):
    file_path = os.path.join("posts", post)
    with open(file_path, "r") as file:
        html, meta = parse_markdown(file.read())

    # Check if summary is missing and generate one if Ollama or Claude API is configured
    summary = get_metadata_value(meta, "summary")
    if not summary and (ollama_client or anthropic_client):
        title = get_metadata_value(meta, "title")
        post_content = extract_post_content(file_path)
        print(f"Generating summary for: {title}")
        summary = generate_summary(post_content, title)
        if summary:
            update_post_with_summary(file_path, summary)
            # Re-parse the file to get updated metadata
            with open(file_path, "r") as file:
                html, meta = parse_markdown(file.read())

    POSTS[post] = {"html": html, "metadata": meta}

POSTS = {
    post: POSTS[post]
    for post in sorted(
        POSTS,
        key=lambda post: datetime.strptime(
            get_metadata_value(POSTS[post]["metadata"], "date"), "%Y-%m-%d"
        ),
        reverse=True,
    )
}

# Parse pages
PAGES = {}
for page in os.listdir("pages"):
    file_path = os.path.join("pages", page)
    with open(file_path, "r") as file:
        html, meta = parse_markdown(file.read())
        PAGES[page] = {"html": html, "metadata": meta}

# Set up templates
env = Environment(loader=PackageLoader("main", "templates"))
home_template = env.get_template("main.html")
post_template = env.get_template("posts.html")
page_template = env.get_template("pages.html")


def extract_metadata(items):
    """Extract metadata dicts from parsed items, converting Meta format."""
    result = []
    for item in items.values():
        meta = item["metadata"]
        result.append(
            {
                "title": get_metadata_value(meta, "title"),
                "date": get_metadata_value(meta, "date"),
                "tags": get_metadata_value(meta, "tags"),
                "summary": get_metadata_value(meta, "summary"),
                "slug": get_metadata_value(meta, "slug"),
            }
        )
    return result


def discover_themes(themes_dir="themes"):
    themes = []
    if not os.path.isdir(themes_dir):
        return themes
    for name in sorted(os.listdir(themes_dir)):
        theme_path = os.path.join(themes_dir, name)
        if not os.path.isdir(theme_path):
            continue
        if not os.path.isfile(os.path.join(theme_path, "styles.css")):
            continue
        theme = {"name": name, "label": name.capitalize(), "description": "", "pygments_style": "monokai"}
        json_path = os.path.join(theme_path, "theme.json")
        if os.path.isfile(json_path):
            with open(json_path) as f:
                try:
                    meta = json.load(f)
                    theme.update({k: meta[k] for k in ("label", "description", "pygments_style") if k in meta})
                except json.JSONDecodeError:
                    pass
        themes.append(theme)
    themes.sort(key=lambda t: (0 if t["name"] == "default" else 1, t["name"]))
    return themes


def build_themes(themes, out_dir="dist/styles/themes"):
    os.makedirs(out_dir, exist_ok=True)
    for theme in themes:
        dst = os.path.join(out_dir, f"{theme['name']}.css")
        shutil.copyfile(os.path.join("themes", theme["name"], "styles.css"), dst)
        formatter = HtmlFormatter(style=theme["pygments_style"])
        with open(dst, "a") as f:
            f.write("\n/* Syntax highlighting (Pygments) */\n")
            f.write(formatter.get_style_defs(".highlight"))
    manifest = [{"name": t["name"], "label": t["label"], "description": t["description"]} for t in themes]
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)


def generate_rss_feed(posts, site_url):
    """Generate an RSS 2.0 feed from parsed posts."""
    fg = FeedGenerator()
    fg.title("adair.tech")
    fg.link(href=site_url)
    fg.link(href=f"{site_url}/feed.xml", rel="self")
    fg.description("Posts from adair.tech")
    fg.language("en")

    for post in posts.values():
        meta = post["metadata"]
        slug = get_metadata_value(meta, "slug")
        post_url = f"{site_url}/posts/{slug}.html"

        fe = fg.add_entry()
        fe.id(post_url)
        fe.title(get_metadata_value(meta, "title"))
        fe.link(href=post_url)
        fe.description(get_metadata_value(meta, "summary"))
        fe.content(post["html"], type="html")

        date_str = get_metadata_value(meta, "date")
        published = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        fe.published(published)

    fg.rss_file("dist/feed.xml")


posts_metadata = extract_metadata(POSTS)
pages_metadata = extract_metadata(PAGES)
tags = [post["tags"] for post in posts_metadata]

THEMES = discover_themes()
SHOW_THEME_SWITCHER = len(THEMES) >= 2 and not DISABLE_THEME_SWITCHING

# Generate home page
home_html = home_template.render(
    posts=posts_metadata, pages=pages_metadata, tags=tags, site_url=SITE_URL,
    css_base="styles/", themes=THEMES, default_theme=DEFAULT_THEME, show_theme_switcher=SHOW_THEME_SWITCHER,
)
os.makedirs("dist", exist_ok=True)
with open("dist/index.html", "w") as file:
    file.write(home_html)

# Generate post pages
for post in POSTS:
    meta = POSTS[post]["metadata"]
    post_data = {
        "content": POSTS[post]["html"],
        "title": get_metadata_value(meta, "title"),
        "date": get_metadata_value(meta, "date"),
        "slug": get_metadata_value(meta, "slug"),
        "summary": get_metadata_value(meta, "summary"),
        "tags": get_metadata_value(meta, "tags"),
    }

    post_html = post_template.render(
        post=post_data, pages=pages_metadata, site_url=SITE_URL,
        css_base="../styles/", themes=THEMES, default_theme=DEFAULT_THEME, show_theme_switcher=SHOW_THEME_SWITCHER,
    )

    post_file_path = f"dist/posts/{get_metadata_value(meta, 'slug')}.html"
    os.makedirs(os.path.dirname(post_file_path), exist_ok=True)
    with open(post_file_path, "w") as file:
        file.write(post_html)

# Share new posts to LinkedIn (if configured)
share_new_posts_to_linkedin(POSTS, SITE_URL)

# Share new posts to Bluesky (if configured)
share_new_posts_to_bluesky(POSTS, SITE_URL)

# Generate static pages
for page in PAGES:
    meta = PAGES[page]["metadata"]
    page_data = {
        "content": PAGES[page]["html"],
        "title": get_metadata_value(meta, "title"),
        "slug": get_metadata_value(meta, "slug"),
    }

    page_html = page_template.render(
        page=page_data, pages=pages_metadata, site_url=SITE_URL,
        css_base="styles/", themes=THEMES, default_theme=DEFAULT_THEME, show_theme_switcher=SHOW_THEME_SWITCHER,
    )

    page_file_path = f"dist/{get_metadata_value(meta, 'slug')}.html"
    os.makedirs(os.path.dirname(page_file_path), exist_ok=True)
    with open(page_file_path, "w") as file:
        file.write(page_html)

# Generate RSS feed
generate_rss_feed(POSTS, SITE_URL)

# Build themes
build_themes(THEMES)

# Copy favicon if present
if os.path.exists("favicon.svg"):
    shutil.copyfile("favicon.svg", "dist/favicon.svg")
