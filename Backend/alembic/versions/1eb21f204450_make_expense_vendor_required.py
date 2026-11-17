"""make_expense_vendor_required

Revision ID: 1eb21f204450
Revises: 19e7b9d418b3
Create Date: 2026-11-03 18:39:41.612140

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '1eb21f204450'
down_revision: Union[str, Sequence[str], None] = '19e7b9d418b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # 1. Safely remove existing foreign key on vendor_id if present
    fk_list = inspector.get_foreign_keys("expenses")
    for fk in fk_list:
        if fk.get("name") == "expenses_ibfk_3" or "vendor_id" in fk.get("constrained_columns", []):
            try:
                op.drop_constraint(fk["name"], "expenses", type_="foreignkey")
            except Exception:
                pass

    # 2. Backfill existing NULL vendor_id values in expenses before altering to NOT NULL
    null_companies = bind.execute(
        sa.text("SELECT DISTINCT company_id FROM expenses WHERE vendor_id IS NULL")
    ).fetchall()

    for row in null_companies:
        cid = row[0]
        # Find an existing vendor for this company if available
        vendor_id = bind.execute(
            sa.text(
                "SELECT vendor_id FROM vendors "
                "WHERE company_id = :cid "
                "ORDER BY is_deleted ASC, vendor_id ASC LIMIT 1"
            ),
            {"cid": cid},
        ).scalar()

        if not vendor_id:
            # Create a fallback default vendor for this company
            bind.execute(
                sa.text(
                    "INSERT INTO vendors (company_id, vendor_name, contact_person, email, phone, address, is_deleted) "
                    "VALUES (:cid, 'Default Vendor', 'Admin', 'admin@staffly.com', '9999999999', 'Head Office', 0)"
                ),
                {"cid": cid},
            )
            vendor_id = bind.execute(
                sa.text(
                    "SELECT vendor_id FROM vendors "
                    "WHERE company_id = :cid "
                    "ORDER BY vendor_id DESC LIMIT 1"
                ),
                {"cid": cid},
            ).scalar()

        # Update NULL expenses for this company
        bind.execute(
            sa.text(
                "UPDATE expenses SET vendor_id = :vid "
                "WHERE company_id = :cid AND vendor_id IS NULL"
            ),
            {"vid": vendor_id, "cid": cid},
        )

    # Global safety backfill for any remaining NULLs (e.g. orphan records)
    remaining_nulls = bind.execute(
        sa.text("SELECT COUNT(*) FROM expenses WHERE vendor_id IS NULL")
    ).scalar()

    if remaining_nulls and remaining_nulls > 0:
        fallback_vid = bind.execute(
            sa.text("SELECT vendor_id FROM vendors ORDER BY vendor_id ASC LIMIT 1")
        ).scalar()
        if fallback_vid:
            bind.execute(
                sa.text("UPDATE expenses SET vendor_id = :vid WHERE vendor_id IS NULL"),
                {"vid": fallback_vid},
            )

    # 3. Safely alter column vendor_id to NOT NULL
    op.alter_column(
        "expenses",
        "vendor_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # 4. Recreate foreign key with RESTRICT if not already present
    fk_list_after = inspect(bind).get_foreign_keys("expenses")
    has_vendor_fk = any(
        "vendor_id" in fk.get("constrained_columns", [])
        for fk in fk_list_after
    )
    fk_names_after = [fk.get("name") for fk in fk_list_after if fk.get("name")]
    if not has_vendor_fk and "expenses_ibfk_3" not in fk_names_after:
        op.create_foreign_key(
            "expenses_ibfk_3",
            "expenses",
            "vendors",
            ["vendor_id"],
            ["vendor_id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # Remove the RESTRICT foreign key
    fk_list = inspector.get_foreign_keys("expenses")
    for fk in fk_list:
        if fk.get("name") == "expenses_ibfk_3" or "vendor_id" in fk.get("constrained_columns", []):
            try:
                op.drop_constraint(fk["name"], "expenses", type_="foreignkey")
            except Exception:
                pass

    # Make vendor_id optional again
    op.alter_column(
        "expenses",
        "vendor_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # Restore the original foreign key
    fk_list_after = inspect(bind).get_foreign_keys("expenses")
    has_vendor_fk = any(
        "vendor_id" in fk.get("constrained_columns", [])
        for fk in fk_list_after
    )
    fk_names_after = [fk.get("name") for fk in fk_list_after if fk.get("name")]
    if not has_vendor_fk and "expenses_ibfk_3" not in fk_names_after:
        op.create_foreign_key(
            "expenses_ibfk_3",
            "expenses",
            "vendors",
            ["vendor_id"],
            ["vendor_id"],
            ondelete="SET NULL",
        )
