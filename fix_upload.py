# 读取文件
with open("d:/code/vibe_route/backend/app/services/overlay_template_service.py", "r", encoding="utf-8") as f:
    content = f.read()

# 找到 upload_user_font 函数并完全重写
start = content.find("async def upload_user_font")
if start == -1:
    print("Function not found!")
    exit(1)

# 找到函数结束位置
end = content.find("\n    async def delete_font", start)
if end == -1:
    print("delete_font not found!")
    exit(1)

# 提取函数签名之前的所有内容
before_sig = content[start:end]

# 新的函数体
new_func = """    async def upload_user_font(
        self,
        user_id: int,
        is_admin: bool,
        filename: str,
        file_content: bytes
    ) -> Font:
        \"\"\"上传用户字体\"\"\"
        # 检查是否允许用户上传字体
        if not settings.overlay_allow_user_fonts:
            raise HTTPException(403, "用户字体上传功能已关闭")

        # 殡理员上传时 type='admin'，普通用户上传时 type='user'
        font_type = 'admin' if is_admin else 'user'

        # 检查数量限制
        from sqlalchemy import func
        count_result = await self.db.execute(
            select(func.count(Font.id))
            .where(Font.owner_id == user_id)
            .where(Font.type == font_type)
            .where(Font.is_valid == True)
        )
        count = count_result.scalar() or 0
        if count >= settings.overlay_max_user_fonts:
            raise HTTPException(
                400,
                f"已达到字体数量上限 ({settings.overlay_max_user_fonts})"
            )

        # 检查大小限制
        file_size = len(file_content)
        size_result = await self.db.execute(
            select(func.sum(Font.file_size))
            .where(Font.owner_id == user_id)
            .where(Font.type == font_type)
            .where(Font.is_valid == True)
        )
        total_size = size_result.scalar() or 0
        max_size_bytes = settings.overlay_max_user_fonts_size_mb * 1024 * 1024
        if total_size + file_size > max_size_bytes:
            raise HTTPException(
                400,
                f"已达到存储空间上限 ({settings.overlay_max_user_fonts_size_mb}MB)"
            )

        # 保存文件
        upload_dir = Path(settings.UPLOAD_DIR) / "fonts" / "user"
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / filename
        with open(file_path, 'wb') as f:
            f.write(file_content)

        # 创建字体记录
        font = Font(
            id=f"user_{user_id}_{filename}",
            name=filename.rsplit('.', 1)[0],  # 去掉扩展名
            filename=filename,
            type=font_type,
            owner_id=user_id,
            file_path=str(file_path),
            file_size=file_size,
            supports_chinese=True,  # 假设支持中文
        )
        self.db.add(font)
        await self.db.commit()
        await self.db.refresh(font)
        return font

    """ + before_sig

# 写回文件
new_content = content[:start] + new_func + content[end:]
with open("d:/code/vibe_route/backend/app/services/overlay_template_service.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Function rewritten successfully")
