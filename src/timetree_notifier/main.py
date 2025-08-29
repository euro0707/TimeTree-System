"""TimeTree毎朝通知システム - メインアプリケーション"""

import asyncio
import signal
import sys
from pathlib import Path
from datetime import datetime

from loguru import logger

from .config import Config
from .core.scheduler import SchedulerManager
from .utils.logger import setup_logging


class TimeTreeNotifierApp:
    """TimeTree通知アプリケーション"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = None
        self.scheduler_manager = None
        self.config_path = config_path
        self.is_running = False
        
    async def initialize(self):
        """アプリケーション初期化"""
        try:
            # 設定ファイル読み込み
            logger.info(f"Loading configuration from {self.config_path}")
            self.config = Config.load_from_file(self.config_path)
            
            # ディレクトリ作成
            self.config.ensure_directories()
            
            # ログ設定
            setup_logging(self.config.logging)
            
            # スケジューラー初期化
            self.scheduler_manager = SchedulerManager(self.config)
            
            logger.info("TimeTree Notifier initialized successfully")
            self._log_configuration()
            
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            raise
    
    def _log_configuration(self):
        """設定内容をログ出力"""
        logger.info(f"Daily notification time: {self.config.daily_summary.time}")
        logger.info(f"Timezone: {self.config.daily_summary.timezone}")
        logger.info(f"Include description: {self.config.daily_summary.include_description}")
        logger.info(f"Include location: {self.config.daily_summary.include_location}")
        logger.info(f"Max events display: {self.config.daily_summary.max_events_display}")
    
    async def start(self):
        """アプリケーション開始"""
        try:
            if self.is_running:
                logger.warning("Application is already running")
                return
            
            logger.info("Starting TimeTree Notifier...")
            
            # スケジューラー開始
            await self.scheduler_manager.start()
            
            self.is_running = True
            logger.info("TimeTree Notifier started successfully")
            
            # 次回実行時刻をログ出力
            status = self.scheduler_manager.get_status()
            if status.get('next_run_time'):
                logger.info(f"Next notification scheduled at: {status['next_run_time']}")
            
        except Exception as e:
            logger.error(f"Failed to start application: {e}")
            raise
    
    async def stop(self):
        """アプリケーション停止"""
        try:
            if not self.is_running:
                return
            
            logger.info("Stopping TimeTree Notifier...")
            
            if self.scheduler_manager:
                await self.scheduler_manager.stop()
            
            self.is_running = False
            logger.info("TimeTree Notifier stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop application: {e}")
    
    async def run_manual_notification(self, target_date: datetime = None):
        """手動通知実行（テスト用）"""
        try:
            if not self.scheduler_manager:
                raise RuntimeError("Application not initialized")
            
            logger.info("Running manual notification...")
            success = await self.scheduler_manager.run_manual(target_date)
            
            if success:
                logger.info("Manual notification completed successfully")
            else:
                logger.error("Manual notification failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Manual notification error: {e}")
            return False
    
    def get_status(self) -> dict:
        """アプリケーション状態取得"""
        base_status = {
            "app_running": self.is_running,
            "config_loaded": self.config is not None,
            "scheduler_initialized": self.scheduler_manager is not None
        }
        
        if self.scheduler_manager:
            scheduler_status = self.scheduler_manager.get_status()
            base_status.update(scheduler_status)
        
        return base_status


# グローバルアプリケーションインスタンス
app = TimeTreeNotifierApp()


async def run_daemon():
    """デーモンモードで実行"""
    
    # シグナルハンドラー設定
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(shutdown())
    
    async def shutdown():
        """グレースフルシャットダウン"""
        await app.stop()
        sys.exit(0)
    
    # SIGINT, SIGTERM ハンドラー登録
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # アプリケーション初期化・開始
        await app.initialize()
        await app.start()
        
        logger.info("TimeTree Notifier is running. Press Ctrl+C to stop.")
        
        # 無限ループでアプリケーション維持
        while app.is_running:
            await asyncio.sleep(60)  # 1分間隔でチェック
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await app.stop()


async def run_manual():
    """手動実行モード"""
    try:
        await app.initialize()
        
        logger.info("Running manual notification...")
        success = await app.run_manual_notification()
        
        if success:
            logger.info("Manual notification completed successfully")
            return 0
        else:
            logger.error("Manual notification failed")
            return 1
            
    except Exception as e:
        logger.error(f"Manual execution failed: {e}")
        return 1


def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TimeTree毎朝通知システム")
    parser.add_argument(
        "--mode", 
        choices=['daemon', 'manual', 'status'],
        default='daemon',
        help="実行モード (default: daemon)"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="設定ファイルパス (default: config.yaml)"
    )
    
    args = parser.parse_args()
    
    # 設定ファイルパスを設定
    app.config_path = args.config
    
    try:
        if args.mode == 'daemon':
            # デーモンモード
            asyncio.run(run_daemon())
        elif args.mode == 'manual':
            # 手動実行モード
            exit_code = asyncio.run(run_manual())
            sys.exit(exit_code)
        elif args.mode == 'status':
            # ステータス表示モード
            asyncio.run(app.initialize())
            status = app.get_status()
            print("=== TimeTree Notifier Status ===")
            for key, value in status.items():
                print(f"{key}: {value}")
    
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()