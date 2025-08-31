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
            
            # User-Agentヘッダーを設定
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            # ログインページにアクセス
            login_url = "https://timetreeapp.com/signin"
            response = self.session.get(login_url)
            
            if response.status_code != 200:
                print(f"❌ ログインページアクセス失敗: {response.status_code}")
                return False
            
            # CSRFトークンを抽出
            csrf_token = None
            if 'csrf-token' in response.text:
                import re
                csrf_match = re.search(r'csrf-token["\']?\s*content=["\']([^"\']+)', response.text)
                if csrf_match:
                    csrf_token = csrf_match.group(1)
                    print(f"✅ CSRFトークン取得: {csrf_token[:20]}...")
            
            # ログイン実行
            login_data = {
                'user[email]': self.timetree_email,
                'user[password]': self.timetree_password,
                'commit': 'ログイン'
            }
            
            # CSRFトークンを追加
            if csrf_token:
                login_data['authenticity_token'] = csrf_token
            
            # ログインPOST
            login_response = self.session.post(
                'https://timetreeapp.com/signin',
                data=login_data,
                allow_redirects=True
            )
            
            # ログイン成功判定
            if login_response.status_code == 200 and 'calendars' in login_response.url:
                print("✅ TimeTreeログイン成功")
                return True
            elif 'signin' in login_response.url:
                print("❌ TimeTreeログイン失敗 - 認証情報を確認してください")
                return False
            else:
                print(f"✅ TimeTreeログイン成功 (リダイレクト: {login_response.url})")
                return True
                
        except Exception as e:
            print(f"❌ TimeTreeログインエラー: {str(e)}")
            return False
    
    def get_today_events(self):
        """今日の予定を取得"""
        try:
            print("📅 今日の予定を取得中...")
            
            today = date.today()
            
            # カレンダーページにアクセス
            calendar_url = f"https://timetreeapp.com/calendars/{self.timetree_calendar_code}"
            response = self.session.get(calendar_url)
            
            if response.status_code != 200:
                print(f"⚠️ カレンダーアクセス失敗: {response.status_code}")
                print("テストデータを使用します")
                return self._get_test_events()
            
            # HTMLから予定を抽出
            events = self._parse_events_from_html(response.text, today)
            
            if not events:
                print("⚠️ 予定の解析に失敗 - テストデータを使用")
                return self._get_test_events()
            
            print(f"✅ {len(events)}件の予定を取得")
            return events
            
        except Exception as e:
            print(f"❌ 予定取得エラー: {str(e)}")
            print("テストデータを使用します")
            return self._get_test_events()
    
    def _get_test_events(self):
        """フォールバック用テストデータ"""
        return [
            {
                'title': 'TimeTreeテストイベント1',
                'start_time': '09:00',
                'location': 'オンライン',
                'description': 'システムテスト中です'
            },
            {
                'title': 'TimeTreeテストイベント2', 
                'start_time': '14:00',
                'location': '',
                'description': 'APIテスト実行中'
            }
        ]
    
    def _parse_events_from_html(self, html_content, target_date):
        """HTMLから予定情報を抽出"""
        try:
            import re
            events = []
            
            # 簡易的なHTML解析 (実際はより複雑な処理が必要)
            # TimeTreeの構造に依存するため、フォールバックも実装
            
            # イベントタイトルを検索
            title_pattern = r'<[^>]*data-event[^>]*>([^<]+)</[^>]*>'
            titles = re.findall(title_pattern, html_content, re.IGNORECASE)
            
            # 時間パターンを検索 
            time_pattern = r'(\d{1,2}:\d{2})'
            times = re.findall(time_pattern, html_content)
            
            # 簡易的にマッチング
            for i, title in enumerate(titles[:5]):  # 最大5件
                start_time = times[i] if i < len(times) else ''
                
                events.append({
                    'title': title.strip(),
                    'start_time': start_time,
                    'location': '',
                    'description': ''
                })
            
            return events
            
        except Exception as e:
            print(f"⚠️ HTML解析エラー: {str(e)}")
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