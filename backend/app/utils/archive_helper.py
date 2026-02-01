"""
压缩文件处理工具

支持 ZIP 和 RAR 格式（需要安装 rarfile 和 unrar）
"""
import zipfile
import shutil
from pathlib import Path
from typing import Optional
from loguru import logger

# 尝试导入 rarfile（可选依赖）
try:
    import rarfile
    RARFILE_AVAILABLE = True
except ImportError:
    RARFILE_AVAILABLE = False
    logger.info("rarfile 未安装，RAR 格式支持不可用。可使用 pip install rarfile 安装")


class ArchiveExtractor:
    """压缩文件提取器"""

    @staticmethod
    def is_supported(filename: str) -> bool:
        """检查文件格式是否支持"""
        ext = Path(filename).suffix.lower()
        return ext in ('.zip', '.rar')

    @staticmethod
    def extract(
        archive_path: str | Path,
        extract_to: str | Path,
        password: Optional[str] = None
    ) -> list[str]:
        """
        提取压缩文件

        Args:
            archive_path: 压缩文件路径
            extract_to: 提取目标目录
            password: 压缩密码（可选）

        Returns:
            list[str]: 提取的文件列表

        Raises:
            ValueError: 不支持的格式或缺少依赖
            RuntimeError: 提取失败
        """
        archive_path = Path(archive_path)
        extract_to = Path(extract_to)
        extract_to.mkdir(parents=True, exist_ok=True)

        ext = archive_path.suffix.lower()

        if ext == '.zip':
            return ArchiveExtractor._extract_zip(archive_path, extract_to, password)
        elif ext == '.rar':
            return ArchiveExtractor._extract_rar(archive_path, extract_to, password)
        else:
            raise ValueError(f"不支持的压缩格式: {ext}")

    @staticmethod
    def _extract_zip(
        archive_path: Path,
        extract_to: Path,
        password: Optional[str] = None
    ) -> list[str]:
        """提取 ZIP 文件"""
        extracted_files = []
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                # 检查密码
                if password:
                    zf.setpassword(password.encode('utf-8'))

                # 检查是否有加密文件
                for info in zf.infolist():
                    if info.flag_bits & 0x1:  # 加密标志
                        if not password:
                            raise ValueError("ZIP 文件已加密，需要密码")

                # 提取文件
                for info in zf.infolist():
                    # 跳过目录
                    if info.is_dir():
                        continue

                    # 提取文件
                    extracted_path = zf.extract(info, extract_to)
                    extracted_files.append(str(extracted_path))

            logger.info(f"ZIP 文件提取完成: {len(extracted_files)} 个文件")
            return extracted_files

        except zipfile.BadZipFile as e:
            raise RuntimeError(f"无效的 ZIP 文件: {e}")
        except Exception as e:
            raise RuntimeError(f"提取 ZIP 文件失败: {e}")

    @staticmethod
    def _extract_rar(
        archive_path: Path,
        extract_to: Path,
        password: Optional[str] = None
    ) -> list[str]:
        """提取 RAR 文件"""
        if not RARFILE_AVAILABLE:
            raise ValueError(
                "RAR 格式支持不可用。请安装 rarfile:\n"
                "  pip install rarfile\n"
                "Windows 用户还需安装 UnRAR 并添加到 PATH"
            )

        try:
            with rarfile.RarFile(archive_path) as rf:
                # 检查密码
                if rf.needs_password():
                    if not password:
                        raise ValueError("RAR 文件已加密，需要密码")

                # 检查是否有 unrar 工具
                try:
                    rf.namelist()  # 测试是否能读取
                except Exception as e:
                    raise RuntimeError(
                        "无法读取 RAR 文件。请确保安装了 UnRAR 工具:\n"
                        "  Windows: https://www.rarlab.com/rar_add.htm\n"
                        "  Linux: sudo apt-get install unrar"
                    )

                # 提取文件
                extracted_files = []
                for info in rf.infolist():
                    if info.is_dir():
                        continue

                    extracted_path = rf.extract(info, extract_to, pwd=password)
                    extracted_files.append(str(extracted_path))

                logger.info(f"RAR 文件提取完成: {len(extracted_files)} 个文件")
                return extracted_files

        except Exception as e:
            raise RuntimeError(f"提取 RAR 文件失败: {e}")

    @staticmethod
    def list_geojson_files(directory: Path) -> list[Path]:
        """
        列出目录中的 GeoJSON 文件

        Args:
            directory: 目录路径

        Returns:
            list[Path]: GeoJSON 文件列表
        """
        if not directory.exists():
            return []

        # 递归查找所有 .json 文件
        json_files = list(directory.rglob("*.json"))

        # 过滤可能的 GeoJSON 文件
        # GeoJSON 文件通常包含 "type": "FeatureCollection"
        geojson_files = []
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    content = f.read(1000)  # 读取前 1000 字符
                    if '"FeatureCollection"' in content or '"Feature"' in content:
                        geojson_files.append(json_file)
            except Exception:
                # 无法读取，跳过
                continue

        return geojson_files


def clean_temp_directory(temp_dir: Path):
    """清理临时目录"""
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
