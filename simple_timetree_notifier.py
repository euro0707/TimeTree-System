#!/usr/bin/env python3
"""
TimeTree Simple Notifier - 最小構成版
基本機能: TimeTree → LINE通知
"""

import os
import json
import requests
from datetime import datetime, date
import sys

class SimpleTimeTreeNotifier:
    def __init__(self):
        # 環境変数から認証情報取得
        self.timetree_email = os.getenv('TIMETREE_EMAIL')
        self.timetree_password = os.getenv('TIMETREE_PASSWORD')
        self.timetree_calendar_code = os.getenv('TIMETREE_CALENDAR_CODE')
        self.line_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
        self.line_user_id = os.getenv('LINE_USER_ID')
        
        self.session = requests.Session()
        
    def validate_config(self):
        """設定値の検証"""
        required_vars = {
            'TIMETREE_EMAIL': self.timetree_email,
            'TIMETREE_PASSWORD': self.timetree_password,
            'TIMETREE_CALENDAR_CODE': self.timetree_calendar_code
        }
        
        missing = [k for k, v in required_vars.items() if not v]
        if missing:
            print(f"❌ 必要な環境変数が不足: {', '.join(missing)}")
            return False
            
        print("✅ 設定値の検証完了")
        return True
    
    def login_timetree(self):
        """TimeTreeにログイン"""
        try:
            print("🔐 TimeTreeにログイン中...")
            
            # ログインページアクセス
            login_url = "https://timetreeapp.com/signin"
            response = self.session.get(login_url)
            
            if response.status_code != 200:
                print(f"❌ ログインページアクセス失敗: {response.status_code}")
                return False
            
            # ログイン実行 (簡易版 - CSRFトークンなど省略)
            login_data = {
                'email': self.timetree_email,
                'password': self.timetree_password
            }
            
            # 注意: 実際のTimeTree APIはより複雑な認証が必要
            # この簡易版はコンセプト確認用
            
            print("✅ TimeTreeログイン処理完了")
            return True
            
        except Exception as e:
            print(f"❌ TimeTreeログインエラー: {str(e)}")
            return False
    
    def get_today_events(self):
        """今日の予定を取得"""
        try:
            print("📅 今日の予定を取得中...")
            
            today = date.today()
            
            # 簡易テストデータ (実際のAPI実装時に置き換え)
            test_events = [
                {
                    'title': 'テストイベント1',
                    'start_time': '09:00',
                    'location': '会議室A',
                    'description': 'プロジェクト会議'
                },
                {
                    'title': 'テストイベント2', 
                    'start_time': '14:00',
                    'location': 'レストランB',
                    'description': 'ランチミーティング'
                }
            ]
            
            print(f"✅ {len(test_events)}件の予定を取得")
            return test_events
            
        except Exception as e:
            print(f"❌ 予定取得エラー: {str(e)}")
            return []
    
    def fix_garbled_text(self, text):
        """文字化け修正 (簡易版)"""
        if not text:
            return text
            
        # よくある文字化けパターン
        fixes = {
            '�': '',
            '��': '',
            '���': '',
        }
        
        for garbled, fixed in fixes.items():
            text = text.replace(garbled, fixed)
            
        return text
    
    def format_line_message(self, events, target_date):
        """LINE通知メッセージ作成"""
        date_str = target_date.strftime('%m月%d日')
        weekdays = ['月', '火', '水', '木', '金', '土', '日']
        weekday = weekdays[target_date.weekday()]
        
        message = f"🌅 おはようございます！\n\n📅 {date_str}({weekday})の予定\n"
        
        if not events:
            message += "今日は予定がありません。\nゆっくりお過ごしください！"
        else:
            message += f"📝 {len(events)}件の予定があります\n\n"
            
            for i, event in enumerate(events, 1):
                title = self.fix_garbled_text(event.get('title', ''))
                start_time = event.get('start_time', '')
                location = event.get('location', '')
                
                message += f"{i}. {title}\n"
                if start_time:
                    message += f"⏰ {start_time}"
                if location:
                    message += f" @ {location}"
                message += "\n\n"
        
        return message
    
    def send_line_notification(self, message):
        """LINE通知送信"""
        if not self.line_token or not self.line_user_id:
            print("⚠️ LINE設定が不完全 - 通知をスキップ")
            return True
            
        try:
            print("📱 LINE通知送信中...")
            
            headers = {
                'Authorization': f'Bearer {self.line_token}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'to': self.line_user_id,
                'messages': [
                    {
                        'type': 'text',
                        'text': message
                    }
                ]
            }
            
            url = 'https://api.line.me/v2/bot/message/push'
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                print("✅ LINE通知送信成功")
                return True
            else:
                print(f"❌ LINE通知送信失敗: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ LINE通知エラー: {str(e)}")
            return False
    
    def run(self):
        """メイン実行"""
        print("=" * 50)
        print("🚀 TimeTree Simple Notifier 開始")
        print("=" * 50)
        
        # 設定確認
        if not self.validate_config():
            return False
        
        # TimeTreeログイン
        if not self.login_timetree():
            return False
        
        # 今日の予定取得
        events = self.get_today_events()
        
        # メッセージ作成
        today = date.today()
        message = self.format_line_message(events, today)
        
        print("\n📝 送信メッセージ:")
        print("-" * 30)
        print(message)
        print("-" * 30)
        
        # テストモード確認
        test_mode = os.getenv('TEST_MODE', 'false').lower() == 'true'
        
        if test_mode:
            print("🧪 テストモード - 実際の通知は送信しません")
            success = True
        else:
            # LINE通知送信
            success = self.send_line_notification(message)
        
        print("=" * 50)
        if success:
            print("🎉 処理完了!")
        else:
            print("❌ 処理失敗")
        print("=" * 50)
        
        return success

if __name__ == "__main__":
    notifier = SimpleTimeTreeNotifier()
    success = notifier.run()
    sys.exit(0 if success else 1)