#!/usr/bin/env python3
"""Promote a user to super_admin by setting app_metadata.role via Supabase Admin API.

Usage:
    python -m scripts.set_admin_role <email>
    python -m scripts.set_admin_role test@test.com
"""
import sys
import os

# Allow running from backend/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import get_supabase_client


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.set_admin_role <email>")
        sys.exit(1)

    email = sys.argv[1]
    client = get_supabase_client()

    # Find user by email
    users = client.auth.admin.list_users()
    target = None
    for u in users:
        if u.email == email:
            target = u
            break

    if not target:
        print(f"Error: No user found with email '{email}'")
        sys.exit(1)

    # Merge role into existing app_metadata (preserve other fields)
    existing = target.app_metadata or {}
    existing["role"] = "super_admin"

    client.auth.admin.update_user_by_id(
        target.id,
        {"app_metadata": existing},
    )

    print(f"Done. {email} (id={target.id}) is now super_admin.")
    print("The user must sign out and back in for the JWT to update.")


if __name__ == "__main__":
    main()
