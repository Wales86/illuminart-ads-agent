"""
Pobieranie danych z Google Search Console API.

Pobiera:
- Top zapytania (queries) z kliknięciami, wyświetleniami, CTR, pozycją
- Top strony z metrykami wyszukiwania

Wymagania:
- Search Console API włączone w Google Cloud
- OAuth2 credentials w config/credentials.json
- site_url w config/settings.yaml
- Strona zweryfikowana w Google Search Console
"""

import sys
from pathlib import Path

# Dodaj katalog scripts do ścieżki importów
sys.path.insert(0, str(Path(__file__).resolve().parent))

from googleapiclient.discovery import build

from utils import get_oauth_credentials, load_settings, parse_date_args, save_json


def create_gsc_client(credentials):
    """Tworzy klienta Search Console API.

    Args:
        credentials: OAuth2 credentials.

    Returns:
        Resource: Klient Search Console API.
    """
    return build("searchconsole", "v1", credentials=credentials)


def fetch_queries(service, site_url, start_date, end_date, row_limit=200):
    """Pobiera top zapytania z Search Console.

    Dane pomagają ocenić:
    - Widoczność organiczną sklepu
    - Potencjał SEO (wysokie impressions, niska pozycja → szansa)
    - Trendy ruchu organicznego

    Args:
        service: Klient GSC API.
        site_url: URL strony w GSC.
        start_date: Data początkowa (YYYY-MM-DD).
        end_date: Data końcowa (YYYY-MM-DD).
        row_limit: Maksymalna liczba wierszy.

    Returns:
        list[dict]: Dane zapytań.
    """
    request = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["query"],
        "rowLimit": row_limit,
        "dataState": "final",
    }

    response = (
        service.searchanalytics().query(siteUrl=site_url, body=request).execute()
    )

    queries = []
    for row in response.get("rows", []):
        queries.append(
            {
                "query": row["keys"][0],
                "clicks": row["clicks"],
                "impressions": row["impressions"],
                "ctr": round(row["ctr"] * 100, 2),  # Na procenty
                "position": round(row["position"], 1),
            }
        )

    print(f"  Zapytania: {len(queries)}")
    return queries


def fetch_queries_by_date(service, site_url, start_date, end_date):
    """Pobiera zapytania z podziałem na dni.

    Przydatne do identyfikacji trendów i anomalii dziennych.

    Returns:
        list[dict]: Dane zapytań per dzień.
    """
    request = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["date"],
        "dataState": "final",
    }

    response = (
        service.searchanalytics().query(siteUrl=site_url, body=request).execute()
    )

    daily_data = []
    for row in response.get("rows", []):
        daily_data.append(
            {
                "date": row["keys"][0],
                "clicks": row["clicks"],
                "impressions": row["impressions"],
                "ctr": round(row["ctr"] * 100, 2),
                "position": round(row["position"], 1),
            }
        )

    print(f"  Dane dzienne GSC: {len(daily_data)} dni")
    return daily_data


def fetch_pages(service, site_url, start_date, end_date, row_limit=50):
    """Pobiera top strony z Search Console.

    Identyfikuje:
    - Które strony generują ruch organiczny
    - Strony z potencjałem (dużo impressions, mało kliknięć)
    - Strony tracące pozycje

    Args:
        row_limit: Maksymalna liczba stron.

    Returns:
        list[dict]: Dane stron.
    """
    request = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["page"],
        "rowLimit": row_limit,
        "dataState": "final",
    }

    response = (
        service.searchanalytics().query(siteUrl=site_url, body=request).execute()
    )

    pages = []
    for row in response.get("rows", []):
        pages.append(
            {
                "page": row["keys"][0],
                "clicks": row["clicks"],
                "impressions": row["impressions"],
                "ctr": round(row["ctr"] * 100, 2),
                "position": round(row["position"], 1),
            }
        )

    print(f"  Top strony: {len(pages)}")
    return pages


def main():
    """Główna funkcja — pobiera wszystkie dane GSC i zapisuje jako JSON."""
    args = parse_date_args()
    settings = load_settings()

    site_url = settings.get("gsc", {}).get("site_url", "")
    if not site_url:
        print(
            "BŁĄD: Uzupełnij gsc.site_url w config/settings.yaml", file=sys.stderr
        )
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Pobieranie danych Google Search Console ({site_url})")
    print(f"Okres: {args.start} → {args.end}")
    print(f"{'='*60}\n")

    # Autentykacja
    credentials = get_oauth_credentials()
    service = create_gsc_client(credentials)

    # Pobieranie danych
    print("Pobieranie danych...")

    queries = fetch_queries(service, site_url, args.start, args.end)
    save_json(queries, "gsc_queries.json", args.run_date)

    daily = fetch_queries_by_date(service, site_url, args.start, args.end)
    save_json(daily, "gsc_daily.json", args.run_date)

    pages = fetch_pages(service, site_url, args.start, args.end)
    save_json(pages, "gsc_pages.json", args.run_date)

    # Podsumowanie
    total_clicks = sum(q["clicks"] for q in daily) if daily else 0
    total_impressions = sum(q["impressions"] for q in daily) if daily else 0
    avg_position = (
        round(sum(q["position"] for q in daily) / len(daily), 1) if daily else 0
    )

    print(f"\n✅ Dane GSC pobrane pomyślnie → data/{args.run_date}/")
    print(f"  Łączne kliknięcia: {total_clicks}")
    print(f"  Łączne wyświetlenia: {total_impressions}")
    print(f"  Średnia pozycja: {avg_position}")


if __name__ == "__main__":
    main()
