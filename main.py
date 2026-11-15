
import json
from pathlib import Path
from scraper.web_scraper import scrape_article


def save_article(article):
    output_dir = Path("output/articles")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "article.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(
            article,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(f"\nArticle saved to: {output_file}")


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
