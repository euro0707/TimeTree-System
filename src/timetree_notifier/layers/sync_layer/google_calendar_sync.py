"""
Google Calendar同期システム - 設計書の「同期層」に基づく実装
TimeTree ↔ Google Calendar双方向同期・競合解決
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import logging

# Google Calendar API関連
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

# 内部モジュール
from ...core.models import Event as TimeTreeEvent

logger = logging.getLogger(__name__)

# Google Calendar API スコープ
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events'
]


class SyncDirection(Enum):
    """同期方向"""
    ONE_WAY_TIMETREE_TO_GOOGLE = "one_way_tt_to_gc"
    ONE_WAY_GOOGLE_TO_TIMETREE = "one_way_gc_to_tt" 
    TWO_WAY = "two_way"


class SyncStatus(Enum):
    """同期ステータス"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CONFLICT = "conflict"


@dataclass
class GoogleCalendarEvent:
    """Google Calendarイベント"""
    id: str
    summary: str
    description: Optional[str]
    location: Optional[str]
    start: datetime
    end: Optional[datetime]
    all_day: bool
    created: datetime
    updated: datetime
    source_event_id: Optional[str] = None  # TimeTreeイベントID
    
    def to_dict(self) -> Dict[str, Any]:
        """Google Calendar API形式に変換"""
        event_dict = {
            'summary': self.summary,
            'description': self.description or '',
            'location': self.location or '',
        }
        
        if self.all_day:
            event_dict['start'] = {
                'date': self.start.strftime('%Y-%m-%d'),
                'timeZone': 'Asia/Tokyo'
            }
            event_dict['end'] = {
                'date': (self.end or self.start + timedelta(days=1)).strftime('%Y-%m-%d'),
                'timeZone': 'Asia/Tokyo'
            }
        else:
            event_dict['start'] = {
                'dateTime': self.start.isoformat(),
                'timeZone': 'Asia/Tokyo'
            }
            event_dict['end'] = {
                'dateTime': (self.end or self.start + timedelta(hours=1)).isoformat(),
                'timeZone': 'Asia/Tokyo'
            }
        
        # TimeTreeイベントIDを記録（カスタムプロパティ）
        if self.source_event_id:
            event_dict['extendedProperties'] = {
                'private': {
                    'timetree_event_id': self.source_event_id,
                    'sync_source': 'timetree_notifier_v3'
                }
            }
        
        return event_dict


@dataclass 
class SyncResult:
    """同期結果"""
    status: SyncStatus
    events_processed: int
    events_created: int
    events_updated: int
    events_deleted: int
    conflicts: List[Dict[str, Any]]
    errors: List[str]
    sync_time: datetime
    
    def is_successful(self) -> bool:
        return self.status == SyncStatus.SUCCESS
    
    def summary(self) -> str:
        return (f"Sync {self.status.value}: "
                f"{self.events_processed} processed, "
                f"{self.events_created} created, "
                f"{self.events_updated} updated, "
                f"{self.events_deleted} deleted, "
                f"{len(self.conflicts)} conflicts")


class GoogleCalendarSyncManager:
    """Google Calendar同期管理システム"""
    
    def __init__(self, config: Dict[str, Any]):
        if not GOOGLE_API_AVAILABLE:
            raise ImportError("Google API libraries not available. Install google-auth, google-auth-oauthlib, google-api-python-client")
        
        self.config = config
        self.calendar_id = config.get('calendar_id', 'primary')
        self.sync_direction = SyncDirection(config.get('sync_strategy', 'one_way_tt_to_gc'))
        self.credentials_path = config.get('credentials_path', 'config/secrets/google_credentials.json')
        self.token_path = config.get('token_path', 'config/secrets/google_token.json')
        
        self.credentials: Optional[Credentials] = None
        self.service = None
        self.conflict_resolver = None  # 後で初期化
    
    async def initialize(self):
        """同期システムの初期化"""
        try:
            # Google認証
            await self._authenticate()
            
            # Google Calendar サービス構築
            self.service = build('calendar', 'v3', credentials=self.credentials)
            
            # 競合解決器の初期化
            from .conflict_resolver import ConflictResolver
            self.conflict_resolver = ConflictResolver(self.config.get('conflict_resolution', {}))
            
            logger.info("Google Calendar sync manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar sync: {e}")
            return False
    
    async def _authenticate(self):
        """Google認証処理"""
        creds = None
        
        # 既存のトークンファイルから読み込み
        try:
            if Path(self.token_path).exists():
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        except Exception as e:
            logger.warning(f"Failed to load existing credentials: {e}")
        
        # 認証情報が無効または期限切れの場合
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Google credentials refreshed")
                except Exception as e:
                    logger.error(f"Failed to refresh credentials: {e}")
                    creds = None
            
            # 新規認証フローが必要
            if not creds:
                if not Path(self.credentials_path).exists():
                    raise FileNotFoundError(f"Google credentials file not found: {self.credentials_path}")
                
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
                logger.info("New Google credentials obtained")
            
            # トークンを保存
            try:
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
                logger.info(f"Credentials saved to {self.token_path}")
            except Exception as e:
                logger.warning(f"Failed to save credentials: {e}")
        
        self.credentials = creds
    
    async def sync_events(self, timetree_events: List[TimeTreeEvent]) -> SyncResult:
        """TimeTreeイベントをGoogle Calendarに同期"""
        if not self.service:
            raise RuntimeError("Google Calendar service not initialized")
        
        sync_start = datetime.now()
        result = SyncResult(
            status=SyncStatus.SUCCESS,
            events_processed=len(timetree_events),
            events_created=0,
            events_updated=0,
            events_deleted=0,
            conflicts=[],
            errors=[],
            sync_time=sync_start
        )
        
        try:
            logger.info(f"Starting sync: {len(timetree_events)} TimeTree events")
            
            # 1. 既存のGoogle Calendarイベントを取得
            existing_events = await self._fetch_google_events()
            logger.info(f"Found {len(existing_events)} existing Google Calendar events")
            
            # 2. TimeTreeイベントをGoogle Calendar形式に変換
            google_events = self._convert_timetree_to_google(timetree_events)
            
            # 3. 同期処理実行
            if self.sync_direction == SyncDirection.ONE_WAY_TIMETREE_TO_GOOGLE:
                await self._sync_one_way_to_google(google_events, existing_events, result)
            elif self.sync_direction == SyncDirection.TWO_WAY:
                await self._sync_two_way(google_events, existing_events, result)
            
            # 4. 結果判定
            if result.errors:
                result.status = SyncStatus.PARTIAL if result.events_created + result.events_updated > 0 else SyncStatus.FAILED
            
            logger.info(f"Sync completed: {result.summary()}")
            return result
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            result.status = SyncStatus.FAILED
            result.errors.append(str(e))
            return result
    
    async def _fetch_google_events(self, days_ahead: int = 30) -> List[GoogleCalendarEvent]:
        """Google Calendarからイベントを取得"""
        try:
            # 取得期間設定（今日から30日先まで）
            time_min = datetime.now().isoformat() + 'Z'
            time_max = (datetime.now() + timedelta(days=days_ahead)).isoformat() + 'Z'
            
            # Google Calendar APIコール
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=2500,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # GoogleCalendarEventオブジェクトに変換
            google_events = []
            for event in events:
                try:
                    google_event = self._parse_google_event(event)
                    if google_event:
                        google_events.append(google_event)
                except Exception as e:
                    logger.warning(f"Failed to parse Google Calendar event: {e}")
            
            return google_events
            
        except HttpError as e:
            logger.error(f"Google Calendar API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch Google Calendar events: {e}")
            raise
    
    def _parse_google_event(self, event_data: Dict[str, Any]) -> Optional[GoogleCalendarEvent]:
        """Google Calendar APIレスポンスをパース"""
        try:
            # 基本情報
            event_id = event_data.get('id')
            summary = event_data.get('summary', '(No title)')
            description = event_data.get('description', '')
            location = event_data.get('location', '')
            
            # 日時情報
            start_info = event_data.get('start', {})
            end_info = event_data.get('end', {})
            
            # 終日イベントかどうか
            all_day = 'date' in start_info
            
            if all_day:
                start = datetime.fromisoformat(start_info['date']).replace(tzinfo=timezone.utc)
                end = datetime.fromisoformat(end_info['date']).replace(tzinfo=timezone.utc) if end_info.get('date') else None
            else:
                start = datetime.fromisoformat(start_info['dateTime'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(end_info['dateTime'].replace('Z', '+00:00')) if end_info.get('dateTime') else None
            
            # メタデータ
            created = datetime.fromisoformat(event_data.get('created', '').replace('Z', '+00:00'))
            updated = datetime.fromisoformat(event_data.get('updated', '').replace('Z', '+00:00'))
            
            # TimeTreeイベントIDの取得
            extended_props = event_data.get('extendedProperties', {}).get('private', {})
            source_event_id = extended_props.get('timetree_event_id')
            
            return GoogleCalendarEvent(
                id=event_id,
                summary=summary,
                description=description,
                location=location,
                start=start,
                end=end,
                all_day=all_day,
                created=created,
                updated=updated,
                source_event_id=source_event_id
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse Google Calendar event: {e}")
            return None
    
    def _convert_timetree_to_google(self, timetree_events: List[TimeTreeEvent]) -> List[GoogleCalendarEvent]:
        """TimeTreeイベントをGoogle Calendar形式に変換"""
        google_events = []
        
        for tt_event in timetree_events:
            try:
                # TimeTreeイベントをGoogle Calendar形式に変換
                google_event = GoogleCalendarEvent(
                    id='',  # 新規作成時は空
                    summary=f"📱 {tt_event.title}",  # TimeTree印を追加
                    description=f"TimeTreeから同期\n\n{tt_event.description or ''}",
                    location=tt_event.location or '',
                    start=tt_event.start_time or datetime.now(),
                    end=tt_event.end_time,
                    all_day=tt_event.is_all_day,
                    created=datetime.now(),
                    updated=datetime.now(),
                    source_event_id=getattr(tt_event, 'id', None)
                )
                
                google_events.append(google_event)
                
            except Exception as e:
                logger.error(f"Failed to convert TimeTree event: {e}")
        
        return google_events
    
    async def _sync_one_way_to_google(self, google_events: List[GoogleCalendarEvent], 
                                    existing_events: List[GoogleCalendarEvent], 
                                    result: SyncResult):
        """一方向同期: TimeTree → Google Calendar"""
        
        # TimeTree由来の既存イベントを特定（📱プレフィックスまたはextendedPropertiesで判定）
        timetree_events_in_google = [
            event for event in existing_events 
            if event.summary.startswith('📱') or event.source_event_id
        ]
        
        # 既存のTimeTree同期イベントを削除（重複防止）
        for event in timetree_events_in_google:
            try:
                self.service.events().delete(
                    calendarId=self.calendar_id,
                    eventId=event.id
                ).execute()
                result.events_deleted += 1
                logger.debug(f"Deleted old TimeTree event: {event.summary}")
            except Exception as e:
                logger.warning(f"Failed to delete event {event.id}: {e}")
                result.errors.append(f"Delete failed: {e}")
        
        # 新しいTimeTreeイベントを作成
        for google_event in google_events:
            try:
                event_body = google_event.to_dict()
                
                created_event = self.service.events().insert(
                    calendarId=self.calendar_id,
                    body=event_body
                ).execute()
                
                result.events_created += 1
                logger.debug(f"Created Google Calendar event: {google_event.summary}")
                
            except Exception as e:
                logger.error(f"Failed to create event '{google_event.summary}': {e}")
                result.errors.append(f"Create failed: {e}")
    
    async def _sync_two_way(self, google_events: List[GoogleCalendarEvent], 
                          existing_events: List[GoogleCalendarEvent], 
                          result: SyncResult):
        """双方向同期（将来実装）"""
        # 現時点では一方向同期のみ実装
        logger.warning("Two-way sync not implemented yet, falling back to one-way sync")
        await self._sync_one_way_to_google(google_events, existing_events, result)


# 使用例とテスト
if __name__ == "__main__":
    import asyncio
    from pathlib import Path
    
    async def test_google_calendar_sync():
        """Google Calendar同期のテスト"""
        
        # テスト設定
        config = {
            'calendar_id': 'primary',
            'sync_strategy': 'one_way_tt_to_gc',
            'credentials_path': 'config/secrets/google_credentials.json',
            'token_path': 'config/secrets/google_token.json'
        }
        
        # 同期マネージャー初期化
        sync_manager = GoogleCalendarSyncManager(config)
        
        if not await sync_manager.initialize():
            print("Failed to initialize Google Calendar sync")
            return
        
        # テスト用TimeTreeイベント
        from datetime import datetime
        
        test_events = [
            TimeTreeEvent(
                title="テスト会議",
                start_time=datetime.now() + timedelta(hours=1),
                end_time=datetime.now() + timedelta(hours=2),
                is_all_day=False,
                description="Google Calendar同期テスト",
                location="オンライン"
            )
        ]
        
        # 同期実行
        result = await sync_manager.sync_events(test_events)
        print(f"Sync result: {result.summary()}")
        
        if result.errors:
            for error in result.errors:
                print(f"Error: {error}")
    
    # テスト実行（Google API設定済みの場合のみ）
    if GOOGLE_API_AVAILABLE:
        print("Google Calendar sync test (requires Google API setup)")
        # asyncio.run(test_google_calendar_sync())
    else:
        print("Google API libraries not available - install google-auth, google-auth-oauthlib, google-api-python-client")