from __future__ import annotations

import re
import logging
from io import BytesIO
from typing import Protocol

from pypdf import PdfReader

from crud import extract_skills
from llm_client import call_llm_for_resume_extraction
from schemas import ResumeExtractionResult, ResumeStructuredData


MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_LLM_TEXT_CHARS = 30_000
logger = logging.getLogger(__name__)


class ResumeImportError(ValueError):
    pass


class ResumeParserPort(Protocol):
    def parse(self, content: bytes, filename: str, target_role: str = "") -> ResumeExtractionResult:
        ...


class ResumeImportService:
    def __init__(self, parser: ResumeParserPort):
        self.parser = parser

    def import_pdf(self, content: bytes, filename: str, target_role: str = "") -> ResumeExtractionResult:
        return self.parser.parse(content, filename, target_role)


class LocalTextPdfResumeParser:
    def parse(self, content: bytes, filename: str, target_role: str = "") -> ResumeExtractionResult:
        self._validate_file(content, filename)
        raw_text, page_count, warnings = self._extract_text(content)
        structured = self._fallback_structure(raw_text, target_role)
        method = "local_text+rules"
        confidence = 0.45

        llm_text = raw_text[:MAX_LLM_TEXT_CHARS]
        if len(raw_text) > MAX_LLM_TEXT_CHARS:
            warnings.append("简历文本较长，AI 结构化仅分析前 30000 个字符；完整原文仍保留在预览中。")
        try:
            llm_result = call_llm_for_resume_extraction(
                llm_text,
                ResumeStructuredData.model_json_schema(),
            )
            structured = ResumeStructuredData.model_validate(llm_result)
            if target_role and not structured.targetRole:
                structured.targetRole = target_role
            method = "local_text+llm"
            confidence = 0.85
        except Exception:
            logger.warning("简历 AI 结构化失败，已回退到本地规则", exc_info=True)
            warnings.append("AI 结构化暂不可用，当前预览由本地规则生成，请在保存前核对。")

        return ResumeExtractionResult(
            rawText=raw_text,
            structured=structured,
            warnings=warnings,
            extractionMethod=method,
            pageCount=page_count,
            confidence=confidence,
        )

    @staticmethod
    def _validate_file(content: bytes, filename: str):
        if not filename.lower().endswith(".pdf"):
            raise ResumeImportError("仅支持 PDF 格式的简历")
        if not content:
            raise ResumeImportError("PDF 文件为空")
        if len(content) > MAX_PDF_BYTES:
            raise ResumeImportError("PDF 文件不能超过 8 MB")
        if not content.startswith(b"%PDF-"):
            raise ResumeImportError("文件内容不是有效的 PDF")

    @staticmethod
    def _extract_text(content: bytes):
        try:
            reader = PdfReader(BytesIO(content))
        except Exception as exc:
            raise ResumeImportError("PDF 无法读取或已经损坏") from exc

        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception as exc:
                raise ResumeImportError("暂不支持带密码的 PDF") from exc
            if not unlocked:
                raise ResumeImportError("暂不支持带密码的 PDF")

        page_count = len(reader.pages)
        if page_count == 0:
            raise ResumeImportError("PDF 不包含可读取页面")
        if page_count > MAX_PDF_PAGES:
            raise ResumeImportError(f"PDF 页数不能超过 {MAX_PDF_PAGES} 页")

        pages = []
        warnings = []
        empty_pages = 0
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text(extraction_mode="layout") or ""
            except Exception:
                try:
                    page_text = page.extract_text() or ""
                except Exception:
                    page_text = ""
                    warnings.append(f"第 {page_number} 页解析失败，请核对原文件。")
            page_text = LocalTextPdfResumeParser._normalize_text(page_text)
            if page_text:
                pages.append(page_text)
            else:
                empty_pages += 1

        raw_text = "\n\n".join(pages).strip()
        if len(raw_text) < 40:
            raise ResumeImportError("未提取到有效文本；该文件可能是扫描件，当前版本尚未启用 OCR")
        if empty_pages:
            warnings.append(f"有 {empty_pages} 页未提取到文本，请核对预览是否完整。")
        return raw_text, page_count, warnings

    @staticmethod
    def _normalize_text(value: str):
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.replace("\x00", "").splitlines()]
        normalized = []
        previous_blank = False
        for line in lines:
            is_blank = not line
            if is_blank and previous_blank:
                continue
            normalized.append(line)
            previous_blank = is_blank
        return "\n".join(normalized).strip()

    @staticmethod
    def _fallback_structure(raw_text: str, target_role: str):
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", raw_text, re.IGNORECASE)
        phone_match = re.search(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", raw_text)
        full_name = ""
        for line in lines[:8]:
            if 2 <= len(line) <= 24 and not re.search(r"[@\d:：/|]", line):
                full_name = line
                break
        return ResumeStructuredData(
            fullName=full_name,
            email=email_match.group(0) if email_match else "",
            phone=phone_match.group(0) if phone_match else "",
            targetRole=target_role,
            skills=extract_skills(raw_text),
        )
