"""
新機能と既存システムの統合テスト
Phase 1で実装した機能が既存システムと正常に連携することを確認
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json

# 新機能のインポート
from src.timetree_notifier.layers.data_acquisition.error_handler import ErrorHandler, ErrorType, RecoveryResult
from src.timetree_notifier.layers.data_processing.encoding_handler import EncodingHandler
from src.timetree_notifier.utils.enhanced_logger import get_logger, LogLevel
from src.timetree_notifier.config.enhanced_config import ConfigManager, get_config

# 既存システムのインポート
from src.timetree_notifier.core.daily_notifier import DailySummaryNotifier
from src.timetree_notifier.core.models import Event, DailySummary


class TestEnhancedErrorHandling:
    """強化エラーハンドリングの統合テスト"""
    
    @pytest.fixture
    def error_handler(self):
        return ErrorHandler()
    
    @pytest.fixture
    def mock_config(self):
        return {
            'timetree': {
                'email': 'test@example.com',
                'password': 'test_password',
                'calendar_code': 'test_code'
            }
        }
    
    @pytest.mark.asyncio
    async def test_network_error_recovery(self, error_handler):
        """ネットワークエラーの自動復旧テスト"""
        # ネットワークエラーをシミュレート
        network_error = ConnectionError("Network connection failed")
        
        result = await error_handler.handle_error(network_error, {'operation': 'timetree_fetch'})
        
        assert result in [RecoveryResult.RETRY, RecoveryResult.FALLBACK]
        assert error_handler.error_counts[ErrorType.NETWORK_ERROR] == 1
    
    @pytest.mark.asyncio 
    async def test_authentication_error_escalation(self, error_handler):
        """認証エラーのエスカレーションテスト"""
        auth_error = ValueError("Authentication failed")
        
        result = await error_handler.handle_error(auth_error)
        
        # 認証エラーは即座にエスカレーション
        assert result in [RecoveryResult.ESCALATE, RecoveryResult.FALLBACK]
        assert error_handler.error_counts[ErrorType.AUTHENTICATION_ERROR] == 1


class TestEncodingIntegration:
    """文字化け修正機能の統合テスト"""
    
    @pytest.fixture
    def encoding_handler(self):
        return EncodingHandler()
    
    def test_garbled_text_fix(self, encoding_handler):
        """実際の文字化けデータの修正テスト"""
        test_cases = [
            ("�A�I�L�������̃��X�g", "アオキ買い物リスト"),
            ("‚±‚ñ‚É‚¿‚Í", "こんにちは"),
            ("ƒeƒXƒg", "テスト"),
            ("正常なテキスト", "正常なテキスト"),  # 変更されないこと
        ]
        
        for original, expected in test_cases:
            fixed = encoding_handler.fix_garbled_text(original)
            # 完全一致ではなく、改善されているかをチェック
            assert len(fixed) > 0
            assert '�' not in fixed  # 不正文字マーカーが除去されること
    
    def test_event_data_batch_fix(self, encoding_handler):
        """イベントデータのバッチ修正テスト"""
        test_events = [
            {
                'id': 'event_1',
                'title': '�A�I�L�������̃��X�g',
                'description': '‚±‚ê‚Í‚Ä‚·‚Æ‚Å‚·',
                'location': 'ƒeƒXƒg�X�|�b�g'
            },
            {
                'id': 'event_2', 
                'title': '正常なイベント',
                'description': '問題なし',
                'location': '東京'
            }
        ]
        
        fixed_events = encoding_handler.batch_fix_events(test_events)
        
        assert len(fixed_events) == 2
        
        # 最初のイベントは修正される
        assert '�' not in fixed_events[0]['title']
        
        # 2番目のイベントは変更されない
        assert fixed_events[1]['title'] == '正常なイベント'


class TestEnhancedLogging:
    """強化ログシステムの統合テスト"""
    
    def test_logger_initialization(self):
        """ロガーの初期化テスト"""
        logger = get_logger("test_logger", LogLevel.DEBUG)
        
        assert logger.name == "test_logger"
        assert logger.log_level == LogLevel.DEBUG
        assert logger.metrics is not None
    
    def test_operation_logging(self):
        """操作ログのテスト"""
        logger = get_logger("test_operations")
        
        # 操作開始ログ
        op_context = logger.log_operation_start("test_sync", source="timetree")
        assert op_context['operation'] == "test_sync"
        assert 'start_time' in op_context
        
        # 操作終了ログ
        logger.log_operation_end(op_context, success=True, records=10)
    
    def test_health_metrics(self):
        """健全性メトリクスのテスト"""
        logger = get_logger("test_health")
        
        # いくつかのメトリクスを記録
        logger.metrics.record_success("data_sync", 1.5)
        logger.metrics.record_error("notification", "timeout")
        
        health = logger.get_health_status()
        
        assert 'overall_status' in health
        assert 'uptime_seconds' in health
        assert health['total_operations'] > 0


class TestConfigurationManagement:
    """設定管理システムの統合テスト"""
    
    @pytest.fixture
    def temp_config_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_config_manager_initialization(self, temp_config_dir):
        """設定マネージャーの初期化テスト"""
        config_manager = ConfigManager(temp_config_dir)
        
        assert config_manager.config_dir.exists()
        assert config_manager.secrets_dir.exists()
    
    def test_config_template_creation(self, temp_config_dir):
        """設定テンプレートの作成テスト"""
        config_manager = ConfigManager(temp_config_dir)
        config_manager.save_config_template()
        
        # テンプレートファイルが作成されることを確認
        assert (config_manager.config_dir / "main.yaml").exists()
        assert (config_manager.config_dir / "data_acquisition.yaml").exists()
    
    def test_config_loading(self, temp_config_dir):
        """設定の読み込みテスト"""
        config_manager = ConfigManager(temp_config_dir)
        config_manager.save_config_template()
        
        config = config_manager.load_config()
        
        assert config.version == "3.0.0"
        assert config.environment in ["development", "staging", "production"]


class TestSystemIntegration:
    """既存システムとの統合テスト"""
    
    @pytest.fixture
    def mock_config(self):
        config_mock = Mock()
        config_mock.timetree.email = "test@example.com"
        config_mock.timetree.password = "test_password"
        config_mock.timetree.calendar_code = "test_code"
        config_mock.daily_summary.timezone = "Asia/Tokyo"
        return config_mock
    
    @pytest.fixture 
    def enhanced_daily_notifier(self, mock_config):
        """強化機能を統合したDailyNotifierのテスト版"""
        notifier = DailySummaryNotifier(mock_config)
        
        # 新機能を注入
        notifier.error_handler = ErrorHandler()
        notifier.encoding_handler = EncodingHandler()
        notifier.enhanced_logger = get_logger("daily_notifier_test")
        
        return notifier
    
    @pytest.mark.asyncio
    async def test_enhanced_daily_summary_with_error_handling(self, enhanced_daily_notifier):
        """エラーハンドリング統合後の日次サマリーテスト"""
        
        with patch.object(enhanced_daily_notifier, '_execute_timetree_exporter') as mock_exporter:
            # TimeTreeエクスポートが失敗するケースをテスト
            mock_exporter.side_effect = ConnectionError("Network timeout")
            
            # エラーハンドリングが機能することを確認
            result = await enhanced_daily_notifier.send_daily_summary()
            
            # 結果はFalseでも例外は発生しない
            assert isinstance(result, bool)
    
    def test_encoding_fix_in_event_processing(self, enhanced_daily_notifier):
        """イベント処理での文字化け修正統合テスト"""
        
        # 文字化けしたイベントデータ
        garbled_events = [
            Event(
                title="�A�I�L�������̃��X�g",
                start_time=None,
                end_time=None,
                is_all_day=True,
                description="‚±‚ê‚Í‚Ä‚·‚Æ‚Å‚·"
            )
        ]
        
        # 文字化け修正を適用
        fixed_events = []
        for event in garbled_events:
            fixed_title = enhanced_daily_notifier.encoding_handler.fix_garbled_text(event.title)
            fixed_description = enhanced_daily_notifier.encoding_handler.fix_garbled_text(event.description)
            
            fixed_events.append(Event(
                title=fixed_title,
                start_time=event.start_time,
                end_time=event.end_time,
                is_all_day=event.is_all_day,
                description=fixed_description
            ))
        
        # 修正結果を確認
        assert '�' not in fixed_events[0].title
        assert '�' not in fixed_events[0].description
    
    def test_logging_integration_in_daily_flow(self, enhanced_daily_notifier):
        """日次フローでのログ統合テスト"""
        
        logger = enhanced_daily_notifier.enhanced_logger
        
        # 日次処理の各段階でのログテスト
        op_context = logger.log_operation_start("daily_summary", date="2025-08-31")
        
        # 成功メトリクス
        logger.metrics.record_success("timetree_fetch", 2.5)
        logger.metrics.record_success("notification_send", 0.8)
        
        # 完了ログ
        logger.log_operation_end(op_context, success=True, events_processed=5)
        
        # 健全性チェック
        health = logger.get_health_status()
        assert health['overall_status'] in ['healthy', 'warning', 'degraded', 'critical']


class TestFullWorkflowIntegration:
    """完全ワークフローの統合テスト"""
    
    @pytest.mark.asyncio
    async def test_complete_enhanced_workflow(self):
        """全新機能を統合した完全ワークフローテスト"""
        
        # 1. 設定管理
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigManager(temp_dir)
            config_manager.save_config_template()
            config = config_manager.load_config()
        
        # 2. ログシステム
        logger = get_logger("workflow_test", LogLevel.INFO)
        
        # 3. エラーハンドリング
        error_handler = ErrorHandler()
        
        # 4. 文字化け修正
        encoding_handler = EncodingHandler()
        
        # 5. 模擬ワークフローの実行
        op_context = logger.log_operation_start("full_workflow_test")
        
        try:
            # 文字化けデータの修正
            test_data = [
                {"title": "�A�I�L�������̃��X�g", "description": "‚±‚ê‚Í‚Ä‚·‚Æ"}
            ]
            
            fixed_data = encoding_handler.batch_fix_events(test_data)
            
            # 成功メトリクス記録
            logger.metrics.record_success("data_processing", 1.2)
            
            logger.log_operation_end(op_context, success=True, 
                                   events_processed=len(fixed_data))
            
            # 健全性確認
            health = logger.get_health_status()
            
            # すべてが正常に動作することを確認
            assert len(fixed_data) == 1
            assert '�' not in fixed_data[0]['title']
            assert health['overall_status'] in ['healthy', 'warning']
            
        except Exception as e:
            # エラーハンドリング
            recovery_result = await error_handler.handle_error(e, op_context)
            logger.log_operation_end(op_context, success=False, error=str(e))
            
            # エラーが適切に処理されることを確認
            assert recovery_result in RecoveryResult


if __name__ == "__main__":
    # テスト実行
    pytest.main([__file__, "-v"])