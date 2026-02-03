import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import httpx
import msal
import json
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from ..models.user import User
from ..models.email import Email

load_dotenv()


class GraphClient:
    """
    Microsoft Graph API client for accessing Outlook emails with MSAL OAuth2.

    This client handles authentication and requests to the Microsoft Graph API
    to fetch, send, and manage emails.
    """

    SCOPES = [
        "Mail.ReadWrite",
        "Mail.Send",
        "MailboxSettings.ReadWrite",
        "Tasks.ReadWrite",
        "Calendars.Read",
        "User.Read",
    ]

    def __init__(self):
        self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        self.tenant = os.getenv("MICROSOFT_TENANT", "common")
        self.redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI")
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.authority = f"https://login.microsoftonline.com/{self.tenant}"

        self.msal_app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
        )

    def build_auth_url(self) -> str:
        """
        Generate the Microsoft login URL with required scopes.

        Returns:
            Authorization URL for Microsoft login
        """
        auth_url = self.msal_app.get_authorization_request_url(
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri,
        )
        return auth_url

    async def handle_callback(self, code: str, db: Session) -> Dict:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from Microsoft
            db: Database session for storing tokens

        Returns:
            Dictionary with user info and tokens
        """
        result = self.msal_app.acquire_token_by_authorization_code(
            code,
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri,
        )

        if "error" in result:
            raise Exception(f"Failed to acquire token: {result.get('error_description', result['error'])}")

        access_token = result["access_token"]
        refresh_token = result.get("refresh_token")
        expires_in = result.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Get user info from Graph API
        user_info = await self._get_user_info(access_token)

        # Store or update user in database
        user = db.query(User).filter(User.email == user_info["email"]).first()
        if user:
            user.access_token = access_token
            user.refresh_token = refresh_token
            user.token_expires_at = expires_at
            user.display_name = user_info["display_name"]
        else:
            user = User(
                email=user_info["email"],
                display_name=user_info["display_name"],
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=expires_at,
            )
            db.add(user)

        db.commit()
        db.refresh(user)

        return {
            "user": {
                "email": user.email,
                "display_name": user.display_name,
            },
            "access_token": access_token,
        }

    async def get_token(self, user_email: str, db: Session) -> str:
        """
        Get a valid access token, refreshing if expired.

        Args:
            user_email: Email of the user
            db: Database session

        Returns:
            Valid access token
        """
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise Exception("User not found")

        # Check if token is expired or about to expire (within 5 minutes)
        if user.token_expires_at and user.token_expires_at > datetime.utcnow() + timedelta(minutes=5):
            return user.access_token

        # Token expired, refresh it
        if not user.refresh_token:
            raise Exception("No refresh token available")

        result = self.msal_app.acquire_token_by_refresh_token(
            user.refresh_token,
            scopes=self.SCOPES,
        )

        if "error" in result:
            raise Exception(f"Failed to refresh token: {result.get('error_description', result['error'])}")

        # Update stored tokens
        user.access_token = result["access_token"]
        if "refresh_token" in result:
            user.refresh_token = result["refresh_token"]
        user.token_expires_at = datetime.utcnow() + timedelta(seconds=result.get("expires_in", 3600))

        db.commit()

        return user.access_token

    async def _get_user_info(self, access_token: str) -> Dict:
        """
        Get user information from Microsoft Graph API.

        Args:
            access_token: OAuth access token

        Returns:
            Dictionary with user email and display name
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()

            return {
                "email": data.get("mail") or data.get("userPrincipalName"),
                "display_name": data.get("displayName", ""),
            }

    async def fetch_inbox_emails(self, access_token: str, count: int = 50) -> List[Dict]:
        """
        Fetch emails from the user's inbox using Microsoft Graph API.

        Args:
            access_token: Valid OAuth access token
            count: Number of emails to fetch (default 50)

        Returns:
            List of parsed email dictionaries

        Raises:
            Exception: If the API request fails or token is invalid
        """
        emails = []
        url = f"{self.base_url}/me/mailFolders/inbox/messages"

        params = {
            "$top": min(count, 50),  # Graph API max is 50 per page
            "$orderby": "receivedDateTime desc",
            "$select": "id,immutableId,from,subject,bodyPreview,body,receivedDateTime,importance,conversationId,hasAttachments,isRead,toRecipients,ccRecipients"
        }

        async with httpx.AsyncClient() as client:
            while len(emails) < count:
                try:
                    response = await client.get(
                        url,
                        headers={"Authorization": f"Bearer {access_token}"},
                        params=params if url == f"{self.base_url}/me/mailFolders/inbox/messages" else None
                    )

                    if response.status_code == 401:
                        raise Exception("Token expired or invalid. Please re-authenticate.")

                    response.raise_for_status()
                    data = response.json()

                    # Parse and add emails
                    for email in data.get("value", []):
                        parsed_email = self._parse_email(email)
                        emails.append(parsed_email)

                        if len(emails) >= count:
                            break

                    # Check for pagination
                    next_link = data.get("@odata.nextLink")
                    if not next_link or len(emails) >= count:
                        break

                    url = next_link
                    params = None  # Next link already has params

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401:
                        raise Exception("Token expired or invalid. Please re-authenticate.")
                    raise Exception(f"Failed to fetch emails: {str(e)}")
                except Exception as e:
                    raise Exception(f"Error fetching emails: {str(e)}")

        return emails

    def _parse_email(self, email_data: Dict) -> Dict:
        """
        Parse raw email data from Graph API into our format.

        Args:
            email_data: Raw email data from Microsoft Graph API

        Returns:
            Dictionary with parsed email fields
        """
        from_field = email_data.get("from", {}).get("emailAddress", {})

        return {
            "message_id": email_data.get("id"),
            "immutable_id": email_data.get("immutableId"),
            "from_address": from_field.get("address", ""),
            "from_name": from_field.get("name", ""),
            "subject": email_data.get("subject", ""),
            "body_preview": email_data.get("bodyPreview", ""),
            "body": email_data.get("body", {}).get("content", ""),
            "received_at": datetime.fromisoformat(email_data.get("receivedDateTime", "").replace("Z", "+00:00")),
            "importance": email_data.get("importance", "normal").lower(),
            "conversation_id": email_data.get("conversationId", ""),
            "has_attachments": email_data.get("hasAttachments", False),
            "is_read": email_data.get("isRead", False),
            "to_recipients": json.dumps([
                {"name": r.get("emailAddress", {}).get("name", ""),
                 "address": r.get("emailAddress", {}).get("address", "")}
                for r in email_data.get("toRecipients", [])
            ]),
            "cc_recipients": json.dumps([
                {"name": r.get("emailAddress", {}).get("name", ""),
                 "address": r.get("emailAddress", {}).get("address", "")}
                for r in email_data.get("ccRecipients", [])
            ]),
        }

    def store_emails(self, emails: List[Dict], db: Session) -> int:
        """
        Store fetched emails in the database.

        Args:
            emails: List of parsed email dictionaries
            db: Database session

        Returns:
            Number of new emails added

        Note:
            - Checks for existing emails by message_id
            - Only inserts new emails with status='unprocessed'
        """
        new_count = 0

        for email_data in emails:
            # Check if email already exists
            existing = db.query(Email).filter(
                Email.message_id == email_data["message_id"]
            ).first()

            if existing:
                continue

            # Create new email record
            email = Email(
                message_id=email_data["message_id"],
                immutable_id=email_data.get("immutable_id"),
                from_address=email_data["from_address"],
                from_name=email_data["from_name"],
                subject=email_data["subject"],
                body_preview=email_data["body_preview"],
                body=email_data["body"],
                received_at=email_data["received_at"],
                importance=email_data["importance"],
                conversation_id=email_data["conversation_id"],
                has_attachments=email_data["has_attachments"],
                is_read=email_data["is_read"],
                to_recipients=email_data["to_recipients"],
                cc_recipients=email_data["cc_recipients"],
                status="unprocessed",
                folder="inbox"
            )

            db.add(email)
            new_count += 1

        db.commit()
        return new_count

    async def authenticate(self, access_token: str):
        """
        Set the access token for API requests.

        Args:
            access_token: OAuth access token from MSAL
        """
        self.access_token = access_token

    async def get_messages(
        self,
        folder: str = "inbox",
        top: int = 50,
        skip: int = 0,
        filter_query: str = None
    ) -> List[Dict]:
        """
        Placeholder: Fetch messages from Microsoft Graph API.

        Args:
            folder: Folder name (inbox, sent, drafts, etc.)
            top: Number of messages to fetch
            skip: Number of messages to skip
            filter_query: OData filter query

        Returns:
            List of email message dictionaries

        TODO: Implement actual Graph API call
        """
        # TODO: Implement actual API request
        return []

    async def get_message_by_id(self, message_id: str) -> Optional[Dict]:
        """
        Placeholder: Fetch a single message by ID.

        Args:
            message_id: Message ID

        Returns:
            Email message dictionary or None

        TODO: Implement actual Graph API call
        """
        # TODO: Implement actual API request
        return None

    async def send_message(self, to: str, subject: str, body: str) -> Dict:
        """
        Placeholder: Send an email message.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (HTML)

        Returns:
            Sent message dictionary

        TODO: Implement actual Graph API call
        """
        # TODO: Implement actual API request
        return {}

    async def move_message(self, message_id: str, destination_folder: str) -> Dict:
        """
        Placeholder: Move a message to a different folder.

        Args:
            message_id: Message ID
            destination_folder: Destination folder name

        Returns:
            Updated message dictionary

        TODO: Implement actual Graph API call
        """
        # TODO: Implement actual API request
        return {}
