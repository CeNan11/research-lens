
import json
import re
from pathlib import Path
from scraper.web_scraper import scrape_article


def generate_filename(title):
    """Convert an article title into a filesystem-safe filename."""

    filename = re.sub(
        r"[^a-z0-9]+",
        "-",
        title.lower()
    ).strip("-")

    return filename or "article"


def save_article(article):
    output_dir = Path("output/articles")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename from article title.
    base_name = generate_filename(article.get("title") or "article")

    output_file = output_dir / f"{base_name}.json"

    # Prevent existing articles from being overwritten.
    counter = 2

    while output_file.exists():
        output_file = output_dir / f"{base_name}-{counter}.json"
        counter += 1

    # Save article as JSON.
    with output_file.open("w", encoding="utf-8") as file:
        json.dump(
            article,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(f"\nArticle saved to: {output_file}")

    return output_file


def main():
    url = input("Enter article URL: ").strip()

    article = scrape_article(url)

    if article:
        print("\n========== ARTICLE INFORMATION ==========")

        print(f"Title: {article['title']}")
        print(f"Author: {article['author']}")
        print(f"Date: {article['date']}")
        print(f"Website: {article['website']}")
        print(f"URL: {article['url']}")

        print("\n========== ARTICLE CONTENT ==========")

        content = article["text"]

        print(content[:1500])
        print(f"\nTotal extracted characters: {len(content)}")

        save_article(article)

    else:
        print("Unable to extract article.")


if __name__ == "__main__":
    main()
