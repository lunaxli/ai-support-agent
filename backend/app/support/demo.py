"""Optional demo accounts for a local development database."""

import argparse

from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.core.db import engine
from app.models import User, UserCreate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--password", required=True, help="Password for freshly created demo users"
    )
    args = parser.parse_args()
    if settings.FASTAPI_ENV != "development":
        parser.error("Demo accounts require FASTAPI_ENV=development")
    if not 8 <= len(args.password) <= 128:
        parser.error("Use 8–128 characters")
    with Session(engine) as session:
        for email, name, staff in (
            ("customer@example.com", "演示客户", False),
            ("agent@example.com", "演示客服", True),
        ):
            user = session.exec(select(User).where(User.email == email)).first()
            if user is not None:
                continue
            user = crud.create_user(
                session=session,
                user_create=UserCreate(
                    email=email,
                    full_name=name,
                    password=args.password,
                ),
            )
            user.is_support_agent = staff
            session.add(user)
            session.commit()


if __name__ == "__main__":
    main()
