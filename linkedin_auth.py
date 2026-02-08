#! /usr/bin/env python3
"""
LinkedIn OAuth2 helper script for DataForge.

Guides you through the OAuth2 flow to obtain a LinkedIn access token
for auto-posting blog posts.

Required environment variables:
  CLIENT_ID      - LinkedIn app client ID
  CLIENT_SECRET  - LinkedIn app client secret
  REDIRECT_URL   - OAuth redirect URL (e.g., http://localhost:8000/callback)

Usage:
  export CLIENT_ID=your_client_id
  export CLIENT_SECRET=your_client_secret
  export REDIRECT_URL=http://localhost:8000/callback
  python3 linkedin_auth.py
"""

import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REDIRECT_URL = os.environ.get("REDIRECT_URL", "http://localhost:8000/callback")

if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: CLIENT_ID and CLIENT_SECRET environment variables are required.")
    print()
    print("Set them before running this script:")
    print("  export CLIENT_ID=your_client_id")
    print("  export CLIENT_SECRET=your_client_secret")
    sys.exit(1)

try:
    from linkedin_api.clients.auth.client import AuthClient
except ImportError:
    print("Error: linkedin-api-python-client is not installed.")
    print("Install with: pip install linkedin-api-python-client")
    sys.exit(1)

auth_client = AuthClient(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_url=REDIRECT_URL)

auth_url = auth_client.generate_member_auth_url(scopes=["w_member_social"])

print("Opening LinkedIn authorization page in your browser...")
print(f"If it doesn't open automatically, visit:\n  {auth_url}")
print()
webbrowser.open(auth_url)

# Capture the authorization code via a temporary local server
auth_code = None
parsed_redirect = urlparse(REDIRECT_URL)
port = parsed_redirect.port or 8000


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = parse_qs(urlparse(self.path).query)
        if "code" in query:
            auth_code = query["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization successful!</h1><p>You can close this tab.</p>")
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            error = query.get("error", ["unknown"])[0]
            self.wfile.write(f"<h1>Authorization failed</h1><p>Error: {error}</p>".encode())

    def log_message(self, format, *args):
        pass  # Suppress default logging


print(f"Waiting for callback on port {port}...")
server = HTTPServer(("localhost", port), CallbackHandler)
server.handle_request()

if not auth_code:
    print("Error: No authorization code received.")
    sys.exit(1)

print("Exchanging authorization code for access token...")
token_response = auth_client.exchange_auth_code_for_access_token(auth_code)

access_token = token_response.access_token
print()
print("Success! Your LinkedIn access token:")
print(f"  {access_token}")
print()
print("Set it as an environment variable for DataForge:")
print(f'  export LINKEDIN_ACCESS_TOKEN="{access_token}"')
print()
print("Note: LinkedIn access tokens expire after 60 days.")
print("Re-run this script to obtain a new token when it expires.")
