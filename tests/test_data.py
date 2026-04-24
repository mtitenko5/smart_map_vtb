from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    "client_transactions.csv": [
        "user_id",
        "amount",
        "category",
        "shop",
        "lat",
        "lon",
        "date",
    ],
    "business_metrics.csv": [
        "id",
        "date",
        "new_clients",
        "total_transactions",
        "revenue",
        "average_check",
        "repeat_clients",
    ],
    "business_offers.csv": [
        "id",
        "title",
        "description",
        "discount_percent",
        "valid_from",
        "valid_until",
        "category",
        "min_purchase_amount",
        "usage_count",
        "is_active",
    ],
    "business_users.csv": [
        "login",
    ],
}


def test_required_csv_files_exist():
    for filename in REQUIRED_FILES:
        path = BASE_DIR / filename
        assert path.exists(), f"Missing file: {filename}"


def test_required_csv_columns_exist():
    for filename, expected_columns in REQUIRED_FILES.items():
        df = pd.read_csv(BASE_DIR / filename)
        for column in expected_columns:
            assert column in df.columns, f"{filename} is missing column: {column}"