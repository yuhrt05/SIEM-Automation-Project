import os
from dotenv import load_dotenv
import time, requests, urllib3, sys, logging
from elasticsearch import Elasticsearch
from dateutil import tz, parser
from datetime import datetime, timezone
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.getLogger("elasticsearch").setLevel(logging.ERROR)
load_dotenv()
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# --- CONFIG ---
ELASTIC_HOST = os.getenv("ELASTIC_HOST")
AUTH = (os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASS"))
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TARGET_USER = os.getenv("TARGET_USER")
INDEX = ".internal.alerts-security.alerts-default-000001"

es = Elasticsearch(ELASTIC_HOST, basic_auth=AUTH, verify_certs=False)

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"\n[-] Telegram Error: {e}")

def start_monitoring():
    print(f"[*] SOC MONITORING ACTIVE: {TARGET_USER}")
    
    # Chỉ lấy log mới từ lúc chạy script
    last_checkpoint = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    # Lưu vết các Alert đã gửi để tránh trùng lặp trong cùng một đợt quét
    sent_alerts_cache = set()

    print(f"[*] Initialized. Monitoring alerts after: {last_checkpoint}")

    while True:
        try:
            query = {
                "size": 100,
                "query": {
                    "bool": {
                        "must": [{"range": {"@timestamp": {"gt": last_checkpoint}}}],
                        "filter": [{"multi_match": {
                            "query": TARGET_USER, 
                            "fields": ["user.name", "winlog.user.name", "related.user", "user.target.name"]
                        }}]
                    }
                },
                "sort": [{"@timestamp": {"order": "asc"}}]
            }

            res = es.search(index=INDEX, body=query)
            hits = res['hits']['hits']

            if hits:
                # Xóa cache cũ sau mỗi vòng lặp 10 giây để nhận diện Alert mới sau này
                sent_alerts_cache.clear()

                for hit in hits:
                    _src = hit['_source']
                    current_event_time = _src['@timestamp']
                    
                    # --- TRUY XUẤT DỮ LIỆU ---
                    severity_raw = _src.get('kibana.alert.rule.severity') or "low"
                    risk_score = _src.get('kibana.alert.rule.risk_score') or 0
                    rule_name = _src.get('kibana.alert.rule.name') or "Security Alert"

                    proc = _src.get('process', {})
                    p_name = proc.get('name')
                    pp_name = proc.get('parent', {}).get('name')
                    cmd = proc.get('command_line') or _src.get('event', {}).get('original')

                    # 1. BỎ QUA NẾU TRỐNG DỮ LIỆU QUAN TRỌNG
                    if not p_name and not cmd:
                        last_checkpoint = current_event_time
                        continue

                    # 2. KIỂM TRA TRÙNG LẶP (Dựa trên Rule + Process + Command)
                    # Tạo một "dấu vân tay" cho Alert
                    alert_fingerprint = f"{rule_name}|{p_name}|{cmd}"
                    
                    if alert_fingerprint in sent_alerts_cache:
                        # Nếu đã gửi rồi trong đợt quét này, cập nhật checkpoint và bỏ qua
                        last_checkpoint = current_event_time
                        continue
                    
                    # Nếu chưa gửi, thêm vào cache
                    sent_alerts_cache.add(alert_fingerprint)

                    # --- XỬ LÝ HIỂN THỊ ---
                    severity = str(severity_raw).upper()
                    if severity in ["HIGH", "CRITICAL"] or risk_score >= 70:
                        icon, label = "🔴", "HIGH/CRITICAL"
                    elif severity == "MEDIUM" or risk_score >= 40:
                        icon, label = "🟡", "MEDIUM"
                    else:
                        icon, label = "🔵", "LOW"

                    local_time = parser.isoparse(current_event_time).astimezone(tz.tzlocal()).strftime('%H:%M:%S')

                    msg =  f"{icon} <b>{label} RISK ALERT</b>\n"
                    msg += f"<b>Risk Score:</b> <code>{risk_score}</code>\n"
                    msg += f"━━━━━━━━━━━━━━━━━━━━━\n"
                    msg += f"🕒 <b>Time:</b> <code>{local_time}</code> | 👤 <b>User:</b> <code>{TARGET_USER}</code>\n"
                    msg += f"📝 <b>Rule:</b> <i>{rule_name}</i>\n"
                    msg += f"─────────────────────\n"
                    msg += f"🔸 <b>Parent:</b> <code>{(pp_name or 'N/A').upper()}</code>\n"
                    msg += f"🔸 <b>Process:</b> <code>{(p_name or 'N/A').upper()}</code>\n"
                    msg += f"🖥 <b>Evidence:</b>\n<code>{str(cmd or 'N/A').strip()}</code>\n"
                    msg += f"━━━━━━━━━━━━━━━━━━━━━"

                    send_telegram(msg)
                    print(f"[!] Sent Alert: {rule_name} [{label}]")
                    
                    last_checkpoint = current_event_time

            else:
                print(f"\n[*] Monitoring... (Last Check: {last_checkpoint[-13:-1]})", end="\r")

        except Exception as e:
            print(f"\n[-] Error: {e}")
        
        time.sleep(10)

if __name__ == "__main__":
    start_monitoring()