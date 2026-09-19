from sqlalchemy import Column, Integer, String
from ..db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    ev_brand = Column(String, nullable=True)
    charger_type = Column(String, nullable=True)
    location = Column(String, nullable=True)
