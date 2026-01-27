import time
import requests
import urllib3
import sys
import logging
from elasticsearch import Elasticsearch
from dateutil import tz, parser
from datetime import datetime, timezone

# Tắt cảnh báo để terminal sạch sẽ
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.getLogger("elasticsearch").setLevel(logging.ERROR)

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

class SocMonitor:
    def __init__(self, host, auth, token, chat_id, target_user, index):
        self.host = host
        self.auth = auth
        self.token = token
        self.chat_id = chat_id
        self.target_user = target_user
        self.index = index
        self.monitoring = False
        
        # Khởi tạo Elasticsearch Client
        self.es = Elasticsearch(self.host, basic_auth=self.auth, verify_certs=False)

    def send_telegram(self, msg):
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {'chat_id': self.chat_id, 'text': msg, 'parse_mode': 'HTML'}
            requests.post(url, data=payload, timeout=10)
        except Exception as e:
            print(f"\n[-] Telegram Error: {e}")

    def start_monitoring(self):
        self.monitoring = True
        print(f"[*] SOC MONITORING ACTIVE: {self.target_user}")
        
        # Chỉ lấy log mới từ lúc chạy script
        last_checkpoint = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Lưu vết các Alert đã gửi để tránh trùng lặp
        sent_alerts_cache = set()

        print(f"[*] Initialized. Monitoring alerts after: {last_checkpoint}")

        while self.monitoring:
            try:
                query = {
                    "size": 100,
                    "query": {
                        "bool": {
                            "must": [{"range": {"@timestamp": {"gt": last_checkpoint}}}],
                            "filter": [{"multi_match": {
                                "query": self.target_user, 
                                "fields": ["user.name", "winlog.user.name", "related.user", "user.target.name"]
                            }}]
                        }
                    },
                    "sort": [{"@timestamp": {"order": "asc"}}]
                }

                res = self.es.search(index=self.index, body=query)
                hits = res['hits']['hits']

                if hits:
                    sent_alerts_cache.clear()

                    for hit in hits:
                        _src = hit['_source']
                        current_event_time = _src['@timestamp']
                        
                        severity_raw = _src.get('kibana.alert.rule.severity') or "low"
                        risk_score = _src.get('kibana.alert.rule.risk_score') or 0
                        rule_name = _src.get('kibana.alert.rule.name') or "Security Alert"

                        proc = _src.get('process', {})
                        p_name = proc.get('name')
                        pp_name = proc.get('parent', {}).get('name')
                        cmd = proc.get('command_line') or _src.get('event', {}).get('original')

                        if not p_name and not cmd:
                            last_checkpoint = current_event_time
                            continue

                        alert_fingerprint = f"{rule_name}|{p_name}|{cmd}"
                        
                        if alert_fingerprint in sent_alerts_cache:
                            last_checkpoint = current_event_time
                            continue
                        
                        sent_alerts_cache.add(alert_fingerprint)

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
                        msg += f"🕒 <b>Time:</b> <code>{local_time}</code> | 👤 <b>User:</b> <code>{self.target_user}</code>\n"
                        msg += f"📝 <b>Rule:</b> <i>{rule_name}</i>\n"
                        msg += f"─────────────────────\n"
                        msg += f"🔸 <b>Parent:</b> <code>{(pp_name or 'N/A').upper()}</code>\n"
                        msg += f"🔸 <b>Process:</b> <code>{(p_name or 'N/A').upper()}</code>\n"
                        msg += f"🖥 <b>Evidence:</b>\n<code>{str(cmd or 'N/A').strip()}</code>\n"
                        msg += f"━━━━━━━━━━━━━━━━━━━━━"

                        self.send_telegram(msg)
                        print(f"[!] Sent Alert: {rule_name} [{label}]")
                        
                        last_checkpoint = current_event_time

                else:
                    print(f"\n[*] Monitoring... (Last Check: {last_checkpoint[-13:-1]})", end="\r")

            except Exception as e:
                print(f"\n[-] Error: {e}")
            
            time.sleep(10)

    def stop_monitoring(self):
        self.monitoring = False
        print("[*] Stopping SOC Monitoring...")