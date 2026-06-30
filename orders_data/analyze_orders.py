"""Analiza zamówień CSV vs GA4 vs Google Ads dla okresu 2026-06-09 — 2026-06-30."""

import csv
from datetime import datetime

CSV_PATH = "orders_data/default_orders_20260630-061114.csv"
START = datetime(2026, 6, 9)
END = datetime(2026, 6, 30, 23, 59, 59)

orders_in_range = []
all_orders = []
status_map = {}

with open(CSV_PATH, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter=";")
    for row in reader:
        dt_str = row["order_date_time"]
        # Parse ISO format: 2026-05-04T08:01:00.901+00:00
        dt = datetime.fromisoformat(dt_str)
        dt_naive = dt.replace(tzinfo=None)
        
        amount = float(row["amount_total"])
        status_id = row["order_state_id"]
        order_num = row["order_number"]
        
        order = {
            "number": order_num,
            "date": dt_naive.strftime("%Y-%m-%d"),
            "datetime": dt_naive.strftime("%Y-%m-%d %H:%M"),
            "amount": amount,
            "status_id": status_id,
            "customer": f"{row['customer_firstname']} {row['customer_lastname']}",
            "city": row["billing_address_city"],
            "items": row.get("line_items", ""),
        }
        all_orders.append(order)
        
        # Track unique statuses
        if status_id not in status_map:
            status_map[status_id] = []
        status_map[status_id].append(order_num)
        
        if START <= dt_naive <= END:
            orders_in_range.append(order)

print("=" * 70)
print("ANALIZA ZAMÓWIEŃ CSV — ILLUMINART")
print(f"Plik: {CSV_PATH}")
print(f"Zakres analizy: {START.date()} — {END.date()}")
print("=" * 70)

print(f"\nŁączna liczba zamówień w pliku: {len(all_orders)}")
print(f"Zamówienia w analizowanym okresie: {len(orders_in_range)}")

# Status IDs
print(f"\nUnikalne statusy zamówień ({len(status_map)}):")
for sid, nums in status_map.items():
    print(f"  {sid}: {len(nums)} zamówień ({', '.join(nums[:5])}{'...' if len(nums) > 5 else ''})")

# Orders in range details
print(f"\n{'='*70}")
print("ZAMÓWIENIA W OKRESIE 2026-06-09 — 2026-06-30")
print(f"{'='*70}")

total = 0
for o in sorted(orders_in_range, key=lambda x: x["datetime"]):
    total += o["amount"]
    n_items = o["items"].count("|") + 1 if o["items"] else 0
    print(f"  #{o['number']}  {o['date']}  {o['amount']:>8.0f} PLN  {o['city']:<20s}  {n_items} poz.  status: ...{o['status_id'][-8:]}")

print(f"\n  {'─'*50}")
print(f"  SUMA: {total:.0f} PLN ({len(orders_in_range)} zamówień)")
print(f"  Średni koszyk (AOV): {total/len(orders_in_range):.0f} PLN" if orders_in_range else "")

# Daily breakdown
print(f"\n{'='*70}")
print("ROZKŁAD DZIENNY")
print(f"{'='*70}")
daily = {}
for o in orders_in_range:
    d = o["date"]
    if d not in daily:
        daily[d] = {"count": 0, "total": 0}
    daily[d]["count"] += 1
    daily[d]["total"] += o["amount"]

for d in sorted(daily.keys()):
    print(f"  {d}: {daily[d]['count']} zamów.  {daily[d]['total']:.0f} PLN")

# All orders summary for full picture
print(f"\n{'='*70}")
print("WSZYSTKIE ZAMÓWIENIA (pełny CSV)")
print(f"{'='*70}")
for o in sorted(all_orders, key=lambda x: x["datetime"]):
    print(f"  #{o['number']}  {o['date']}  {o['amount']:>8.0f} PLN  ...{o['status_id'][-8:]}")

full_total = sum(o["amount"] for o in all_orders)
print(f"\n  SUMA PEŁNA: {full_total:.0f} PLN ({len(all_orders)} zamówień)")
