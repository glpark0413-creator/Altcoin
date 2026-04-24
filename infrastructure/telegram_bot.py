import requests
from datetime import datetime

class TelegramReporter:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = None

    def send_message(self, text: str):
        """텔레그램 메시지 발송 코어 메서드"""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML" # 필요시 굵은 글씨(<b>) 등 서식 적용 가능
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
        except Exception as e:
            # 텔레그램 에러가 매매 로직을 멈추게 해선 안 되므로 에러만 로깅
            print(f"[{datetime.now()}] 텔레그램 발송 실패: {e}")

    def get_new_commands(self) -> list:
        """새로운 텔레그램 명령어 수신"""
        url = f"{self.base_url}/getUpdates"
        params = {"timeout": 1}
        if self.last_update_id:
            params['offset'] = self.last_update_id + 1
            
        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                commands = []
                if data.get("ok"):
                    for update in data["result"]:
                        self.last_update_id = update["update_id"]
                        if "message" in update and "text" in update["message"]:
                            if str(update["message"]["chat"]["id"]) == str(self.chat_id):
                                commands.append(update["message"]["text"])
                return commands
        except Exception:
            pass
        return []

    def send_buy_report(self, trade_data: dict):
        """기획서 3. 매수 시 리포트 포맷"""
        target_price1 = trade_data['avg_price'] * 1.015
        target_price2 = trade_data['avg_price'] * 1.025
        
        msg = (
            f"🟢 <b>[매수 리포트]</b>\n"
            f"- 매수 코인 : {trade_data['coin']}\n"
            f"- 매수 금액 : {trade_data['total_price']:,.0f} KRW\n"
            f"- 매수 수수료 : {trade_data['fee']:,.0f} KRW\n"
            f"- 매수 평단가 : {trade_data['avg_price']:,.4f} KRW\n"
            f"- 1차 목표 익절가 : {target_price1:,.4f} KRW\n"
            f"- 2차 목표 익절가 : {target_price2:,.4f} KRW\n"
            f"- 잔여 현금 : {trade_data['remain_krw']:,.0f} KRW"
        )
        self.send_message(msg)

    def send_sell_report(self, trade_data: dict, daily_profit: float, monthly_profit: float):
        """기획서 3. 매도 시 리포트 포맷"""
        msg = (
            f"🔴 <b>[매도 리포트]</b>\n"
            f"- 매도 코인 : {trade_data['coin']}\n"
            f"- 매도 금액 : {trade_data['total_price']:,.0f} KRW\n"
            f"- 매도 수수료 : {trade_data['fee']:,.0f} KRW\n"
            f"- 매도 평단가 : {trade_data['avg_price']:,.4f} KRW\n"
            f"--------------------------\n"
            f"📈 당일 수익 : {daily_profit:,.0f} KRW\n"
            f"📊 당월 수익 : {monthly_profit:,.0f} KRW"
        )
        self.send_message(msg)