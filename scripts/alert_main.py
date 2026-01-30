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
        self.ELASTIC_HOST = os.getenv("ELASTIC_HOST")
        self.AUTH = (os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASS"))
        self.TOKEN = os.getenv("TELEGRAM_TOKEN")
        self.CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
        self.INDEX = ".internal.alerts-security.alerts-default-000001" 
        
        self.es = Elasticsearch(self.ELASTIC_HOST, basic_auth=self.AUTH, verify_certs=False)
        self.running = False 
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
        """Hàm chạy logic quét toàn cục (Bỏ lọc User, Ưu tiên lấy Script Block)"""
        log_callback("[*] SOC MONITORING ACTIVE: GLOBAL MODE")
        
        while self.running:
            try:
                query = {
                    "size": 100,
                    "query": {
                        "bool": {
                            "must": [{"range": {"@timestamp": {"gt": self.last_checkpoint}}}]
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
                        user_name = _src.get('user', {}).get('name') or \
                                    _src.get('winlog', {}).get('user', {}).get('name') or "Unknown"
                        
                        cmd = _src.get('powershell', {}).get('file', {}).get('script_block_text') or \
                              _src.get('process', {}).get('command_line') or \
                              _src.get('event', {}).get('original') or "N/A"

                        severity_raw = _src.get('kibana.alert.rule.severity') or "low"
                        risk_score = _src.get('kibana.alert.rule.risk_score') or 0
                        rule_name = _src.get('kibana.alert.rule.name') or "Security Alert"

                        proc = _src.get('process', {})
                        p_name = proc.get('name') or "SYSTEM"
                        pp_name = proc.get('parent', {}).get('name') or "N/A"

                        if p_name == "SYSTEM" and cmd == "N/A":
                            self.last_checkpoint = current_event_time
                            continue

                        alert_fingerprint = f"{rule_name}|{p_name}|{cmd}"
                        if alert_fingerprint in self.sent_alerts_cache:
                            self.last_checkpoint = current_event_time
                            continue
                        
                        self.sent_alerts_cache.add(alert_fingerprint)

                        # Logic hiển thị
                        severity = str(severity_raw).upper()
                        icon = "🔴" if severity in ["HIGH", "CRITICAL"] or risk_score >= 70 else "🟡" if severity == "MEDIUM" or risk_score >= 40 else "🔵"
                        label = "HIGH/CRITICAL" if icon == "🔴" else "MEDIUM" if icon == "🟡" else "LOW"

                        local_time = parser.isoparse(current_event_time).astimezone(tz.tzlocal()).strftime('%H:%M:%S')

                        msg = (f"{icon} <b>{label} RISK ALERT</b>\n"
                               f"Risk Score: <code>{risk_score}</code>\n"
                               f"━━━━━━━━━━━━━━━━━━━━━\n"
                               f"🕒 Time: <code>{local_time}</code> | 👤 User: <code>{user_name}</code>\n"
                               f"📝 Rule: <i>{rule_name}</i>\n"
                               f"─────────────────────\n"
                               f"🔸 Parent: <code>{pp_name.upper()}</code>\n"
                               f"🔸 Process: <code>{p_name.upper()}</code>\n"
                               f"🖥 Evidence:\n<code>{str(cmd).strip()}</code>\n"
                               f"━━━━━━━━━━━━━━━━━━━━━")

                        self.send_telegram(msg)
                        log_callback(f"[!] Alert Triggered: {rule_name} (User: {user_name})")
                        self.last_checkpoint = current_event_time

            except Exception as e:
                log_callback(f"[-] Error: {e}")

            for _ in range(10):
                if not self.running: break
                time.sleep(1)