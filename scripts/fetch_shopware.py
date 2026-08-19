"""
Pobieranie danych o zamówieniach ze sklepu Shopware 6 (Admin API).

Pobiera:
- Zamówienia w zadanym zakresie dat
- Wartość zamówień (brutto / netto), walutę
- Statusy realizacji i płatności
- Podsumowanie przychodów, liczby transakcji i AOV
- Zapisuje do data/{run_date}/shopware_orders.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import requests

from utils import ensure_data_dir, load_settings, parse_date_args, save_json


def get_shopware_token(shop_url, client_id, client_secret):
    """Pobiera token OAuth2 z Shopware 6 Admin API."""
    token_url = f"{shop_url.rstrip('/')}/api/oauth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    try:
        res = requests.post(token_url, json=payload, timeout=15)
        if res.status_code != 200:
            print(
                f"BŁĄD autoryzacji Shopware: {res.status_code} - {res.text}",
                file=sys.stderr,
            )
            return None
        return res.json().get("access_token")
    except Exception as e:
        print(f"BŁĄD połączenia z Shopware: {e}", file=sys.stderr)
        return None


def fetch_orders(shop_url, token, start_date, end_date):
    """Pobiera listę zamówień z Shopware 6 w zadanym zakresie dat."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    order_url = f"{shop_url.rstrip('/')}/api/search/order"

    start_iso = f"{start_date}T00:00:00.000Z"
    end_iso = f"{end_date}T23:59:59.999Z"

    payload = {
        "filter": [
            {
                "type": "range",
                "field": "orderDateTime",
                "parameters": {
                    "gte": start_iso,
                    "lte": end_iso,
                },
            }
        ],
        "associations": {
            "stateMachineState": {},
            "lineItems": {},
            "transactions": {
                "associations": {
                    "stateMachineState": {}
                }
            }
        },
        "sort": [
            {
                "field": "orderDateTime",
                "order": "ASC"
            }
        ],
        "limit": 500,
    }

    try:
        res = requests.post(order_url, headers=headers, json=payload, timeout=30)
        if res.status_code != 200:
            print(
                f"BŁĄD pobierania zamówień Shopware: {res.status_code} - {res.text}",
                file=sys.stderr,
            )
            return None
        return res.json()
    except Exception as e:
        print(f"BŁĄD zapytania o zamówienia: {e}", file=sys.stderr)
        return None


def process_orders(raw_data):
    """Przetwarza surowe dane z Shopware do formatu analitycznego."""
    orders_list = raw_data.get("data", [])
    total_found = raw_data.get("total", len(orders_list))

    processed_orders = []
    daily_stats = {}
    total_revenue = 0.0
    valid_orders_count = 0
    cancelled_orders_count = 0

    for o in orders_list:
        order_num = o.get("orderNumber")
        date_time = o.get("orderDateTime", "")
        date_str = date_time[:10] if date_time else "unknown"
        amount_total = float(o.get("amountTotal", 0.0))
        amount_net = float(o.get("amountNet", 0.0))
        state = o.get("stateMachineState", {}).get("technicalName", "unknown")
        
        # Pobierz status płatności jeśli dostępny
        tx_list = o.get("transactions", [])
        tx_state = "unknown"
        if tx_list and len(tx_list) > 0:
            tx_state = tx_list[0].get("stateMachineState", {}).get("technicalName", "unknown")

        # Pozycje w zamówieniu
        items = []
        for item in o.get("lineItems", []):
            items.append({
                "label": item.get("label"),
                "quantity": item.get("quantity"),
                "unit_price": item.get("unitPrice"),
                "total_price": item.get("totalPrice"),
            })

        is_cancelled = (state == "cancelled" or tx_state == "cancelled")
        if is_cancelled:
            cancelled_orders_count += 1
        else:
            valid_orders_count += 1
            total_revenue += amount_total

            # Dzienny rozkład
            if date_str not in daily_stats:
                daily_stats[date_str] = {"revenue": 0.0, "orders": 0}
            daily_stats[date_str]["revenue"] += amount_total
            daily_stats[date_str]["orders"] += 1

        processed_orders.append({
            "order_number": order_num,
            "date_time": date_time,
            "date": date_str,
            "amount_total": amount_total,
            "amount_net": amount_net,
            "state": state,
            "payment_state": tx_state,
            "is_cancelled": is_cancelled,
            "items_count": len(items),
            "items": items,
        })

    aov = (total_revenue / valid_orders_count) if valid_orders_count > 0 else 0.0

    return {
        "summary": {
            "total_orders_found": total_found,
            "valid_orders_count": valid_orders_count,
            "cancelled_orders_count": cancelled_orders_count,
            "total_revenue_gross": round(total_revenue, 2),
            "aov": round(aov, 2),
        },
        "daily_breakdown": daily_stats,
        "orders": processed_orders,
    }


def main():
    args = parse_date_args()
    settings = load_settings()

    sw_config = settings.get("shopware", {})
    shop_url = sw_config.get("url")
    client_id = sw_config.get("client_id")
    client_secret = sw_config.get("client_secret")

    if not shop_url or not client_id or not client_secret:
        print("BŁĄD: Brak konfiguracji Shopware w settings.yaml", file=sys.stderr)
        sys.exit(1)

    print(f"Zakres dat: {args.start} → {args.end}")
    print(f"Run date: {args.run_date}\n")
    print(f"{'='*60}")
    print(f"Pobieranie zamówień ze sklepu Shopware ({shop_url})")
    print(f"Okres: {args.start} → {args.end}")
    print(f"{'='*60}\n")

    token = get_shopware_token(shop_url, client_id, client_secret)
    if not token:
        sys.exit(1)

    raw_orders = fetch_orders(shop_url, token, args.start, args.end)
    if not raw_orders:
        sys.exit(1)

    summary_data = process_orders(raw_orders)
    save_json(summary_data, "shopware_orders.json", args.run_date)

    print("\n✅ Dane Shopware pobrane pomyślnie!")
    s = summary_data["summary"]
    print(f"  Ważne zamówienia: {s['valid_orders_count']} (anulowane: {s['cancelled_orders_count']})")
    print(f"  Przychód brutto ze sklepu: {s['total_revenue_gross']} PLN")
    print(f"  Średni koszyk (AOV): {s['aov']} PLN")


if __name__ == "__main__":
    main()
