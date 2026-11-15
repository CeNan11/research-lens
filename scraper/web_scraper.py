
import re
import requests
import trafilatura
from bs4 import BeautifulSoup
import json


def get_meta_content(soup, *attributes):
    """Find metadata using possible HTML attributes."""

    for attribute in attributes:
        tag = soup.find("meta", attrs=attribute)

        if tag and tag.get("content"):
            return tag["content"].strip()

    return None


def clean_author(author, website):
    """Remove email/contact details and duplicated website names."""

    if not author:
        return None

    if isinstance(author, (list, tuple)):
        author = " ".join(str(item) for item in author)

    author = str(author)

    # Remove actual email addresses.
    author = re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        " ",
        author,
        flags=re.IGNORECASE
    )

    # Remove email labels and any contact information following them.
    author = re.sub(
        r"\b(?:e-?mail)\b\s*[:\-]?.*$",
        "",
        author,
        flags=re.IGNORECASE
    )

    author = re.sub(r"\s+", " ", author).strip(" -|,;:")

    # Remove a duplicated publisher name at the end of the author field.
    if website:
        website_names = [
            name.strip()
            for name in website.split(":")
            if name.strip()
        ]

        for name in website_names:
            if (
                author.casefold() != name.casefold()
                and author.casefold().endswith(" " + name.casefold())
            ):
                author = author[:-len(name)].strip()

    return author or None


def scrape_article(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=(10,60)
        )

        response.raise_for_status()

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # Extract article content.
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            output_format="json"
        )

        if not extracted:
            print("Unable to extract article content.")
            return None

        article_data = json.loads(extracted)

        # Extract metadata through Trafilatura.
        metadata = trafilatura.metadata.extract_metadata(html)

        # Extract metadata through HTML tags as fallback.
        title = (
            metadata.title
            or get_meta_content(soup, {"property": "og:title"})
            or get_meta_content(soup, {"name": "twitter:title"})
            or (soup.title.get_text(strip=True) if soup.title else None)
        )

        website = (
            metadata.sitename
            or get_meta_content(soup, {"property": "og:site_name"})
        )

        author = (
            metadata.author
            or get_meta_content(soup, {"name": "author"})
            or get_meta_content(soup, {"property": "article:author"})
        )

        date = (
            metadata.date
            or get_meta_content(soup, {"property": "article:published_time"})
            or get_meta_content(soup, {"name": "date"})
            or get_meta_content(soup, {"itemprop": "datePublished"})
        )

        author = clean_author(author, website)

        return {
            "title": title,
            "author": author,
            "date": date,
            "website": website,
            "url": response.url,
            "text": article_data.get("text", "")
        }

    except requests.RequestException as error:
        print(f"Website request failed: {error}")
        return None

    except (json.JSONDecodeError, ValueError) as error:
        print(f"Article extraction failed: {error}")
        return None
