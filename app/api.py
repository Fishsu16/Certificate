import os
import shutil
import uuid
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timedelta
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
#from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
#from sqlalchemy.orm import sessionmaker
from app.db import get_db
from app.models import Certificate
import subprocess
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

router = APIRouter()
print("🚀 issue_certificate called")

CA_INTERMEDIATE_KEY = "ca/intermediate/intermediate.key.pem"
CA_INTERMEDIATE_CERT = "ca/intermediate/intermediate.cert.pem"

CSR_DIR = "csr/"
CERTS_DIR = "certs/"

#os.makedirs(CSR_DIR, exist_ok=True)
#os.makedirs(CERTS_DIR, exist_ok=True)
try:
    os.makedirs(CSR_DIR, exist_ok=True)
    os.makedirs(CERTS_DIR, exist_ok=True)
    logger.info(f"Working Directory: {os.getcwd()}")
except Exception as e:
    logger.info(f"❌ Failed to create directories: {e}")
    logger.info(f"Working Directory: {os.getcwd()}")

@router.post("/issue")
async def issue_certificate(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if file.content_type != "application/x-pem-file" and not (file.filename.endswith(".csr") or file.filename.endswith(".pem")):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a PEM CSR file.")

    csr_id = str(uuid.uuid4())
    csr_path = os.path.join(CSR_DIR, f"{csr_id}.csr")
    with open(csr_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    #try:
    #    result = subprocess.run(
    #        ["openssl", "req", "-in", csr_path, "-noout", "-subject"],
    #        capture_output=True,
    #        text=True,
    #        check=True,
    #    )
    #    subject = result.stdout.strip()
    #    cn = None
    #    if subject.startswith("subject="):
    #        parts = subject[8:].split("/")
    #        for part in parts:
    #            if part.startswith("CN="):
    #                cn = part[3:]
    #                break
    #    if cn is None:
    #        raise ValueError("CN not found in CSR subject")
    #except Exception as e:
    #    os.remove(csr_path)
    #    raise HTTPException(status_code=400, detail=f"Failed to parse CSR: {str(e)}")
    
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

    serial_number = uuid.uuid4().int >> 64
    cert_path = os.path.join(CERTS_DIR, f"{csr_id}.crt")

    cmd = [
        "openssl",
        "x509",
        "-req",
        "-in",
        csr_path,
        "-CA",
        CA_INTERMEDIATE_CERT,
        "-CAkey",
        CA_INTERMEDIATE_KEY,
        "-CAcreateserial",
        "-out",
        cert_path,
        "-days",
        "365",
        "-sha256",
        "-set_serial",
        str(serial_number),
    ]

    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        os.remove(csr_path)
        raise HTTPException(status_code=500, detail=f"Certificate signing failed: {str(e)}")

    issue_time = datetime.utcnow()
    expire_time = issue_time + timedelta(days=365)

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
