![image](Diagram/Luong_chi_tiet.png)


## SIEM Automation Framework
Hệ thống tự động hóa quy trình quản lý luật phát hiện (Detection Rules) trên Elastic Stack thông qua pipeline CI/CD và cơ chế giám sát cảnh báo tập trung.

## Các thành phần chính
- Management Layer: Quản lý mã nguồn luật trên GitHub với hai nhánh chính: dev (thử nghiệm) và main (môi trường vận hành).

- CI/CD & API Push: Sử dụng GitHub Actions để tự động đẩy các thay đổi cấu hình tới Kibana API tương ứng (Dev/Prod) sau khi kiểm tra.

- SIEM - Elastic Stack:

    - Detection Engine: Thực hiện đối soát dữ liệu log (Pattern Match) dựa trên các luật đã nạp.

    - Elasticsearch Alert Index: Nơi lưu trữ tập trung các cảnh báo được kích hoạt.

- Automated Monitoring:

    - Script Python (AlertMonitor) thực hiện lấy dữ liệu (polling) từ Alert Index.

    - Xử lý logic nội bộ: Loại bỏ trùng lặp (Deduplicate), lọc mức độ nghiêm trọng và định dạng dữ liệu.

    - Thông báo: Gửi cảnh báo trực tiếp tới Security Analyst qua Telegram Bot API.