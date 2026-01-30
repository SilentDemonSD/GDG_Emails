import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SENDER = "cirilabangg@gmail.com"
RECEIVER = "mysterysd.sd@gmail.com"
APP_PASSWORD = "sptu fmem shui oblr"

def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

base = read("base.html")
header = read("blocks/header.html")
divider = read("blocks/divider.html")
content = read("blocks/content.html")
footer = read("blocks/footer.html")

content = (
    content
    .replace("{{FNAME}}", "John")
    .replace("{{DATE}}", "2026/01/30")
)

final_html = (
    base
    .replace("{{HEADER}}", header)
    .replace("{{DIVIDER}}", divider)
    .replace("{{CONTENT}}", content)
    .replace("{{FOOTER}}", footer)
)


msg = MIMEMultipart("alternative")
msg["Subject"] = "Community Partnership Proposal"
msg["From"] = SENDER
msg["To"] = RECEIVER

msg.attach(MIMEText("This email requires HTML support.", "plain"))
msg.attach(MIMEText(final_html, "html"))

with smtplib.SMTP("smtp.gmail.com", 587) as server:
    server.starttls()
    server.login(SENDER, APP_PASSWORD)
    server.send_message(msg)

print("✅ Email sent successfully")
