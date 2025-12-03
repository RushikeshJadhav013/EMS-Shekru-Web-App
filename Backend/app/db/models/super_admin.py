from sqlalchemy import Column, Integer, String
from app.db.database import Base

class SuperAdmin(Base):
    __tablename__ = 'super_admins'

    super_admin_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    contact_no = Column(String(20), nullable=False)
