"""
Pobieranie danych z Google Ads API.

Pobiera:
- Performance kampanii (koszt, konwersje, ROAS, CTR, CPC)
- Słowa kluczowe z quality score
- Wyszukiwane frazy (search terms) — kluczowe do identyfikacji wasted spend
- Historia zmian (change history) — co agencja zmieniała

Wymagania:
- Google Ads API włączone w Google Cloud
- Developer Token z API Center w panelu Google Ads
- OAuth2 credentials w config/credentials.json
- customer_id i developer_token w config/settings.yaml
"""

import sys
from datetime import datetime
from pathlib import Path

# Dodaj katalog scripts do ścieżki importów
sys.path.insert(0, str(Path(__file__).resolve().parent))

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

from utils import get_oauth_credentials, load_settings, parse_date_args, save_json


def create_ads_client(settings, credentials):
    """Tworzy klienta Google Ads API.

    Konfiguruje klienta programatycznie (bez pliku google-ads.yaml)
    używając OAuth2 credentials i developer token z settings.

    Args:
        settings: Konfiguracja z settings.yaml.
        credentials: OAuth2 credentials.

    Returns:
        GoogleAdsClient: Skonfigurowany klient.
    """
    ads_settings = settings.get("google_ads", {})
    developer_token = ads_settings.get("developer_token", "")
    login_customer_id = ads_settings.get("login_customer_id", "")

    if not developer_token:
        print(
            "BŁĄD: Uzupełnij google_ads.developer_token w config/settings.yaml",
            file=sys.stderr,
        )
        sys.exit(1)

    config = {
        "developer_token": developer_token,
        "use_proto_plus": True,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "refresh_token": credentials.refresh_token,
    }

    if login_customer_id:
        config["login_customer_id"] = login_customer_id.replace("-", "")

    return GoogleAdsClient.load_from_dict(config)


def normalize_customer_id(customer_id):
    """Usuwa myślniki z customer ID.

    Args:
        customer_id: ID klienta, np. "123-456-7890" lub "1234567890".

    Returns:
        str: ID bez myślników.
    """
    return str(customer_id).replace("-", "")


def fetch_campaigns(client, customer_id, start_date, end_date):
    """Pobiera performance kampanii.

    Metryki per kampania: wydatki, konwersje, wartość konwersji, ROAS,
    wyświetlenia, kliknięcia, CTR, średni CPC.

    Returns:
        list[dict]: Dane kampanii.
    """
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_per_conversion
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
    """

    campaigns = []
    try:
        response = ga_service.search(customer_id=customer_id, query=query)
        for row in response:
            cost = row.metrics.cost_micros / 1_000_000  # Micros → PLN/waluta
            conv_value = row.metrics.conversions_value
            roas = round(conv_value / cost, 2) if cost > 0 else 0

            campaigns.append(
                {
                    "campaign_id": str(row.campaign.id),
                    "campaign_name": row.campaign.name,
                    "status": row.campaign.status.name,
                    "channel_type": row.campaign.advertising_channel_type.name,
                    "cost": round(cost, 2),
                    "conversions": round(row.metrics.conversions, 2),
                    "conversion_value": round(conv_value, 2),
                    "roas": roas,
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "ctr": round(row.metrics.ctr * 100, 2),  # Na procenty
                    "avg_cpc": round(row.metrics.average_cpc / 1_000_000, 2),
                    "cost_per_conversion": round(
                        row.metrics.cost_per_conversion / 1_000_000, 2
                    ),
                }
            )
    except GoogleAdsException as ex:
        print(f"BŁĄD Google Ads API (kampanie): {ex.failure}", file=sys.stderr)
        sys.exit(1)

    print(f"  Kampanie: {len(campaigns)}")
    return campaigns


def fetch_keywords(client, customer_id, start_date, end_date):
    """Pobiera performance słów kluczowych z quality score.

    Kluczowe do identyfikacji:
    - Słowa które konwertują vs nie konwertują
    - Słowa z niskim quality score (optymalizacja)
    - Wasted spend na nieefektywnych słowach

    Returns:
        list[dict]: Dane słów kluczowych.
    """
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            ad_group.name,
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            ad_group_criterion.quality_info.quality_score,
            campaign.name,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr,
            metrics.average_cpc
        FROM keyword_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND campaign.status != 'REMOVED'
            AND ad_group.status != 'REMOVED'
            AND ad_group_criterion.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
    """

    keywords = []
    try:
        response = ga_service.search(customer_id=customer_id, query=query)
        for row in response:
            cost = row.metrics.cost_micros / 1_000_000
            conv_value = row.metrics.conversions_value
            conversions = row.metrics.conversions
            quality_score = row.ad_group_criterion.quality_info.quality_score

            keywords.append(
                {
                    "keyword": row.ad_group_criterion.keyword.text,
                    "match_type": row.ad_group_criterion.keyword.match_type.name,
                    "ad_group": row.ad_group.name,
                    "campaign": row.campaign.name,
                    "quality_score": quality_score if quality_score > 0 else None,
                    "cost": round(cost, 2),
                    "conversions": round(conversions, 2),
                    "conversion_value": round(conv_value, 2),
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "ctr": round(row.metrics.ctr * 100, 2),
                    "avg_cpc": round(row.metrics.average_cpc / 1_000_000, 2),
                    # Flaga: koszt > 0, konwersje = 0 → potencjalny wasted spend
                    "is_wasted": cost > 0 and conversions == 0,
                }
            )
    except GoogleAdsException as ex:
        print(f"BŁĄD Google Ads API (keywords): {ex.failure}", file=sys.stderr)
        sys.exit(1)

    wasted_count = sum(1 for kw in keywords if kw["is_wasted"])
    print(f"  Słowa kluczowe: {len(keywords)} (wasted: {wasted_count})")
    return keywords


def fetch_search_terms(client, customer_id, start_date, end_date):
    """Pobiera wyszukiwane frazy (search terms report).

    To najważniejsze źródło do identyfikacji:
    - Na co faktycznie wydajemy pieniądze
    - Śmieciowe frazy do wykluczenia (negative keywords)
    - Frazy z potencjałem konwersji

    Uwaga: Google może nie zwracać wszystkich fraz dla małych kont
    (ochrona prywatności użytkowników).

    Returns:
        list[dict]: Dane wyszukiwanych fraz.
    """
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            search_term_view.search_term,
            campaign.name,
            ad_group.name,
            segments.keyword.info.text,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.impressions,
            metrics.clicks,
            metrics.ctr
        FROM search_term_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
    """

    search_terms = []
    try:
        response = ga_service.search(customer_id=customer_id, query=query)
        for row in response:
            cost = row.metrics.cost_micros / 1_000_000
            conversions = row.metrics.conversions

            search_terms.append(
                {
                    "search_term": row.search_term_view.search_term,
                    "matched_keyword": row.segments.keyword.info.text,
                    "campaign": row.campaign.name,
                    "ad_group": row.ad_group.name,
                    "cost": round(cost, 2),
                    "conversions": round(conversions, 2),
                    "conversion_value": round(row.metrics.conversions_value, 2),
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "ctr": round(row.metrics.ctr * 100, 2),
                    "is_wasted": cost > 0 and conversions == 0,
                }
            )
    except GoogleAdsException as ex:
        print(f"BŁĄD Google Ads API (search terms): {ex.failure}", file=sys.stderr)
        sys.exit(1)

    wasted_count = sum(1 for st in search_terms if st["is_wasted"])
    wasted_cost = sum(st["cost"] for st in search_terms if st["is_wasted"])
    print(
        f"  Search terms: {len(search_terms)} "
        f"(wasted: {wasted_count}, koszt: {wasted_cost:.2f})"
    )
    return search_terms


def fetch_change_history(client, customer_id, start_date, end_date):
    """Pobiera historię zmian na koncie — co agencja zmieniała.

    Zwraca informacje o:
    - Kto dokonał zmiany (email)
    - Kiedy
    - Co zmieniono (kampania, grupa, słowo kluczowe, reklama)
    - Typ zmiany (utworzenie, modyfikacja, usunięcie)

    Returns:
        list[dict]: Historia zmian.
    """
    ga_service = client.get_service("GoogleAdsService")

    # Formatuj daty na format wymagany przez change_event
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    query = f"""
        SELECT
            change_event.change_date_time,
            change_event.user_email,
            change_event.change_resource_type,
            change_event.change_resource_name,
            change_event.resource_change_operation,
            change_event.changed_fields,
            change_event.old_resource,
            change_event.new_resource,
            campaign.name
        FROM change_event
        WHERE change_event.change_date_time >= '{start_dt.strftime("%Y-%m-%d")}' 
            AND change_event.change_date_time <= '{end_dt.strftime("%Y-%m-%d")} 23:59:59'
        ORDER BY change_event.change_date_time DESC
        LIMIT 1000
    """

    changes = []
    try:
        response = ga_service.search(customer_id=customer_id, query=query)
        for row in response:
            event = row.change_event
            changes.append(
                {
                    "timestamp": event.change_date_time,
                    "user_email": event.user_email,
                    "resource_type": event.change_resource_type.name,
                    "resource_name": event.change_resource_name,
                    "operation": event.resource_change_operation.name,
                    "changed_fields": str(event.changed_fields),
                    "campaign": row.campaign.name if row.campaign.name else None,
                }
            )
    except GoogleAdsException as ex:
        # Change history może nie być dostępna na wszystkich kontach
        print(
            f"OSTRZEŻENIE: Nie udało się pobrać historii zmian: {ex.failure}",
            file=sys.stderr,
        )
        return []

    # Podsumowanie
    unique_users = set(c["user_email"] for c in changes if c["user_email"])
    print(f"  Historia zmian: {len(changes)} zmian")
    print(f"  Aktywni użytkownicy: {', '.join(unique_users) if unique_users else 'brak'}")
    return changes


def main():
    """Główna funkcja — pobiera wszystkie dane Google Ads i zapisuje jako JSON."""
    args = parse_date_args()
    settings = load_settings()

    ads_settings = settings.get("google_ads", {})
    customer_id = normalize_customer_id(ads_settings.get("customer_id", ""))

    if not customer_id:
        print(
            "BŁĄD: Uzupełnij google_ads.customer_id w config/settings.yaml",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Pobieranie danych Google Ads (customer: {customer_id})")
    print(f"Okres: {args.start} → {args.end}")
    print(f"{'='*60}\n")

    # Autentykacja
    credentials = get_oauth_credentials()
    client = create_ads_client(settings, credentials)

    # Pobieranie danych
    print("Pobieranie danych...")

    campaigns = fetch_campaigns(client, customer_id, args.start, args.end)
    save_json(campaigns, "ads_campaigns.json", args.run_date)

    keywords = fetch_keywords(client, customer_id, args.start, args.end)
    save_json(keywords, "ads_keywords.json", args.run_date)

    search_terms = fetch_search_terms(client, customer_id, args.start, args.end)
    save_json(search_terms, "ads_search_terms.json", args.run_date)

    changes = fetch_change_history(client, customer_id, args.start, args.end)
    save_json(changes, "ads_changes.json", args.run_date)

    # Podsumowanie
    total_cost = sum(c["cost"] for c in campaigns)
    total_conv_value = sum(c["conversion_value"] for c in campaigns)
    total_roas = round(total_conv_value / total_cost, 2) if total_cost > 0 else 0
    wasted = sum(st["cost"] for st in search_terms if st["is_wasted"])

    print(f"\n✅ Dane Google Ads pobrane pomyślnie → data/{args.run_date}/")
    print(f"  Łączny koszt: {total_cost:.2f}")
    print(f"  Łączna wartość konwersji: {total_conv_value:.2f}")
    print(f"  ROAS: {total_roas}")
    print(f"  Wasted spend (search terms): {wasted:.2f}")


if __name__ == "__main__":
    main()
