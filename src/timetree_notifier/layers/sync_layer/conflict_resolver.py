"""
競合解決システム - 設計書の「同期層」に基づく実装
TimeTree ↔ Google Calendar間の同期競合を解決
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import logging
import hashlib

logger = logging.getLogger(__name__)


class ConflictStrategy(Enum):
    """競合解決戦略"""
    TIMETREE_WINS = "timetree_wins"      # TimeTree優先
    GOOGLE_WINS = "google_wins"          # Google優先
    MERGE = "merge"                      # インテリジェントマージ
    MANUAL_REVIEW = "manual_review"      # 手動レビュー
    LATEST_WINS = "latest_wins"          # 最新更新優先


class ConflictType(Enum):
    """競合タイプ"""
    TITLE_CONFLICT = "title_conflict"
    TIME_CONFLICT = "time_conflict"
    DESCRIPTION_CONFLICT = "description_conflict"
    LOCATION_CONFLICT = "location_conflict"
    DELETION_CONFLICT = "deletion_conflict"
    DUPLICATE_CONFLICT = "duplicate_conflict"


@dataclass
class ConflictItem:
    """競合項目"""
    field_name: str
    timetree_value: Any
    google_value: Any
    conflict_type: ConflictType
    confidence_score: float = 0.0
    
    def __str__(self) -> str:
        return f"{self.field_name}: TT='{self.timetree_value}' vs GC='{self.google_value}'"


@dataclass
class EventConflict:
    """イベント競合"""
    timetree_event_id: Optional[str]
    google_event_id: str
    conflicts: List[ConflictItem]
    conflict_severity: float = 0.0
    resolution_strategy: Optional[ConflictStrategy] = None
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    resolution_result: Optional[Dict[str, Any]] = None
    
    def calculate_severity(self):
        """競合の重要度計算"""
        if not self.conflicts:
            self.conflict_severity = 0.0
            return
        
        # 重要度ウェイト
        field_weights = {
            "title": 3.0,
            "start": 3.0,
            "end": 2.0,
            "description": 1.0,
            "location": 1.5
        }
        
        total_weight = sum(
            field_weights.get(conflict.field_name, 1.0) * (1.0 - conflict.confidence_score)
            for conflict in self.conflicts
        )
        
        self.conflict_severity = min(total_weight, 10.0)  # 最大10点
    
    def is_critical(self) -> bool:
        """クリティカル競合かどうか"""
        return self.conflict_severity >= 6.0
    
    def summary(self) -> str:
        return f"Conflict (severity: {self.conflict_severity:.1f}): {len(self.conflicts)} issues"


@dataclass
class MergePolicy:
    """マージポリシー"""
    title: str = "timetree_priority"         # タイトル優先: timetree_priority, google_priority, longer_text
    description: str = "longer_text"         # 説明優先: longer_text, timetree_priority, google_priority
    location: str = "non_empty_priority"     # 場所優先: non_empty_priority, timetree_priority, google_priority
    time: str = "latest_update"              # 時刻優先: latest_update, timetree_priority, google_priority


class ConflictResolver:
    """競合解決エンジン"""
    
    def __init__(self, config: Dict[str, Any]):
        self.strategy = ConflictStrategy(config.get('strategy', 'timetree_wins'))
        self.merge_policy = MergePolicy(**config.get('merge_policy', {}))
        self.auto_resolve_threshold = config.get('auto_resolve_threshold', 3.0)
        self.similarity_threshold = config.get('similarity_threshold', 0.8)
        
        # 統計情報
        self.conflicts_detected = 0
        self.conflicts_resolved = 0
        self.manual_reviews_required = 0
    
    async def resolve_conflicts(self, 
                              timetree_events: List[Any], 
                              google_events: List[Any]) -> Tuple[List[EventConflict], List[Any]]:
        """競合検出と解決"""
        logger.info(f"Starting conflict resolution: {len(timetree_events)} TT events, {len(google_events)} GC events")
        
        # 1. 競合検出
        conflicts = await self._detect_conflicts(timetree_events, google_events)
        self.conflicts_detected = len(conflicts)
        
        if not conflicts:
            logger.info("No conflicts detected")
            return [], timetree_events  # 競合なし、元のイベントを返す
        
        logger.info(f"Detected {len(conflicts)} conflicts")
        
        # 2. 競合解決
        resolved_events = []
        for conflict in conflicts:
            try:
                resolved_event = await self._resolve_conflict(conflict, timetree_events, google_events)
                if resolved_event:
                    resolved_events.append(resolved_event)
                    conflict.resolved = True
                    conflict.resolution_time = datetime.now()
                    self.conflicts_resolved += 1
                else:
                    # 手動レビューが必要
                    self.manual_reviews_required += 1
                    logger.warning(f"Manual review required for conflict: {conflict.summary()}")
                    
            except Exception as e:
                logger.error(f"Failed to resolve conflict: {e}")
        
        logger.info(f"Conflict resolution completed: {self.conflicts_resolved}/{len(conflicts)} resolved")
        
        return conflicts, resolved_events
    
    async def _detect_conflicts(self, timetree_events: List[Any], google_events: List[Any]) -> List[EventConflict]:
        """競合を検出"""
        conflicts = []
        
        # TimeTreeイベントに対応するGoogle Calendarイベントを探す
        for tt_event in timetree_events:
            matching_gc_events = self._find_matching_google_events(tt_event, google_events)
            
            for gc_event in matching_gc_events:
                conflict_items = self._compare_events(tt_event, gc_event)
                
                if conflict_items:
                    conflict = EventConflict(
                        timetree_event_id=getattr(tt_event, 'id', None),
                        google_event_id=gc_event.id,
                        conflicts=conflict_items
                    )
                    conflict.calculate_severity()
                    conflicts.append(conflict)
        
        return conflicts
    
    def _find_matching_google_events(self, tt_event: Any, google_events: List[Any]) -> List[Any]:
        """TimeTreeイベントに対応するGoogle Calendarイベントを検索"""
        matches = []
        
        for gc_event in google_events:
            # 1. TimeTree IDによる直接マッチ
            if (hasattr(gc_event, 'source_event_id') and 
                gc_event.source_event_id and 
                str(gc_event.source_event_id) == str(getattr(tt_event, 'id', ''))):
                matches.append(gc_event)
                continue
            
            # 2. タイトル・時刻による類似性マッチ
            similarity_score = self._calculate_similarity(tt_event, gc_event)
            if similarity_score >= self.similarity_threshold:
                matches.append(gc_event)
        
        return matches
    
    def _calculate_similarity(self, tt_event: Any, gc_event: Any) -> float:
        """イベント間の類似性スコア計算"""
        scores = []
        
        # タイトル類似性
        tt_title = getattr(tt_event, 'title', '').strip()
        gc_title = getattr(gc_event, 'summary', '').replace('📱 ', '').strip()
        
        title_similarity = self._text_similarity(tt_title, gc_title)
        scores.append(title_similarity * 0.4)  # 40%重み
        
        # 時刻類似性
        tt_start = getattr(tt_event, 'start_time', None)
        gc_start = getattr(gc_event, 'start', None)
        
        if tt_start and gc_start:
            time_diff = abs((tt_start - gc_start).total_seconds())
            time_similarity = max(0, 1.0 - (time_diff / 3600))  # 1時間で類似度0
            scores.append(time_similarity * 0.4)  # 40%重み
        
        # 場所類似性
        tt_location = getattr(tt_event, 'location', '') or ''
        gc_location = getattr(gc_event, 'location', '') or ''
        
        location_similarity = self._text_similarity(tt_location, gc_location)
        scores.append(location_similarity * 0.2)  # 20%重み
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """テキスト類似性計算（簡易版）"""
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        if text1 == text2:
            return 1.0
        
        # 単純な部分文字列マッチング
        if text1 in text2 or text2 in text1:
            return 0.8
        
        # 共通文字数ベースの類似性
        common_chars = len(set(text1) & set(text2))
        total_chars = len(set(text1) | set(text2))
        
        return common_chars / total_chars if total_chars > 0 else 0.0
    
    def _compare_events(self, tt_event: Any, gc_event: Any) -> List[ConflictItem]:
        """2つのイベントを比較して競合項目を特定"""
        conflicts = []
        
        # タイトル比較
        tt_title = getattr(tt_event, 'title', '').strip()
        gc_title = getattr(gc_event, 'summary', '').replace('📱 ', '').strip()
        
        if tt_title != gc_title and tt_title and gc_title:
            similarity = self._text_similarity(tt_title, gc_title)
            conflicts.append(ConflictItem(
                field_name="title",
                timetree_value=tt_title,
                google_value=gc_title,
                conflict_type=ConflictType.TITLE_CONFLICT,
                confidence_score=similarity
            ))
        
        # 時刻比較
        tt_start = getattr(tt_event, 'start_time', None)
        gc_start = getattr(gc_event, 'start', None)
        
        if tt_start and gc_start:
            time_diff = abs((tt_start - gc_start).total_seconds())
            if time_diff > 300:  # 5分以上の差
                conflicts.append(ConflictItem(
                    field_name="start",
                    timetree_value=tt_start,
                    google_value=gc_start,
                    conflict_type=ConflictType.TIME_CONFLICT,
                    confidence_score=max(0, 1.0 - (time_diff / 3600))
                ))
        
        # 説明比較
        tt_desc = getattr(tt_event, 'description', '') or ''
        gc_desc = getattr(gc_event, 'description', '') or ''
        
        if tt_desc != gc_desc and (tt_desc or gc_desc):
            similarity = self._text_similarity(tt_desc, gc_desc)
            if similarity < 0.9:  # 90%未満の類似性
                conflicts.append(ConflictItem(
                    field_name="description",
                    timetree_value=tt_desc,
                    google_value=gc_desc,
                    conflict_type=ConflictType.DESCRIPTION_CONFLICT,
                    confidence_score=similarity
                ))
        
        # 場所比較
        tt_location = getattr(tt_event, 'location', '') or ''
        gc_location = getattr(gc_event, 'location', '') or ''
        
        if tt_location != gc_location and (tt_location or gc_location):
            similarity = self._text_similarity(tt_location, gc_location)
            if similarity < 0.9:
                conflicts.append(ConflictItem(
                    field_name="location",
                    timetree_value=tt_location,
                    google_value=gc_location,
                    conflict_type=ConflictType.LOCATION_CONFLICT,
                    confidence_score=similarity
                ))
        
        return conflicts
    
    async def _resolve_conflict(self, conflict: EventConflict, 
                              timetree_events: List[Any], 
                              google_events: List[Any]) -> Optional[Any]:
        """個別競合の解決"""
        
        # 競合の重要度に基づく処理判定
        if conflict.is_critical() and self.strategy == ConflictStrategy.MANUAL_REVIEW:
            logger.info(f"Critical conflict requires manual review: {conflict.summary()}")
            return None
        
        # 自動解決閾値チェック
        if conflict.conflict_severity > self.auto_resolve_threshold:
            if self.strategy not in [ConflictStrategy.TIMETREE_WINS, ConflictStrategy.GOOGLE_WINS]:
                logger.info(f"Conflict exceeds auto-resolve threshold: {conflict.summary()}")
                return None
        
        # 対象イベントの取得
        tt_event = self._find_timetree_event(conflict.timetree_event_id, timetree_events)
        gc_event = self._find_google_event(conflict.google_event_id, google_events)
        
        if not tt_event:
            logger.error(f"TimeTree event not found: {conflict.timetree_event_id}")
            return None
        
        # 戦略に基づく解決
        if self.strategy == ConflictStrategy.TIMETREE_WINS:
            resolved_event = self._resolve_timetree_wins(tt_event, gc_event, conflict)
        elif self.strategy == ConflictStrategy.GOOGLE_WINS:
            resolved_event = self._resolve_google_wins(tt_event, gc_event, conflict)
        elif self.strategy == ConflictStrategy.MERGE:
            resolved_event = self._resolve_merge(tt_event, gc_event, conflict)
        elif self.strategy == ConflictStrategy.LATEST_WINS:
            resolved_event = self._resolve_latest_wins(tt_event, gc_event, conflict)
        else:
            logger.warning(f"Unhandled conflict strategy: {self.strategy}")
            return None
        
        # 解決結果を記録
        if resolved_event:
            conflict.resolution_result = self._event_to_dict(resolved_event)
            logger.info(f"Conflict resolved using {self.strategy.value}: {conflict.summary()}")
        
        return resolved_event
    
    def _find_timetree_event(self, event_id: Optional[str], events: List[Any]) -> Optional[Any]:
        """TimeTreeイベントをIDで検索"""
        if not event_id:
            return None
        
        for event in events:
            if str(getattr(event, 'id', '')) == str(event_id):
                return event
        return None
    
    def _find_google_event(self, event_id: str, events: List[Any]) -> Optional[Any]:
        """Google Calendarイベントを検索"""
        for event in events:
            if getattr(event, 'id', '') == event_id:
                return event
        return None
    
    def _resolve_timetree_wins(self, tt_event: Any, gc_event: Any, conflict: EventConflict) -> Any:
        """TimeTree優先の解決"""
        # TimeTreeイベントの値を使用
        return tt_event
    
    def _resolve_google_wins(self, tt_event: Any, gc_event: Any, conflict: EventConflict) -> Any:
        """Google優先の解決"""
        # Google Calendarの値でTimeTreeイベントを更新（概念的）
        # 実際の実装では適切なイベントオブジェクトを作成
        return tt_event  # 簡略化
    
    def _resolve_merge(self, tt_event: Any, gc_event: Any, conflict: EventConflict) -> Any:
        """インテリジェントマージ解決"""
        # マージポリシーに基づいて各フィールドを解決
        merged_data = {}
        
        for conflict_item in conflict.conflicts:
            field = conflict_item.field_name
            tt_value = conflict_item.timetree_value
            gc_value = conflict_item.google_value
            
            if field == "title":
                merged_data["title"] = self._merge_field_title(tt_value, gc_value)
            elif field == "description":
                merged_data["description"] = self._merge_field_description(tt_value, gc_value)
            elif field == "location":
                merged_data["location"] = self._merge_field_location(tt_value, gc_value)
            elif field == "start":
                merged_data["start_time"] = self._merge_field_time(tt_value, gc_value)
        
        # マージされたデータでイベントを更新（概念的）
        return tt_event  # 実際の実装では適切に更新
    
    def _merge_field_title(self, tt_value: str, gc_value: str) -> str:
        """タイトルフィールドのマージ"""
        if self.merge_policy.title == "longer_text":
            return tt_value if len(tt_value) >= len(gc_value) else gc_value
        elif self.merge_policy.title == "google_priority":
            return gc_value
        else:  # timetree_priority
            return tt_value
    
    def _merge_field_description(self, tt_value: str, gc_value: str) -> str:
        """説明フィールドのマージ"""
        if self.merge_policy.description == "longer_text":
            return tt_value if len(tt_value) >= len(gc_value) else gc_value
        elif self.merge_policy.description == "google_priority":
            return gc_value
        else:  # timetree_priority
            return tt_value
    
    def _merge_field_location(self, tt_value: str, gc_value: str) -> str:
        """場所フィールドのマージ"""
        if self.merge_policy.location == "non_empty_priority":
            return tt_value if tt_value.strip() else gc_value
        elif self.merge_policy.location == "google_priority":
            return gc_value
        else:  # timetree_priority
            return tt_value
    
    def _merge_field_time(self, tt_value: datetime, gc_value: datetime) -> datetime:
        """時刻フィールドのマージ"""
        if self.merge_policy.time == "latest_update":
            # 実際の実装では更新時刻を比較
            return tt_value  # 簡略化
        else:  # timetree_priority
            return tt_value
    
    def _resolve_latest_wins(self, tt_event: Any, gc_event: Any, conflict: EventConflict) -> Any:
        """最新更新優先の解決"""
        # 更新時刻を比較（実際の実装では適切な時刻フィールドを使用）
        return tt_event  # 簡略化
    
    def _event_to_dict(self, event: Any) -> Dict[str, Any]:
        """イベントを辞書形式に変換"""
        return {
            "id": getattr(event, 'id', ''),
            "title": getattr(event, 'title', ''),
            "start": str(getattr(event, 'start_time', '')),
            "description": getattr(event, 'description', ''),
            "location": getattr(event, 'location', '')
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """競合解決統計情報"""
        total = self.conflicts_detected
        return {
            "conflicts_detected": total,
            "conflicts_resolved": self.conflicts_resolved,
            "manual_reviews_required": self.manual_reviews_required,
            "auto_resolution_rate": (self.conflicts_resolved / total * 100) if total > 0 else 0.0,
            "strategy_used": self.strategy.value
        }


# 使用例とテスト
if __name__ == "__main__":
    import asyncio
    
    async def test_conflict_resolver():
        """競合解決のテスト"""
        
        # テスト設定
        config = {
            'strategy': 'merge',
            'merge_policy': {
                'title': 'timetree_priority',
                'description': 'longer_text',
                'location': 'non_empty_priority'
            },
            'auto_resolve_threshold': 3.0,
            'similarity_threshold': 0.8
        }
        
        resolver = ConflictResolver(config)
        
        # モック用のテストイベント
        class MockEvent:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
        
        # テスト用イベント
        tt_events = [
            MockEvent(id="tt1", title="会議A", start_time=datetime(2025, 9, 1, 10, 0), description="TimeTreeの説明"),
        ]
        
        gc_events = [
            MockEvent(id="gc1", summary="📱 会議A", start=datetime(2025, 9, 1, 10, 5), description="Googleの説明"),
        ]
        
        # 競合解決テスト
        conflicts, resolved = await resolver.resolve_conflicts(tt_events, gc_events)
        
        print(f"競合検出: {len(conflicts)}件")
        for conflict in conflicts:
            print(f"  - {conflict.summary()}")
        
        print(f"解決済み: {len(resolved)}件")
        
        # 統計情報
        stats = resolver.get_statistics()
        print(f"統計: {stats}")
    
    # テスト実行
    asyncio.run(test_conflict_resolver())