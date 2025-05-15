import os
from dotenv import load_dotenv

load_dotenv()

ADMIN_EMAILS = set(os.getenv("ADMIN_EMAILS", "admin@example.com").split(","))