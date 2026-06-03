"""One-time interactive login for the Monarch MCP server.

Run this ONCE from a terminal to authenticate and cache a session token:

    python auth_setup.py

It will prompt for your Monarch email, password, and (if MFA is on) a
6-digit code. The resulting token is saved to the session file defined in
config.py. After that, the MCP server reuses the token silently and you
won't need to log in again until it expires.

Nothing is sent anywhere except Monarch's own API. Credentials are not
stored — only the resulting session token is.
"""
import asyncio
import getpass
import os

from monarchmoney import MonarchMoney, RequireMFAException

from config import SESSION_FILE


async def main() -> None:
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    mm = MonarchMoney(session_file=SESSION_FILE)

    email = input("Monarch email: ").strip()
    password = getpass.getpass("Monarch password: ")

    # Optional: a permanent MFA secret avoids re-typing codes on future logins.
    # Find it in Monarch: Settings -> Security -> Enable MFA -> "Two-factor text code".
    mfa_secret = os.environ.get("MONARCH_MFA_SECRET")

    try:
        await mm.login(
            email=email,
            password=password,
            use_saved_session=False,
            save_session=True,
            mfa_secret_key=mfa_secret,
        )
    except RequireMFAException:
        code = input("MFA code (6 digits from your authenticator/SMS): ").strip()
        await mm.multi_factor_authenticate(email, password, code)
        mm.save_session(SESSION_FILE)

    # Confirm it works.
    accounts = await mm.get_accounts()
    n = len(accounts.get("accounts", []))
    print(f"\nSuccess. Session saved to {SESSION_FILE}")
    print(f"Found {n} account(s). You're ready to run the MCP server.")


if __name__ == "__main__":
    asyncio.run(main())
