"""Populate the database with a realistic demo tenant.

    python -m scripts.seed_demo               # uses DATABASE_URL from .env
    python -m scripts.seed_demo --email me@example.com

Creates (or reuses) a user + company, a fake connected bot, branches, vacancies with
questions, and a handful of candidates and applications spread over the last few weeks so
the dashboard and kanban have something to show.

The bot row carries a syntactically valid but non-functional token: it exercises the panel
without touching Telegram. Connect a real bot through the UI when you want the bot half.
"""

import argparse
import asyncio
import random
import secrets
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.crypto import encrypt
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import (
    Application,
    ApplicationStatusHistory,
    Bot,
    Branch,
    Candidate,
    Company,
    CompanyMember,
    News,
    Question,
    User,
    Vacancy,
)

BRANCHES = [
    ("Филиал Чиланзар", "Ташкент", "ул. Бунёдкор, 12", 41.2756, 69.2035),
    ("Филиал Юнусабад", "Ташкент", "ул. Амира Темура, 108", 41.3639, 69.2878),
    ("Филиал Самарканд", "Самарканд", "ул. Регистан, 4", 39.6547, 66.9758),
]

NEWS = [
    ("Открылся новый филиал на Юнусабаде",
     "Ждём вас каждый день с 8:00 до 23:00. Для новых сотрудников — обучение с нуля."),
    ("Повышаем зарплаты бариста",
     "С октября ставка выросла на 15%. Ищем ребят в утреннюю и вечернюю смены."),
    ("Мы в Instagram",
     "Публикуем закулисье кофеен и новые вакансии первыми."),
]

VACANCIES = [
    ("Бариста", "Готовим кофе и делаем гостям хорошее утро. Обучение с нуля.",
     4_000_000, 6_000_000),
    ("Кассир", "Работа на кассе, приём оплаты, помощь гостям.", 3_500_000, 5_000_000),
    ("Администратор зала", "Следите за порядком в зале и работой смены.", 6_000_000, 9_000_000),
    ("Курьер", "Доставка заказов по городу. График свободный.", 3_000_000, 7_000_000),
]

QUESTIONS = [
    {"text": "Сколько вам лет?", "type": "number", "validation": {"min": 16, "max": 70}},
    {"text": "Ваш номер телефона", "type": "phone"},
    {
        "text": "Есть ли опыт работы в общепите?",
        "type": "single_choice",
        "options": ["Нет опыта", "До 1 года", "1–3 года", "Больше 3 лет"],
    },
    {
        "text": "В какие смены готовы работать?",
        "type": "multi_choice",
        "options": ["Утро", "День", "Вечер", "Выходные"],
    },
    {"text": "Расскажите о себе", "type": "long_text", "is_required": False},
]

NAMES = [
    ("Азиз", "aziz_k"), ("Малика", "malika_y"), ("Дилшод", "dilshod_r"),
    ("Нилуфар", "nilufar_a"), ("Тимур", "timur_s"), ("Севара", "sevara_m"),
    ("Жасур", "jasur_t"), ("Камола", "kamola_n"), ("Рустам", None),
    ("Зарина", "zarina_b"), ("Бекзод", "bekzod_i"), ("Феруза", "feruza_o"),
]

STATUSES = [
    "new", "new", "new", "viewed", "viewed",
    "interview", "interview", "offer", "hired", "rejected",
]


async def seed(email: str, password: str) -> None:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email, password_hash=hash_password(password), full_name="Малика Юсупова"
            )
            db.add(user)
            await db.flush()
            print(f"✓ user      {email} / {password}")
        else:
            print(f"· user      {email} (existing)")

        membership = await db.scalar(
            select(CompanyMember).where(CompanyMember.user_id == user.id)
        )
        if membership is None:
            company = Company(
                name="Acme Coffee",
                slug=f"acme-coffee-{secrets.token_hex(3)}",
                branches_enabled=True,
            )
            db.add(company)
            await db.flush()
            db.add(CompanyMember(company_id=company.id, user_id=user.id, role="owner"))
        else:
            company = await db.get(Company, membership.company_id)
            company.branches_enabled = True
        print(f"✓ company   {company.name}")

        if await db.scalar(select(Bot).where(Bot.company_id == company.id)) is None:
            db.add(
                Bot(
                    company_id=company.id,
                    # Syntactically valid, deliberately non-functional.
                    token_encrypted=encrypt(
                        f"{random.randint(10**9, 10**10)}:AA{secrets.token_urlsafe(24)}"
                    ),
                    bot_username="acme_coffee_hr_bot",
                    webhook_secret=secrets.token_urlsafe(32),
                    welcome_message="👋 Привет! Мы Acme Coffee. Выберите филиал и откликайтесь.",
                    about_text=(
                        "Сеть кофеен Acme Coffee. 3 филиала, дружная команда, "
                        "обучение с нуля."
                    ),
                    after_apply_message=(
                        "Спасибо! Мы свяжемся с вами в течение 2 рабочих дней ☕️"
                    ),
                )
            )
            print("✓ bot       @acme_coffee_hr_bot (demo token — not on Telegram)")

        await db.flush()

        # --- branches ---
        branches: list[Branch] = list(
            (await db.scalars(select(Branch).where(Branch.company_id == company.id))).all()
        )
        if not branches:
            for order, (name, city, address, lat, lon) in enumerate(BRANCHES):
                branch = Branch(
                    company_id=company.id, name=name, city=city, address=address,
                    latitude=lat, longitude=lon, sort_order=order,
                )
                db.add(branch)
                branches.append(branch)
            await db.flush()
        print(f"✓ branches  {len(branches)}")

        # --- vacancies + questions ---
        vacancies: list[Vacancy] = list(
            (await db.scalars(select(Vacancy).where(Vacancy.company_id == company.id))).all()
        )
        if not vacancies:
            for order, (title, description, low, high) in enumerate(VACANCIES):
                vacancy = Vacancy(
                    company_id=company.id,
                    # Leave the last one unassigned so the bot's "general vacancies" bucket
                    # and the branch filters both have data.
                    branch_id=branches[order].id if order < len(branches) else None,
                    title=title,
                    description=description,
                    city=branches[order].city if order < len(branches) else "Ташкент",
                    employment_type="full_time",
                    salary_from=low,
                    salary_to=high,
                    status="active",
                    # First two are featured, so the 🔥 / 🌐 split has both halves.
                    is_hot=order < 2,
                    sort_order=order,
                )
                db.add(vacancy)
                vacancies.append(vacancy)
            await db.flush()

            for order, spec in enumerate(QUESTIONS):
                db.add(Question(company_id=company.id, vacancy_id=None, sort_order=order, **spec))
            await db.flush()
        print(f"✓ vacancies {len(vacancies)}  (+ {len(QUESTIONS)} company-wide questions)")

        # --- news + contacts ---
        if not await db.scalar(select(News).where(News.company_id == company.id).limit(1)):
            for order, (title, content) in enumerate(NEWS):
                db.add(
                    News(
                        company_id=company.id, title=title, content=content, sort_order=order
                    )
                )
            print(f"✓ news      {len(NEWS)}")

        bot_row = await db.scalar(select(Bot).where(Bot.company_id == company.id))
        if bot_row is not None and not bot_row.contacts_text:
            bot_row.contacts_text = (
                "☎️ +998 90 123 45 67\n"
                "🕗 Ежедневно 08:00–23:00\n"
                "📍 Ташкент, ул. Бунёдкор, 12"
            )
        await db.flush()

        # --- candidates + applications ---
        existing = await db.scalar(
            select(Application).where(Application.company_id == company.id).limit(1)
        )
        if existing is not None:
            print("· applications already present — skipping")
            await db.commit()
            return

        questions = list(
            (
                await db.scalars(
                    select(Question)
                    .where(Question.company_id == company.id)
                    .order_by(Question.sort_order)
                )
            ).all()
        )

        # A Telegram account maps to exactly one candidate platform-wide, so
        # `telegram_user_id` is globally UNIQUE. Seeding a second demo tenant would collide
        # on a fixed base — pick a random one per run instead.
        tg_base = random.randint(500_000_000, 900_000_000)

        created = 0
        for index, (first_name, username) in enumerate(NAMES):
            candidate = Candidate(
                telegram_user_id=tg_base + index,
                telegram_username=username,
                first_name=first_name,
                phone=f"+9989{random.randint(10, 99)}{random.randint(1000000, 9999999)}"[:13],
            )
            db.add(candidate)
            await db.flush()

            vacancy = vacancies[index % len(vacancies)]
            status = STATUSES[index % len(STATUSES)]
            created_at = datetime.now(UTC) - timedelta(
                days=random.randint(0, 25), hours=random.randint(0, 23)
            )

            answers = []
            for q in questions:
                if q.type == "number":
                    answer = str(random.randint(18, 45))
                elif q.type == "phone":
                    answer = candidate.phone
                elif q.type == "single_choice":
                    answer = random.choice(q.options)
                elif q.type == "multi_choice":
                    answer = random.sample(q.options, random.randint(1, len(q.options)))
                elif not q.is_required and random.random() < 0.4:
                    answers.append(
                        {"question_id": q.id.hex, "question_text": q.text, "type": q.type,
                         "answer": None, "skipped": True}
                    )
                    continue
                else:
                    answer = "Люблю кофе и работу с людьми. Готов учиться."
                answers.append(
                    {"question_id": q.id.hex, "question_text": q.text, "type": q.type,
                     "answer": answer, "skipped": False}
                )

            application = Application(
                company_id=company.id,
                vacancy_id=vacancy.id,
                candidate_id=candidate.id,
                status=status,
                answers=answers,
                created_at=created_at,
            )
            db.add(application)
            await db.flush()

            db.add(
                ApplicationStatusHistory(
                    application_id=application.id, from_status=None, to_status="new",
                    created_at=created_at,
                )
            )
            if status != "new":
                db.add(
                    ApplicationStatusHistory(
                        application_id=application.id, from_status="new", to_status=status,
                        changed_by=user.id, created_at=created_at + timedelta(hours=6),
                    )
                )
            created += 1

        await db.commit()
        print(f"✓ applications {created}")
        print(f"\nSign in at http://localhost:5173 with {email} / {password}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default="demo@talento.uz")
    parser.add_argument("--password", default="demo-password-123")
    args = parser.parse_args()
    asyncio.run(seed(args.email, args.password))
    return 0


if __name__ == "__main__":
    sys.exit(main())
