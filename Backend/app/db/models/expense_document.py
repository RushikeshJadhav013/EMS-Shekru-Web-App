
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func

from app.db.database import Base


class ExpenseDocument(Base):
    __tablename__ = "expense_documents"

    document_id = Column(
        Integer,
        primary_key=True,
    )

    expense_id = Column(
        Integer,
        ForeignKey("expenses.expense_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_name = Column(String(255), nullable=False)
    document_path = Column(String(500), nullable=False)
    document_type = Column(String(50), nullable=True)

    uploaded_by = Column(
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    uploaded_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
