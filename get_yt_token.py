"""
Run this ONCE locally to get your YouTube refresh token.
It opens a browser for Google login, then prints the refresh token.
Store the token as a GitHub Secret.

Usage:
  python get_yt_token.py
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

CLIENT_ID     = input("Paste your Google Client ID: ").strip()
CLIENT_SECRET = input("Paste your Google Client Secret: ").strip()

client_config = {
    "installed": {
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uris": ["http://localhost"],
        "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
        "token_uri":     "https://oauth2.googleapis.com/token",
    }
}

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(port=8080)

print("\n" + "="*60)
print("YOUR REFRESH TOKEN (save this as a GitHub Secret):")
print("="*60)
print(creds.refresh_token)
print("="*60)
print("\nAlso save these:")
print(f"GOOGLE_CLIENT_ID:     {CLIENT_ID}")
print(f"GOOGLE_CLIENT_SECRET: {CLIENT_SECRET}")
