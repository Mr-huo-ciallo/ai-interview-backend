from io import BytesIO


def register_and_login(client, username):
    password = "secret123"
    assert client.post("/api/auth/register", json={"username": username, "password": password}).status_code == 200
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def build_text_pdf(text: str):
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{number} 0 obj\n".encode("ascii"))
        output.write(body)
        output.write(b"\nendobj\n")
    xref = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    return output.getvalue()


def test_resume_pdf_import_requires_login(client):
    response = client.post(
        "/api/career/resume/import",
        files={"file": ("resume.pdf", build_text_pdf("John Doe Python FastAPI Docker experience"), "application/pdf")},
    )
    assert response.status_code == 401


def test_resume_pdf_import_returns_editable_preview(client, monkeypatch):
    headers = register_and_login(client, "pdf-owner")
    monkeypatch.setattr(
        "services.resume_import.call_llm_for_resume_extraction",
        lambda _text, _schema: {
            "fullName": "John Doe",
            "email": "john@example.com",
            "phone": "13800138000",
            "targetRole": "Backend Engineer",
            "skills": ["Python", "FastAPI", "Docker"],
            "education": [],
            "experience": [],
            "projects": [],
            "certifications": [],
            "location": "",
            "summary": "Backend developer",
        },
    )
    pdf = build_text_pdf(
        "John Doe Python FastAPI Docker backend developer john@example.com 13800138000 project experience"
    )
    response = client.post(
        "/api/career/resume/import",
        headers=headers,
        files={"file": ("resume.pdf", pdf, "application/pdf")},
        data={"targetRole": "Backend Engineer"},
    )
    assert response.status_code == 200
    extraction = response.json()["extraction"]
    assert extraction["extractionMethod"] == "local_text+llm"
    assert extraction["structured"]["fullName"] == "John Doe"
    assert "Python" in extraction["structured"]["skills"]
    assert "John Doe" in extraction["rawText"]


def test_resume_pdf_import_falls_back_to_local_rules(client, monkeypatch):
    headers = register_and_login(client, "pdf-fallback")
    monkeypatch.setattr(
        "services.resume_import.call_llm_for_resume_extraction",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("LLM unavailable")),
    )
    pdf = build_text_pdf("Li Ming Python FastAPI Docker 13800138000 liming@example.com project experience")
    response = client.post(
        "/api/career/resume/import",
        headers=headers,
        files={"file": ("resume.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 200
    extraction = response.json()["extraction"]
    assert extraction["extractionMethod"] == "local_text+rules"
    assert "Python" in extraction["structured"]["skills"]
    assert extraction["warnings"]


def test_resume_pdf_import_rejects_invalid_file(client):
    headers = register_and_login(client, "pdf-invalid")
    response = client.post(
        "/api/career/resume/import",
        headers=headers,
        files={"file": ("resume.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert "有效的 PDF" in response.json()["detail"]


def test_job_json_preview_and_confirm(client):
    headers = register_and_login(client, "job-importer")
    existing = {
        "title": "Backend Engineer",
        "company": "Example",
        "location": "Shanghai",
        "requiredSkills": "Python FastAPI",
    }
    assert client.post("/api/career/jobs", headers=headers, json=existing).status_code == 200
    jobs = [
        existing,
        {
            "title": "Frontend Engineer",
            "company": "Example",
            "location": "Remote",
            "requiredSkills": "Vue TypeScript",
        },
        {"title": "", "company": "Invalid"},
    ]
    preview = client.post("/api/career/jobs/import/preview", headers=headers, json={"jobs": jobs})
    assert preview.status_code == 200
    assert preview.json()["summary"] == {"total": 3, "valid": 1, "duplicate": 1, "invalid": 1}

    confirmed = client.post(
        "/api/career/jobs/import/confirm",
        headers=headers,
        json={"jobs": [jobs[1]]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["importedCount"] == 1
    dashboard = client.get("/api/career/dashboard", headers=headers).json()
    assert dashboard["summary"]["jobCount"] == 2
