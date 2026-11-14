
from scraper.web_scraper import scrape_article


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

    print(content)
    print(f"\nExtracted characters: {len(content)}")

else:
    print("Unable to extract article.")
