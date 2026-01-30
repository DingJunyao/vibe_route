"""
速率限制配置
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# 速率限制器实例
limiter = Limiter(key_func=get_remote_address)
