# common/logging_config.py

import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

class LogConfig:
    """統一的なロギング設定"""
    
    DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    DEFAULT_LEVEL = logging.INFO
    MAX_BYTES = 1024 * 1024  # 1MB
    BACKUP_COUNT = 5

    @classmethod
    def setup_logger(cls, 
                    name: str, 
                    log_file: Optional[str] = None,
                    log_dir: str = 'logs',
                    level: int = DEFAULT_LEVEL) -> logging.Logger:
        """
        ロガーのセットアップ
        
        Args:
            name: ロガー名
            log_file: ログファイル名（Noneの場合は{name}.logを使用）
            log_dir: ログディレクトリ
            level: ロギングレベル
            
        Returns:
            設定済みのロガー
        """
        # ログディレクトリの作成
        os.makedirs(log_dir, exist_ok=True)

        # ロガーの取得
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # 既存のハンドラをクリア
        if logger.hasHandlers():
            logger.handlers.clear()

        # ファイル名の設定
        if log_file is None:
            log_file = f"{name}.log"
        log_path = os.path.join(log_dir, log_file)

        # ハンドラの設定
        handler = RotatingFileHandler(
            log_path,
            maxBytes=cls.MAX_BYTES,
            backupCount=cls.BACKUP_COUNT
        )
        handler.setFormatter(logging.Formatter(cls.DEFAULT_FORMAT))
        logger.addHandler(handler)

        # コンソール出力用ハンドラ
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(cls.DEFAULT_FORMAT))
        logger.addHandler(console_handler)

        return logger

    @classmethod
    def get_component_logger(cls, component_name: str) -> logging.Logger:
        """
        コンポーネント用ロガーの取得
        
        Args:
            component_name: コンポーネント名
            
        Returns:
            設定済みのロガー
        """
        return cls.setup_logger(
            name=component_name,
            log_file=f"{component_name.lower()}.log"
        )