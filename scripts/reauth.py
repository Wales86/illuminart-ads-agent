"""Skrypt do ręcznej re-autoryzacji OAuth2 (console flow).

Wyświetla URL do skopiowania w przeglądarkę, a następnie czeka
na wklejenie kodu autoryzacyjnego.
"""

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
    credentials_path = CONFIG_DIR / "credentials.json"
    token_path = CONFIG_DIR / "token.json"

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_path), SCOPES
    )

    # Console flow — drukuje URL, czeka na wklejenie kodu
    creds = flow.run_local_server(port=8085, open_browser=False)

    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    print("\n✅ Token zapisany pomyślnie w config/token.json!")
    print("Możesz teraz uruchomić skrypty pobierania danych.")


if __name__ == "__main__":
    main()
