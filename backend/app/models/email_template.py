"""
邮件模板模型
管理员可在后台管理中编辑通知邮件的主题与正文
"""
from sqlalchemy import Column, Integer, String, Text, Boolean
from sqlalchemy.orm import validates

from app.core.database import Base
from app.models.base import AuditMixin


class EmailTemplate(Base, AuditMixin):
    """
    邮件模板表

    按事件类型（template_key）存储通知邮件模板：
    - recording_completed：录屏任务完成通知
    - recording_failed：录屏任务失败通知

    正文中支持 {{variable}} 占位符（见 email_service.render）。
    """
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, index=True)
    template_key = Column(String(50), unique=True, index=True, nullable=False, comment="模板标识")
    subject = Column(String(200), nullable=False, comment="邮件主题（支持占位符）")
    body = Column(Text, nullable=False, comment="邮件正文（支持占位符）")
    is_html = Column(Boolean, default=False, nullable=False, comment="正文是否为 HTML 格式")

    @validates("template_key")
    def validate_template_key(self, _key, value):
        if not value or not value.strip():
            raise ValueError("template_key 不能为空")
        return value.strip()

    def __repr__(self):
        return f"<EmailTemplate(template_key={self.template_key})>"
