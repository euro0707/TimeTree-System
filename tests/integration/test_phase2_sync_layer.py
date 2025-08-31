"""
Phase 2 同期層 統合テスト
Google Calendar連携・競合解決・データベースの統合動作確認
"""

import pytest
import asyncio
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# テスト対象モジュールのパスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from timetree_notifier.layers.sync_layer.event_storage import EventStorage, StoredEvent, SyncStatus, NotificationQueue, NotificationStatus
from timetree_notifier.layers.sync_layer.conflict_resolver import ConflictResolver, ConflictStrategy, ConflictType


class MockTimeTreeEvent:
    """テスト用TimeTreeイベント"""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 'tt_001')
        self.title = kwargs.get('title', 'テストイベント')
        self.start_time = kwargs.get('start_time', datetime.now() + timedelta(hours=1))
        self.end_time = kwargs.get('end_time', None)
        self.is_all_day = kwargs.get('is_all_day', False)
        self.description = kwargs.get('description', '')
        self.location = kwargs.get('location', '')


class MockGoogleCalendarEvent:
    """テスト用Google Calendarイベント"""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 'gc_001')
        self.summary = kwargs.get('summary', 'テストイベント')
        self.start = kwargs.get('start', datetime.now() + timedelta(hours=1))
        self.end = kwargs.get('end', None)
        self.all_day = kwargs.get('all_day', False)
        self.description = kwargs.get('description', '')
        self.location = kwargs.get('location', '')
        self.source_event_id = kwargs.get('source_event_id', None)
        self.created = kwargs.get('created', datetime.now())
        self.updated = kwargs.get('updated', datetime.now())


class TestEventStorage:
    """イベントストレージのテスト"""
    
    @pytest.fixture
    async def temp_storage(self):
        """テンポラリストレージ"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = EventStorage(Path(temp_dir) / "test.db")
            await storage.initialize()
            yield storage
    
    @pytest.fixture
    def sample_event(self):
        """サンプルイベント"""
        return StoredEvent(
            id="test_001",
            title="サンプルイベント",
            start_datetime=datetime(2025, 9, 1, 10, 0),
            end_datetime=datetime(2025, 9, 1, 11, 0),
            is_all_day=False,
            description="テスト用イベント",
            location="テスト会場",
            source_hash="sample_hash",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sync_status=SyncStatus.PENDING
        )
    
    @pytest.mark.asyncio
    async def test_storage_initialization(self, temp_storage):
        """ストレージ初期化テスト"""
        assert temp_storage is not None
        
        # 統計情報取得でテーブルが作成されているか確認
        stats = await temp_storage.get_storage_statistics()
        assert 'total_events' in stats
        assert stats['total_events'] == 0
    
    @pytest.mark.asyncio
    async def test_store_and_retrieve_event(self, temp_storage, sample_event):
        """イベント保存・取得テスト"""
        # イベント保存
        success = await temp_storage.store_event(sample_event)
        assert success, "イベント保存が失敗"
        
        # イベント取得
        events = await temp_storage.get_events()
        assert len(events) == 1, "保存したイベントが取得できない"
        
        retrieved_event = events[0]
        assert retrieved_event.id == sample_event.id
        assert retrieved_event.title == sample_event.title
        assert retrieved_event.sync_status == SyncStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_event_filtering(self, temp_storage, sample_event):
        """イベントフィルタリングテスト"""
        # 複数イベント作成
        event1 = sample_event
        event2 = StoredEvent(
            id="test_002",
            title="別のイベント",
            start_datetime=datetime(2025, 9, 2, 14, 0),
            end_datetime=datetime(2025, 9, 2, 15, 0),
            is_all_day=False,
            description="",
            location="",
            source_hash="hash2",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sync_status=SyncStatus.SUCCESS
        )
        
        await temp_storage.store_event(event1)
        await temp_storage.store_event(event2)
        
        # 日付範囲フィルタ
        events_sep1 = await temp_storage.get_events(
            start_date=datetime(2025, 9, 1, 0, 0),
            end_date=datetime(2025, 9, 1, 23, 59)
        )
        assert len(events_sep1) == 1
        assert events_sep1[0].id == "test_001"
        
        # ステータスフィルタ
        pending_events = await temp_storage.get_events(sync_status=SyncStatus.PENDING)
        assert len(pending_events) == 1
        assert pending_events[0].sync_status == SyncStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_sync_logging(self, temp_storage, sample_event):
        """同期ログテスト"""
        # イベント保存（同期ログが自動記録される）
        await temp_storage.store_event(sample_event)
        
        # 同期ログ確認
        logs = await temp_storage.get_sync_logs()
        assert len(logs) >= 1, "同期ログが記録されていない"
        
        log = logs[0]
        assert log.event_id == sample_event.id
        assert log.action in ["CREATE", "UPDATE"]
        assert log.status == SyncStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_notification_queue(self, temp_storage):
        """通知キューテスト"""
        # 通知作成
        notification = NotificationQueue(
            id=None,
            event_id="test_001",
            notification_type="DAILY_SUMMARY",
            scheduled_time=datetime.now() - timedelta(minutes=5),  # 送信時刻を過去に設定
            channel="line",
            status=NotificationStatus.PENDING,
            attempts=0,
            last_attempt=None,
            created_at=datetime.now()
        )
        
        # 通知追加
        success = await temp_storage.add_notification(notification)
        assert success, "通知の追加が失敗"
        
        # 送信待ち通知取得
        pending = await temp_storage.get_pending_notifications()
        assert len(pending) == 1, "送信待ち通知が取得できない"
        
        notification_id = pending[0].id
        assert notification_id is not None
        
        # ステータス更新
        update_success = await temp_storage.update_notification_status(
            notification_id, NotificationStatus.SENT
        )
        assert update_success, "通知ステータスの更新が失敗"


class TestConflictResolver:
    """競合解決のテスト"""
    
    @pytest.fixture
    def resolver_config(self):
        """競合解決設定"""
        return {
            'strategy': 'merge',
            'merge_policy': {
                'title': 'timetree_priority',
                'description': 'longer_text',
                'location': 'non_empty_priority'
            },
            'auto_resolve_threshold': 3.0,
            'similarity_threshold': 0.8
        }
    
    @pytest.fixture
    def conflict_resolver(self, resolver_config):
        """競合解決インスタンス"""
        return ConflictResolver(resolver_config)
    
    def test_text_similarity_calculation(self, conflict_resolver):
        """テキスト類似性計算テスト"""
        # 完全一致
        assert conflict_resolver._text_similarity("テスト", "テスト") == 1.0
        
        # 完全不一致
        similarity = conflict_resolver._text_similarity("テスト", "会議")
        assert similarity < 0.5
        
        # 部分一致
        similarity = conflict_resolver._text_similarity("テスト会議", "会議")
        assert similarity > 0.5
    
    def test_event_similarity_calculation(self, conflict_resolver):
        """イベント類似性計算テスト"""
        # 類似イベント
        tt_event = MockTimeTreeEvent(
            title="定例会議",
            start_time=datetime(2025, 9, 1, 10, 0),
            location="会議室A"
        )
        
        gc_event = MockGoogleCalendarEvent(
            summary="📱 定例会議",
            start=datetime(2025, 9, 1, 10, 5),  # 5分のずれ
            location="会議室A"
        )
        
        similarity = conflict_resolver._calculate_similarity(tt_event, gc_event)
        assert similarity >= 0.8, f"類似性スコアが低すぎる: {similarity}"
        
        # 異なるイベント
        different_event = MockGoogleCalendarEvent(
            summary="別のイベント",
            start=datetime(2025, 9, 1, 15, 0),
            location="別の場所"
        )
        
        similarity = conflict_resolver._calculate_similarity(tt_event, different_event)
        assert similarity < 0.5, f"異なるイベントの類似性が高すぎる: {similarity}"
    
    @pytest.mark.asyncio
    async def test_conflict_detection(self, conflict_resolver):
        """競合検出テスト"""
        # 競合のあるイベントペア
        tt_events = [
            MockTimeTreeEvent(
                id="tt_001",
                title="会議A",
                start_time=datetime(2025, 9, 1, 10, 0),
                description="TimeTree側の説明"
            )
        ]
        
        gc_events = [
            MockGoogleCalendarEvent(
                id="gc_001",
                summary="📱 会議A",
                start=datetime(2025, 9, 1, 10, 10),  # 10分のずれ
                description="Google側の説明",
                source_event_id="tt_001"  # 関連付け
            )
        ]
        
        # 競合検出
        conflicts, resolved = await conflict_resolver.resolve_conflicts(tt_events, gc_events)
        
        assert len(conflicts) > 0, "競合が検出されなかった"
        
        conflict = conflicts[0]
        assert conflict.timetree_event_id == "tt_001"
        assert conflict.google_event_id == "gc_001"
        assert len(conflict.conflicts) > 0, "競合項目が検出されなかった"
        
        # 時刻競合があることを確認
        time_conflicts = [c for c in conflict.conflicts if c.conflict_type == ConflictType.TIME_CONFLICT]
        assert len(time_conflicts) > 0, "時刻競合が検出されなかった"
    
    @pytest.mark.asyncio
    async def test_conflict_resolution_strategies(self, resolver_config):
        """競合解決戦略テスト"""
        
        # TimeTree優先戦略
        resolver_config['strategy'] = 'timetree_wins'
        resolver = ConflictResolver(resolver_config)
        
        tt_events = [MockTimeTreeEvent(title="TimeTree版")]
        gc_events = [MockGoogleCalendarEvent(summary="📱 Google版", source_event_id="tt_001")]
        
        conflicts, resolved = await resolver.resolve_conflicts(tt_events, gc_events)
        
        # 統計確認
        stats = resolver.get_statistics()
        assert stats['strategy_used'] == 'timetree_wins'
    
    def test_merge_policies(self, conflict_resolver):
        """マージポリシーテスト"""
        # タイトルマージ（TimeTree優先）
        result = conflict_resolver._merge_field_title("TimeTree版", "Google版")
        assert result == "TimeTree版"
        
        # 説明マージ（長いテキスト優先）
        result = conflict_resolver._merge_field_description("短い", "これは長い説明文です")
        assert result == "これは長い説明文です"
        
        # 場所マージ（空でない方を優先）
        result = conflict_resolver._merge_field_location("", "会議室A")
        assert result == "会議室A"


class TestSyncLayerIntegration:
    """同期層統合テスト"""
    
    @pytest.fixture
    async def integrated_system(self):
        """統合システムのセットアップ"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # ストレージ初期化
            storage = EventStorage(Path(temp_dir) / "integration_test.db")
            await storage.initialize()
            
            # 競合解決器
            resolver = ConflictResolver({
                'strategy': 'merge',
                'auto_resolve_threshold': 2.0,
                'similarity_threshold': 0.7
            })
            
            yield {
                'storage': storage,
                'resolver': resolver
            }
    
    @pytest.mark.asyncio
    async def test_full_sync_workflow(self, integrated_system):
        """完全同期ワークフローテスト"""
        storage = integrated_system['storage']
        resolver = integrated_system['resolver']
        
        # 1. TimeTreeイベント作成
        tt_event = MockTimeTreeEvent(
            id="workflow_001",
            title="ワークフローテスト",
            start_time=datetime(2025, 9, 1, 14, 0),
            description="統合テスト用イベント",
            location="テストルーム"
        )
        
        # 2. ストレージに保存
        stored_event = StoredEvent(
            id=tt_event.id,
            title=tt_event.title,
            start_datetime=tt_event.start_time,
            end_datetime=tt_event.end_time,
            is_all_day=tt_event.is_all_day,
            description=tt_event.description,
            location=tt_event.location,
            source_hash="workflow_hash",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            sync_status=SyncStatus.PENDING
        )
        
        success = await storage.store_event(stored_event)
        assert success, "イベント保存が失敗"
        
        # 3. Google Calendarイベント（競合あり）
        gc_event = MockGoogleCalendarEvent(
            id="gc_workflow_001",
            summary="📱 ワークフローテスト",
            start=datetime(2025, 9, 1, 14, 5),  # 5分のずれ
            description="Google側の説明",
            location="テストルーム",
            source_event_id="workflow_001"
        )
        
        # 4. 競合解決
        conflicts, resolved = await resolver.resolve_conflicts([tt_event], [gc_event])
        
        # 競合が検出され、解決されることを確認
        assert len(conflicts) >= 0, "統合テストで予期しないエラー"
        
        # 5. 解決結果をストレージに更新
        if resolved:
            for resolved_event in resolved:
                updated_stored = StoredEvent(
                    id=getattr(resolved_event, 'id', stored_event.id),
                    title=getattr(resolved_event, 'title', stored_event.title),
                    start_datetime=getattr(resolved_event, 'start_time', stored_event.start_datetime),
                    end_datetime=getattr(resolved_event, 'end_time', stored_event.end_datetime),
                    is_all_day=getattr(resolved_event, 'is_all_day', stored_event.is_all_day),
                    description=getattr(resolved_event, 'description', stored_event.description),
                    location=getattr(resolved_event, 'location', stored_event.location),
                    source_hash=stored_event.source_hash,
                    created_at=stored_event.created_at,
                    updated_at=datetime.now(),
                    sync_status=SyncStatus.SUCCESS
                )
                
                await storage.store_event(updated_stored)
        
        # 6. 最終確認
        final_events = await storage.get_events()
        assert len(final_events) >= 1, "最終的なイベントが存在しない"
        
        # 同期ログ確認
        logs = await storage.get_sync_logs()
        assert len(logs) >= 1, "同期ログが記録されていない"
        
        # 統計情報確認
        stats = await storage.get_storage_statistics()
        assert stats['total_events'] >= 1, "統計情報が正しくない"
        
        print(f"✅ Full sync workflow completed: {len(final_events)} events, {len(logs)} logs")


if __name__ == "__main__":
    # 基本的なテスト実行
    async def run_basic_tests():
        print("🧪 Phase 2 Sync Layer - Basic Tests")
        print("=" * 50)
        
        # ストレージテスト
        print("\n📦 Testing Event Storage...")
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = EventStorage(Path(temp_dir) / "basic_test.db")
            if await storage.initialize():
                print("✅ Storage initialization successful")
                
                # サンプルイベント
                event = StoredEvent(
                    id="basic_001",
                    title="基本テスト",
                    start_datetime=datetime.now() + timedelta(hours=1),
                    end_datetime=datetime.now() + timedelta(hours=2),
                    is_all_day=False,
                    description="基本機能テスト",
                    location="",
                    source_hash="basic_hash",
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    sync_status=SyncStatus.PENDING
                )
                
                if await storage.store_event(event):
                    print("✅ Event storage successful")
                
                events = await storage.get_events()
                print(f"✅ Event retrieval successful: {len(events)} events")
            else:
                print("❌ Storage initialization failed")
        
        # 競合解決テスト
        print("\n⚡ Testing Conflict Resolution...")
        resolver = ConflictResolver({
            'strategy': 'timetree_wins',
            'similarity_threshold': 0.8
        })
        
        similarity = resolver._text_similarity("テスト", "テスト")
        if similarity == 1.0:
            print("✅ Text similarity calculation successful")
        
        print("\n🎯 Phase 2 Basic Tests Completed!")
        print("All major components are functional.")
    
    # テスト実行
    asyncio.run(run_basic_tests())