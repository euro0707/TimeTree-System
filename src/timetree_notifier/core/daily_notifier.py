"""毎朝の定時通知機能"""

import asyncio
import subprocess
import time
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo

from icalendar import Calendar
from loguru import logger

from .models import Event, NotificationResult, ExportResult, DailySummary
from ..config import Config


class DailySummaryNotifier:
    """毎朝の定時通知管理クラス"""
    
    def __init__(self, config: Config):
        self.config = config
        self.line_notifier = LineNotifier(
            config.notification.line_channel_access_token, 
            config.notification.line_user_id
        )
        
    async def send_daily_summary(self, target_date: Optional[date] = None) -> bool:
        """毎朝の予定サマリー送信"""
        try:
            if target_date is None:
                target_date = datetime.now(ZoneInfo(self.config.daily_summary.timezone)).date()
            
            logger.info(f"Starting daily summary for {target_date}")
            
            # TimeTree-Exporterでデータ取得
            export_result = await self._execute_timetree_exporter()
            
            if not export_result.success:
                logger.error(f"TimeTree export failed: {export_result.error_message}")
                return await self._send_error_notification(target_date, export_result.error_message)
            
            # 今日の予定を抽出
            today_events = self._extract_today_events(export_result.output_file, target_date)
            
            # 日次サマリー生成
            summary = self._generate_daily_summary(target_date, today_events)
            
            # LINE通知送信
            result = await self.line_notifier.send_message(summary.message)
            
            if result.success:
                logger.info(f"Daily summary sent successfully for {target_date}")
                # バックアップファイル保存
                self._backup_ics_file(export_result.output_file)
            else:
                logger.error(f"Failed to send daily summary: {result.error_message}")
            
            return result.success
            
        except Exception as e:
            logger.error(f"Unexpected error in daily summary: {e}")
            return await self._send_error_notification(target_date, str(e))
    
    async def _execute_timetree_exporter(self) -> ExportResult:
        """TimeTree-Exporterの実行"""
        temp_file = Path(self.config.paths.temp_ics)
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        
        start_time = time.time()
        
        try:
            cmd = [
                "python", "-m", "timetree_exporter",
                "-o", str(temp_file),
                "-e", self.config.timetree.email,
                "-c", self.config.timetree.calendar_code
            ]
            
            # 環境変数設定
            import os
            env = os.environ.copy()
            env.update({
                "TIMETREE_EMAIL": self.config.timetree.email,
                "TIMETREE_PASSWORD": self.config.timetree.password
            })
            
            logger.debug(f"Executing: {' '.join(cmd)}")
            
            # プロセス実行
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.timetree.exporter.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return ExportResult(
                    success=False,
                    error_message="TimeTree-Exporter execution timeout",
                    error_type="timeout",
                    execution_time=time.time() - start_time
                )
            
            execution_time = time.time() - start_time
            
            if process.returncode == 0:
                if temp_file.exists() and temp_file.stat().st_size > 0:
                    return ExportResult(
                        success=True,
                        output_file=temp_file,
                        execution_time=execution_time
                    )
                else:
                    return ExportResult(
                        success=False,
                        error_message="ICS file was not created or is empty",
                        error_type="empty_output",
                        execution_time=execution_time
                    )
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                return ExportResult(
                    success=False,
                    error_message=error_msg,
                    error_type="execution_error",
                    execution_time=execution_time
                )
                
        except Exception as e:
            return ExportResult(
                success=False,
                error_message=str(e),
                error_type="system_error",
                execution_time=time.time() - start_time
            )
    
    def _extract_today_events(self, ics_file: Path, target_date: date) -> List[Event]:
        """ICSファイルから今日の予定を抽出"""
        events = []
        
        try:
            with open(ics_file, 'rb') as f:
                calendar = Calendar.from_ical(f.read())
            
            for component in calendar.walk():
                if component.name == "VEVENT":
                    try:
                        event = self._parse_event_component(component, target_date)
                        if event:
                            events.append(event)
                    except Exception as e:
                        logger.warning(f"Failed to parse event: {e}")
                        continue
            
            # 時間順でソート（タイムゾーンを考慮）
            def sort_key(event):
                if isinstance(event.start_time, datetime):
                    # タイムゾーン付きdatetimeの場合、ローカル時間に変換
                    return event.start_time.replace(tzinfo=None) if event.start_time.tzinfo else event.start_time
                else:
                    # dateの場合、その日の開始時間として扱う
                    return datetime.combine(event.start_time, datetime.min.time())
            
            events.sort(key=sort_key)
            
            logger.info(f"Extracted {len(events)} events for {target_date}")
            return events
            
        except Exception as e:
            logger.error(f"Failed to parse ICS file: {e}")
            return []
    
    def _parse_event_component(self, component, target_date: date) -> Optional[Event]:
        """ICSコンポーネントからEventオブジェクトを生成"""
        try:
            # 開始時間の取得
            dtstart = component.get('dtstart')
            if not dtstart:
                return None
            
            start_time = dtstart.dt
            
            # 日付の比較
            if isinstance(start_time, datetime):
                event_date = start_time.date()
            elif isinstance(start_time, date):
                event_date = start_time
            else:
                logger.warning(f"Unexpected start_time type: {type(start_time)}")
                return None
                
            if event_date != target_date:
                return None
            
            # 終了時間の取得
            dtend = component.get('dtend')
            end_time = dtend.dt if dtend else None
            
            # その他の情報取得
            title = str(component.get('summary', '無題'))
            description = str(component.get('description', ''))
            location = str(component.get('location', ''))
            
            return Event(
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=description,
                location=location
            )
            
        except Exception as e:
            logger.warning(f"Event parsing error: {e}")
            return None
    
    def _generate_daily_summary(self, target_date: date, events: List[Event]) -> DailySummary:
        """日次サマリーの生成"""
        config = self.config.daily_summary
        notification_config = self.config.notification
        weekday_names = ['月', '火', '水', '木', '金', '土', '日']
        weekday = weekday_names[target_date.weekday()]
        
        # メッセージ組み立て
        message_parts = []
        
        # ヘッダー
        message_parts.append(notification_config.greeting)
        message_parts.append("")
        message_parts.append(f"📅 {target_date.strftime('%Y年%m月%d日')}（{weekday}）")
        message_parts.append("")
        
        # 予定内容
        if not events:
            message_parts.append("📝 " + config.no_events_message)
        else:
            message_parts.append("⏰ 今日の予定:")
            display_events = events[:config.max_events_display]
            
            for event in display_events:
                time_str = event.format_time_range()
                message_parts.append(f"・{time_str} {event.title}")
                
                # 説明を追加
                if config.include_description and event.description.strip():
                    desc = event.description.strip()[:100]  # 100文字制限
                    message_parts.append(f"  {desc}")
                
                # 場所を追加
                if config.include_location and event.location.strip():
                    message_parts.append(f"  📍 {event.location}")
            
            # 省略表示
            if len(events) > config.max_events_display:
                remaining = len(events) - config.max_events_display
                message_parts.append(f"  ... 他{remaining}件の予定")
        
        message_parts.append("")
        message_parts.append(notification_config.closing)
        message_parts.append("")
        message_parts.append("---")
        message_parts.append(f"{notification_config.footer} | {datetime.now().strftime('%H:%M')}送信")
        
        full_message = "\n".join(message_parts)
        
        # 文字数制限チェック
        if len(full_message) > self.config.notification.max_message_length:
            logger.warning("Message too long, truncating...")
            full_message = full_message[:self.config.notification.max_message_length - 10] + "...(省略)"
        
        return DailySummary(
            date=target_date,
            events=events,
            total_events=len(events),
            message=full_message,
            generated_at=datetime.now()
        )
    
    def _backup_ics_file(self, source_file: Path):
        """ICSファイルのバックアップ保存"""
        try:
            backup_path = Path(self.config.paths.backup_data)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            import shutil
            shutil.copy2(source_file, backup_path)
            logger.debug(f"ICS file backed up to {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to backup ICS file: {e}")
    
    async def _send_error_notification(self, target_date: date, error_message: str) -> bool:
        """エラー通知の送信"""
        try:
            message = f"⚠️ TimeTree通知システム エラー\n\n"
            message += f"日付: {target_date}\n"
            message += f"時刻: {datetime.now().strftime('%H:%M')}\n\n"
            message += f"エラー内容:\n{error_message}\n\n"
            message += "手動でTimeTreeを確認してください。"
            
            result = await self.line_notifier.send_message(message)
            return result.success
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
            return False


class LineNotifier:
    """LINE Messaging API通知クラス"""
    
    def __init__(self, channel_access_token: str, user_id: str):
        self.channel_access_token = channel_access_token
        self.user_id = user_id
        self.api_url = "https://api.line.me/v2/bot/message/push"
    
    async def send_message(self, message: str) -> NotificationResult:
        """LINE通知送信（Messaging API）"""
        try:
            import requests
            
            headers = {
                "Authorization": f"Bearer {self.channel_access_token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "to": self.user_id,
                "messages": [
                    {
                        "type": "text",
                        "text": message
                    }
                ]
            }
            
            response = requests.post(self.api_url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                return NotificationResult(success=True, message="Notification sent successfully")
            else:
                error_detail = response.text if response.text else "Unknown error"
                return NotificationResult(
                    success=False,
                    error_message=f"HTTP {response.status_code}: {error_detail}"
                )
                
        except Exception as e:
            return NotificationResult(
                success=False,
                error_message=str(e)
            )
