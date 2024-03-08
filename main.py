#! /usr/bin/env python3
import os
import shutil
from datetime import datetime
from jinja2 import Environment, PackageLoader
from markdown2 import markdown

POSTS = {}
for post in os.listdir("posts"):
    file_path = os.path.join("posts", post)
    with open(file_path, "r") as file:
        POSTS[post] = markdown(file.read(), extras=["metadata"])

POSTS = {
    post: POSTS[post]
    for post in sorted(
        POSTS,
        key=lambda post: datetime.strptime(POSTS[post].metadata["date"], "%Y-%m-%d"),
        reverse=True,
    )
}

PAGES = {}
for page in os.listdir("pages"):
    file_path = os.path.join("pages", page)
    with open(file_path, "r") as file:
        PAGES[page] = markdown(file.read(), extras=["metadata"])

env = Environment(loader=PackageLoader("main", "templates"))
home_template = env.get_template("main.html")
post_template = env.get_template("posts.html")
page_template = env.get_template("pages.html")

posts_metadata = [POSTS[post].metadata for post in POSTS]
tags = [post["tags"] for post in posts_metadata]
pages_metadata = [PAGES[page].metadata for page in PAGES]

home_html = home_template.render(posts=posts_metadata, pages=pages_metadata, tags=tags)

index_file_path = "dist/index.html"
os.makedirs(os.path.dirname(index_file_path), exist_ok=True)
with open("dist/index.html", "w") as file:
    file.write(home_html)

for post in POSTS:
    post_metadata = POSTS[post].metadata

    post_data = {
        "content": POSTS[post],
        "title": post_metadata["title"],
        "date": post_metadata["date"],
    }

    post_html = post_template.render(
        post=post_data, pages=pages_metadata, ss_path="../styles/main.css"
    )

    post_file_path = "dist/posts/{slug}.html".format(slug=post_metadata["slug"])

    os.makedirs(os.path.dirname(post_file_path), exist_ok=True)
    with open(post_file_path, "w") as file:
        file.write(post_html)

for page in PAGES:
    page_metadata = PAGES[page].metadata

    page_data = {"content": PAGES[page], "title": page_metadata["title"]}

    page_html = page_template.render(page=page_data, pages=pages_metadata)

    page_file_path = "dist/{slug}.html".format(slug=page_metadata["slug"])

    os.makedirs(os.path.dirname(page_file_path), exist_ok=True)
    with open(page_file_path, "w") as file:
        file.write(page_html)


os.makedirs("dist/styles", exist_ok=True)
shutil.copyfile("styles.css", "dist/styles/main.css")
