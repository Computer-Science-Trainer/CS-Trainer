import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_ADDRESS = os.getenv("FROM_EMAIL", SMTP_USER)


def send_email(to_address: str, subject: str, body: str):
    msg = MIMEMultipart()
    msg["From"] = FROM_ADDRESS
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def send_verification_email(to_address: str, code: str):
    subject = "Your CS-Trainer Verification Code"
    body = f"Your verification code is: {code}"
    send_email(to_address, subject, body)
