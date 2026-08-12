import os
from dotenv import load_dotenv

load_dotenv()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@expensetracker.com")

print("=" * 60)
print("SendGrid Configuration Test")
print("=" * 60)

print(f"\nSMTP_FROM: {SMTP_FROM}")
print(f"SENDGRID_API_KEY: {'SET' if SENDGRID_API_KEY else 'NOT SET'}")

if not SENDGRID_API_KEY:
    print("\nERROR: SENDGRID_API_KEY is not configured!")
    print("   Add it to your .env file:")
    print("   SENDGRID_API_KEY=SG.your_api_key_here")
    exit(1)

print("\n" + "=" * 60)
print("Testing SendGrid Connection...")
print("=" * 60)

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    print("SendGrid libraries imported successfully")

    # Test creating a message (use shikharbhatia106@gmail.com as sender)
    message = Mail(
        from_email="shikharbhatia106@gmail.com",
        to_emails="shikharbhatia106@gmail.com",
        subject="Test Email from Expense Tracker",
        plain_text_content="This is a test email from SendGrid"
    )
    print("Email message created successfully")

    # Test API client
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    print("SendGrid API client initialized successfully")

    # Try to send (will fail with invalid recipient but shows API is working)
    print("\nAttempting to send test email...")
    response = sg.send(message)
    print(f"Email sent! Status Code: {response.status_code}")
    print(f"  If status is 202: Email accepted for delivery")
    print(f"  If status is 400: Invalid recipient (but API works)")

except ImportError as e:
    print(f"Import Error: {e}")
    print("   Run: pip install sendgrid aiohttp")
except Exception as e:
    print(f"Error: {e}")
    print(f"   Error Type: {type(e).__name__}")

print("\n" + "=" * 60)
