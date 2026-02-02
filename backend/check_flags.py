"""
Check flag status of emails
"""

import requests
import sys

sys.path.insert(0, '/Users/shahid/Projects/triage/backend')

from app.database import SessionLocal
from app.models import User, Email
from app.services.graph import GraphClient
import asyncio

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


async def check_email_flags():
    db = SessionLocal()
    user = db.query(User).first()

    if not user:
        print("No user found. Please authenticate first.")
        return

    # Get access token
    graph = GraphClient()
    access_token = await graph.get_token(user.email, db)

    # Get first 10 emails
    emails = db.query(Email).filter(
        Email.message_id.isnot(None)
    ).limit(10).all()

    print(f"Checking flag status of first {len(emails)} emails:\n")

    for i, email in enumerate(emails, 1):
        try:
            url = f"{GRAPH_API_BASE}/me/messages/{email.message_id}"
            response = requests.get(url, headers={
                "Authorization": f"Bearer {access_token}"
            }, timeout=30)

            if response.status_code == 200:
                data = response.json()
                flag_status = data.get('flag', {}).get('flagStatus', 'unknown')
                subject = email.subject[:50] if email.subject else "No subject"
                print(f"{i}. {subject}")
                print(f"   Flag status: {flag_status}")
            else:
                print(f"{i}. Error: {response.status_code}")

        except Exception as e:
            print(f"{i}. Error: {str(e)}")

    db.close()


if __name__ == "__main__":
    asyncio.run(check_email_flags())
