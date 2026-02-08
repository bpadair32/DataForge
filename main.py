#! /usr/bin/env python3
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
SITE_URL = os.environ.get("SITE_URL", "https://adair.tech")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL")

ollama_client = None
if OLLAMA_HOST and OLLAMA_MODEL:
    try:
        from ollama import Client
        ollama_client = Client(host=OLLAMA_HOST)
    except ImportError:
        print("Warning: ollama package not installed. Auto-summary generation disabled.")
        print("Install with: pip install ollama")


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
    """Generate a 50-60 word summary for a post using Ollama."""
    if not ollama_client:
        return None

    prompt = f"""Write a summary for the following blog post titled "{title}".
The summary must be exactly 50-60 words. Do not include any preamble or explanation,
just output the summary text directly. The summary should be engaging and give readers
a clear idea of what the post covers.

Post content:
{content}

Summary:"""

    response = ollama_client.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"].strip()


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

    # Check if summary already exists in frontmatter
    if re.search(r"^summary:", frontmatter, re.MULTILINE):
        return

    # Add summary before slug line, or at the end of frontmatter
    if re.search(r"^slug:", frontmatter, re.MULTILINE):
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


# Parse posts and generate summaries if missing
POSTS = {}
for post in os.listdir("posts"):
    file_path = os.path.join("posts", post)
    with open(file_path, "r") as file:
        html, meta = parse_markdown(file.read())

    # Check if summary is missing and generate one if Ollama is configured
    summary = get_metadata_value(meta, "summary")
    if not summary and ollama_client:
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

# Generate home page
home_html = home_template.render(posts=posts_metadata, pages=pages_metadata, tags=tags, site_url=SITE_URL)
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
    }

    post_html = post_template.render(
        post=post_data, pages=pages_metadata, ss_path="../styles/main.css", site_url=SITE_URL
    )

    post_file_path = f"dist/posts/{get_metadata_value(meta, 'slug')}.html"
    os.makedirs(os.path.dirname(post_file_path), exist_ok=True)
    with open(post_file_path, "w") as file:
        file.write(post_html)

# Generate static pages
for page in PAGES:
    meta = PAGES[page]["metadata"]
    page_data = {
        "content": PAGES[page]["html"],
        "title": get_metadata_value(meta, "title"),
    }

    page_html = page_template.render(page=page_data, pages=pages_metadata, site_url=SITE_URL)

    page_file_path = f"dist/{get_metadata_value(meta, 'slug')}.html"
    os.makedirs(os.path.dirname(page_file_path), exist_ok=True)
    with open(page_file_path, "w") as file:
        file.write(page_html)

# Generate RSS feed
generate_rss_feed(POSTS, SITE_URL)

# Copy styles and generate Pygments CSS
os.makedirs("dist/styles", exist_ok=True)
shutil.copyfile("styles.css", "dist/styles/main.css")

# Append Pygments syntax highlighting CSS
formatter = HtmlFormatter(style="monokai")
with open("dist/styles/main.css", "a") as file:
    file.write("\n/* Syntax highlighting (Pygments) */\n")
    file.write(formatter.get_style_defs(".highlight"))
