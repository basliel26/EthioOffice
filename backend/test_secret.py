#!/usr/bin/env python3
import sys
from jose import jwt
import httpx

candidates = [
    "euro-office-secret-change-in-production",
    "secret",
    "onlyoffice",
    "documentserver",
    "jwtsecret",
    "123456",
    "password",
]

target_url = "http://10.18.113.9/coauthoring/CommandService.ashx"

print(f"[*] Testing EuroOffice JWT Secret against {target_url}...\n")

matched = None

with httpx.Client(trust_env=False, timeout=5.0) as client:
    for s in candidates:
        token = jwt.encode({"c": "version"}, s, algorithm="HS256")
        body = {"c": "version", "token": token}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        try:
            r = client.post(target_url, json=body, headers=headers)
            res = r.text.strip()
            if '"error":0' in res or '"error": 0' in res:
                print(f"[SUCCESS] MATCH FOUND! Secret is: '{s}'")
                print(f"          Response: {res}")
                matched = s
                break
            else:
                print(f"[-] Tried '{s}': {res}")
        except Exception as e:
            print(f"[!] Error testing '{s}': {e}")

print("-" * 50)
if matched:
    print(f"\n[+] Set EURO_OFFICE_JWT_SECRET=\"{matched}\" in your .env file!")
else:
    print("\n[!] None of the default secrets matched.")
    print("    EuroOffice on 10.18.113.9 has a custom or auto-generated JWT secret.")
    print("    To find the exact secret, run this command on 10.18.113.9:")
    print("    docker exec $(docker ps -q) cat /etc/onlyoffice/documentserver/local.json | grep -i 'secret'\n")
