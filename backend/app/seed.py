"""
Conductor Again — Database Seeding
Creates initial admin user if not exists.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()

from app.auth import hash_password
from app.database import MasterSessionLocal, ensure_master_db
from app.models import User


def seed():
    ensure_master_db()
    db: Session = MasterSessionLocal()

    admin_email = os.getenv("ADMIN_EMAIL", "admin@conductoragain.local")
    admin_password = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")

    existing = db.query(User).filter(User.email == admin_email).first()
    if not existing:
        admin = User(
            email=admin_email,
            password_hash=hash_password(admin_password),
            display_name="Conductor Admin",
            role="admin",
            active=True,
        )
        db.add(admin)
        db.commit()
        print(f"✅ Admin user created: {admin_email}")
    else:
        print(f"ℹ️  Admin user already exists: {admin_email}")

    db.close()


if __name__ == "__main__":
    seed()
