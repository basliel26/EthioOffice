"""
EthioOffice Commercial Licensing Field Engineering CLI Tool
Used by deployment engineers to generate, inspect, and verify signed offline license tokens.

Usage examples:
    # Print current host hardware node fingerprint:
    python -m app.cli.licensing_tool fingerprint

    # Issue an offline Enterprise license for Awash Bank:
    python -m app.cli.licensing_tool issue --org awash-bank --tier ENTERPRISE --users 500 --storage 2000 --days 365

    # Issue a node-locked license:
    python -m app.cli.licensing_tool issue --org cbe-bank --tier ENTERPRISE --users 1000 --storage 5000 --node-lock NODE-XXXX-XXXX-XXXX-XXXX

    # Verify a license token:
    python -m app.cli.licensing_tool verify --key EO-LIC.eyJ...
"""

import sys
import json
import argparse
from datetime import datetime, timezone, timedelta

from app.core.licensing import (
    generate_license_token,
    verify_license_token,
    evaluate_license_lifecycle,
    get_server_hardware_fingerprint,
    LicenseTier,
)
from app.services.capability_service import DEFAULT_TIER_CAPABILITIES


def main():
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.licensing_tool",
        description="EthioOffice Commercial Licensing CLI Tool for Field Engineers"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: fingerprint
    subparsers.add_parser("fingerprint", help="Display local host hardware node fingerprint for node-locking")

    # Command: issue
    issue_parser = subparsers.add_parser("issue", help="Issue a cryptographically signed offline license token")
    issue_parser.add_argument("--org", required=True, help="Organization slug (e.g. 'awash-bank')")
    issue_parser.add_argument("--tier", choices=["STARTER", "BUSINESS", "ENTERPRISE"], default="BUSINESS", help="License tier")
    issue_parser.add_argument("--users", type=int, default=50, help="Maximum user seat count")
    issue_parser.add_argument("--storage", type=int, default=100, help="Storage quota in Gigabytes")
    issue_parser.add_argument("--days", type=int, default=365, help="Validity period in days")
    issue_parser.add_argument("--grace", type=int, default=14, help="Grace period in days (default 14)")
    issue_parser.add_argument("--node-lock", dest="node_lock", default=None, help="Target host hardware fingerprint for node-locking")
    issue_parser.add_argument("--features", default=None, help="Comma-separated custom features override")

    # Command: verify
    verify_parser = subparsers.add_parser("verify", help="Inspect and verify an offline license token")
    verify_parser.add_argument("--key", required=True, help="Full license key string")
    verify_parser.add_argument("--org", default=None, help="Expected organization slug")

    args = parser.parse_args()

    if args.command == "fingerprint":
        fp = get_server_hardware_fingerprint()
        print("\n=======================================================")
        print("  EthioOffice Host Hardware Node Fingerprint")
        print("=======================================================")
        print(f"  Fingerprint: {fp}")
        print("  Use this value with --node-lock when issuing node-locked licenses.\n")

    elif args.command == "issue":
        tier_enum = LicenseTier[args.tier.upper()]
        if args.features:
            features = [f.strip().upper() for f in args.features.split(",") if f.strip()]
        else:
            features = [c.value for c in DEFAULT_TIER_CAPABILITIES.get(tier_enum, DEFAULT_TIER_CAPABILITIES[LicenseTier.BUSINESS])]

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=args.days)

        token = generate_license_token(
            organization_slug=args.org,
            tier=args.tier.upper(),
            max_users=args.users,
            storage_limit_gb=args.storage,
            features=features,
            expires_at=expires_at,
            issued_at=now,
            grace_period_days=args.grace,
            machine_fingerprint=args.node_lock,
        )

        print("\n=======================================================")
        print("  EthioOffice License Generated Successfully")
        print("=======================================================")
        print(f"  Organization: {args.org}")
        print(f"  Tier:         {args.tier.upper()}")
        print(f"  Max Seats:    {args.users}")
        print(f"  Storage:      {args.storage} GB")
        print(f"  Valid Until:  {expires_at.strftime('%Y-%m-%d')} ({args.days} days)")
        print(f"  Grace Period: {args.grace} days")
        print(f"  Node-Lock:    {args.node_lock or 'None (Floating on-premise)'}")
        print(f"  Capabilities: {', '.join(features)}")
        print("\n--- LICENSE KEY ---")
        print(token)
        print("-------------------\n")

    elif args.command == "verify":
        is_valid, payload, err = verify_license_token(
            token=args.key,
            expected_org_slug=args.org,
            enforce_node_lock=False,  # CLI inspection allows examining keys from other nodes
        )
        print("\n=======================================================")
        print("  EthioOffice License Key Verification")
        print("=======================================================")
        if not is_valid:
            print(f"  STATUS: REJECTED")
            print(f"  ERROR:  {err}\n")
            sys.exit(1)

        expires_at = datetime.fromisoformat(payload["expires_at"])
        grace_days = payload.get("grace_period_days", 14)
        lifecycle = evaluate_license_lifecycle(expires_at, grace_period_days=grace_days)

        print("  STATUS: CRYPTOGRAPHICALLY VALID")
        print(f"  License ID:       {payload.get('license_id')}")
        print(f"  Organization:     {payload.get('organization_slug')}")
        print(f"  Tier:             {payload.get('tier')}")
        print(f"  Max Users:        {payload.get('max_users')}")
        print(f"  Storage Limit:    {payload.get('storage_limit_gb')} GB")
        print(f"  Issued At:        {payload.get('issued_at')}")
        print(f"  Expires At:       {payload.get('expires_at')}")
        print(f"  Lifecycle State:  {lifecycle['status'].value}")
        print(f"  Days Remaining:   {lifecycle['days_remaining']}")
        print(f"  Grace Days Left:  {lifecycle['grace_days_remaining']}")
        print(f"  Node-Lock:        {payload.get('machine_fingerprint') or 'None (Floating)'}")
        print(f"  Capabilities:     {', '.join(payload.get('features', []))}\n")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
