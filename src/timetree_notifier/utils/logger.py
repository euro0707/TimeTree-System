"""ログ設定ユーティリティ"""

import sys
from pathlib import Path
from loguru import logger

from ..config.settings import LoggingConfig


def setup_logging(config: LoggingConfig):
    """ログ設定のセットアップ"""
    
    # デフォルトハンドラーを削除
    logger.remove()
    
    # ログレベル設定
    log_level = config.level.upper()
    
    # コンソール出力設定
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )
    
    # ファイル出力設定
    if config.file:
        log_file = Path(config.file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            log_file,
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation=config.max_size,
            retention=config.rotation,
            compression="gz",
            encoding="utf-8"
        )
    
    # 初期ログメッセージ
    logger.info(f"Logging configured: level={log_level}, file={config.file}")


def mask_sensitive_info(message: str) -> str:
    """機密情報をマスク"""
    import re
    
    patterns = [
        (r'password[\'\"]*\s*[=:]\s*[\'\"]*([^\'\"\s]+)', r'password: [MASKED]'),
        (r'token[\'\"]*\s*[=:]\s*[\'\"]*([^\'\"\s]+)', r'token: [MASKED]'),
        (r'Bearer\s+([A-Za-z0-9\-_]+)', r'Bearer [MASKED]'),
    ]
    
    masked_message = message
    for pattern, replacement in patterns:
        masked_message = re.sub(pattern, replacement, masked_message, flags=re.IGNORECASE)
    
    return masked_message