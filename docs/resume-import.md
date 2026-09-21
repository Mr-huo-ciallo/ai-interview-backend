# 简历与职位导入

## 运行链路

PDF 导入采用“提取、预览、确认保存”三段式流程：

```text
UploadFile → ResumeParserPort → pypdf 文本提取 → LLM 固定 Schema → 前端预览 → 用户确认 → resume_profiles
```

- `POST /api/career/resume/import` 只解析，不写数据库。
- `PUT /api/career/resume` 是唯一保存入口。
- PDF 上限为 8 MB、20 页；当前只处理带文本层的 PDF。
- LLM 输出必须通过 `ResumeStructuredData` 校验；失败时回退到本地规则，并在 `warnings` 中说明。
- 原始 PDF 不落盘，接口完成后关闭临时上传文件。

`ResumeParserPort` 位于 `services/resume_import.py`。OCR 或第三方 PDF 服务必须实现该接口，路由和前端不应感知具体提供者。

## 职位 JSON 格式

JSON 顶层可以直接是数组，也可以使用 `{"jobs": [...]}`。单次最多 100 条，文件前端限制为 1 MB。

```json
{
  "jobs": [
    {
      "title": "Python 后端工程师",
      "company": "示例公司",
      "location": "上海",
      "salary": "15-25K",
      "requiredSkills": "Python、FastAPI、MySQL、Docker",
      "description": "负责后端接口与服务工程化",
      "sourceUrl": "https://example.com/jobs/1"
    }
  ]
}
```

预览接口负责字段校验和去重；确认接口再次校验，并在单次数据库事务中写入选中职位。

## OCR 与外部适配器启用条件

日志事件 `resume_pdf_import_completed` 会记录解析方法、页数和警告数；`resume_pdf_import_failed` 会记录失败原因，不记录简历正文。

在至少积累 50 次真实导入前不增加新提供者。样本达到后按以下事实决策：

- 扫描件或无文本层导致的失败占比持续达到 10%：增加本地 OCR 适配器。
- 文本可以提取，但复杂排版导致关键字段持续缺失，且现有 LLM 无法稳定纠正：评估 Anthropic PDF 适配器。
- 普通文本型 PDF 已满足使用：保持本地实现，避免增加部署体积、网络延迟和供应商耦合。

失败率按下式计算：

\[
r_{failure}=\frac{N_{failed}}{N_{completed}+N_{failed}}
\]

增加提供者前必须补对应契约测试，并保留本地解析作为默认实现。
