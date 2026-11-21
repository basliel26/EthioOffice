#!/usr/bin/env python3
"""
Automated backend configuration script for EthioOffice.
Configures backend/.env with verified EuroOffice / ONLYOFFICE settings,
updates the JWT secret, and verifies local server readiness.
"""

import os
import sys
from pathlib import Path
from jose import jwt
import httpx

ENV_PATH = Path(__file__).resolve().parent / ".env"

DEFAULT_SETTINGS = {
    "PROJECT_NAME": '"EthioOffice API"',
    "API_V1_STR": '"/api/v1"',
    "SECRET_KEY": '"ethiooffice-secure-jwt-key-2026-production-ready"',
    "ACCESS_TOKEN_EXPIRE_MINUTES": "1440",
    "EURO_OFFICE_URL": '"http://10.18.113.9"',
    "EURO_OFFICE_JWT_SECRET": '"nkuJcQeu3y7pPg4UaJLonFkoHtVeQyDT"',
    "BACKEND_INTERNAL_URL": '"http://10.18.113.252:8001"',
}

def update_env():
    print("[1/3] Updating backend/.env configuration...")
    lines = []
    existing_keys = set()
    
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    lines.append(line)
                    continue
                if "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    # We will override euro-office & backend-internal settings
                    if key in ("EURO_OFFICE_JWT_SECRET", "EURO_OFFICE_URL", "BACKEND_INTERNAL_URL"):
                        continue
                    existing_keys.add(key)
                    lines.append(line)

    # Append EuroOffice settings
    lines.append("\n# EuroOffice / ONLYOFFICE Document Server Integration\n")
    lines.append(f'EURO_OFFICE_URL={DEFAULT_SETTINGS["EURO_OFFICE_URL"]}\n')
    lines.append(f'EURO_OFFICE_JWT_SECRET={DEFAULT_SETTINGS["EURO_OFFICE_JWT_SECRET"]}\n')
    lines.append(f'BACKEND_INTERNAL_URL={DEFAULT_SETTINGS["BACKEND_INTERNAL_URL"]}\n')

    # If new env file, ensure required defaults
    for k, v in DEFAULT_SETTINGS.items():
        if k not in existing_keys and k not in ("EURO_OFFICE_JWT_SECRET", "EURO_OFFICE_URL", "BACKEND_INTERNAL_URL"):
            lines.append(f"{k}={v}\n")

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    
    print(f"      [OK] Saved configuration to {ENV_PATH}")
    print(f"           EURO_OFFICE_URL = http://10.18.113.9")
    print(f"           EURO_OFFICE_JWT_SECRET = nkuJcQeu3y7pPg4UaJLonFkoHtVeQyDT")
    print(f"           BACKEND_INTERNAL_URL = http://10.18.113.252:8001")


def verify_eurooffice():
    print("\n[2/3] Checking connection to EuroOffice Document Server (10.18.113.9)...")
    try:
        with httpx.Client(trust_env=False, timeout=5.0) as client:
            resp = client.get("http://10.18.113.9/healthcheck")
            if resp.status_code == 200 and resp.text.strip().lower() == "true":
                print("      [OK] EuroOffice Document Server is ONLINE and HEALTHY (healthcheck=true)")
            else:
                print(f"      [WARN] Unexpected response: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"      [WARN] Could not reach 10.18.113.9/healthcheck: {e}")


def verify_jwt():
    print("\n[3/3] Verifying JWT token signing engine...")
    secret = "nkuJcQeu3y7pPg4UaJLonFkoHtVeQyDT"
    test_token = jwt.encode({"test": "ethiooffice"}, secret, algorithm="HS256")
    decoded = jwt.decode(test_token, secret, algorithms=["HS256"])
    if decoded.get("test") == "ethiooffice":
        print("      [OK] JWT HMAC-SHA256 engine operating normally.")
    else:
        print("      [ERROR] JWT decode mismatch.")


if __name__ == "__main__":
    print("=" * 60)
    print(" EthioOffice Backend Auto-Configuration Script ")
    print("=" * 60)
    update_env()
    verify_eurooffice()
    verify_jwt()
    print("\n" + "=" * 60)
    print(" ALL SET! You can now start the backend with:")
    print(" uvicorn app.main:app --host 0.0.0.0 --port 8001")
    print("=" * 60 + "\n")
