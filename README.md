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
- feedgen - RSS feed generation

**Optional Dependencies:**
- ollama - Auto-generate post summaries (requires running Ollama server)
- linkedin-api-python-client - Auto-post to LinkedIn
- atproto - Auto-post to Bluesky

## Usage

1. Put static pages in Markdown format in the `pages/` directory
2. Put blog posts in Markdown format in the `posts/` directory
3. (Optional) Set environment variables for integrations (see below)
4. Run the build:
   ```bash
   python3 main.py
   ```
5. Upload the contents of the `dist/` directory to your web server

## Environment Variables

**Optional - for site URL:**
- `SITE_URL` - Base URL for your site (defaults to https://adair.tech)

All other environment variables are documented in their respective integration sections below.

## Content Format

All Markdown files require YAML frontmatter with these fields:

```markdown
---
title: Post Title
date: YYYY-MM-DD
tags: tag1, tag2
summary: Brief description of the content
slug: url-slug
linkedin: true    # Optional: auto-post to LinkedIn
bluesky: true     # Optional: auto-post to Bluesky
---

Your content here...
```

**Note:** If `summary` is omitted and Ollama is configured, a summary will be auto-generated and added to the file.

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

### RSS Feed

An RSS 2.0 feed is automatically generated at `dist/feed.xml` with all posts.

### Social Media Integration

#### Ollama Summary Generation (Optional)

Auto-generate summaries for posts that don't have one. Requires a running Ollama server.

**Setup:**
```bash
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=llama3.2
pip install ollama
```

When you build, any post missing a `summary` field will have one generated and added automatically.

#### LinkedIn Auto-Posting (Optional)

Automatically post new blog posts to LinkedIn during builds.

**Setup:**
1. Create a LinkedIn app at https://developer.linkedin.com
2. Run the helper script to get an OAuth token:
   ```bash
   export CLIENT_ID=your_client_id
   export CLIENT_SECRET=your_client_secret
   python3 linkedin_auth.py
   ```
3. Set environment variables:
   ```bash
   export LINKEDIN_ACCESS_TOKEN=your_token
   export LINKEDIN_PERSON_URN=urn:li:person:abc123
   pip install linkedin-api-python-client
   ```
4. Add `linkedin: true` to post frontmatter to enable sharing

Posts are tracked in `.linkedin_shared.json` to prevent duplicates. Tokens expire after 60 days.

#### Bluesky Auto-Posting (Optional)

Automatically post new blog posts to Bluesky during builds.

**Setup:**
1. Generate an app password at Bluesky Settings > App Passwords
2. Set environment variables:
   ```bash
   export BLUESKY_HANDLE=user.bsky.social
   export BLUESKY_APP_PASSWORD=your_app_password
   pip install atproto
   ```
3. Add `bluesky: true` to post frontmatter to enable sharing

Posts are tracked in `.bluesky_shared.json` to prevent duplicates.

#### Share Buttons

Posts automatically include share buttons for:
- LinkedIn (client-side, no API key needed)
- Bluesky (uses intent URL)
- HackerNews (uses submission URL)

## Output Structure

```
dist/
├── index.html              # Homepage with post listings
├── feed.xml                # RSS 2.0 feed
├── {page-slug}.html        # Static pages
├── posts/
│   └── {post-slug}.html    # Individual blog posts
└── styles/
    └── main.css            # Combined stylesheet with syntax highlighting
```

## Project Structure

```
├── main.py             # Entry point and build logic (527 lines)
├── linkedin_auth.py    # Helper script for LinkedIn OAuth
├── templates/
│   ├── layout.html     # Base template
│   ├── main.html       # Homepage template
│   ├── posts.html      # Post template
│   └── pages.html      # Page template
├── styles.css          # Source stylesheet
├── pages/              # Static page Markdown files
└── posts/              # Blog post Markdown files
```

## Issues/Contributions

This was written for my own use and to scratch my own itch. It is simple by design.

If there is a feature you want, feel free to open an issue. I may or may not implement it.

If I do not end up implementing something you want, feel free to fork the project and do with it what you will. It is one of the great things about open source.

## License

[MIT](https://choosealicense.com/licenses/mit/)
