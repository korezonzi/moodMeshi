"""Test script: Send a properly signed Slack slash command request to the endpoint."""

import hashlib
import hmac
import os
import time
import urllib.parse

import httpx
from dotenv import load_dotenv

load_dotenv()

SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
TARGET_URL = os.getenv("TEST_URL", "https://moodmeshi.onrender.com/slack/events")

if not SIGNING_SECRET:
    print("ERROR: SLACK_SIGNING_SECRET not found in .env")
    raise SystemExit(1)

# Build slash command payload
body = urllib.parse.urlencode({
    "command": "/meshi",
    "text": "疲れた",
    "user_id": "U_TEST123",
    "user_name": "test_user",
    "team_id": "T_TEST123",
    "channel_id": "C_TEST123",
    "response_url": "https://hooks.slack.com/commands/test",
    "trigger_id": "test_trigger",
})

timestamp = str(int(time.time()))
sig_basestring = f"v0:{timestamp}:{body}"
signature = "v0=" + hmac.new(
    SIGNING_SECRET.encode(),
    sig_basestring.encode(),
    hashlib.sha256,
).hexdigest()

headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Slack-Request-Timestamp": timestamp,
    "X-Slack-Signature": signature,
}

print(f"Sending signed request to: {TARGET_URL}")
print(f"Timestamp: {timestamp}")
print(f"Signature: {signature[:20]}...")

response = httpx.post(TARGET_URL, content=body, headers=headers, timeout=10)
print(f"\nStatus: {response.status_code}")
print(f"Response: {response.text}")
