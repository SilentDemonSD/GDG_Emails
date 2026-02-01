import smtplib
from email.message import EmailMessage

SENDER = "gdgoncampus@miet.ac.in"
RECEIVER = "mysterysd.sd@gmail.com"   # or your personal Gmail for testing

msg = EmailMessage()
msg["Subject"] = "SMTP Relay Test - MIET Org Mail"
msg["From"] = SENDER
msg["To"] = RECEIVER
msg.set_content("This is a test email sent via SMTP Relay (no password).")

try:
    with smtplib.SMTP("smtp-relay.gmail.com", 587, timeout=10) as server:
        server.starttls()
        server.send_message(msg)

    print("✅ SUCCESS: SMTP relay works for this org mail")

except Exception as e:
    print("❌ FAILED: SMTP relay not allowed")
    print(e)
