"""
イベントストレージシステム - 設計書の「データベース設計」に基づく実装
SQLiteによるイベント永続化・同期ログ・通知キューの管理
"""

import sqlite3
import asyncio
import aiosqlite
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pathlib import Path
import logging
import hashlib

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """同期ステータス"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CONFLICT = "conflict"


class NotificationStatus(Enum):
    """通知ステータス"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StoredEvent:
    """ストレージイベント"""
    id: str
    title: str
    start_datetime: datetime
    end_datetime: Optional[datetime]
    is_all_day: bool
    description: str
    location: str
    source_hash: str
    created_at: datetime
    updated_at: datetime
    sync_status: SyncStatus
    google_calendar_id: Optional[str] = None
    
    def calculate_hash(self) -> str:
        """イベント内容のハッシュ計算"""
        content = f"{self.title}|{self.start_datetime}|{self.end_datetime}|{self.description}|{self.location}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        data = asdict(self)
        data['start_datetime'] = self.start_datetime.isoformat()
        data['end_datetime'] = self.end_datetime.isoformat() if self.end_datetime else None
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        data['sync_status'] = self.sync_status.value
        return data


@dataclass
class SyncLog:
    """同期ログ"""
    id: Optional[int]
    event_id: str
    action: str  # CREATE, UPDATE, DELETE, SYNC
    source: str  # timetree, google_calendar
    target: str
    status: SyncStatus
    error_message: Optional[str]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['status'] = self.status.value
        return data


@dataclass
class NotificationQueue:
    """通知キュー"""
    id: Optional[int]
    event_id: str
    notification_type: str  # DAILY_SUMMARY, EVENT_ADDED, EVENT_UPDATED, REMINDER
    scheduled_time: datetime
    channel: str  # line, gas, slack, discord
    status: NotificationStatus
    attempts: int
    last_attempt: Optional[datetime]
    created_at: datetime
    message_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['scheduled_time'] = self.scheduled_time.isoformat()
        data['last_attempt'] = self.last_attempt.isoformat() if self.last_attempt else None
        data['created_at'] = self.created_at.isoformat()
        data['status'] = self.status.value
        data['message_data'] = json.dumps(self.message_data) if self.message_data else None
        return data


class EventStorage:
    """イベントストレージ管理システム"""
    
    def __init__(self, database_path: Union[str, Path] = "data/events.db"):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 接続プール（非同期）
        self._connection_pool: Optional[aiosqlite.Connection] = None
    
    async def initialize(self) -> bool:
        """データベース初期化"""
        try:
            await self._create_tables()
            await self._create_indexes()
            
            logger.info(f"Event storage initialized: {self.database_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize event storage: {e}")
            return False
    
    async def _create_tables(self):
        """テーブル作成"""
        
        # イベントテーブル
        events_table_sql = """
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            start_datetime TIMESTAMP NOT NULL,
            end_datetime TIMESTAMP,
            is_all_day BOOLEAN DEFAULT FALSE,
            description TEXT DEFAULT '',
            location TEXT DEFAULT '',
            source_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sync_status TEXT DEFAULT 'pending',
            google_calendar_id TEXT
        )
        """
        
        # 同期ログテーブル
        sync_logs_table_sql = """
        CREATE TABLE IF NOT EXISTS sync_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT,
            action TEXT NOT NULL,
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
        """
        
        # 通知キューテーブル
        notification_queue_table_sql = """
        CREATE TABLE IF NOT EXISTS notification_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT,
            notification_type TEXT NOT NULL,
            scheduled_time TIMESTAMP NOT NULL,
            channel TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            attempts INTEGER DEFAULT 0,
            last_attempt TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            message_data TEXT,
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
        """
        
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute(events_table_sql)
            await db.execute(sync_logs_table_sql)
            await db.execute(notification_queue_table_sql)
            await db.commit()
    
    async def _create_indexes(self):
        """インデックス作成"""
        indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_events_start_datetime ON events(start_datetime)",
            "CREATE INDEX IF NOT EXISTS idx_events_sync_status ON events(sync_status)",
            "CREATE INDEX IF NOT EXISTS idx_events_source_hash ON events(source_hash)",
            "CREATE INDEX IF NOT EXISTS idx_sync_logs_event_id ON sync_logs(event_id)",
            "CREATE INDEX IF NOT EXISTS idx_sync_logs_timestamp ON sync_logs(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_notification_queue_scheduled_time ON notification_queue(scheduled_time)",
            "CREATE INDEX IF NOT EXISTS idx_notification_queue_status ON notification_queue(status)"
        ]
        
        async with aiosqlite.connect(self.database_path) as db:
            for index_sql in indexes_sql:
                await db.execute(index_sql)
            await db.commit()
    
    async def store_event(self, event: StoredEvent) -> bool:
        """イベントの保存"""
        try:
            async with aiosqlite.connect(self.database_path) as db:
                # 既存イベントチェック
                existing = await self._get_event_by_id(event.id, db)
                
                if existing:
                    # 更新
                    await self._update_event(event, db)
                    action = "UPDATE"
                else:
                    # 新規作成
                    await self._insert_event(event, db)
                    action = "CREATE"
                
                # 同期ログ記録
                await self._log_sync_action(event.id, action, "timetree", "local_storage", SyncStatus.SUCCESS, None, db)
                
                await db.commit()
                logger.debug(f"Event stored: {event.id} ({action})")
                return True
                
        except Exception as e:
            logger.error(f"Failed to store event {event.id}: {e}")
            return False
    
    async def _insert_event(self, event: StoredEvent, db: aiosqlite.Connection):
        """新規イベント挿入"""
        sql = """
        INSERT INTO events (
            id, title, start_datetime, end_datetime, is_all_day,
            description, location, source_hash, created_at, updated_at,
            sync_status, google_calendar_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        await db.execute(sql, (
            event.id, event.title, event.start_datetime.isoformat(),
            event.end_datetime.isoformat() if event.end_datetime else None,
            event.is_all_day, event.description, event.location,
            event.source_hash, event.created_at.isoformat(),
            event.updated_at.isoformat(), event.sync_status.value,
            event.google_calendar_id
        ))
    
    async def _update_event(self, event: StoredEvent, db: aiosqlite.Connection):
        """既存イベント更新"""
        sql = """
        UPDATE events SET
            title = ?, start_datetime = ?, end_datetime = ?, is_all_day = ?,
            description = ?, location = ?, source_hash = ?, updated_at = ?,
            sync_status = ?, google_calendar_id = ?
        WHERE id = ?
        """
        
        await db.execute(sql, (
            event.title, event.start_datetime.isoformat(),
            event.end_datetime.isoformat() if event.end_datetime else None,
            event.is_all_day, event.description, event.location,
            event.source_hash, event.updated_at.isoformat(),
            event.sync_status.value, event.google_calendar_id, event.id
        ))
    
    async def get_events(self, 
                        start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None,
                        sync_status: Optional[SyncStatus] = None) -> List[StoredEvent]:
        """イベント取得"""
        try:
            conditions = []
            params = []
            
            # 日付範囲フィルタ
            if start_date:
                conditions.append("start_datetime >= ?")
                params.append(start_date.isoformat())
            
            if end_date:
                conditions.append("start_datetime <= ?")
                params.append(end_date.isoformat())
            
            # 同期ステータスフィルタ
            if sync_status:
                conditions.append("sync_status = ?")
                params.append(sync_status.value)
            
            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            sql = f"SELECT * FROM events{where_clause} ORDER BY start_datetime ASC"
            
            async with aiosqlite.connect(self.database_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(sql, params)
                rows = await cursor.fetchall()
                
                events = []
                for row in rows:
                    event = self._row_to_stored_event(row)
                    if event:
                        events.append(event)
                
                logger.debug(f"Retrieved {len(events)} events")
                return events
                
        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return []
    
    async def _get_event_by_id(self, event_id: str, db: aiosqlite.Connection) -> Optional[StoredEvent]:
        """IDによるイベント取得"""
        sql = "SELECT * FROM events WHERE id = ?"
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(sql, (event_id,))
        row = await cursor.fetchone()
        
        return self._row_to_stored_event(row) if row else None
    
    def _row_to_stored_event(self, row: aiosqlite.Row) -> Optional[StoredEvent]:
        """データベース行をStoredEventに変換"""
        try:
            return StoredEvent(
                id=row['id'],
                title=row['title'],
                start_datetime=datetime.fromisoformat(row['start_datetime']),
                end_datetime=datetime.fromisoformat(row['end_datetime']) if row['end_datetime'] else None,
                is_all_day=bool(row['is_all_day']),
                description=row['description'] or '',
                location=row['location'] or '',
                source_hash=row['source_hash'],
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at']),
                sync_status=SyncStatus(row['sync_status']),
                google_calendar_id=row['google_calendar_id']
            )
        except Exception as e:
            logger.error(f"Failed to parse stored event: {e}")
            return None
    
    async def _log_sync_action(self, event_id: str, action: str, source: str, target: str,
                             status: SyncStatus, error_message: Optional[str],
                             db: aiosqlite.Connection):
        """同期アクション記録"""
        sql = """
        INSERT INTO sync_logs (event_id, action, source, target, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        
        await db.execute(sql, (event_id, action, source, target, status.value, error_message))
    
    async def get_sync_logs(self, event_id: Optional[str] = None, limit: int = 100) -> List[SyncLog]:
        """同期ログ取得"""
        try:
            if event_id:
                sql = "SELECT * FROM sync_logs WHERE event_id = ? ORDER BY timestamp DESC LIMIT ?"
                params = (event_id, limit)
            else:
                sql = "SELECT * FROM sync_logs ORDER BY timestamp DESC LIMIT ?"
                params = (limit,)
            
            async with aiosqlite.connect(self.database_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(sql, params)
                rows = await cursor.fetchall()
                
                logs = []
                for row in rows:
                    log = SyncLog(
                        id=row['id'],
                        event_id=row['event_id'],
                        action=row['action'],
                        source=row['source'],
                        target=row['target'],
                        status=SyncStatus(row['status']),
                        error_message=row['error_message'],
                        timestamp=datetime.fromisoformat(row['timestamp'])
                    )
                    logs.append(log)
                
                return logs
                
        except Exception as e:
            logger.error(f"Failed to get sync logs: {e}")
            return []
    
    async def add_notification(self, notification: NotificationQueue) -> bool:
        """通知をキューに追加"""
        try:
            sql = """
            INSERT INTO notification_queue (
                event_id, notification_type, scheduled_time, channel,
                status, attempts, last_attempt, created_at, message_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            async with aiosqlite.connect(self.database_path) as db:
                await db.execute(sql, (
                    notification.event_id,
                    notification.notification_type,
                    notification.scheduled_time.isoformat(),
                    notification.channel,
                    notification.status.value,
                    notification.attempts,
                    notification.last_attempt.isoformat() if notification.last_attempt else None,
                    notification.created_at.isoformat(),
                    json.dumps(notification.message_data) if notification.message_data else None
                ))
                await db.commit()
                
                logger.debug(f"Notification added: {notification.notification_type} for {notification.event_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to add notification: {e}")
            return False
    
    async def get_pending_notifications(self, limit: int = 50) -> List[NotificationQueue]:
        """送信待ち通知取得"""
        try:
            sql = """
            SELECT * FROM notification_queue 
            WHERE status = 'pending' AND scheduled_time <= ?
            ORDER BY scheduled_time ASC LIMIT ?
            """
            
            async with aiosqlite.connect(self.database_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(sql, (datetime.now().isoformat(), limit))
                rows = await cursor.fetchall()
                
                notifications = []
                for row in rows:
                    notification = NotificationQueue(
                        id=row['id'],
                        event_id=row['event_id'],
                        notification_type=row['notification_type'],
                        scheduled_time=datetime.fromisoformat(row['scheduled_time']),
                        channel=row['channel'],
                        status=NotificationStatus(row['status']),
                        attempts=row['attempts'],
                        last_attempt=datetime.fromisoformat(row['last_attempt']) if row['last_attempt'] else None,
                        created_at=datetime.fromisoformat(row['created_at']),
                        message_data=json.loads(row['message_data']) if row['message_data'] else None
                    )
                    notifications.append(notification)
                
                return notifications
                
        except Exception as e:
            logger.error(f"Failed to get pending notifications: {e}")
            return []
    
    async def update_notification_status(self, notification_id: int, status: NotificationStatus,
                                       error_message: Optional[str] = None) -> bool:
        """通知ステータス更新"""
        try:
            sql = """
            UPDATE notification_queue 
            SET status = ?, attempts = attempts + 1, last_attempt = ?
            WHERE id = ?
            """
            
            async with aiosqlite.connect(self.database_path) as db:
                await db.execute(sql, (status.value, datetime.now().isoformat(), notification_id))
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update notification status: {e}")
            return False
    
    async def cleanup_old_data(self, retention_days: int = 30):
        """古いデータのクリーンアップ"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        try:
            async with aiosqlite.connect(self.database_path) as db:
                # 古い同期ログを削除
                await db.execute("DELETE FROM sync_logs WHERE timestamp < ?", (cutoff_date.isoformat(),))
                
                # 古い通知を削除
                await db.execute("DELETE FROM notification_queue WHERE created_at < ? AND status != 'pending'", 
                                (cutoff_date.isoformat(),))
                
                # 古いイベントを削除（オプション）
                # await db.execute("DELETE FROM events WHERE end_datetime < ?", (cutoff_date.isoformat(),))
                
                await db.commit()
                logger.info(f"Cleaned up data older than {retention_days} days")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
    
    async def get_storage_statistics(self) -> Dict[str, Any]:
        """ストレージ統計情報"""
        try:
            stats = {}
            
            async with aiosqlite.connect(self.database_path) as db:
                # イベント統計
                cursor = await db.execute("SELECT COUNT(*) FROM events")
                stats['total_events'] = (await cursor.fetchone())[0]
                
                cursor = await db.execute("SELECT COUNT(*) FROM events WHERE sync_status = 'success'")
                stats['synced_events'] = (await cursor.fetchone())[0]
                
                # 同期ログ統計
                cursor = await db.execute("SELECT COUNT(*) FROM sync_logs")
                stats['total_sync_logs'] = (await cursor.fetchone())[0]
                
                # 通知統計
                cursor = await db.execute("SELECT COUNT(*) FROM notification_queue WHERE status = 'pending'")
                stats['pending_notifications'] = (await cursor.fetchone())[0]
                
                # データベースサイズ
                stats['database_size_mb'] = self.database_path.stat().st_size / (1024 * 1024)
                
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get storage statistics: {e}")
            return {}


# 使用例とテスト
if __name__ == "__main__":
    async def test_event_storage():
        """イベントストレージのテスト"""
        
        # テスト用ストレージ
        storage = EventStorage("test_events.db")
        
        if not await storage.initialize():
            print("Failed to initialize storage")
            return
        
        # テストイベント作成
        test_event = StoredEvent(
            id="test_001",
            title="テストイベント",
            start_datetime=datetime.now() + timedelta(hours=1),
            end_datetime=datetime.now() + timedelta(hours=2),
            is_all_day=False,
            description="ストレージテスト用イベント",
            location="テスト会場",
            source_hash="test_hash",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sync_status=SyncStatus.PENDING
        )
        
        # イベント保存
        if await storage.store_event(test_event):
            print(f"✅ Event stored: {test_event.id}")
        
        # イベント取得
        events = await storage.get_events()
        print(f"✅ Retrieved {len(events)} events")
        
        # 同期ログ取得
        logs = await storage.get_sync_logs()
        print(f"✅ Retrieved {len(logs)} sync logs")
        
        # 統計情報
        stats = await storage.get_storage_statistics()
        print(f"✅ Storage statistics: {stats}")
        
        # テストファイル削除
        import os
        if os.path.exists("test_events.db"):
            os.remove("test_events.db")
            print("✅ Test database cleaned up")
    
    # テスト実行
    asyncio.run(test_event_storage())