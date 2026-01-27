# DataForge

A lightweight static site generator written in Python. Converts Markdown files into HTML using Jinja2 templating. Built for [adair.tech](https://adair.tech).

## Why?

There are so many SSGs, you may wonder why I created my own. There are a couple of reasons:

- I wanted something that exactly fit my needs and what I was trying to do. Many SSGs that are available come close to doing what I want, but not exactly.
- I wanted something very simple and fast.
- I wanted something opinionated, but in the way that I am opinionated.

## Installation

```bash
pip install -r requirements.txt
```

**Dependencies:**
- Jinja2 - Template engine
- Markdown - Python-Markdown for parsing
- Pygments - Syntax highlighting for code blocks

## Usage

1. Put static pages in Markdown format in the `pages/` directory
2. Put blog posts in Markdown format in the `posts/` directory
3. Run the build:
   ```bash
   python3 main.py
   ```
4. Upload the contents of the `dist/` directory to your web server

## Content Format

All Markdown files require YAML frontmatter with these fields:

```markdown
---
title: Post Title
date: YYYY-MM-DD
tags: tag1, tag2
summary: Brief description of the content
slug: url-slug
---

Your content here...
```

## Features

### Syntax Highlighting

Fenced code blocks are automatically highlighted using Pygments with the Monokai theme:

````markdown
```python
def hello():
    print("Hello, world!")
```
````

### Obsidian-Style Callouts

Supports callout blocks compatible with Obsidian syntax:

```markdown
> [!NOTE]
> This is a note callout

> [!WARNING] Custom Title
> This is a warning with a custom title

> [!TIP]
> Helpful tip here

> [!INFO]
> Informational content

> [!DANGER]
> Important warning
```

## Output Structure

```
dist/
├── index.html              # Homepage with post listings
├── {page-slug}.html        # Static pages
├── posts/
│   └── {post-slug}.html    # Individual blog posts
└── styles/
    └── main.css            # Combined stylesheet with syntax highlighting
```

## Project Structure

```
├── main.py          # Entry point and build logic
├── templates/
│   ├── layout.html  # Base template
│   ├── main.html    # Homepage template
│   ├── posts.html   # Post template
│   └── pages.html   # Page template
├── styles.css       # Source stylesheet
├── pages/           # Static page Markdown files
└── posts/           # Blog post Markdown files
```

## Issues/Contributions

This was written for my own use and to scratch my own itch. It is simple by design.

If there is a feature you want, feel free to open an issue. I may or may not implement it.

If I do not end up implementing something you want, feel free to fork the project and do with it what you will. It is one of the great things about open source.

## License

[MIT](https://choosealicense.com/licenses/mit/)
