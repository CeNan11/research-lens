
import requests
import trafilatura
import json


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
            timeout=20
        )

        response.raise_for_status()

        extracted = trafilatura.extract(
            response.text,
            include_comments=False,
            include_tables=True,
            output_format="json"
        )

        if not extracted:
            return None

        return json.loads(extracted)

    except requests.RequestException as error:
        print(f"Website request failed: {error}")
        return None

    except (json.JSONDecodeError, ValueError) as error:
        print(f"Article extraction failed: {error}")
        return None
