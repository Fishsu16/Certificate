from sqlalchemy import Column, String, DateTime, BigInteger
from app.db import Base

class Certificate(Base):
    __tablename__ = "issued_certificates"

    id = Column(String, primary_key=True, index=True)
    common_name = Column(String, index=True)
    csr_filename = Column(String)
    cert_filename = Column(String)
    issue_time = Column(DateTime)
    expire_time = Column(DateTime)
    serial_number = Column(BigInteger, unique=True)
