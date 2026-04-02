#!/usr/bin/env python3
"""
Scrape cheapest flight prices and price insights from Google Flights.
Writes results to flight_data.json in the same directory.

Usage:
    pip install playwright
    playwright install chromium
    python3 scrape_flights.py
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = SCRIPT_DIR / "flight_data.json"

# Define your itinerary here
ROUTES = [
    {"order": 0, "from_city": "Hong Kong",      "from_code": "HKG", "to_city": "Bangkok",       "to_code": "BKK", "date": "2026-05-26"},
    {"order": 1, "from_city": "Bangkok",         "from_code": "BKK", "to_city": "Phuket",        "to_code": "HKT", "date": "2026-05-30"},
    {"order": 2, "from_city": "Phuket",          "from_code": "HKT", "to_city": "Kuala Lumpur",   "to_code": "KUL", "date": "2026-06-03"},
    {"order": 3, "from_city": "Kuala Lumpur",    "from_code": "KUL", "to_city": "Bali",           "to_code": "DPS", "date": "2026-06-05"},
    {"order": 4, "from_city": "Bali",            "from_code": "DPS", "to_city": "Hanoi",          "to_code": "HAN", "date": "2026-06-08"},
]


def build_google_flights_url(from_code, to_code, date):
    """Build a Google Flights search URL for a one-way flight."""
    return (
        f"https://www.google.com/travel/flights/search"
        f"?tfs=CBwQAhooEgoyMDI2LTA1LTI2agwIAhIIL20vMDJwZmNyDAgCEggvbS8wMTViMkABSAFwAYIBCwj___________8BmAEB"
        # The encoded URL above won't work for all routes.
        # Instead, use the text-based search URL:
    )


def build_search_url(from_code, to_code, date):
    """Build a simple Google Flights search URL."""
    return (
        f"https://www.google.com/travel/flights?q="
        f"Flights+from+{from_code}+to+{to_code}+on+{date}+oneway&curr=USD"
    )


def extract_price(text):
    """Extract a dollar amount from text like '$119' or 'US$119'."""
    match = re.search(r'\$\s*(\d[\d,]*)', text)
    if match:
        return int(match.group(1).replace(',', ''))
    return None


def scrape_route(page, route, attempt=1):
    """
    Scrape a single route from Google Flights.
    Returns a dict with cheapest_price, flights list, and price_insights.
    """
    from_code = route["from_code"]
    to_code = route["to_code"]
    date = route["date"]

    url = build_search_url(from_code, to_code, date)
    print(f"  Navigating to: {route['from_city']} -> {route['to_city']} ({date})")
    print(f"  URL: {url}")

    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    # Wait for flight results to load — look for price elements
    try:
        page.wait_for_selector('[class*="price"], [data-price], span:has-text("$")', timeout=20000)
    except PlaywrightTimeout:
        print("  Warning: Timed out waiting for price elements, will try to extract anyway")

    # Give extra time for dynamic content (price insights, graphs) to render
    time.sleep(5)

    # Dismiss any cookie consent or overlay dialogs
    for dismiss_sel in ['button:has-text("Accept")', 'button:has-text("Reject")', 'button:has-text("Got it")']:
        try:
            btn = page.query_selector(dismiss_sel)
            if btn and btn.is_visible():
                btn.click()
                time.sleep(0.5)
        except Exception:
            pass

    # --- Extract cheapest price ---
    cheapest_price = None
    flights = []

    # Strategy 1: Look for the "best departing flight" or first result price
    # Google Flights shows prices in spans, usually the first prominent one is cheapest
    all_prices = []

    # Try multiple selectors that Google Flights uses for prices
    price_selectors = [
        'span[data-gs]',                          # Price spans with data attribute
        '[class*="price"] span',                   # Generic price containers
        'span[aria-label*="dollars"]',             # Accessible price labels
        'span[aria-label*="USD"]',                 # USD price labels
    ]

    for selector in price_selectors:
        elements = page.query_selector_all(selector)
        for el in elements:
            text = el.inner_text().strip()
            price = extract_price(text)
            if price and 5 < price < 5000:  # Sanity check
                all_prices.append(price)
        if all_prices:
            break

    # Fallback: scan all visible text for dollar amounts
    if not all_prices:
        body_text = page.inner_text('body')
        dollar_matches = re.findall(r'\$\s*(\d[\d,]*)', body_text)
        for m in dollar_matches:
            price = int(m.replace(',', ''))
            if 5 < price < 5000:
                all_prices.append(price)

    if all_prices:
        cheapest_price = min(all_prices)
        # Collect unique prices as flight options
        unique_prices = sorted(set(all_prices))
        for p in unique_prices[:10]:  # Top 10 unique prices
            flights.append({"price_usd": f"${p}"})
        print(f"  Found {len(all_prices)} prices, cheapest: ${cheapest_price}")
    else:
        print("  WARNING: No prices found!")

    # --- Extract price insights ---
    price_insights = extract_price_insights(page, cheapest_price)

    return {
        "cheapest_price": f"${cheapest_price}" if cheapest_price else None,
        "flights": flights,
        "total_options": len(flights),
        "price_insights": price_insights,
    }


def extract_price_insights(page, cheapest_price):
    """
    Extract the 'Price insights' section from Google Flights.
    Google Flights shows a price graph with typical range info.
    We look for the specific DOM elements and aria-labels that contain this data.
    """
    insights = {
        "level": "",
        "typical_low": "",
        "typical_high": "",
        "insight_text": "",
        "trend": "",
        "notes": "",
    }

    try:
        # Scroll down to reveal price insights section, then try to expand it
        page.evaluate('window.scrollBy(0, 600)')
        time.sleep(1)

        for selector in [
            'text="Price insights"',
            'text="View price history"',
            'text="Price history"',
            '[aria-label*="rice insight"]',
            '[aria-label*="rice history"]',
        ]:
            try:
                el = page.query_selector(selector)
                if el and el.is_visible():
                    el.click()
                    time.sleep(1.5)
                    break
            except Exception:
                continue

        body_text = page.inner_text('body')

        # Debug: dump text around "typical" or "usually" keywords
        for keyword in ['typical', 'usually', 'normally', 'low for', 'high for', 'price range']:
            idx = body_text.lower().find(keyword)
            if idx >= 0:
                snippet = body_text[max(0, idx - 80):idx + 120]
                print(f"  Found '{keyword}' context: ...{snippet.strip()}...")
                break

        # Strategy 1: Look for price range patterns in various formats
        # Google Flights uses formats like "$65–110" (no $ before second number)
        range_patterns = [
            # "between $65–110" or "between $65-$110" (Google Flights format)
            r'(?:between|from)\s+\$\s*(\d[\d,]*)\s*[\-–—]+\s*\$?\s*(\d[\d,]*)',
            # "usually cost between $65–110"
            r'(?:usually|typically|normally)\s+cost[s]?\s+(?:between\s+)?\$\s*(\d[\d,]*)\s*[\-–—]+\s*\$?\s*(\d[\d,]*)',
            # "$65 – $110" near "typical" or "usual"
            r'\$\s*(\d[\d,]*)\s*[\-–—]+\s*\$?\s*(\d[\d,]*)\s*(?:is\s+)?(?:the\s+)?(?:typical|usual|normal)',
            r'(?:typical|usual|normal)\s*(?:price\s*)?(?:range)?[:\s]*\$\s*(\d[\d,]*)\s*[\-–—]+\s*\$?\s*(\d[\d,]*)',
            # "$65 — $110 typical price"
            r'\$\s*(\d[\d,]*)\s*[\-–—]+\s*\$?\s*(\d[\d,]*)\s*(?:typical|usual)',
            # Broader: any "$XX – YY" or "$XX – $YY" near range/price keywords
            r'(?:range|prices?)[^$]{0,30}\$\s*(\d[\d,]*)\s*[\-–—]+\s*\$?\s*(\d[\d,]*)',
        ]

        range_match = None
        for pattern in range_patterns:
            range_match = re.search(pattern, body_text, re.IGNORECASE)
            if range_match:
                break

        # Also try extracting from aria-labels (Google often puts data there)
        if not range_match:
            aria_texts = page.eval_on_selector_all(
                '[aria-label]',
                'els => els.map(e => e.getAttribute("aria-label")).filter(a => a && (a.includes("typical") || a.includes("price") || a.includes("range") || a.includes("usually")))'
            )
            for aria in aria_texts:
                m = re.search(r'\$\s*(\d[\d,]*)\s*[\-–—]+\s*\$\s*(\d[\d,]*)', aria)
                if m:
                    range_match = m
                    print(f"  Found range in aria-label: {aria[:100]}")
                    break

        if range_match:
            low = int(range_match.group(1).replace(',', ''))
            high = int(range_match.group(2).replace(',', ''))
            if low > high:
                low, high = high, low
            insights["typical_low"] = f"${low}"
            insights["typical_high"] = f"${high}"
            print(f"  Price range: ${low} - ${high}")

            if cheapest_price:
                if cheapest_price < low:
                    insights["level"] = "low"
                    insights["notes"] = f"${cheapest_price} is low"
                    insights["insight_text"] = f"${cheapest_price} is low. Usually costs between ${low}-${high}."
                elif cheapest_price > high:
                    insights["level"] = "high"
                    insights["notes"] = f"${cheapest_price} is high"
                    insights["insight_text"] = f"${cheapest_price} is high. Usually costs between ${low}-${high}."
                else:
                    insights["level"] = "typical"
                    insights["notes"] = f"${cheapest_price} is typical"
                    insights["insight_text"] = f"${cheapest_price} is typical. Usually costs between ${low}-${high}."
        else:
            # Check for level keywords even without range
            level_patterns = [
                (r'(?:prices?\s+(?:are|is)\s+)?(?:currently\s+)?low', 'low'),
                (r'(?:prices?\s+(?:are|is)\s+)?(?:currently\s+)?(?:typical|normal|average)', 'typical'),
                (r'(?:prices?\s+(?:are|is)\s+)?(?:currently\s+)?high', 'high'),
            ]
            for pattern, level in level_patterns:
                if re.search(pattern, body_text, re.IGNORECASE):
                    insights["level"] = level
                    insights["notes"] = f"Price is {level} (no range data)"
                    break

            if not insights["insight_text"]:
                insights["insight_text"] = "Tracked flight prices"

        # Look for trend information
        trend_patterns = [
            (r'prices?\s+(?:are|have been)\s+(?:currently\s+)?(increasing|rising|going up)', 'increasing'),
            (r'prices?\s+(?:are|have been)\s+(?:currently\s+)?(decreasing|falling|going down|dropping)', 'decreasing'),
            (r'prices?\s+(?:are|have been)\s+(?:currently\s+)?(stable|steady|flat)', 'stable'),
            (r'(increased?|risen|climbed)\s+(?:by\s+)?\$?\d+', 'increasing'),
            (r'(decreased?|fallen|dropped)\s+(?:by\s+)?\$?\d+', 'decreasing'),
            (r'expect prices to (increase|rise|go up)', 'increasing'),
            (r'expect prices to (decrease|drop|fall)', 'decreasing'),
        ]

        for pattern, trend_label in trend_patterns:
            if re.search(pattern, body_text, re.IGNORECASE):
                insights["trend"] = trend_label
                print(f"  Trend: {trend_label}")
                break

    except Exception as e:
        print(f"  Warning: Could not extract price insights: {e}")

    return insights


def scrape_all_routes():
    """Scrape all routes and write results to flight_data.json."""
    print("=" * 60)
    print("Google Flights Scraper")
    print("=" * 60)

    results = []
    total_cheapest = 0

    with sync_playwright() as p:
        print("\nLaunching browser...")
        browser = p.chromium.launch(
            headless=False,  # Set to True for unattended runs
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-first-run',
                '--no-default-browser-check',
            ]
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()

        # First, visit Google to establish cookies
        print("Establishing session...")
        page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)

        for route in ROUTES:
            print(f"\n--- Route {route['order'] + 1}/{len(ROUTES)} ---")

            result = None
            for attempt in range(1, 4):  # Up to 3 attempts
                try:
                    result = scrape_route(page, route, attempt=attempt)
                    # If we got a price, we're good
                    if result["cheapest_price"]:
                        break
                    print(f"  No prices found on attempt {attempt}, retrying...")
                    time.sleep(2)
                except Exception as e:
                    print(f"  ERROR on attempt {attempt}: {e}")
                    time.sleep(2)

            if not result or not result["cheapest_price"]:
                print("  FAILED after all attempts")
                result = {
                    "cheapest_price": None,
                    "flights": [],
                    "total_options": 0,
                    "price_insights": {
                        "level": "", "typical_low": "", "typical_high": "",
                        "insight_text": "", "trend": "", "notes": "Failed to scrape"
                    },
                }

            route_data = {
                **route,
                "cheapest_price": result["cheapest_price"],
                "flights": result["flights"],
                "total_options": result["total_options"],
                "price_insights": result["price_insights"],
            }
            results.append(route_data)

            price = extract_price(result["cheapest_price"]) if result["cheapest_price"] else 0
            total_cheapest += price

            # Brief pause between routes to avoid rate limiting
            time.sleep(2)

        browser.close()

    # Build final output
    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_cheapest": f"${total_cheapest}",
        "routes": results,
    }

    # Write to file
    OUTPUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\n{'=' * 60}")
    print(f"Done! Total cheapest: ${total_cheapest}")
    print(f"Results written to: {OUTPUT_FILE}")
    print(f"{'=' * 60}")

    return output


if __name__ == "__main__":
    scrape_all_routes()
