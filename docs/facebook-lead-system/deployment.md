# Hướng dẫn Triển khai & Vận hành: Deployment Guide

Tài liệu hướng dẫn cấu hình hạ tầng, biến môi trường, dịch vụ nền và quy trình triển khai hệ thống **Facebook Lead Intelligence V1** trên máy ảo Google Cloud Compute Engine (`crawl-fb-cic`).

---

## 1. Thông số Hạ tầng Triển khai (Infrastructure Spec)

* **Máy ảo (VM):** `crawl-fb-cic`
* **Google Cloud Project:** `cic-rag-host` (Zone: `asia-southeast1-c`)
* **Địa chỉ IP Public:** `34.142.194.165`
* **Cấu hình phần cứng:**
  * CPU: 4 vCPUs
  * RAM: 15 GB (Dư dả để xử lý hàng ngàn lead mỗi ngày)
  * Ổ đĩa: 96 GB SSD NVMe
* **Hệ điều hành:** Ubuntu 26.04.1 LTS
* **Database chính:** PostgreSQL Hosted trên **Supabase** (Project `qllwfecwujzhuwexrlqi`, Vùng `ap-southeast-2`).

---

## 2. Cấu trúc Thư mục trên Máy chủ

```
/home/ADMIN/
├── docs/
│   └── facebook-lead-system/      # Tài liệu kiến trúc, database, error handling
├── n8n/
│   ├── docker-compose.yml         # File định nghĩa container n8n
│   └── data/                      # Thư mục volume mount của n8n (/home/node/.n8n)
│       ├── database.sqlite        # SQLite lưu trữ state của n8n
│       └── config                 # File mã hóa credentials của n8n
```

---

## 3. Cấu hình Docker Compose (`/home/ADMIN/n8n/docker-compose.yml`)

```yaml
services:
  n8n:
    image: docker.n8n.io/n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    ports:
      - "5678:5678"
    environment:
      - N8N_HOST=0.0.0.0
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - N8N_EDITOR_BASE_URL=http://34.142.194.165:5678/
      - WEBHOOK_URL=https://feb-bookmark-foot-grateful.trycloudflare.com/
      - GENERIC_TIMEZONE=Asia/Ho_Chi_Minh
      - TZ=Asia/Ho_Chi_Minh
      - N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
      
      # Kết nối Supabase PostgreSQL (IPv4 Pooler)
      - SUPABASE_URL=https://qllwfecwujzhuwexrlqi.supabase.co
      - SUPABASE_DB_HOST=aws-0-ap-southeast-2.pooler.supabase.com
      - SUPABASE_DB_PORT=5432
      - SUPABASE_DB_USER=postgres.qllwfecwujzhuwexrlqi
      - SUPABASE_DB_NAME=postgres
      
      # AI Engine & API Keys
      - CIC_AI_API_KEY=sk-cic-2026
      - CIC_AI_ENDPOINT=https://ai-api.cic.com.vn:9443/v1
    volumes:
      - /home/ADMIN/n8n/data:/home/node/.n8n
```

---

## 4. Dịch vụ Tên miền & Webhook (Cloudflare Tunnel)

Hệ thống sử dụng **Cloudflare Tunnel** chạy dưới dạng Systemd Daemon để cung cấp kết nối HTTPS an toàn, vượt qua yêu cầu chứng chỉ SSL của Facebook Webhooks mà không cần mở port nguy hiểm:

* **File dịch vụ:** `/etc/systemd/system/cloudflared-n8n.service`
  ```ini
  [Unit]
  Description=Cloudflare Tunnel for n8n Webhook
  After=network.target

  [Service]
  Type=simple
  Restart=always
  RestartSec=5s
  ExecStart=/usr/local/bin/cloudflared --config /dev/null --no-autoupdate tunnel --url http://127.0.0.1:5678

  [Install]
  WantedBy=multi-user.target
  ```

* **Dịch vụ Tự động đồng bộ Webhook URL:**
  * File Timer: `/etc/systemd/system/cloudflared-n8n-sync.timer` (Chạy mỗi 30s)
  * File Service: `/etc/systemd/system/cloudflared-n8n-sync.service`
  * Script thực thi: `/usr/local/bin/sync_cloudflared_n8n.py` (Tự động đọc URL tunnel mới từ log và update biến `WEBHOOK_URL` cho n8n container).

---

## 5. Lệnh Thao tác Quản trị (Ops Commands)

### Quản lý Docker & n8n:
* Khởi động lại n8n: `docker compose -f /home/ADMIN/n8n/docker-compose.yml restart`
* Cập nhật n8n lên bản mới:
  ```bash
  docker compose -f /home/ADMIN/n8n/docker-compose.yml pull
  docker compose -f /home/ADMIN/n8n/docker-compose.yml up -d
  ```
* Xem log n8n trực tiếp: `docker logs -f --tail 100 n8n`

### Quản lý Cloudflare Tunnel:
* Kiểm tra URL tunnel hiện tại:
  `journalctl -u cloudflared-n8n -n 30 --no-pager | grep trycloudflare.com`
* Khởi động lại tunnel: `sudo systemctl restart cloudflared-n8n.service`

### Sao lưu Dữ liệu (Backup Strategy):
1. **Dữ liệu n8n:** Toàn bộ workflows và credentials nằm tại `/home/ADMIN/n8n/data/database.sqlite`. Định kỳ sao lưu:
   `sqlite3 /home/ADMIN/n8n/data/database.sqlite ".backup /home/ADMIN/n8n/data/backup_$(date +%Y%m%d).sqlite"`
2. **Dữ liệu Leads:** Nằm trực tiếp trên cơ sở dữ liệu Supabase, được tự động Snapshot & WAL Backup theo cơ chế Point-in-Time Recovery của Supabase.
