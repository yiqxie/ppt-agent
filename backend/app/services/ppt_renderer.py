"""PPT 转图片服务。

策略：调用 LibreOffice headless 把 .pptx / .ppt 转为 PDF，
再用 pdf2image / poppler 把 PDF 每一页渲染成 PNG。

之所以选 LibreOffice 是因为：
- 跨平台（Linux 容器内可装 libreoffice + poppler-utils）
- 免费、稳定、对动画/图片/字体保真度可接受
- python-pptx 自身没有真实渲染能力
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger
from pdf2image import convert_from_path


# Windows 调试时可通过环境变量指定 soffice / poppler 位置
_SOFFICE_BIN_ENV = "SOFFICE_BIN"
_POPPLER_PATH_ENV = "POPPLER_PATH"


def _find_soffice() -> str:
    """查找 LibreOffice 可执行文件。"""
    custom = os.environ.get(_SOFFICE_BIN_ENV)
    if custom and Path(custom).exists():
        return custom
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    # Windows 默认路径
    win_default = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
    if win_default.exists():
        return str(win_default)
    raise RuntimeError(
        "未找到 LibreOffice，可设置环境变量 SOFFICE_BIN 指向 soffice 可执行文件"
    )


async def _run_subprocess(cmd: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
    """异步执行子进程，返回 (returncode, stdout, stderr)。"""
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, stderr_b = await process.communicate()
    return process.returncode or 0, stdout_b.decode(errors="replace"), stderr_b.decode(errors="replace")


async def convert_ppt_to_images(
    ppt_bytes: bytes, original_filename: str, dpi: int = 150
) -> List[bytes]:
    """把 PPT 字节流转为每页 PNG 字节流列表。

    参数：
        ppt_bytes: 原始 PPT 文件字节
        original_filename: 用于决定后缀
        dpi: 渲染分辨率，默认 150（文件大小与清晰度平衡）

    返回：
        每一页 slide 对应的 PNG bytes 列表，顺序与 PPT 顺序一致。
    """
    suffix = Path(original_filename).suffix.lower()
    if suffix not in (".ppt", ".pptx"):
        raise ValueError(f"不支持的文件类型：{suffix}")

    soffice = _find_soffice()
    poppler_path = os.environ.get(_POPPLER_PATH_ENV) or None

    with tempfile.TemporaryDirectory(prefix="ppt-agent-") as tmp_str:
        tmp = Path(tmp_str)
        ppt_path = tmp / f"input{suffix}"
        ppt_path.write_bytes(ppt_bytes)

        # 1) PPT -> PDF
        pdf_dir = tmp / "pdf_out"
        pdf_dir.mkdir()
        cmd = [
            soffice,
            "--headless",
            "--norestore",
            "--nofirststartwizard",
            "--convert-to",
            "pdf",
            "--outdir",
            str(pdf_dir),
            str(ppt_path),
        ]
        rc, out, err = await _run_subprocess(cmd, cwd=str(tmp))
        if rc != 0:
            raise RuntimeError(f"LibreOffice 转换失败 (rc={rc}): {err or out}")

        pdfs = list(pdf_dir.glob("*.pdf"))
        if not pdfs:
            raise RuntimeError("LibreOffice 未输出任何 PDF 文件")
        pdf_path = pdfs[0]
        logger.info(f"PPT 已转为 PDF：{pdf_path.name}")

        # 2) PDF -> PNGs（pdf2image 是同步阻塞，放到线程池里）
        loop = asyncio.get_running_loop()

        def _render() -> List[bytes]:
            images = convert_from_path(
                str(pdf_path),
                dpi=dpi,
                fmt="png",
                poppler_path=poppler_path,
            )
            result: List[bytes] = []
            for img in images:
                from io import BytesIO

                buf = BytesIO()
                img.save(buf, format="PNG", optimize=True)
                result.append(buf.getvalue())
            return result

        images_bytes = await loop.run_in_executor(None, _render)
        logger.info(f"已渲染 {len(images_bytes)} 张 slide 截图")
        return images_bytes
