"""
邮件模板管理 API（管理员）

模板按 template_key 存 email_templates 表，正文/主题支持 {{variable}} 占位符。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin_user
from app.models.email_template import EmailTemplate
from app.models.user import User
from app.services.config_service import config_service
from app.services.email_service import email_service, render_template

router = APIRouter(prefix="/admin/email-templates", tags=["邮件模板"])


class EmailTemplateUpdate(BaseModel):
    """邮件模板更新 schema"""
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    is_html: Optional[bool] = None


class EmailTemplateResponse(BaseModel):
    """邮件模板响应 schema"""
    template_key: str
    subject: str
    body: str
    is_html: bool
    # 模板说明（固定文案，来源于 DEFAULT_TEMPLATES 的 key）
    name: str = ""

    class Config:
        from_attributes = True


# template_key 的展示名与变量说明（前端直接透出）
TEMPLATE_META = {
    "recording_completed": {
        "name": "录屏任务完成通知",
        "variables": ["app_name", "username", "track_name", "finished_at", "download_url"],
    },
    "recording_failed": {
        "name": "录屏任务失败通知",
        "variables": ["app_name", "username", "track_name", "finished_at", "error"],
    },
}


def _to_response(template: EmailTemplate) -> EmailTemplateResponse:
    meta = TEMPLATE_META.get(template.template_key, {})
    return EmailTemplateResponse(
        template_key=template.template_key,
        subject=template.subject,
        body=template.body,
        is_html=bool(template.is_html),
        name=meta.get("name", template.template_key),
    )


async def _get_template(db: AsyncSession, template_key: str) -> EmailTemplate:
    result = await db.execute(
        select(EmailTemplate).where(
            EmailTemplate.template_key == template_key,
            EmailTemplate.is_valid == True,  # noqa: E712
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="邮件模板不存在",
        )
    return template


@router.get("", response_model=list[EmailTemplateResponse])
async def list_email_templates(
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有邮件模板（管理员）"""
    result = await db.execute(
        select(EmailTemplate).where(EmailTemplate.is_valid == True)  # noqa: E712
    )
    templates = result.scalars().all()
    return [_to_response(t) for t in templates]


@router.get("/meta")
async def get_template_meta(
    _current_admin: User = Depends(get_current_admin_user),
):
    """获取模板 key 的展示名与可用变量列表（管理员）"""
    return [
        {
            "template_key": key,
            "name": meta["name"],
            "variables": meta["variables"],
        }
        for key, meta in TEMPLATE_META.items()
    ]


@router.put("/{template_key}", response_model=EmailTemplateResponse)
async def update_email_template(
    template_key: str,
    data: EmailTemplateUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """更新邮件模板（管理员）"""
    if template_key not in TEMPLATE_META:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="邮件模板不存在",
        )
    template = await _get_template(db, template_key)

    template.subject = data.subject
    template.body = data.body
    if data.is_html is not None:
        template.is_html = data.is_html
    template.updated_by = current_admin.id

    from app.models.base import get_utc_now
    template.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(template)
    return _to_response(template)


@router.post("/{template_key}/test")
async def send_test_email(
    template_key: str,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    向当前管理员发送测试邮件（使用保存的 SMTP 配置，不检查通知开关）
    """
    if template_key not in TEMPLATE_META:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="邮件模板不存在",
        )
    template = await _get_template(db, template_key)

    configs = await config_service.get_all_configs(db)
    email_config = configs.get("email_config") or {}
    if not email_service.is_smtp_configured(email_config):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP 未配置，请先在系统配置中填写邮件服务器",
        )

    from app.core.config import settings
    context = {
        "app_name": settings.APP_NAME,
        "username": current_admin.username,
        "track_name": "测试轨迹（示例）",
        "finished_at": "2026-01-01 12:00:00 UTC",
        "error": "测试失败原因（示例）",
        "download_url": f"{settings.FRONTEND_URL.rstrip('/')}/api/animation/export/test/download",
    }
    subject = render_template(template.subject, context)
    body = render_template(template.body, context)
    try:
        await email_service.send_email(
            email_config=email_config,
            to_email=current_admin.email,
            subject=subject,
            body=body,
            is_html=bool(template.is_html),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"测试邮件发送失败：{e}",
        )
    return {"message": f"测试邮件已发送至 {current_admin.email}"}
