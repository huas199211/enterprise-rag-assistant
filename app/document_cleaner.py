"""
文档清洗流水线 — Document Cleaning Pipeline

覆盖场景：
  编码检测修复 / 格式统一 / 噪声过滤 / 敏感信息脱敏 /
  语言检测 / 文档去重 / 表格保留 / OCR 识别 / 结构解析

使用方式：
    from .document_cleaner import CleaningPipeline, CleaningConfig

    config = CleaningConfig()
    pipeline = CleaningPipeline(config)
    result = pipeline.run(raw_text, filename="xxx.pdf")
    cleaned_text = result.text

可依次禁用单个步骤：
    config.enable_noise_filter = False
"""

from __future__ import annotations

import hashlib
import logging
import re
import string
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

CHINESE_SENSITIVE_PATTERNS: dict[str, str] = {
    "手机号": r"\b1[3-9]\d{9}\b",
    "固话": r"\b0\d{2,3}[-\s]?\d{7,8}\b",
    "身份证": r"\b\d{17}[\dXx]\b",
    "银行卡": r"\b\d{16,19}\b",
    "邮箱": r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
    "IP地址": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "统一社会信用代码": r"\b[A-Za-z0-9]{18}\b",
    "护照": r"\b[A-Za-z]\d{8}\b",
}

# 中英文混排时保留的最小连续字符长度
MIN_CONTINUOUS_ZH = 2

# SimHash 指纹位数
SIMHASH_BITS = 64
# 海明距离阈值（<= 此值判定为近似重复）
SIMHASH_DISTANCE_THRESHOLD = 3


@dataclass
class CleaningConfig:
    """文档清洗配置"""

    # ── 编码修复 ──
    enable_encoding_fix: bool = True
    encoding_fix_target: str = "utf-8"

    # ── 格式统一 ──
    enable_text_normalize: bool = True
    normalize_line_endings: bool = True     # 统一换行符
    normalize_whitespace: bool = True       # 合并连续空白
    strip_control_chars: bool = True        # 移除控制字符（保留 \n \t）

    # ── 噪声过滤 ──
    enable_noise_filter: bool = True
    noise_header_footer: bool = True        # 页眉/页脚/页码
    noise_watermark: bool = True            # 水印标记（机密/内部资料）
    noise_toc_markers: bool = True          # 目录标记（第 X 章/节）
    noise_urls: bool = True                 # URL 保留与否 — 此处直接移除
    noise_empty_lines: bool = True          # 合并连续空行

    # ── 敏感信息脱敏 ──
    enable_sensitive_mask: bool = True
    sensitive_mask_token: str = "***"
    sensitive_enabled_patterns: tuple[str, ...] = field(
        default_factory=lambda: tuple(CHINESE_SENSITIVE_PATTERNS.keys())
    )

    # ── 语言检测与过滤 ──
    enable_language_filter: bool = False
    language_target: str = "zh"             # 只保留该语言的段落（空=不限制）
    language_min_length: int = 20           # 短段落不检测

    # ── 文档去重 ──
    enable_deduplication: bool = True
    dedup_threshold: int = SIMHASH_DISTANCE_THRESHOLD
    dedup_index: list[int] | None = field(default_factory=list)

    # ── OCR ──
    enable_ocr: bool = False
    ocr_lang: str = "chi_sim+eng"
    ocr_ppi_threshold: int = 150            # 低于此分辨率跳过 OCR

    # ── 表格保留 ──
    enable_table_preserve: bool = True
    table_row_sep: str = " | "

    # ── 结构解析 ──
    enable_structure_parse: bool = True
    structure_heading_patterns: tuple[str, ...] = (
        r"^#{1,6}\s+",                     # Markdown 标题
        r"^[一二三四五六七八九十]+[、．\.]\s*",    # 中文数字标题
        r"^第[一二三四五六七八九十]+[章节条款]\s*",  # 第X章/节
        r"^\d+[、．\.]\s*",                 # 数字编号
        r"^[A-Z]\.\s*",                    # 字母编号
    )

    # ── 日志 ──
    log_stats: bool = True


# ---------------------------------------------------------------------------
# 结果模型
# ---------------------------------------------------------------------------


@dataclass
class CleaningResult:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 步骤基类
# ---------------------------------------------------------------------------


class CleaningStep:
    name: str = "base"

    def __call__(self, text: str, config: CleaningConfig) -> tuple[str, dict[str, Any]]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 1. 编码检测与修复
# ---------------------------------------------------------------------------


class EncodingFixer(CleaningStep):
    name = "encoding_fix"

    def __call__(self, text: str, config: CleaningConfig) -> tuple[str, dict[str, Any]]:
        if not config.enable_encoding_fix:
            return text, {}
        stats: dict[str, Any] = {"detected_encoding": None, "fixed": False}

        # 检测并修复 garbled Unicode（如 "ç¾Žå›½" → UTF-8 bytes 被误判为 Latin-1）
        try:
            text.encode("latin-1")
            decoded = text.encode("latin-1").decode("utf-8", errors="strict")
            if self._has_meaningful_chinese(decoded):
                text = decoded
                stats["fixed"] = True
                stats["detected_encoding"] = "utf-8_via_latin1"
        except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
            pass

        # 尝试 GBK → UTF-8（Windows 中文环境常见）
        if not stats["fixed"]:
            try:
                text.encode("latin-1")
                decoded = text.encode("latin-1").decode("gbk", errors="strict")
                if self._has_meaningful_chinese(decoded):
                    text = decoded
                    stats["fixed"] = True
                    stats["detected_encoding"] = "gbk_via_latin1"
            except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
                pass

        # 尝试 GB18030
        if not stats["fixed"]:
            try:
                text.encode("latin-1")
                decoded = text.encode("latin-1").decode("gb18030", errors="strict")
                if self._has_meaningful_chinese(decoded):
                    text = decoded
                    stats["fixed"] = True
                    stats["detected_encoding"] = "gb18030_via_latin1"
            except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
                pass

        # 检测替代字符（U+FFFD）— 表示有损转换
        replacement_count = text.count("�")
        if replacement_count > 0:
            stats["replacement_chars"] = replacement_count

        return text, stats

    @staticmethod
    def _has_meaningful_chinese(text: str, min_ratio: float = 0.05) -> bool:
        if not text.strip():
            return False
        zh_count = sum(1 for ch in text if "一" <= ch <= "鿿")
        return zh_count / max(1, len(text.strip())) >= min_ratio


class ChardetEncodingFixer(CleaningStep):
    """基于 chardet 的编码检测（需安装 chardet）"""

    name = "chardet_encoding_fix"

    def __call__(self, text: str, config: CleaningConfig) -> tuple[str, dict[str, Any]]:
        if not config.enable_encoding_fix:
            return text, {}
        try:
            import chardet
        except ImportError:
            return text, {"warning": "chardet 未安装，跳过"}

        raw_bytes = text.encode("utf-8", errors="replace")
        result = chardet.detect(raw_bytes)
        stats: dict[str, Any] = {"chardet_encoding": result.get("encoding"), "confidence": result.get("confidence")}

        detected = result.get("encoding", "").lower()
        confidence = result.get("confidence", 0)
        if detected not in ("utf-8", "ascii") and confidence > 0.7:
            try:
                text = raw_bytes.decode(detected, errors="replace")
                stats["fixed"] = True
            except (LookupError, UnicodeDecodeError):
                stats["fixed"] = False

        return text, stats


# ---------------------------------------------------------------------------
# 2. 格式统一
# ---------------------------------------------------------------------------


class TextNormalizer(CleaningStep):
    name = "text_normalize"

    def __call__(self, text: str, config: CleaningConfig) -> tuple[str, dict[str, Any]]:
        if not config.enable_text_normalize:
            return text, {}
        stats: dict[str, Any] = {}
        original_len = len(text)

        if config.normalize_line_endings:
            text = text.replace("\r\n", "\n").replace("\r", "\n")

        if config.strip_control_chars:
            text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

        if config.normalize_whitespace:
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text)

        stats["length_before"] = original_len
        stats["length_after"] = len(text)
        stats["removed_chars"] = original_len - len(text)
        return text, stats


# ---------------------------------------------------------------------------
# 3. 噪声过滤
# ---------------------------------------------------------------------------


class NoiseFilter(CleaningStep):
    name = "noise_filter"

    def __call__(self, text: str, config: CleaningConfig) -> tuple[str, dict[str, Any]]:
        if not config.enable_noise_filter:
            return text, {}
        stats: dict[str, Any] = {}
        original_len = len(text)

        if config.noise_header_footer:
            # 页码: "第 X 页" / "第 X 页，共 Y 页" / "— X —" / "- X -"
            text = re.sub(r"第\s*\d+\s*页[，,]\s*共\s*\d+\s*页", "", text)
            text = re.sub(r"第\s*\d+\s*页", "", text)
            text = re.sub(r"[—\-]\s*\d+\s*[—\-]", "", text)
            text = re.sub(r"^\d+\s*/\s*\d+\s*$", "", text, flags=re.MULTILINE)
            # 常见页眉: "公司名称" + 分割线
            text = re.sub(r"^[^。\n]{2,20}\n[-═=]{3,}\n", "", text, flags=re.MULTILINE)

        if config.noise_watermark:
            for pattern in [
                r"机密[^。\n]*",
                r"内部资料[^。\n]*",
                r"严禁[抄传][^。\n]*",
                r"仅供参考[^。\n]*",
                r"未经[^。\n]*不得[^。\n]*",
                r"Copyright\s*[©\d].*",
                r"All\s+Rights\s+Reserved.*",
            ]:
                text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        if config.noise_toc_markers:
            # 目录标记: "第X章 标题" / "第一章" / "1.1 标题"
            text = re.sub(r"^[第第][一二三四五六七八九十百千]+[章节篇]\s*.*$", "", text, flags=re.MULTILINE)
            text = re.sub(r"^目\s*录\s*$", "", text, flags=re.MULTILINE)

        if config.noise_urls:
            text = re.sub(r"https?://\S+", "", text)

        if config.noise_empty_lines:
            text = re.sub(r"\n{3,}", "\n\n", text)

        stats["removed_chars"] = original_len - len(text)
        return text.strip(), stats


# ---------------------------------------------------------------------------
# 4. 敏感信息脱敏
# ---------------------------------------------------------------------------


class SensitiveMasker(CleaningStep):
    name = "sensitive_mask"

    def __call__(self, text: str, config: CleaningConfig) -> tuple[str, dict[str, Any]]:
        if not config.enable_sensitive_mask:
            return text, {}
        stats: dict[str, int] = {}

        for name in config.sensitive_enabled_patterns:
            pattern = CHINESE_SENSITIVE_PATTERNS.get(name)
            if not pattern:
                continue
            repl = config.sensitive_mask_token
            count_before = len(re.findall(pattern, text))
            if not count_before:
                continue
            text = re.sub(pattern, repl, text)
            stats[name] = count_before

        return text, stats


# ---------------------------------------------------------------------------
# 5. 语言检测与过滤
# ---------------------------------------------------------------------------


class LanguageFilter(CleaningStep):
    name = "language_filter"

    def __call__(self, text: str, config: CleaningConfig) -> tuple[str, dict[str, Any]]:
        if not config.enable_language_filter:
            return text, {}
        try:
            from langdetect import detect
        except ImportError:
            return text, {"warning": "langdetect 未安装，跳过"}

        stats: dict[str, Any] = {"dropped_paragraphs": 0}
        paragraphs = text.split("\n\n")
        kept = []
        for para in paragraphs:
            para = para.strip()
            if not para or len(para) < config.language_min_length:
                kept.append(para)
                continue
            try:
                lang = detect(para)
                if lang == config.language_target:
                    kept.append(para)
                else:
                    stats["dropped_paragraphs"] += 1
            except Exception:
                kept.append(para)

        return "\n\n".join(kept), stats


# ---------------------------------------------------------------------------
# 6. 文档去重 — SimHash
# ---------------------------------------------------------------------------


class _SimHash:
    """SimHash 局部敏感哈希，用于近似去重"""

    def __init__(self, bits: int = SIMHASH_BITS):
        self.bits = bits

    def fingerprint(self, text: str) -> int:
        tokens = re.findall(r"[\w一-鿿]+", text.lower())
        v = [0] * self.bits
        for token in tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            for i in range(self.bits):
                mask = 1 << i
                if h & mask:
                    v[i] += 1
                else:
                    v[i] -= 1
        fp = 0
        for i in range(self.bits):
            if v[i] > 0:
                fp |= 1 << i
        return fp

    @staticmethod
    def hamming_distance(a: int, b: int) -> int:
        return (a ^ b).bit_count()


class Deduplicator(CleaningStep):
    name = "deduplication"

    def __call__(self, text: str, config: CleaningConfig) -> tuple[str, dict[str, Any]]:
        if not config.enable_deduplication:
            return text, {}
        stats: dict[str, Any] = {"duplicates_found": 0}
        sh = _SimHash()
        fp = sh.fingerprint(text)

        if config.dedup_index is not None:
            for existing_fp in config.dedup_index:
                if sh.hamming_distance(fp, existing_fp) <= config.dedup_threshold:
                    stats["duplicates_found"] += 1
                    stats["duplicate_of"] = existing_fp
                    return "", stats  # 判定为重复，返回空文本

        return text, stats


# ---------------------------------------------------------------------------
# 7. 表格保留
# ---------------------------------------------------------------------------


class TablePreserver(CleaningStep):
    """检测并保留表格结构（处理文本化表格）"""

    name = "table_preserve"

    def __call__(self, text: str, config: CleaningConfig) -> tuple[str, dict[str, Any]]:
        if not config.enable_table_preserve:
            return text, {}
        stats: dict[str, Any] = {}
        lines = text.split("\n")
        cleaned = []
        in_table = False
        table_buffer: list[str] = []
        table_count = 0

        for line in lines:
            # 检测表格行（包含 | 且非空）
            if "|" in line and line.strip().startswith("|"):
                if not in_table:
                    in_table = True
                    table_buffer = []
                table_buffer.append(line)
            else:
                if in_table and table_buffer:
                    flat = self._flatten_table(table_buffer)
                    cleaned.append(flat)
                    table_count += 1
                    in_table = False
                cleaned.append(line)

        if in_table and table_buffer:
            cleaned.append(self._flatten_table(table_buffer))
            table_count += 1

        stats["tables_preserved"] = table_count
        return "\n".join(cleaned), stats

    @staticmethod
    def _flatten_table(rows: list[str]) -> str:
        cells = []
        for row in rows:
            parts = [p.strip() for p in row.split("|") if p.strip()]
            if parts:
                cells.extend(parts)
        sep = " | "
        result = sep.join(cells)
        return f"[表格] {result}" if result else ""


# ---------------------------------------------------------------------------
# 8. OCR 处理器
# ---------------------------------------------------------------------------


class OCRProcessor(CleaningStep):
    name = "ocr"

    def __call__(self, text: str, config: CleaningConfig) -> tuple[str, dict[str, Any]]:
        if not config.enable_ocr or text.strip():
            return text, {}
        stats: dict[str, Any] = {}
        try:
            from PIL import Image
            import pytesseract
        except ImportError:
            return text, {"warning": "pytesseract / Pillow 未安装，跳过"}

        stats["ocr_applied"] = False
        # 此步骤通常不在此处使用（OCR 在文本提取阶段已完成）
        # 保留接口以便图片嵌入文档场景
        return text, stats


# ---------------------------------------------------------------------------
# 9. 文档结构解析
# ---------------------------------------------------------------------------


class StructureParser(CleaningStep):
    """识别标题层级、段落结构，输出结构化元数据"""

    name = "structure_parse"

    def __call__(self, text: str, config: CleaningConfig) -> tuple[str, dict[str, Any]]:
        if not config.enable_structure_parse:
            return text, {}
        headings: list[dict[str, Any]] = []
        paragraph_count = 0
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            for pattern in config.structure_heading_patterns:
                if re.match(pattern, line.strip()):
                    headings.append({"text": line.strip(), "line": i, "pattern": pattern})
                    break
            if line.strip():
                paragraph_count += 1
            i += 1

        stats: dict[str, Any] = {
            "headings_found": len(headings),
            "paragraph_count": paragraph_count,
            "headings": headings[:50],  # 最多保存 50 个标题
        }
        return text, stats


# ---------------------------------------------------------------------------
# 流水线编排
# ---------------------------------------------------------------------------


class CleaningPipeline:
    """文档清洗流水线 — 按顺序执行所有启用步骤"""

    def __init__(self, config: CleaningConfig | None = None):
        self.config = config or CleaningConfig()
        self.dedup_index: list[int] = []

        self.steps: list[CleaningStep] = [
            EncodingFixer(),
            ChardetEncodingFixer(),
            TextNormalizer(),
            NoiseFilter(),
            SensitiveMasker(),
            LanguageFilter(),
            Deduplicator(),
            TablePreserver(),
            OCRProcessor(),
            StructureParser(),
        ]

    def run(self, text: str, filename: str = "", **extra_meta: Any) -> CleaningResult:
        """执行完整清洗流水线"""
        metadata: dict[str, Any] = {"filename": filename, **extra_meta}
        step_stats: dict[str, Any] = {}

        for step in self.steps:
            text, step_stat = step(text, self.config)
            if step_stat:
                step_stats[step.name] = step_stat

        # 更新去重索引
        if self.config.enable_deduplication and text.strip():
            sh = _SimHash()
            self.dedup_index.append(sh.fingerprint(text))

        result = CleaningResult(text=text.strip(), metadata=metadata)
        if self.config.log_stats:
            result.stats = step_stats
            result.stats["total_length"] = len(text)

        return result

    def reset_dedup_index(self) -> None:
        """重置去重索引（例如切换文档批次时）"""
        self.dedup_index.clear()


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

_default_pipeline = CleaningPipeline()


def clean_text(text: str, filename: str = "") -> str:
    """快速清洗：一行调用"""
    return _default_pipeline.run(text, filename=filename).text


def build_pipeline_from_config(config_dict: dict[str, Any]) -> CleaningPipeline:
    """从字典构建流水线（用于 API 配置）"""
    config = CleaningConfig(**{k: v for k, v in config_dict.items() if hasattr(CleaningConfig, k)})
    return CleaningPipeline(config)


# ---------------------------------------------------------------------------
# 命令行测试入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    sample = """第 1 页
机密

目  录

第一章 总则...

联系邮箱: test@company.com
手机: 13800138000

| 姓名 | 部门 | 职位 |
| 张三 | 技术部 | 工程师 |

第 2 页
"""
    result = CleaningPipeline().run(sample, filename="test.md")
    print("=== 清洗后文本 ===")
    print(result.text)
    print("\n=== 统计 ===")
    import json
    print(json.dumps(result.stats, ensure_ascii=False, indent=2))
