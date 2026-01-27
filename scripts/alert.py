import os
from dotenv import load_dotenv
import time, requests, urllib3, sys, logging
from elasticsearch import Elasticsearch
from dateutil import tz, parser
from datetime import datetime, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.getLogger("elasticsearch").setLevel(logging.ERROR)
load_dotenv()

class AlertMonitor:
    def __init__(self):
        # Giữ nguyên cấu hình từ .env
        self.ELASTIC_HOST = os.getenv("ELASTIC_HOST")
        self.AUTH = (os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASS"))
        self.TOKEN = os.getenv("TELEGRAM_TOKEN")
        self.CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
        self.TARGET_USER = os.getenv("TARGET_USER")
        self.INDEX = ".internal.alerts-security.alerts-default-000001"
        
        self.es = Elasticsearch(self.ELASTIC_HOST, basic_auth=self.AUTH, verify_certs=False)
        self.running = False # Biến kiểm soát trạng thái Bật/Tắt
        self.last_checkpoint = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.sent_alerts_cache = set()

    def send_telegram(self, msg):
        try:
            url = f"https://api.telegram.org/bot{self.TOKEN}/sendMessage"
            payload = {'chat_id': self.CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}
            requests.post(url, data=payload, timeout=10)
        except Exception as e:
            print(f"\n[-] Telegram Error: {e}")

    def run_logic(self, log_callback):
        """Hàm chạy logic quét, gọi từ thread của Dashboard"""
        log_callback(f"[*] SOC MONITORING ACTIVE: {self.TARGET_USER}")
        
        while self.running:
            try:
                query = {
                    "size": 100,
                    "query": {
                        "bool": {
                            "must": [{"range": {"@timestamp": {"gt": self.last_checkpoint}}}],
                            "filter": [{"multi_match": {
                                "query": self.TARGET_USER, 
                                "fields": ["user.name", "winlog.user.name", "related.user", "user.target.name"]
                            }}]
                        }
                    },
                    "sort": [{"@timestamp": {"order": "asc"}}]
                }

                res = self.es.search(index=self.INDEX, body=query)
                hits = res['hits']['hits']

                if hits:
                    self.sent_alerts_cache.clear()
                    for hit in hits:
                        _src = hit['_source']
                        current_event_time = _src['@timestamp']
                        
                        # --- GIỮ NGUYÊN TOÀN BỘ LOGIC TRUY XUẤT ---
                        severity_raw = _src.get('kibana.alert.rule.severity') or "low"
                        risk_score = _src.get('kibana.alert.rule.risk_score') or 0
                        rule_name = _src.get('kibana.alert.rule.name') or "Security Alert"

                        proc = _src.get('process', {})
                        p_name = proc.get('name')
                        pp_name = proc.get('parent', {}).get('name')
                        cmd = proc.get('command_line') or _src.get('event', {}).get('original')

                        if not p_name and not cmd:
                            self.last_checkpoint = current_event_time
                            continue

                        alert_fingerprint = f"{rule_name}|{p_name}|{cmd}"
                        if alert_fingerprint in self.sent_alerts_cache:
                            self.last_checkpoint = current_event_time
                            continue
                        
                        self.sent_alerts_cache.add(alert_fingerprint)

                        # --- XỬ LÝ HIỂN THỊ ALERT ---
                        severity = str(severity_raw).upper()
                        icon = "🔴" if severity in ["HIGH", "CRITICAL"] or risk_score >= 70 else "🟡" if severity == "MEDIUM" or risk_score >= 40 else "🔵"
                        label = "HIGH/CRITICAL" if icon == "🔴" else "MEDIUM" if icon == "🟡" else "LOW"

                        local_time = parser.isoparse(current_event_time).astimezone(tz.tzlocal()).strftime('%H:%M:%S')

                        msg = f"{icon} <b>{label} RISK ALERT</b>\nRisk Score: <code>{risk_score}</code>\n━━━━━━━━━━━━━━━━━━━━━\n🕒 Time: <code>{local_time}</code> | 👤 User: <code>{self.TARGET_USER}</code>\n📝 Rule: <i>{rule_name}</i>\n─────────────────────\n🔸 Parent: <code>{(pp_name or 'N/A').upper()}</code>\n🔸 Process: <code>{(p_name or 'N/A').upper()}</code>\n🖥 Evidence:\n<code>{str(cmd or 'N/A').strip()}</code>\n━━━━━━━━━━━━━━━━━━━━━"

                        self.send_telegram(msg)
                        log_callback(f"[!] Alert Triggered: {rule_name}")
                        self.last_checkpoint = current_event_time

            except Exception as e:
                log_callback(f"[-] Error: {e}")
            
            time.sleep(10) # Chu kỳ quét 10 giây