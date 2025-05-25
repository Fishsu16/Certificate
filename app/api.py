import os
import shutil
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Certificate
import subprocess

router = APIRouter()

CA_INTERMEDIATE_KEY = "ca/intermediate/intermediate.key.pem"
CA_INTERMEDIATE_CERT = "ca/intermediate/intermediate.cert.pem"

CSR_DIR = "csr"
CERTS_DIR = "certs"

os.makedirs(CSR_DIR, exist_ok=True)
os.makedirs(CERTS_DIR, exist_ok=True)

@router.post("/issue")
async def issue_certificate(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if file.content_type != "application/x-pem-file" and not (file.filename.endswith(".csr") or file.filename.endswith(".pem")):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a PEM CSR file.")

    csr_id = str(uuid.uuid4())
    csr_path = os.path.join(CSR_DIR, f"{csr_id}.csr")
    with open(csr_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = subprocess.run(
            ["openssl", "req", "-in", csr_path, "-noout", "-subject"],
            capture_output=True,
            text=True,
            check=True,
        )
        subject = result.stdout.strip()
        cn = None
        if subject.startswith("subject="):
            parts = subject[8:].split("/")
            for part in parts:
                if part.startswith("CN="):
                    cn = part[3:]
                    break
        if cn is None:
            raise ValueError("CN not found in CSR subject")
    except Exception as e:
        os.remove(csr_path)
        raise HTTPException(status_code=400, detail=f"Failed to parse CSR: {str(e)}")

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
    db.commit()

    return FileResponse(cert_path, filename=f"{cn}.crt", media_type="application/x-pem-file")
