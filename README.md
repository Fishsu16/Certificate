# CA Certificate Server

## 簡介
一個使用 FastAPI 與 OpenSSL 的自建 CA 伺服器，簽發 X.509 憑證並儲存簽發紀錄到 PostgreSQL。

## 環境建置
1. 執行 `bash init_ca.sh` 初始化 CA key 和 cert
2. 設定 `.env` 的 `DATABASE_URL`
3. 建立資料表：
   ```bash
   python
   >>> from app.db import engine, Base
   >>> Base.metadata.create_all(bind=engine)
