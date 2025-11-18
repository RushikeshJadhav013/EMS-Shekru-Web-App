"""
Database Migration Script: Add responsibilities & nice_to_have_skills columns to vacancies table

Run this ONCE to update your database schema:

    python add_vacancy_details_columns.py
"""

from sqlalchemy import create_engine, text
from app.core.config import settings

COLUMNS = [
    ("responsibilities", "TEXT"),
    ("nice_to_have_skills", "TEXT"),
]


def add_column_if_missing(connection, column_name, column_type):
    check_query = text(
        """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='vacancies' AND column_name=:column
        """
    )
    result = connection.execute(check_query, {"column": column_name})
    if result.fetchone():
        print(f"✅ Column '{column_name}' already exists on 'vacancies'")
        return

    print(f"Adding '{column_name}' column to 'vacancies'...")
    connection.execute(
        text(f"ALTER TABLE vacancies ADD COLUMN {column_name} {column_type} NULL")
    )
    connection.commit()
    print(f"✅ Added '{column_name}' column.")


def run_migration():
    engine = create_engine(settings.DATABASE_URL)
    try:
        with engine.connect() as connection:
            for column_name, column_type in COLUMNS:
                add_column_if_missing(connection, column_name, column_type)
    finally:
        engine.dispose()


if __name__ == "__main__":
    print("=" * 60)
    print("Database Migration: Add Vacancy Detail Columns")
    print("=" * 60)
    run_migration()
    print("=" * 60)
    print("Migration completed!")
    print("=" * 60)

