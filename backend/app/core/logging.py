"""统一日志配置。

使用 loguru 提供更友好的日志格式，并将 uvicorn / fastapi 的标准日志桥接过来。
"""

import logging
import sys

from loguru import logger


class _InterceptHandler(logging.Handler):
    """将 logging 模块的日志重定向到 loguru。"""

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - 日志桥接
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        # 找到原始调用位置以保持堆栈信息正确
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(debug: bool = False) -> None:
    """初始化 loguru 与标准 logging 桥接。"""
    # 移除默认 handler
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG" if debug else "INFO",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level:<8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )
    # 桥接标准 logging
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logging.getLogger(name).handlers = [_InterceptHandler()]
        logging.getLogger(name).propagate = False
