# 🧬 ChromoGen — 3D Chromatin Structure & Clinical Variant Analysis Platform

## 📌 Overview

ChromoGen is a Django-based bioinformatics web application built for deployment at a medical center. It takes a patient's DNA (FASTA) sequence, locates it on the reference genome, and runs a full clinical analysis pipeline against a healthy control sequence — covering nucleotide-level variant detection, protein-level mutation classification, chromatin accessibility (DNase), Hi-C contact prediction, and 3D chromatin structure reconstruction. Results are compiled into an AI-formatted clinical PDF report.

The system was redirected during development — on request of the medical center — from a pure chromatin-visualization tool toward protein-level clinical variant analysis, with chromatin structure kept as a secondary, complementary layer.

This repository is also the practical basis of an Arabic graduation thesis (Faculty of Information Technology Engineering).

## 🚀 Key Features

- **Sequence localization** — locates an uploaded patient FASTA sequence on the reference genome (chromosome, coordinates, strand) using a lightweight seed-and-extend algorithm (no external aligner binary required).
- **Nucleotide-level variant detection** — direct sequence diff (SNPs, insertions, deletions) between patient and reference.
- **Gene/transcript resolution** — GENCODE GTF-based lookup of intersecting genes, MANE_Select/Ensembl_canonical transcript selection, CDS splicing per gene.
- **Protein-level mutation classification** — translation + codon-by-codon comparison (silent / missense / nonsense / frameshift), including Grantham distance/severity scoring per substitution.
- **Chromatin accessibility (DNase)** — Basset deep-learning model predicts per-base accessibility for patient and control; peak calling and open/closed region diffing.
- **Hi-C contact map prediction** — ChromoGen Transformer+RoPE model predicts contact matrices from sequence + DNase signal, with windowing/merging for regions longer than the model's input size.
- **3D structure reconstruction** — MDS-based reconstruction from predicted Hi-C matrices into smoothed 3D coordinates, with TAD boundary detection and a nucleosome-level (~200bp) accessibility track layered on top.
- **AI clinical report generation** — an LLM (via Hugging Face Inference API) reformats the deterministic pipeline output into a structured clinical report; the LLM is strictly prompted to reformat only and never invent gene names, codon numbers, or numeric values. Falls back to a deterministic Markdown template if the API is unavailable.
- **Protein name lookup** — batch UniProt REST API lookup for gene-to-protein-name resolution.
- **PDF export** — clinical reports exported as polished PDFs via WeasyPrint.
- **Robust background processing** — Celery-based async pipeline with cooperative cancellation, a watchdog that detects and recovers from stale/stuck tasks, and incremental per-step database saves so progress is visible even mid-run.
- **3D visualization frontend** — Three.js-based viewer for the reconstructed chromatin structure (developed by a collaborator).

## 🏗️ Architecture

ChromoGen is built as a **modular monolith** (not microservices) — a single Django deployment with clearly separated internal service modules, designed for simple single-admin deployment at a medical center on a local Windows machine.

**Pipeline execution order:**

```
0. DNA_locator        → locate patient sequence on reference genome
2. gtf_index           → find intersecting genes + representative transcripts
1. fetcher              → fetch matching reference (control) sequence
3. sequence_diff        → nucleotide-level variant detection
4-6. per gene: splicer → translator → mutation_classifier
7. DNase prediction (patient + control)          [Basset]
8. DNase diff (open/closed region comparison)
9. Hi-C prediction (patient + control)           [ChromoGen Transformer+RoPE]
10. 3D coordinates + nucleosome track
11. Hi-C/structural diff
12. Motif/regulatory-binding analysis            [currently disabled]
13. Report payload assembly → async LLM report generation
```

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6.0.5, Django REST Framework |
| Database | SQLite |
| Async tasks | Celery (`--pool=solo` on Windows), Memurai (Redis-compatible, port 6378) |
| Production server | Waitress |
| AI/ML | PyTorch — Basset (DNase accessibility), ChromoGen Transformer+RoPE (Hi-C) |
| External APIs | Hugging Face Inference API (LLM reports — DeepSeek-V3 primary, Llama-3.3-70B-Instruct fallback), UniProt REST API |
| Numerics | NumPy, SciPy (MDS, k-mer indexing) |
| PDF generation | WeasyPrint + Markdown |
| Frontend | Plain HTML/CSS/JS served via Django + Whitenoise, Three.js (3D viewer) |
| Genome I/O | pyfaidx |

## 📁 Repository Layout (key paths)

```
project_root/
├── start_windows.bat        # one-click launcher (Memurai check, Celery, watchdog, Waitress)
├── .env                      # environment variables (HF_TOKEN, DB, etc.)
└── backend/
    ├── manage.py
    ├── .env/                 # Python virtual environment (not "venv")
    ├── core/                 # Django project settings, celery.py, urls.py
    ├── apps/
    │   ├── patients/
    │   ├── genomics/         # InputData/OutputData/GeneProteinResult, pipeline trigger views, tasks
    │   └── reports/          # AnalysisReport, PDF export
    ├── services/genomics/    # pipeline_manager.py + all pipeline step modules
    └── ai_engine/models/     # Basset weights, ChromoGen Hi-C model, LLM report generator
```

## 📖 Getting Started (Windows)

### 1. Clone the repository

```bash
git clone https://github.com/YourUsername/ChromoGen.git
cd ChromoGen
```

### 2. Create the virtual environment

The project's virtual environment lives **inside `backend/`** and is named `.env` (not the conventional `venv`):

```bash
cd backend
python -m venv .env
.env\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file at the **project root** (not inside `backend/`) with at least:

```
SECRET_KEY=your-django-secret-key
DEBUG=True
HF_TOKEN=your-huggingface-inference-api-token
HF_MODEL_PRIMARY=deepseek-ai/DeepSeek-V3
HF_MODEL_FALLBACK=meta-llama/Llama-3.3-70B-Instruct
CELERY_BROKER_URL=redis://localhost:6378/0
CELERY_RESULT_BACKEND=redis://localhost:6378/0
```

### 5. Genome reference & annotation

Place the reference genome FASTA (with its `.fai` index) and the GENCODE GTF annotation under the configured `GENOME_REFERENCE_ROOT` (see `core/settings.py`):

```
genome_reference/
├── genome.fa
├── genome.fa.fai
└── gencode.v50.basic.annotation.gtf.gz
```

The GTF index and k-mer chromosome indexes are built automatically on first use and cached to disk for subsequent runs.

### 6. Database setup

```bash
cd backend
python manage.py makemigrations
python manage.py migrate
```

### 7. Install and start Memurai (Redis-compatible broker)

Memurai must be installed and running as a Windows service on port `6378` before starting Celery.

### 8. Run the project

The recommended way is via the bundled launcher, which starts Memurai (if needed), the Celery worker, the stale-task watchdog, and the Waitress production server together:

```bat
start_windows.bat
```

Alternatively, for development, run each component manually:

```bash
# Terminal 1 — Celery worker (Windows requires --pool=solo)
celery -A core worker --loglevel=info --pool=solo

# Terminal 2 — Django dev server
python manage.py runserver
```

## 🧪 Validated Test Case

The pipeline has been validated end-to-end against the **HBB gene / rs334 (sickle-cell) mutation**: E6V (GAG→GTG), genomic position `chr11:5227002`. Note the codon numbering distinction — HGVS numbering counts the initiator Met as codon 1 (`c.20A>T`, codon 7), while traditional clinical nomenclature excludes it (hence "E6V" / "Glu6Val").

## ⚠️ Current Limitations

- Motif/regulatory-protein binding analysis (`_step_motifs`) is currently **disabled** and returns an empty result — pending re-integration.
- Chromosome LRU caching and parallel Celery task paths (protein branch | DNase→Hi-C branch) have been designed but are **not yet applied** to the pipeline.
- Hi-C/structural diffing between patient and control is currently a shallow statistical comparison (stress, TAD count, collapse ratio) rather than a true structural distance metric (e.g., RMSD).

## 📄 License

Academic graduation project — Faculty of Information Technology Engineering, Damascus University.