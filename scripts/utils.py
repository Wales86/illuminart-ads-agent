"""
Wspólne funkcje narzędziowe dla skryptów pobierania danych.

Obsługuje:
- Ładowanie konfiguracji z settings.yaml
- Uwierzytelnianie OAuth2 (z automatycznym odświeżaniem tokenu)
- Zarządzanie katalogami danych (per-run)
- Parsowanie argumentów CLI (zakres dat)
- Zapis danych do JSON
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yaml

# Ścieżki bazowe — relatywne do katalogu głównego projektu
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Zakresy OAuth2 wymagane przez poszczególne API
SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/adwords",
    "https://www.googleapis.com/auth/webmasters.readonly",
]


def load_settings():
    """Ładuje konfigurację z config/settings.yaml.

    Returns:
        dict: Słownik z konfiguracją.

    Raises:
        FileNotFoundError: Gdy plik settings.yaml nie istnieje.
        ValueError: Gdy brakuje wymaganych pól.
    """
    settings_path = CONFIG_DIR / "settings.yaml"
    if not settings_path.exists():
        print(f"BŁĄD: Brak pliku konfiguracji: {settings_path}", file=sys.stderr)
        print("Skopiuj config/settings.yaml i uzupełnij swoje dane.", file=sys.stderr)
        sys.exit(1)

    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    return settings


def get_oauth_credentials():
    """Pobiera OAuth2 credentials z automatycznym odświeżaniem tokenu.

    Przy pierwszym uruchomieniu otwiera przeglądarkę do autoryzacji.
    Przy kolejnych — używa zapisanego token.json z refresh tokenem.

    Returns:
        google.oauth2.credentials.Credentials: Ważne credentials.

    Raises:
        FileNotFoundError: Gdy brak credentials.json.
    """
    # Importy wewnątrz funkcji — nie wymuszamy instalacji przy imporcie modułu
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials_path = CONFIG_DIR / "credentials.json"
    token_path = CONFIG_DIR / "token.json"

    if not credentials_path.exists():
        print(
            f"BŁĄD: Brak pliku OAuth credentials: {credentials_path}", file=sys.stderr
        )
        print(
            "Pobierz credentials.json z Google Cloud Console → APIs & Services → Credentials.",
            file=sys.stderr,
        )
        sys.exit(1)

    creds = None

    # Sprawdź czy istnieje zapisany token
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # Jeśli brak ważnych credentials — odśwież lub autoryzuj od nowa
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Odświeżanie tokenu OAuth2...")
            creds.refresh(Request())
        else:
            print("Wymagana autoryzacja OAuth2 — otwieram przeglądarkę...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Zapisz token do ponownego użycia
        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())
        print(f"Token zapisany: {token_path}")

    return creds


def ensure_data_dir(run_date):
    """Tworzy katalog na dane dla danego uruchomienia.

    Args:
        run_date: Data uruchomienia w formacie YYYY-MM-DD.

    Returns:
        Path: Ścieżka do katalogu danych.
    """
    data_dir = DATA_DIR / run_date
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def save_json(data, filename, run_date):
    """Zapisuje dane do pliku JSON w katalogu danego uruchomienia.

    Args:
        data: Dane do zapisania (dict lub list).
        filename: Nazwa pliku (np. "ga4_traffic.json").
        run_date: Data uruchomienia w formacie YYYY-MM-DD.

    Returns:
        Path: Ścieżka do zapisanego pliku.
    """
    data_dir = ensure_data_dir(run_date)
    filepath = data_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"Zapisano: {filepath}")
    return filepath


def parse_date_args():
    """Parsuje argumenty CLI z zakresem dat.

    Wspiera:
        --start YYYY-MM-DD  Data początkowa
        --end YYYY-MM-DD    Data końcowa
        --run-date YYYY-MM-DD  Identyfikator uruchomienia (domyślnie: dziś)

    Jeśli nie podano --start/--end, używa domyślnego okresu z settings.yaml.

    Returns:
        argparse.Namespace: Sparsowane argumenty z polami start, end, run_date.
    """
    settings = load_settings()
    default_days = settings.get("report", {}).get("default_period_days", 14)
    today = datetime.now().strftime("%Y-%m-%d")

    parser = argparse.ArgumentParser(
        description="Pobieranie danych z Google API"
    )
    parser.add_argument(
        "--start",
        type=str,
        default=(datetime.now() - timedelta(days=default_days)).strftime("%Y-%m-%d"),
        help=f"Data początkowa (YYYY-MM-DD). Domyślnie: {default_days} dni temu.",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=today,
        help="Data końcowa (YYYY-MM-DD). Domyślnie: dziś.",
    )
    parser.add_argument(
        "--run-date",
        type=str,
        default=today,
        help="Identyfikator uruchomienia / katalog danych (YYYY-MM-DD). Domyślnie: dziś.",
    )

    args = parser.parse_args()

    # Walidacja formatu dat
    for date_field in ["start", "end", "run_date"]:
        value = getattr(args, date_field.replace("-", "_"))
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            print(
                f"BŁĄD: Nieprawidłowy format daty dla --{date_field}: '{value}'. "
                f"Oczekiwany format: YYYY-MM-DD",
                file=sys.stderr,
            )
            sys.exit(1)

    print(f"Zakres dat: {args.start} → {args.end}")
    print(f"Run date: {args.run_date}")

    return args
