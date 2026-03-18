![image](Diagram/Luong_chi_tiet.png)


## SIEM Automation
Hệ thống quản lý Sigma Rules dựa trên mô hình DaC và giám sát cảnh báo tập trung cho ELK Stack thông qua giao diện GUI và tự động hóa CI/CD.

### Tính năng chính
- Rule Manager: Quản lý, chỉnh sửa và đồng bộ hóa Sigma Rules giữa Local Repo và Kibana.
- Alert Monitor: Giám sát thời gian thực (Real-time) các chỉ số rủi ro và gửi cảnh báo qua Telegram.
- Git Integration: Tự động hóa quy trình Git Add/Commit/Push khi thay đổi Rule.

### Cài đặt nhanh
1. Clone repository:

```Bash
git clone https://github.com/yuhrt05/SIEM-Automation-Project/
cd <repo-folder>
```

2. Cài đặt thư viện:

```Bash
pip install -r requirements.txt
```
3. Cấu hình file .env:

```Plaintext
ELASTIC_HOST1=https://<ip>:9200
ELASTIC_USER=elastic
ELASTIC_PASS=<password>
TELEGRAM_TOKEN=<bot_token>
TELEGRAM_CHAT_ID=<chat_id>
INDEX_PROD=.alerts-security.alerts-default
INDEX_DEV=.alerts-security.alerts-dev
KIBANA_SPACE_PROD=default
KIBANA_SPACE_DEV=detection-dev
```
### Cấu trúc chính
- main.py: Khởi chạy giao diện chính.
- manager.py: Xử lý logic quản lý file Sigma và API Elastic.
- alert.py: Engine quét và đẩy cảnh báo Telegram.
- deploy.py: Chuyển đổi và triển khai rule từ Repo lên Kibana
- rules/: Thư mục lưu trữ các file Sigma (.yml).

### Sử dụng
Chạy lệnh sau để bắt đầu:

```Bash
python main.py
```