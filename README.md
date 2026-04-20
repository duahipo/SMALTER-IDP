# SMALTER-IDP
**Intelligent Document Processing — AI-powered extraction and technical validation of business documents**

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Project Structure](#4-project-structure)
5. [Processing Pipeline](#5-processing-pipeline)
6. [Extraction Architecture](#6-extraction-architecture)
   - [Rule-Based Extraction (Regex)](#61-rule-based-extraction-regex)
   - [AI-Based Extraction (LLM)](#62-ai-based-extraction-llm)
   - [Hybrid Extraction](#63-hybrid-extraction)
   - [Specialized Agents](#64-specialized-agents)
   - [Document Router](#65-document-router)
7. [API Reference](#7-api-reference)
8. [Configuration](#8-configuration)
9. [Testing](#9-testing)
10. [Current Limitations](#10-current-limitations)
11. [Roadmap](#11-roadmap)
12. [Authors](#12-authors)

---

## 1. Project Overview

SMALTER-IDP is a modular, AI-assisted backend system designed to automate the extraction and technical validation of data from business documents. It targets platforms integrating multiple functional domains, including:

- Accounting (invoices, accounting documents)
- Human Resources (medical certificates, HR documents)
- Electronic Document Management (EDM/GED)

### Problem Statement

In current back-office workflows, documents uploaded by clients are processed manually by human operators. This approach introduces:

- Low scalability under high document volumes
- Elevated processing latency
- Significant operational cost
- Exposure to human error

### Solution

SMALTER-IDP replaces manual processing with an automated pipeline that receives a document, identifies its type, assesses its quality, applies OCR if required, and returns a structured, machine-readable response — ready for consumption by downstream business systems.

---

## 2. System Architecture

The system is built around a modular FastAPI backend. Each functional concern (type detection, quality analysis, OCR, extraction, routing) is encapsulated in a dedicated module.

```
Client Upload
     |
     v
[ FastAPI Endpoint ]
     |
     +---> [ File Type Detector ]
     |
     +---> [ PDF-to-Image Converter ] (if PDF non-native)
     |
     +---> [ Image Quality Checker ]  (score threshold: 70%)
     |              |
     |         score < 70 --> REJECTED
     |         score >= 70 --> continue
     |
     +---> [ OCR Engine ]
     |
     +---> [ Document Router ]
     |              |
     |         +----+----+----+
     |         |         |    |
     |     Invoice    Bank  Cash ...
     |      Agent    Agent Agent
     |         |         |    |
     |     [ HybridExtractor ]
     |         |
     |     Regex --> LLM (if fields missing) --> Merge
     |
     v
[ Structured JSON Response ]
```

---

## 3. Technology Stack

| Layer | Component | Purpose |
|---|---|---|
| API | FastAPI | REST endpoint, request orchestration |
| Validation | Pydantic | Response schema definition and validation |
| File Detection | python-magic | Real MIME type detection (not extension-based) |
| Image Analysis | OpenCV | Quality scoring (sharpness, contrast, readability) |
| PDF Conversion | pdf2image | PDF-to-image rasterization for OCR processing |
| OCR | pytesseract | Text extraction from images and rasterized PDFs |
| Extraction | Regex (rule-based) | Deterministic field extraction for critical fields |
| Extraction | LLM (AI-based) | Fallback extraction for ambiguous or missing fields |
| Configuration | python-dotenv | Centralized parameter management via `.env` |
| Testing | unittest | Component-level validation |

---

## 4. Project Structure

```
smalter-autodoc/
├── api/
│   └── main.py                    # FastAPI entrypoint, request orchestration
├── core/
│   ├── file_type_detector.py      # MIME type detection via python-magic
│   ├── image_quality_checker.py   # Quality scoring via OpenCV
│   ├── ocr_engine.py              # Text extraction via pytesseract
│   └── pdf_to_image_converter.py  # PDF rasterization via pdf2image
├── agents/
│   ├── base_agent.py              # Abstract base agent (process/extract pipeline)
│   ├── invoice_agent.py           # Invoice-specific extraction logic
│   ├── bank_agent.py              # Bank statement extraction logic
│   └── cash_agent.py              # Cash receipt extraction logic
├── extractors/
│   ├── regex_extractor.py         # Rule-based field extraction
│   ├── llm_extractor.py           # LLM-based fallback extraction
│   └── hybrid_extractor.py        # Regex + LLM merge strategy
├── routing/
│   └── document_router.py         # Agent selection by document type
├── models/
│   └── responses.py               # Pydantic response schemas
├── utils/
│   └── config.py                  # Configuration loader
├── tests/
│   └── ...                        # Unit tests per module
├── .env                           # Environment variables (not committed)
└── requirements.txt
```

---

## 5. Processing Pipeline

The end-to-end processing pipeline operates as follows:

```
Step 1  Upload Document
Step 2  Detect file type (PDF / PNG / JPEG / other)
Step 3  If PDF:
           - Attempt native text extraction
           - If non-native PDF: convert to image
Step 4  Analyze image quality
           - Score >= 70%  → proceed
           - Score < 70%   → reject with diagnostic
Step 5  Apply OCR (if image or non-native PDF)
Step 6  Route to specialized agent (Invoice / Bank / Cash / ...)
Step 7  Apply HybridExtractor
           - Regex extracts critical fields
           - LLM fills missing or ambiguous fields
           - Merge results (Regex takes precedence)
Step 8  Normalize and clean output
Step 9  Return structured JSON response
```

---

## 6. Extraction Architecture

### 6.1 Rule-Based Extraction (Regex)

The `RegexExtractor` applies predefined regular expression patterns to raw OCR text. For each business field, multiple patterns are defined to handle formatting variations present in real-world documents.

**Example — Total TTC field:**

```python
patterns = [
    r"Montant\s*TTC\s*[:\-]?\s*(\d+[.,]\d+)",
    r"Total\s*TTC\s*[:\-]?\s*(\d+[.,]\d+)",
    r"TTC\s*[:\-]?\s*(\d+[.,]\d+)"
]
```

**Date normalization:** Multiple input formats (`DD/MM/YYYY`, `YYYY-MM-DD`, `1 Janvier 2024`, `January 1st, 2024`) are accepted and normalized to ISO 8601 (`YYYY-MM-DD`). Abbreviated years are expanded (e.g., `24` → `2024`).

**Amount normalization:** Space separators, comma/dot decimal variants, and currency symbols (`€`, `$`, `EUR`, `USD`) are handled uniformly and converted to a standard `float`.

**Mandatory field enforcement:** If a critical field (invoice number, date, total TTC) is absent, the missing field is logged and either a rejection is triggered or the LLM fallback is activated.

Regex is applied first because it offers deterministic, hallucination-free behavior with full control over extraction results.

### 6.2 AI-Based Extraction (LLM)

The `LLMExtractor` is invoked as a fallback when Regex fails to extract one or more fields. It is never called for fields already reliably extracted.

**Activation conditions:**
- At least one important field is missing after Regex extraction
- Or explicit AI extraction mode is enabled by the caller

**Prompt design:**

```
Extract the following fields from the text.
Return STRICTLY valid JSON.
If a field is absent, return null.
```

**Example LLM response:**

```json
{
  "date": "2024-01-01",
  "total_ttc": 1500,
  "tva": null
}
```

Results are merged with the Regex output. Regex-extracted values are never overwritten by the LLM.

### 6.3 Hybrid Extraction

The `HybridExtractor` orchestrates both extractors according to the following priority rule:

```
Regex > LLM
```

```python
results = regex.extract(text)
if missing_fields:
    llm_results = llm.extract(missing_fields)
    merge(results, llm_results)
```

| Criterion | Regex | LLM |
|---|---|---|
| Speed | Fast | Slower |
| Precision | High | Variable |
| Determinism | Yes | No |
| Flexibility | Low | High |
| Hallucination risk | None | Possible |
| Ideal use case | Amounts, dates, IDs | Free text, ambiguous fields |

### 6.4 Specialized Agents

Each document type is handled by a dedicated agent inheriting from `BaseAgent`.

`BaseAgent` provides:
- `process()` — full orchestration pipeline
- `extract()` — field extraction dispatch
- Utility methods and document schema

Specialized agents:

| Agent | Target Document Type |
|---|---|
| `InvoiceAgent` | Invoices (`factures`) |
| `BankAgent` | Bank statements |
| `CashAgent` | Cash receipts |

Each agent defines its own field list, Regex patterns, and normalization logic, then delegates extraction to `HybridExtractor`.

### 6.5 Document Router

`document_router.py` selects the appropriate agent based on the detected document type:

```python
agent = router.get_agent(document_type)
result = agent.process(text)
```

---

## 7. API Reference

### POST `/api/v1/upload`

Upload a document for processing.

**Request:** `multipart/form-data` with a file field.

**Response schema:**

```json
{
  "file_type": "image/jpeg",
  "quality_score": 82,
  "status": "PENDING",
  "extracted_text": "...",
  "message": "Extraction completed successfully"
}
```

**Status values:**

| Status | Meaning |
|---|---|
| `PENDING` | Extraction completed, awaiting downstream validation |
| `REJECTED` | Document rejected (quality below threshold or missing mandatory fields) |

**Example rejection response:**

```json
{
  "document_id": "71a066d2-ed37-405b-ab72-b58dab61663S",
  "status": "REJECTED",
  "rejected_at_gate": 1,
  "rejection_reason": "IMAGE_QUALITY_LOW",
  "file_type": "IMAGE_PURE",
  "quality_score": {
    "overall": 81.16,
    "sharpness": 100.0,
    "contrast": 5.8,
    "resolution": 100.0,
    "threshold": 70.0,
    "passed": false
  },
  "message": "Qualité image insuffisante: 81.16%",
  "metadata": {
    "width": 192,
    "height": 193,
    "mode": "P",
    "format": "PNG",
    "dpi": [72, 72]
  }
}
```

---

## 8. Configuration

All configurable parameters are managed through a `.env` file and loaded via `utils/config.py`.

```env
QUALITY_THRESHOLD=70
OCR_LANGUAGE=fra
```

Key parameters:

| Parameter | Description | Default |
|---|---|---|
| `QUALITY_THRESHOLD` | Minimum quality score (%) to accept a document | `70` |
| `OCR_LANGUAGE` | Language passed to pytesseract | `fra` |

---

## 9. Testing

Unit tests are located in the `tests/` directory and cover all core modules.

Run the full test suite:

```bash
python -m pytest tests/
```

Run the extraction pipeline test:

```bash
python test_extraction.py
```

The extraction test simulates a document through the full router → agent → extractor pipeline and prints the structured result.

---

## 10. Current Limitations

The following capabilities are not yet implemented in the current release (Phase 1):

- Structured extraction of business-specific fields (names, amounts, dates per document type)
- Advanced technical validation of extracted field formats
- Transmission to downstream business systems
- Full microservices architecture
- Per-document-type specialized agent coverage beyond invoices, bank statements, and cash receipts

---

## 11. Roadmap

### Phase 2 — Structured Field Extraction
- Extraction of typed fields (name, date, amount, SIRET, etc.)
- Technical validation of field formats
- Advanced data normalization

### Phase 3 — Agent Expansion and Integration
- Expanded agent coverage (HR documents, medical certificates, etc.)
- Integration with business system APIs
- Microservices architecture deployment

### Phase 4 — Performance and Scale
- Throughput optimization
- Horizontal scalability
- Observability and monitoring

---

## 12. Authors

- **ELHAJJOULI Douaa**
- **Hachim BOUBACAR MAHAMADOU**

Project developed within the context of the digital transformation of a multi-module business platform — **Smalter**.
