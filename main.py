#! /usr/bin/env python3
import os
import re
import shutil
from datetime import datetime

from jinja2 import Environment, PackageLoader
from markdown import Markdown
from pygments.formatters import HtmlFormatter


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


# Parse posts
POSTS = {}
for post in os.listdir("posts"):
    file_path = os.path.join("posts", post)
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


posts_metadata = extract_metadata(POSTS)
pages_metadata = extract_metadata(PAGES)
tags = [post["tags"] for post in posts_metadata]

# Generate home page
home_html = home_template.render(posts=posts_metadata, pages=pages_metadata, tags=tags)
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
        post=post_data, pages=pages_metadata, ss_path="../styles/main.css"
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

    page_html = page_template.render(page=page_data, pages=pages_metadata)

    page_file_path = f"dist/{get_metadata_value(meta, 'slug')}.html"
    os.makedirs(os.path.dirname(page_file_path), exist_ok=True)
    with open(page_file_path, "w") as file:
        file.write(page_html)

# Copy styles and generate Pygments CSS
os.makedirs("dist/styles", exist_ok=True)
shutil.copyfile("styles.css", "dist/styles/main.css")

# Append Pygments syntax highlighting CSS
formatter = HtmlFormatter(style="monokai")
with open("dist/styles/main.css", "a") as file:
    file.write("\n/* Syntax highlighting (Pygments) */\n")
    file.write(formatter.get_style_defs(".highlight"))
