"""Skrypt do ręcznej re-autoryzacji OAuth2 (console flow).

Wyświetla URL do skopiowania w przeglądarkę, a następnie czeka
na wklejenie kodu autoryzacyjnego.
"""

import argparse
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/adwords",
    "https://www.googleapis.com/auth/webmasters.readonly",
]

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def main():
    parser = argparse.ArgumentParser(description="Re-autoryzacja OAuth2")
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port serwera autoryzacji (domyślnie 0 = automatyczny wolny port)",
    )
    args = parser.parse_args()

    credentials_path = CONFIG_DIR / "credentials.json"
    token_path = CONFIG_DIR / "token.json"

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_path), SCOPES
    )

    # Local server flow — drukuje URL, nasłuchuje na wolnym porcie
    creds = flow.run_local_server(port=args.port, open_browser=False)

    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    print("\n✅ Token zapisany pomyślnie w config/token.json!")
    print("Możesz teraz uruchomić skrypty pobierania danych.")


if __name__ == "__main__":
    main()
