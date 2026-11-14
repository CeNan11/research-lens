
from scraper.web_scraper import scrape_article

url = input("Enter article URL: ").strip()

article = scrape_article(url)

if article:
    print("\n========== ARTICLE INFORMATION ==========")

    print(f"Title: {article.get('title')}")
    print(f"Author: {article.get('author')}")
    print(f"Date: {article.get('date')}")
    print(f"Website: {article.get('sitename')}")

    print("\n========== ARTICLE CONTENT ==========")

    content = article.get("text", "")
    print(content)

    print(f"\nExtracted characters: {len(content)}")

else:
    print("Unable to extract article.")
