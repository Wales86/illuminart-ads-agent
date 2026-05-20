"""
Pobieranie danych z Google Analytics 4 Data API.

Pobiera:
- Przegląd ruchu dziennego (sesje, użytkownicy, bounce rate, zaangażowanie)
- Ruch wg źródeł/medium/kampanii (z konwersjami i przychodem)
- Konwersje dzienne wg źródeł
- Top strony wg wyświetleń

Wymagania:
- GA4 Data API włączone w Google Cloud
- OAuth2 credentials w config/credentials.json
- GA4 property_id w config/settings.yaml
"""

import sys
from pathlib import Path

# Dodaj katalog scripts do ścieżki importów
sys.path.insert(0, str(Path(__file__).resolve().parent))

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    OrderBy,
    RunReportRequest,
)

from utils import get_oauth_credentials, load_settings, parse_date_args, save_json


def create_ga4_client(credentials):
    """Tworzy klienta GA4 Data API z podanymi credentials.

    Args:
        credentials: OAuth2 credentials.

    Returns:
        BetaAnalyticsDataClient: Klient GA4 Data API.
    """
    return BetaAnalyticsDataClient(credentials=credentials)


def parse_report_response(response):
    """Konwertuje odpowiedź GA4 API na listę słowników.

    Args:
        response: Odpowiedź z RunReportRequest.

    Returns:
        list[dict]: Lista wierszy z nazwanymi polami.
    """
    rows = []

    # Pobierz nazwy nagłówków
    dimension_headers = [h.name for h in response.dimension_headers]
    metric_headers = [h.name for h in response.metric_headers]

    for row in response.rows:
        row_data = {}
        for i, dim_value in enumerate(row.dimension_values):
            row_data[dimension_headers[i]] = dim_value.value
        for i, metric_value in enumerate(row.metric_values):
            row_data[metric_headers[i]] = metric_value.value
        rows.append(row_data)

    return rows


def fetch_traffic_overview(client, property_id, start_date, end_date):
    """Pobiera dzienny przegląd ruchu.

    Metryki: sesje, użytkownicy, nowi użytkownicy, bounce rate,
    engagement rate, średni czas sesji, wyświetlenia stron.

    Returns:
        list[dict]: Dane dzienne.
    """
    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="date")],
        metrics=[
            Metric(name="sessions"),
            Metric(name="totalUsers"),
            Metric(name="newUsers"),
            Metric(name="bounceRate"),
            Metric(name="engagementRate"),
            Metric(name="averageSessionDuration"),
            Metric(name="screenPageViews"),
        ],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
    )

    response = client.run_report(request)
    data = parse_report_response(response)
    print(f"  Przegląd ruchu: {len(data)} dni")
    return data


def fetch_traffic_sources(client, property_id, start_date, end_date):
    """Pobiera ruch wg źródła / medium / kampanii z konwersjami.

    Kluczowe do oceny:
    - Jakie źródła generują ruch
    - Które kampanie przynoszą konwersje i przychód
    - Porównanie ruchu płatnego vs organicznego

    Returns:
        list[dict]: Dane per źródło/medium/kampania.
    """
    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[
            Dimension(name="sessionSource"),
            Dimension(name="sessionMedium"),
            Dimension(name="sessionCampaignName"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="totalUsers"),
            Metric(name="conversions"),
            Metric(name="totalRevenue"),
            Metric(name="bounceRate"),
            Metric(name="engagementRate"),
        ],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        order_bys=[
            OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True
            )
        ],
    )

    response = client.run_report(request)
    data = parse_report_response(response)
    print(f"  Źródła ruchu: {len(data)} kombinacji")
    return data


def fetch_conversions(client, property_id, start_date, end_date):
    """Pobiera konwersje dzienne wg źródeł.

    Skupia się na zdarzeniach zakupu (purchase) i przychodach.

    Returns:
        list[dict]: Dane konwersji dziennych.
    """
    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="sessionSource"),
            Dimension(name="sessionMedium"),
        ],
        metrics=[
            Metric(name="conversions"),
            Metric(name="totalRevenue"),
            Metric(name="purchaseRevenue"),
            Metric(name="ecommercePurchases"),
        ],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        order_bys=[OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))],
    )

    response = client.run_report(request)
    data = parse_report_response(response)
    print(f"  Konwersje: {len(data)} wierszy")
    return data


def fetch_top_pages(client, property_id, start_date, end_date, limit=30):
    """Pobiera top strony wg wyświetleń.

    Przydatne do identyfikacji:
    - Które strony generują największy ruch
    - Które strony mają problemy z bounce rate
    - Strony docelowe kampanii

    Args:
        limit: Maksymalna liczba stron do pobrania.

    Returns:
        list[dict]: Top strony z metrykami.
    """
    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="pagePath")],
        metrics=[
            Metric(name="screenPageViews"),
            Metric(name="sessions"),
            Metric(name="averageSessionDuration"),
            Metric(name="bounceRate"),
            Metric(name="conversions"),
        ],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        order_bys=[
            OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"),
                desc=True,
            )
        ],
        limit=limit,
    )

    response = client.run_report(request)
    data = parse_report_response(response)
    print(f"  Top strony: {len(data)} stron")
    return data


def main():
    """Główna funkcja — pobiera wszystkie dane GA4 i zapisuje jako JSON."""
    args = parse_date_args()
    settings = load_settings()

    property_id = settings.get("ga4", {}).get("property_id", "")
    if not property_id:
        print("BŁĄD: Uzupełnij ga4.property_id w config/settings.yaml", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Pobieranie danych GA4 (property: {property_id})")
    print(f"Okres: {args.start} → {args.end}")
    print(f"{'='*60}\n")

    # Autentykacja
    credentials = get_oauth_credentials()
    client = create_ga4_client(credentials)

    # Pobieranie danych
    print("Pobieranie danych...")

    traffic = fetch_traffic_overview(client, property_id, args.start, args.end)
    save_json(traffic, "ga4_traffic.json", args.run_date)

    sources = fetch_traffic_sources(client, property_id, args.start, args.end)
    save_json(sources, "ga4_sources.json", args.run_date)

    conversions = fetch_conversions(client, property_id, args.start, args.end)
    save_json(conversions, "ga4_conversions.json", args.run_date)

    top_pages = fetch_top_pages(client, property_id, args.start, args.end)
    save_json(top_pages, "ga4_pages.json", args.run_date)

    print(f"\n✅ Dane GA4 pobrane pomyślnie → data/{args.run_date}/")


if __name__ == "__main__":
    main()
