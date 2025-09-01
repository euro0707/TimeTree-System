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
        """TimeTreeログイン (現在は無効化)"""
        print("⚠️ TimeTree自動ログイン: JavaScript必須のSPAのため技術的に困難")
        print("💡 推奨: 手動でTimeTreeアプリまたはWeb版を使用")
        print("📂 ICSファイル手動取得後、data/backup.icsに配置すれば実データ通知可能")
        return False
    
    def get_today_events(self):
        """今日の予定を取得"""
        print("📅 今日の予定を取得中...")
        
        # Method 1: TimeTree-Exporter実行試行
        events = self._try_timetree_exporter()
        if events:
            print(f"✅ TimeTree-Exporterで{len(events)}件取得")
            return events
        
        # Method 2: Web API試行 (既存)
        events = self._try_web_api()
        if events:
            print(f"✅ Web APIで{len(events)}件取得")
            return events
            
        # Method 3: フォールバック
        print("⚠️ 全ての取得方法が失敗 - フォールバックデータを使用")
        return self._get_test_events()
    
    def _try_timetree_exporter(self):
        """既存のICSファイルから取得試行"""
        try:
            from pathlib import Path
            
            print("🔧 既存ICSファイル確認中...")
            
            # 既存のバックアップファイルを確認
            backup_ics = Path("./data/backup.ics")
            temp_ics = Path("./temp/timetree_export.ics")
            
            # 優先順位: 新しいファイル → バックアップファイル
            for ics_file in [temp_ics, backup_ics]:
                if ics_file.exists() and ics_file.stat().st_size > 0:
                    print(f"✅ ICSファイル発見: {ics_file}")
                    
                    # ICSファイルをパース
                    events = self._parse_ics_file(str(ics_file))
                    
                    if events:
                        print(f"✅ ICSファイルから{len(events)}件の予定を取得")
                        return events
                    else:
                        print(f"⚠️ {ics_file}に今日の予定なし")
                        continue
            
            print("⚠️ 利用可能なICSファイルが見つからない")
            return None
                
        except Exception as e:
            print(f"⚠️ ICSファイル読み込みエラー: {str(e)}")
            return None
    
    def _try_web_api(self):
        """Web API による取得試行 (現在は無効化)"""
        print("⚠️ TimeTree Web API: JavaScript必須のため自動ログイン不可")
        print("💡 解決方法: 手動でTimeTreeからICSファイルを取得してdata/backup.icsに配置")
        return None
    
    def _parse_ics_file(self, file_path):
        """ICSファイルから今日の予定を抽出"""
        try:
            from datetime import datetime
            import re
            
            today = date.today()
            events = []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # ICS形式の簡易パース (icalendarライブラリなしで)
            # VEVENT...END:VEVENT のブロックを抽出
            event_blocks = re.findall(r'BEGIN:VEVENT(.*?)END:VEVENT', content, re.DOTALL)
            
            for block in event_blocks:
                event_data = {}
                
                # SUMMARY (タイトル) 抽出
                summary_match = re.search(r'SUMMARY:(.*)', block)
                if summary_match:
                    event_data['title'] = summary_match.group(1).strip()
                
                # DTSTART (開始時間) 抽出
                dtstart_match = re.search(r'DTSTART[^:]*:(.*)', block)
                if dtstart_match:
                    dtstart = dtstart_match.group(1).strip()
                    
                    # 今日の予定かチェック
                    if today.strftime('%Y%m%d') in dtstart:
                        # 時間抽出
                        if 'T' in dtstart:
                            time_part = dtstart.split('T')[1][:4]
                            hour = int(time_part[:2])
                            minute = int(time_part[2:])
                            event_data['start_time'] = f"{hour:02d}:{minute:02d}"
                        else:
                            event_data['start_time'] = ''
                        
                        # LOCATION 抽出
                        location_match = re.search(r'LOCATION:(.*)', block)
                        event_data['location'] = location_match.group(1).strip() if location_match else ''
                        
                        # DESCRIPTION 抽出
                        desc_match = re.search(r'DESCRIPTION:(.*)', block)
                        event_data['description'] = desc_match.group(1).strip() if desc_match else ''
                        
                        if 'title' in event_data:
                            events.append(event_data)
            
            return events
            
        except Exception as e:
            print(f"⚠️ ICSファイル解析エラー: {str(e)}")
            return None
    
    def _get_test_events(self):
        """フォールバック用テストデータ"""
        from datetime import datetime
        current_time = datetime.now().strftime('%H:%M')
        
        return [
            {
                'title': '⚠️ TimeTree自動同期停止中',
                'start_time': '08:00',
                'location': 'システム通知',
                'description': f'TimeTree SPAへの変更により自動ログイン不可 ({current_time})'
            },
            {
                'title': '💡 手動データ更新が必要', 
                'start_time': '08:30',
                'location': 'data/backup.ics',
                'description': 'TimeTreeから手動でICSエクスポート → data/backup.icsに配置'
            },
            {
                'title': '🔧 システム正常動作中',
                'start_time': '09:00',
                'location': 'GitHub Actions',
                'description': 'LINE通知機能は正常 - データ取得のみ課題'
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
            print(f"   TOKEN設定: {'✅' if self.line_token else '❌'}")
            print(f"   USER_ID設定: {'✅' if self.line_user_id else '❌'}")
            return True
            
        try:
            print("📱 LINE通知送信中...")
            print(f"   送信先ユーザーID: {self.line_user_id}")
            print(f"   メッセージ長: {len(message)}文字")
            
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
            print(f"   API URL: {url}")
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            print(f"   レスポンス: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ LINE通知送信成功")
                response_data = response.json() if response.text else {}
                print(f"   応答データ: {response_data}")
                return True
            else:
                print(f"❌ LINE通知送信失敗: {response.status_code}")
                print(f"   エラー応答: {response.text}")
                print(f"   応答ヘッダー: {dict(response.headers)}")
                return False
                
        except Exception as e:
            print(f"❌ LINE通知エラー: {str(e)}")
            print(f"   エラー種類: {type(e).__name__}")
            import traceback
            print(f"   詳細トレース: {traceback.format_exc()}")
            return False
    
    def run(self):
        """メイン実行"""
        print("=" * 50)
        print("🚀 TimeTree Simple Notifier 開始")
        print("=" * 50)
        
        # 設定確認
        if not self.validate_config():
            return False
        
        # TimeTreeログイン (失敗時はフォールバック)
        login_success = self.login_timetree()
        if not login_success:
            print("⚠️ TimeTreeログイン失敗 - フォールバックモードで継続")
        
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