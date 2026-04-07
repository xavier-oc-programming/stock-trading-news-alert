import os
from pathlib import Path
from dotenv import load_dotenv
from twilio.rest import Client

# Always load .env from the script's directory
dotenv_path = Path(__file__).with_name(".env")
load_dotenv(dotenv_path=dotenv_path)

def require_env(name):
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing {name}")
    return v

ACCOUNT_SID = require_env("TWILIO_ACCOUNT_SID")
AUTH_TOKEN  = require_env("TWILIO_AUTH_TOKEN")
FROM_NUMBER = require_env("TWILIO_FROM")
TO_NUMBER   = require_env("TWILIO_TO")

# Optional: brief masked print to verify values were read
print("SID:", ACCOUNT_SID[:6] + "..." + ACCOUNT_SID[-4:])
print("FROM:", FROM_NUMBER, "TO:", TO_NUMBER)

client = Client(ACCOUNT_SID, AUTH_TOKEN)
msg = client.messages.create(body="Twilio sanity check", from_=FROM_NUMBER, to=TO_NUMBER)
print("OK. Message SID:", msg.sid)
