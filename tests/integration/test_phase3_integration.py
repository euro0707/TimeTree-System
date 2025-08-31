#!/usr/bin/env python3
"""
Phase 3: マルチチャンネル通知システム統合テスト

TimeTree Notifier v3.0 - Phase 3の統合テストスイート
- GAS音声通知システムの動作確認
- マルチチャンネル配信システムの検証
- メッセージフォーマット最適化の確認
- Slack/Discord連携の統合テスト
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any

# テスト対象モジュール
from src.timetree_notifier.layers.notification_layer.multi_channel_dispatcher import (
    NotificationDispatcher, DeliveryMethod, ChannelType
)
from src.timetree_notifier.layers.notification_layer.message_formatter import (
    MessageFormatter, MessageFormat, EventData
)
from src.timetree_notifier.layers.notification_layer.gas_notifier import GASNotifier
from src.timetree_notifier.layers.notification_layer.slack_discord_notifiers import (
    SlackNotifier, DiscordNotifier
)

class TestPhase3Integration:
    """Phase 3統合テストクラス"""
    
    def setup_method(self):
        """テストセットアップ"""
        self.today = datetime.now().date()
        self.tomorrow = self.today + timedelta(days=1)
        
        # テストイベントデータ
        self.test_events = [
            EventData(
                title="朝の会議",
                start_time=datetime.combine(self.today, datetime.min.time().replace(hour=9)),
                end_time=datetime.combine(self.today, datetime.min.time().replace(hour=10)),
                location="会議室A",
                description="月次進捗レビュー",
                is_all_day=False
            ),
            EventData(
                title="ランチミーティング",
                start_time=datetime.combine(self.today, datetime.min.time().replace(hour=12)),
                end_time=datetime.combine(self.today, datetime.min.time().replace(hour=13)),
                location="レストランB",
                description="新プロジェクト打ち合わせ",
                is_all_day=False
            ),
            EventData(
                title="定期健康診断",
                start_time=datetime.combine(self.today, datetime.min.time()),
                end_time=None,
                location="病院C",
                description="年1回の健康チェック",
                is_all_day=True
            )
        ]
    
    @pytest.mark.asyncio
    async def test_full_notification_pipeline(self):
        """完全な通知パイプラインの統合テスト"""
        
        # モックの設定
        mock_line_notifier = AsyncMock()
        mock_gas_notifier = AsyncMock()
        mock_slack_notifier = AsyncMock()
        mock_discord_notifier = AsyncMock()
        
        # 成功レスポンスの設定
        success_result = Mock()
        success_result.success = True
        success_result.channel_type = ChannelType.LINE
        success_result.message_id = "msg_123"
        success_result.delivery_time = datetime.now()
        success_result.error = None
        
        mock_line_notifier.send_message.return_value = success_result
        mock_gas_notifier.send_message.return_value = success_result
        mock_slack_notifier.send_message.return_value = success_result
        mock_discord_notifier.send_message.return_value = success_result
        
        # ディスパッチャーの設定
        dispatcher = NotificationDispatcher()
        dispatcher.channels = {
            ChannelType.LINE: mock_line_notifier,
            ChannelType.GAS_VOICE: mock_gas_notifier,
            ChannelType.SLACK: mock_slack_notifier,
            ChannelType.DISCORD: mock_discord_notifier
        }
        
        # メッセージフォーマッターの設定
        formatter = MessageFormatter()
        
        # 全チャンネルへの配信テスト
        result = await dispatcher.send_to_all_channels(
            events=self.test_events,
            target_date=self.today,
            delivery_method=DeliveryMethod.PARALLEL
        )
        
        # 結果検証
        assert result.total_channels == 4
        assert result.successful_deliveries == 4
        assert result.failed_deliveries == 0
        assert result.success_rate == 1.0
        
        # 各チャンネルが呼び出されたことを確認
        mock_line_notifier.send_message.assert_called_once()
        mock_gas_notifier.send_message.assert_called_once()
        mock_slack_notifier.send_message.assert_called_once()
        mock_discord_notifier.send_message.assert_called_once()
        
        print("✅ 完全な通知パイプライン統合テスト - 成功")
    
    @pytest.mark.asyncio
    async def test_message_format_optimization(self):
        """メッセージフォーマット最適化の統合テスト"""
        
        formatter = MessageFormatter()
        
        # 各フォーマットでのメッセージ生成テスト
        formats_to_test = [
            MessageFormat.LINE_SIMPLE,
            MessageFormat.LINE_FLEX,
            MessageFormat.SLACK_BLOCKS,
            MessageFormat.DISCORD_EMBED,
            MessageFormat.GAS_VOICE
        ]
        
        for message_format in formats_to_test:
            message = await formatter.format_daily_message(
                events=self.test_events,
                target_date=self.today,
                message_format=message_format
            )
            
            # 基本的な構造確認
            assert message is not None
            assert len(str(message)) > 0
            
            # フォーマット固有の検証
            if message_format == MessageFormat.LINE_FLEX:
                assert isinstance(message, dict)
                assert "type" in message
                assert message["type"] == "flex"
            
            elif message_format == MessageFormat.SLACK_BLOCKS:
                assert isinstance(message, dict)
                assert "blocks" in message
                assert isinstance(message["blocks"], list)
            
            elif message_format == MessageFormat.DISCORD_EMBED:
                assert isinstance(message, dict)
                assert "embed" in message
                assert "title" in message["embed"]
            
            elif message_format == MessageFormat.GAS_VOICE:
                assert isinstance(message, dict)
                assert "text" in message or "ssml" in message
            
            print(f"✅ {message_format.value}フォーマット - 最適化確認完了")
    
    @pytest.mark.asyncio
    async def test_gas_voice_notification_integration(self):
        """GAS音声通知システムの統合テスト"""
        
        with patch('src.timetree_notifier.layers.notification_layer.gas_notifier.requests') as mock_requests:
            # モックレスポンスの設定
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "success",
                "message_id": "gas_voice_123"
            }
            mock_requests.post.return_value = mock_response
            
            # GAS通知設定
            config = {
                'gas_webhook_url': 'https://script.google.com/test/webhook',
                'gas_timeout': 30,
                'gas_voice_enabled': True,
                'gas_voice_speed': 'medium',
                'gas_voice_pitch': 'neutral'
            }
            
            gas_notifier = GASNotifier(config)
            
            # 音声メッセージの作成と送信
            result = await gas_notifier.send_message({
                'events': self.test_events,
                'target_date': self.today,
                'message_format': MessageFormat.GAS_VOICE
            })
            
            # 結果検証
            assert result.success == True
            assert result.channel_type == ChannelType.GAS_VOICE
            assert result.message_id == "gas_voice_123"
            
            # API呼び出し確認
            mock_requests.post.assert_called_once()
            call_args = mock_requests.post.call_args
            
            # リクエストボディの検証
            request_data = json.loads(call_args[1]['data'])
            assert 'voice_message' in request_data
            assert 'ssml_content' in request_data
            assert request_data['voice_enabled'] == True
            
            print("✅ GAS音声通知システム統合テスト - 成功")
    
    @pytest.mark.asyncio
    async def test_slack_discord_rich_messaging(self):
        """Slack/Discord リッチメッセージング統合テスト"""
        
        # Slack統合テスト
        with patch('src.timetree_notifier.layers.notification_layer.slack_discord_notifiers.aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"ok": True, "message": {"ts": "1234567890"}})
            
            mock_session_instance = AsyncMock()
            mock_session_instance.post.return_value.__aenter__.return_value = mock_response
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            slack_config = {
                'slack_webhook_url': 'https://hooks.slack.com/test/webhook',
                'slack_timeout': 30,
                'slack_format': 'blocks'
            }
            
            slack_notifier = SlackNotifier(slack_config)
            
            result = await slack_notifier.send_message({
                'events': self.test_events,
                'target_date': self.today,
                'message_format': MessageFormat.SLACK_BLOCKS
            })
            
            assert result.success == True
            assert result.channel_type == ChannelType.SLACK
            
            print("✅ Slack リッチメッセージング統合テスト - 成功")
        
        # Discord統合テスト
        with patch('src.timetree_notifier.layers.notification_layer.slack_discord_notifiers.aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"id": "discord_msg_123"})
            
            mock_session_instance = AsyncMock()
            mock_session_instance.post.return_value.__aenter__.return_value = mock_response
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            discord_config = {
                'discord_webhook_url': 'https://discord.com/api/webhooks/test',
                'discord_timeout': 30,
                'discord_format': 'embed'
            }
            
            discord_notifier = DiscordNotifier(discord_config)
            
            result = await discord_notifier.send_message({
                'events': self.test_events,
                'target_date': self.today,
                'message_format': MessageFormat.DISCORD_EMBED
            })
            
            assert result.success == True
            assert result.channel_type == ChannelType.DISCORD
            
            print("✅ Discord リッチメッセージング統合テスト - 成功")
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """エラーハンドリングと回復処理の統合テスト"""
        
        # 部分的な失敗をシミュレート
        mock_line_notifier = AsyncMock()
        mock_gas_notifier = AsyncMock()
        mock_slack_notifier = AsyncMock()
        mock_discord_notifier = AsyncMock()
        
        # LINEは成功、GASは失敗、Slackは成功、Discordは失敗のシナリオ
        success_result = Mock()
        success_result.success = True
        success_result.channel_type = ChannelType.LINE
        success_result.delivery_time = datetime.now()
        success_result.error = None
        
        failure_result = Mock()
        failure_result.success = False
        failure_result.channel_type = ChannelType.GAS_VOICE
        failure_result.delivery_time = datetime.now()
        failure_result.error = Exception("API timeout")
        
        mock_line_notifier.send_message.return_value = success_result
        mock_gas_notifier.send_message.return_value = failure_result
        mock_slack_notifier.send_message.return_value = success_result
        mock_discord_notifier.send_message.return_value = failure_result
        
        # ディスパッチャーの設定
        dispatcher = NotificationDispatcher()
        dispatcher.channels = {
            ChannelType.LINE: mock_line_notifier,
            ChannelType.GAS_VOICE: mock_gas_notifier,
            ChannelType.SLACK: mock_slack_notifier,
            ChannelType.DISCORD: mock_discord_notifier
        }
        
        # 配信実行
        result = await dispatcher.send_to_all_channels(
            events=self.test_events,
            target_date=self.today,
            delivery_method=DeliveryMethod.PARALLEL,
            retry_failed=True
        )
        
        # 部分的な成功を確認
        assert result.total_channels == 4
        assert result.successful_deliveries == 2
        assert result.failed_deliveries == 2
        assert result.success_rate == 0.5
        assert len(result.failed_channels) == 2
        
        print("✅ エラーハンドリングと回復処理統合テスト - 成功")
    
    @pytest.mark.asyncio
    async def test_performance_and_rate_limiting(self):
        """パフォーマンスとレート制限の統合テスト"""
        
        # 大量のイベント（20件）でテスト
        many_events = []
        for i in range(20):
            event = EventData(
                title=f"会議 #{i+1}",
                start_time=datetime.combine(self.today, datetime.min.time().replace(hour=9 + i % 10)),
                end_time=datetime.combine(self.today, datetime.min.time().replace(hour=10 + i % 10)),
                location=f"会議室{chr(65 + i % 5)}",
                description=f"テストイベント {i+1}",
                is_all_day=False
            )
            many_events.append(event)
        
        # モック設定（高速レスポンス）
        mock_notifier = AsyncMock()
        success_result = Mock()
        success_result.success = True
        success_result.delivery_time = datetime.now()
        mock_notifier.send_message.return_value = success_result
        
        dispatcher = NotificationDispatcher()
        dispatcher.channels = {ChannelType.LINE: mock_notifier}
        
        # パフォーマンス測定
        start_time = datetime.now()
        
        result = await dispatcher.send_to_all_channels(
            events=many_events,
            target_date=self.today,
            delivery_method=DeliveryMethod.PARALLEL
        )
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # パフォーマンス検証（20イベントが3秒以内で処理）
        assert processing_time < 3.0
        assert result.success_rate == 1.0
        
        print(f"✅ パフォーマンステスト - 処理時間: {processing_time:.2f}秒")

if __name__ == "__main__":
    """統合テストの実行"""
    
    async def run_integration_tests():
        """統合テストの実行"""
        print("🧪 TimeTree Notifier v3.0 - Phase 3 統合テスト開始")
        print("=" * 60)
        
        test_instance = TestPhase3Integration()
        test_instance.setup_method()
        
        # 各テストメソッドを実行
        test_methods = [
            test_instance.test_full_notification_pipeline,
            test_instance.test_message_format_optimization,
            test_instance.test_gas_voice_notification_integration,
            test_instance.test_slack_discord_rich_messaging,
            test_instance.test_error_handling_and_recovery,
            test_instance.test_performance_and_rate_limiting
        ]
        
        passed_tests = 0
        total_tests = len(test_methods)
        
        for test_method in test_methods:
            try:
                await test_method()
                passed_tests += 1
            except Exception as e:
                print(f"❌ テスト失敗: {test_method.__name__} - {str(e)}")
        
        print("=" * 60)
        print(f"📊 テスト結果: {passed_tests}/{total_tests} 成功")
        
        if passed_tests == total_tests:
            print("🎉 Phase 3統合テスト - 全て成功！")
            return True
        else:
            print("⚠️ 一部のテストが失敗しました")
            return False
    
    # 統合テストの実行
    success = asyncio.run(run_integration_tests())
    
    if success:
        print("\n✨ TimeTree Notifier v3.0 Phase 3実装完了")
        print("📱 マルチチャンネル通知システムの準備が整いました！")
    else:
        print("\n🔧 テスト失敗があります。実装を確認してください。")