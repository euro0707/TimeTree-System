"""TimeTree通知スケジューラー"""

import asyncio
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from .daily_notifier import DailySummaryNotifier
from ..config import Config


class TimeTreeScheduler:
    """TimeTree通知スケジュール管理"""
    
    def __init__(self, config: Config):
        self.config = config
        self.scheduler = AsyncIOScheduler()
        self.daily_notifier = DailySummaryNotifier(config)
        self.is_running = False
        
    async def start(self):
        """スケジューラー開始"""
        try:
            if self.is_running:
                logger.warning("Scheduler is already running")
                return
                
            # スケジュール設定
            self._setup_daily_schedule()
            
            # スケジューラー開始
            self.scheduler.start()
            self.is_running = True
            
            logger.info("TimeTree scheduler started successfully")
            logger.info(f"Daily notification scheduled at {self.config.daily_summary.time}")
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise
    
    async def stop(self):
        """スケジューラー停止"""
        try:
            if not self.is_running:
                return
                
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("TimeTree scheduler stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
    
    def _setup_daily_schedule(self):
        """毎朝の定時通知スケジュール設定"""
        if not self.config.daily_summary.enabled:
            logger.info("Daily summary is disabled, skipping schedule setup")
            return
        
        # 時間解析
        time_str = self.config.daily_summary.time  # "07:30"
        hour, minute = map(int, time_str.split(':'))
        
        # Cronトリガー作成
        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            timezone=self.config.daily_summary.timezone
        )
        
        # ジョブ登録
        self.scheduler.add_job(
            func=self._execute_daily_summary,
            trigger=trigger,
            id='daily_summary',
            name='Daily Schedule Summary',
            coalesce=True,  # 複数実行を防ぐ
            max_instances=1,  # 同時実行数制限
            replace_existing=True
        )
        
        logger.info(f"Daily summary job scheduled: {hour:02d}:{minute:02d} {self.config.daily_summary.timezone}")
    
    async def _execute_daily_summary(self):
        """毎朝の定時通知実行"""
        try:
            logger.info("Starting daily summary execution")
            
            success = await self.daily_notifier.send_daily_summary()
            
            if success:
                logger.info("Daily summary completed successfully")
            else:
                logger.error("Daily summary failed")
                
        except Exception as e:
            logger.error(f"Unexpected error in daily summary execution: {e}")
    
    async def run_manual_summary(self, target_date: Optional[datetime] = None):
        """手動での日次サマリー実行（テスト用）"""
        try:
            logger.info("Running manual daily summary")
            
            if target_date:
                success = await self.daily_notifier.send_daily_summary(target_date.date())
            else:
                success = await self.daily_notifier.send_daily_summary()
            
            return success
            
        except Exception as e:
            logger.error(f"Manual summary failed: {e}")
            return False
    
    def get_next_run_time(self) -> Optional[datetime]:
        """次回実行時刻を取得"""
        try:
            job = self.scheduler.get_job('daily_summary')
            if job and job.next_run_time:
                return job.next_run_time
            return None
        except Exception:
            return None
    
    def get_scheduler_status(self) -> dict:
        """スケジューラー状態取得"""
        next_run = self.get_next_run_time()
        
        return {
            "is_running": self.is_running,
            "scheduler_state": self.scheduler.state if hasattr(self.scheduler, 'state') else 'unknown',
            "daily_summary_enabled": self.config.daily_summary.enabled,
            "scheduled_time": self.config.daily_summary.time,
            "timezone": self.config.daily_summary.timezone,
            "next_run_time": next_run.isoformat() if next_run else None,
            "jobs_count": len(self.scheduler.get_jobs())
        }


class SchedulerManager:
    """スケジューラー管理クラス（シングルトン）"""
    
    _instance = None
    
    def __new__(cls, config: Config = None):
        if cls._instance is None:
            if config is None:
                raise ValueError("Config is required for first instantiation")
            cls._instance = super().__new__(cls)
            cls._instance.scheduler = TimeTreeScheduler(config)
        return cls._instance
    
    async def start(self):
        """スケジューラー開始"""
        await self.scheduler.start()
    
    async def stop(self):
        """スケジューラー停止"""
        await self.scheduler.stop()
    
    async def run_manual(self, target_date: Optional[datetime] = None):
        """手動実行"""
        return await self.scheduler.run_manual_summary(target_date)
    
    def get_status(self) -> dict:
        """状態取得"""
        return self.scheduler.get_scheduler_status()