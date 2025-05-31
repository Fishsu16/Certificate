import os
import shutil
import uuid
import random
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.db import get_db
from app.models import Certificate
import subprocess
import logging

# 匯入自訂 OID（你可以放在共用模組）
from cryptography.x509.oid import ObjectIdentifier, NameOID
OID_SIGN_TAG = ObjectIdentifier("1.3.6.1.4.1.55555.1.1")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

router = APIRouter()

# path setting
CA_INTERMEDIATE_KEY = "ca/intermediate/intermediate.key.pem"
CA_INTERMEDIATE_CERT = "ca/intermediate/intermediate.cert.pem"

CSR_DIR = "csr/"
CERTS_DIR = "certs/"

try:
    os.makedirs(CSR_DIR, exist_ok=True)
    os.makedirs(CERTS_DIR, exist_ok=True)
    logger.info(f"Working Directory: {os.getcwd()}")
except Exception as e:
    logger.info(f"❌ Failed to create directories: {e}")
    logger.info(f"Working Directory: {os.getcwd()}")

@router.get("/intermediate_cert")
async def get_intermediate_cert():
    """
    讓 client 下載 Intermediate CA 憑證
    """
    return FileResponse(
        CA_INTERMEDIATE_CERT,
        media_type="application/x-pem-file",
        filename="intermediate.cert.pem",
    )


@router.post("/issue")
async def issue_certificate(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if file.content_type != "application/x-pem-file" and not (file.filename.endswith(".csr") or file.filename.endswith(".pem")):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a PEM CSR file.")

    csr_id = str(uuid.uuid4())
    csr_path = os.path.join(CSR_DIR, f"{csr_id}.csr")
    with open(csr_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    with open(csr_path, "rb") as f:
        csr_data = f.read()

    try:
        csr = x509.load_pem_x509_csr(csr_data, default_backend())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load CSR: {str(e)}")

    cn_attr = csr.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
    if not cn_attr:
        raise HTTPException(status_code=400, detail="CN not found in CSR subject")

    cn = cn_attr[0].value
    serial_number = random.getrandbits(63)

    issue_time = datetime.utcnow()
    expire_time = issue_time + timedelta(days=365)

    # 載入 CA 私鑰與憑證
    with open(CA_INTERMEDIATE_KEY, "rb") as f:
        ca_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())
    with open(CA_INTERMEDIATE_CERT, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read(), backend=default_backend())

    # 準備 certificate builder
    cert_builder = x509.CertificateBuilder()
    cert_builder = cert_builder.subject_name(csr.subject)
    cert_builder = cert_builder.issuer_name(ca_cert.subject)
    cert_builder = cert_builder.public_key(csr.public_key())
    cert_builder = cert_builder.serial_number(serial_number)
    cert_builder = cert_builder.not_valid_before(issue_time)
    cert_builder = cert_builder.not_valid_after(expire_time)

    # 複製 CSR 中的 extension（包括自訂的 extended info）
    for ext in csr.extensions:
        cert_builder = cert_builder.add_extension(ext.value, critical=ext.critical)

    # 簽署憑證
    cert = cert_builder.sign(private_key=ca_key, algorithm=hashes.SHA256(), backend=default_backend())

    cert_path = os.path.join(CERTS_DIR, f"{csr_id}.crt")
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    # 儲存到資料庫
    cert_record = Certificate(
        id=csr_id,
        common_name=cn,
        csr_filename=f"{csr_id}.csr",
        cert_filename=f"{csr_id}.crt",
        issue_time=issue_time,
        expire_time=expire_time,
        serial_number=serial_number,
    )
    db.add(cert_record)
    await db.commit()

    return FileResponse(cert_path, filename=f"{cn}.crt", media_type="application/x-pem-file")
