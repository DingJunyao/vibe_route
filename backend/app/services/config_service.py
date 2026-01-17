"""
配置服务层
"""
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import Config, InviteCode
from app.models.user import User


class ConfigService:
    """配置服务类"""

    # 默认配置
    DEFAULT_CONFIGS = {
        "registration_enabled": True,
        "invite_code_required": False,
        "default_map_provider": "osm",
        "geocoding_provider": "nominatim",
        "geocoding_config": {
            "nominatim": {
                "url": "http://192.168.100.3:6664",
                "email": None,
            },
            "gdf": {
                "data_path": "data/area_data",
            },
            "amap": {
                "api_key": "",
            },
            "baidu": {
                "api_key": "",
            },
        },
        "map_layers": {
            "osm": {
                "id": "osm",
                "name": "OpenStreetMap",
                "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                "crs": "wgs84",
                "attribution": "&copy; OpenStreetMap contributors",
                "max_zoom": 19,
                "min_zoom": 1,
                "enabled": True,
                "order": 1,
                "subdomains": "abc",
            },
            "amap": {
                "id": "amap",
                "name": "高德地图",
                "url": "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
                "crs": "gcj02",
                "attribution": "&copy; 高德地图",
                "max_zoom": 19,
                "min_zoom": 1,
                "enabled": True,
                "order": 0,
                "subdomains": ["1", "2", "3", "4"],
            },
            "baidu": {
                "id": "baidu",
                "name": "百度地图",
                "url": "https://apimaponline{s}.bdimg.com/tile/?qt=vtile&v=three&ak={ak}&x={x}&y={y}&z={z}&styles=pl&scaler=2&udt=20211014&from=mapvthree",
                "crs": "bd09",
                "attribution": "&copy; 百度地图",
                "max_zoom": 19,
                "min_zoom": 3,
                "enabled": True,
                "order": 2,
                "subdomains": ["0", "1", "2", "3"],
                "ak": "",
            },
        },
    }

    async def get(self, db: AsyncSession, key: str) -> Optional[str]:
        """获取配置值"""
        result = await db.execute(
            select(Config).where(and_(Config.key == key, Config.is_valid == True))
        )
        config = result.scalar_one_or_none()
        return config.value if config else None

    async def get_json(self, db: AsyncSession, key: str, default=None):
        """
        获取配置值（智能解析）

        尝试解析为 JSON，如果失败则尝试解析为简单类型或返回默认值
        """
        value = await self.get(db, key)
        if value is None or value == '':
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # 不是 JSON 格式，尝试解析为简单类型
            # 处理布尔值
            if value.lower() == 'true':
                return True
            if value.lower() == 'false':
                return False
            # 处理数字
            try:
                if '.' in value:
                    return float(value)
                return int(value)
            except ValueError:
                pass
            # 返回原始字符串
            return value

    async def set(self, db: AsyncSession, key: str, value: str, user_id: int) -> None:
        """设置配置值"""
        result = await db.execute(
            select(Config).where(and_(Config.key == key, Config.is_valid == True))
        )
        config = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if config:
            config.value = value
            config.updated_by = user_id
            config.updated_at = now
        else:
            config = Config(
                key=key,
                value=value,
                created_by=user_id,
                updated_by=user_id,
                is_valid=True
            )
            db.add(config)

        await db.commit()

    async def set_json(self, db: AsyncSession, key: str, value, user_id: int) -> None:
        """
        设置配置值（智能处理）

        对于简单类型（str, int, bool, float, None），直接存储为字符串
        对于复杂类型（dict, list），使用 JSON 序列化
        """
        if value is None or isinstance(value, (str, int, bool, float)):
            # 简单类型直接存储
            if value is None:
                str_value = ''
            elif isinstance(value, bool):
                str_value = 'true' if value else 'false'
            else:
                str_value = str(value)
        else:
            # 复杂类型使用 JSON 序列化
            str_value = json.dumps(value, ensure_ascii=False)

        await self.set(db, key, str_value, user_id)

    async def get_all_configs(self, db: AsyncSession) -> dict:
        """
        获取所有配置

        使用智能解析来读取配置值
        """
        configs = self.DEFAULT_CONFIGS.copy()

        # 从数据库获取配置并覆盖默认值
        result = await db.execute(select(Config).where(Config.is_valid == True))
        for config in result.scalars().all():
            # 使用智能解析逻辑（与 get_json 相同）
            raw_value = config.value
            if raw_value == '':
                configs[config.key] = None
            else:
                try:
                    configs[config.key] = json.loads(raw_value)
                except json.JSONDecodeError:
                    # 不是 JSON 格式，尝试解析为简单类型
                    if raw_value.lower() == 'true':
                        configs[config.key] = True
                    elif raw_value.lower() == 'false':
                        configs[config.key] = False
                    else:
                        # 尝试解析为数字
                        try:
                            if '.' in raw_value:
                                configs[config.key] = float(raw_value)
                            else:
                                configs[config.key] = int(raw_value)
                        except ValueError:
                            # 返回原始字符串
                            configs[config.key] = raw_value

        return configs

    def _parse_config_value(self, value: str):
        """
        智能解析配置值
        - 尝试解析为 JSON
        - 如果失败，检查是否是被过度引号包裹的字符串
        - 最后直接返回原始值
        """
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # 检查是否是带引号的字符串
            if value.startswith('"') and value.endswith('"'):
                try:
                    return json.loads(value)
                except:
                    return value[1:-2]
            return value

    async def update_config(self, db: AsyncSession, updates: dict, user_id: int) -> dict:
        """更新配置"""
        for key, value in updates.items():
            await self.set_json(db, key, value, user_id)
        return await self.get_all_configs(db)

    async def init_default_configs(self, db: AsyncSession, user_id: int = 1) -> None:
        """初始化默认配置"""
        for key, value in self.DEFAULT_CONFIGS.items():
            existing = await self.get(db, key)
            if existing is None:
                await self.set_json(db, key, value, user_id)

    # 邀请码相关方法
    async def create_invite_code(
        self,
        db: AsyncSession,
        code: Optional[str],
        max_uses: int,
        created_by: int,
        expires_in_days: Optional[int] = None,
    ) -> InviteCode:
        """创建邀请码"""
        if code is None:
            code = secrets.token_urlsafe(8)

        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        invite_code = InviteCode(
            code=code,
            max_uses=max_uses,
            created_by=created_by,  # 创建者外键
            expires_at=expires_at,
            is_valid=True,
            updated_by=created_by,
        )
        db.add(invite_code)
        await db.commit()
        await db.refresh(invite_code)
        return invite_code

    async def get_invite_code(self, db: AsyncSession, code: str) -> Optional[InviteCode]:
        """获取邀请码"""
        result = await db.execute(
            select(InviteCode).where(
                and_(InviteCode.code == code, InviteCode.is_valid == True)
            )
        )
        return result.scalar_one_or_none()

    async def validate_invite_code(self, db: AsyncSession, code: str) -> bool:
        """验证邀请码是否有效"""
        invite_code = await self.get_invite_code(db, code)
        if not invite_code:
            return False
        return invite_code.is_valid

    async def use_invite_code(self, db: AsyncSession, code: str, user_id: int) -> bool:
        """使用邀请码"""
        invite_code = await self.get_invite_code(db, code)
        if not invite_code or not invite_code.is_valid:
            return False

        invite_code.used_count += 1
        invite_code.updated_by = user_id
        await db.commit()
        return True

    async def get_invite_codes(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
    ) -> list[InviteCode]:
        """获取邀请码列表"""
        result = await db.execute(
            select(InviteCode)
            .where(InviteCode.is_valid == True)
            .offset(skip)
            .limit(limit)
            .order_by(InviteCode.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_invite_code(
        self,
        db: AsyncSession,
        invite_code: InviteCode,
        user_id: int
    ) -> None:
        """软删除邀请码"""
        invite_code.is_valid = False
        invite_code.updated_by = user_id
        invite_code.updated_at = datetime.now(timezone.utc)
        await db.commit()


config_service = ConfigService()
