# Kịch bản thực nghiệm
## Video thực nghiệm: https://drive.google.com/drive/folders/1Gmgtp_FmUd20vFxsRamV8dOc75Zk6oNt
## Mục tiêu thực nghiệm:
Kiểm chứng khả năng tự động hóa toàn trình của hệ thống tự xây dựng, bao gồm: tính năng phát hiện sai lệch dữ liệu (Sync Audit), quản lý rule, giám sát thời gian thực qua Telegram và quy trình CI/CD từ môi trường Dev sang Prod.
Các bước thực hiện:
## Quy trình thực nghiệm:
###	Bước 1: Khởi tạo kết nối và môi trường
- Thiết lập một Cloudflare Tunnel tạm thời để tạo Public URL, đảm bảo khả năng truy cập từ xa và kết nối ổn định trong quá trình demo.
- Xác nhận hệ thống đang hoạt động trên nhánh dev của Git và trỏ tới không gian detection-dev trên Kibana.
###	Bước 2: Kiểm thử tính năng phát hiện sai lệch đồng bộ (Sync Audit)
- Kiểm chứng khả năng phát hiện sai lệch dữ liệu giữa hệ thống SIEM và kho mã nguồn Local.
- Thao tác: Tạo thủ công một Rule bất kỳ trực tiếp trên giao diện web của Kibana (Rule này không tồn tại trong Repo Local). Trên giao diện SOC GUI, nhấn nút SYNC AUDIT.
- Hệ thống cảnh báo phát hiện sai lệnh và chỉ ra Rule ID đang tồn tại trên Kibana nhưng thiếu trong Repo, chứng minh module quản lý hoạt động chính xác.
###	Bước 3: Nạp dữ liệu rule vào hệ thống
- Sử dụng chức năng LOAD RULE trên GUI để nạp tập hợp các Sigma rule đã được chắt lọc cho bài.
- Các rule được chuyển đổi tự động và xuất hiện trong danh sách quản lý của Kibana dev-space.
###	Bước 4: Kiểm thử tính năng quản lý vòng đời rule
- Đảm bảo các thao tác quản trị tác động tức thời lên hệ thống SIEM.
- Thực hiện tuần tự các hành động trên một Rule cụ thể: Disable, Delete, Restore, Enable.
###	Bước 5: Thực nghiệm tấn công và giám sát cảnh báo
- Bật chế độ THREAT SCAN trên GUI để kích hoạt module AlertMonitor.
- Thực hiện hành vi độc hại trên máy Victim bằng script mô phỏng tấn công.
- Kết quả: Log được đẩy lên Elasticsearch, được Detection Engine phát hiện và tạo cảnh báo. Telegram Bot gửi thông báo chi tiết về hành vi tấn công tới điện thoại quản trị viên ngay lập tức.
###	Bước 6: Hợp nhất và triển khai Production
- Áp dụng các rule đã được kiểm định trên vào môi trường thực tế.
- Thực hiện hợp nhất mã nguồn từ nhánh dev vào nhánh main thông qua Git.
- Kết quả: GitHub Actions tự động kích hoạt luồng triển khai Production, cập nhật các rule mới vào không gian production-space trên Kibana, hoàn tất quy trình phát triển an toàn.