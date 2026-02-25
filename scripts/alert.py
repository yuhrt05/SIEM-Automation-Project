import os
import subprocess
import time
import requests
import urllib3
import logging
from collections import deque
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from dateutil import tz, parser
from datetime import datetime, timezone
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.getLogger("elasticsearch").setLevel(logging.ERROR)
load_dotenv()

class AlertMonitor:
    def __init__(self):
        self.branch = self._get_current_branch()
        print(f"[*] Detected Environment: {self.branch.upper()}")

        self.ELASTIC_HOST = os.getenv("ELASTIC_HOST1")
        self.AUTH = (os.getenv("ELASTIC_USER"), os.getenv("ELASTIC_PASS"))
        self.TOKEN = os.getenv("TELEGRAM_TOKEN")
        self.CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
        
        env_settings = {
            "main": {"index": os.getenv("INDEX_PROD"), "label": "PROD"},
            "dev":  {"index": os.getenv("INDEX_DEV"),  "label": "DEV"}
        }

        current_config = env_settings.get(self.branch, env_settings["dev"])
        self.INDEX = current_config["index"]
        self.ENV_LABEL = current_config["label"]
        self.es = Elasticsearch(self.ELASTIC_HOST, basic_auth=self.AUTH, verify_certs=False)
        self.running = False 
        self.last_checkpoint = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.sent_alerts_cache = deque(maxlen=500)
        
    def _get_current_branch(self):
        try:
            return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode().strip()
        except Exception:
            return "dev"

    def send_telegram(self, msg):
        try:
            url = f"https://api.telegram.org/bot{self.TOKEN}/sendMessage"
            payload = {'chat_id': self.CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}
            requests.post(url, data=payload, timeout=10)
        except Exception as e:
            print(f"\n[-] Telegram Error: {e}")

    def run_logic(self, log_callback):
        log_callback(f"[*] SOC MONITORING ACTIVE: {self.ENV_LABEL}")
        
        while self.running:
            try:
                query = {
                    "size": 1000,
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "range": {
                                        "@timestamp": {
                                            "gte": self.last_checkpoint
                                        }
                                    }
                                }
                            ]
                        }
                    },
                    "sort": [{"@timestamp": {"order": "asc"}}]
                }

                res = self.es.search(index=self.INDEX, body=query)
                hits = res['hits']['hits']

                if hits:
                    aggregated_alerts = {}

                    for hit in hits:
                        alert_id = hit['_id']
                        if alert_id in self.sent_alerts_cache:
                            continue
                            
                        _src = hit['_source']
                        timestamp = _src['@timestamp']
                        
                        rule_name = _src.get('kibana.alert.rule.name') or "Security Alert"
                        user_name = _src.get('user', {}).get('name') or \
                                    _src.get('winlog', {}).get('user', {}).get('name') or "Unknown"
                        
                        evidence = _src.get('powershell', {}).get('file', {}).get('script_block_text') or \
                                   _src.get('process', {}).get('command_line') or \
                                   _src.get('source', {}).get('ip') or "N/A"

                        proc_name = _src.get('process', {}).get('name') or "N/A"
                        fingerprint = f"{rule_name}|{user_name}|{evidence}"

                        if fingerprint not in aggregated_alerts:
                            aggregated_alerts[fingerprint] = {
                                "source": _src,
                                "count": 1,
                                "last_time": timestamp,
                                "evidence": evidence,
                                "proc_name": proc_name,
                                "user": user_name,
                                "rule": rule_name,
                                "ids": [alert_id]
                            }
                        else:
                            aggregated_alerts[fingerprint]["count"] += 1
                            aggregated_alerts[fingerprint]["last_time"] = timestamp
                            aggregated_alerts[fingerprint]["ids"].append(alert_id)
                    for fp, alert in aggregated_alerts.items():
                        _s = alert["source"]
                        count = alert["count"]
                        risk_score = _s.get('kibana.alert.rule.risk_score') or 0
                        pp_name = _s.get('process', {}).get('parent', {}).get('name') or "N/A"

                        icon = "🔴" if risk_score >= 70 else "🟡" if risk_score >= 40 else "🔵"
                        label = "HIGH" if icon == "🔴" else "MEDIUM" if icon == "🟡" else "LOW"
                        local_time = parser.isoparse(alert["last_time"]).astimezone(tz.tzlocal()).strftime('%H:%M:%S')

                        attempt_str = f" (x{count})" if count > 1 else ""

                        msg = (f"{icon} <b>{label} RISK ALERT{attempt_str}</b>\n"
                               f"Risk Score: <code>{risk_score}</code>\n"
                               f"━━━━━━━━━━━━━━━━━━━━━\n"
                               f"- Time: <code>{local_time}</code> | User: <code>{alert['user']}</code>\n"
                               f"- Rule: <i>{alert['rule']}</i>\n"
                               f"─────────────────────\n"
                               f"- Parent: <code>{pp_name.upper()}</code>\n"
                               f"- Process: <code>{alert['proc_name'].upper()}</code>\n"
                               f"- Evidence:\n<code>{str(alert['evidence']).strip()[:500]}</code>\n"
                               f"━━━━━━━━━━━━━━━━━━━━━")

                        self.send_telegram(msg)
                        for aid in alert["ids"]:
                            self.sent_alerts_cache.append(aid)
                    self.last_checkpoint = hits[-1]['_source']['@timestamp']
            except Exception as e:
                log_callback(f"[-] Error: {e}")

            time.sleep(5)