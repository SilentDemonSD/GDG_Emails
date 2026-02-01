import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SENDER = "cirilabangg@gmail.com"
RECEIVER = "mysterysd.sd@gmail.com" #"kumarhimanshu1104k@gmail.com"
APP_PASSWORD = "sptu fmem shui oblr"

def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

final_html = read("templates/base.html")

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
