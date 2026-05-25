# RoadLawQA

RoadLawQA is a CS529 course project at the University of Information Technology (UIT). The system answers Vietnamese road-law questions using a Retrieval-Augmented Generation (RAG) pipeline over selected legal documents about road traffic, road infrastructure, and traffic penalties.

This is a group project. The core technical work in this repository focuses on data processing, hybrid retrieval, reranking, answer generation, quiz generation, and the Streamlit application.

## Demo

Demo materials: [Google Drive folder](https://drive.google.com/drive/u/0/folders/1EvIlpftgOCiCtmg6J0KFYhahq10RMEVm)

## Project Scope

RoadLawQA is designed for Vietnamese legal QA in the road-traffic domain. Given a user question, the system retrieves relevant legal chunks, reranks them, and generates an answer with legal-source citations.

Main supported documents:

- `Nghị định số 168/2024/NĐ-CP`
- `Luật số 36/2024/QH15`
- `Luật số 35/2024/QH15`

## System Features

- Answer Vietnamese road-law questions with retrieved legal citations.
- Retrieve relevant clauses using hybrid keyword and semantic search.
- Generate multiple-choice quizzes from selected legal topics.
- Provide a Streamlit demo interface for QA and quiz generation.
- Support CLI scripts for data processing, indexing, retrieval testing, QA, and quiz generation.

## Tech Stack

- **Core language:** Python
- **Interface:** Streamlit
- **Retrieval:** BM25, dense embeddings, Weaviate
- **Models:** `Alibaba-NLP/gte-multilingual-base`, `BAAI/bge-reranker-v2-m3`, Gemini 2.5 Flash
- **Infrastructure:** Docker Compose

## Methodology / Workflow

1. Parse raw legal documents into structured chunks by article, clause, point, and bullet.
2. Enrich each chunk with legal hierarchy and citation metadata.
3. Build a Weaviate index with dense embeddings and BM25-searchable fields.
4. Retrieve candidates with hybrid search, rerank them, and pass the top chunks to Gemini.
5. Generate cited answers or topic-based multiple-choice quizzes.

## Results

The implemented system demonstrates:

- end-to-end Vietnamese road-law QA;
- hybrid retrieval with legal-source citation tracking;
- Streamlit chat interface for question answering;
- topic-based multiple-choice quiz generation;
- command-line scripts for retrieval testing, QA, and quiz generation.

Formal benchmark results are not included yet. Current evaluation is based on functional testing, manual QA checks, and course demo usage.

## Repository Structure

```text
RoadLawQA/
├── backend/
│   ├── build_index.py          # Build the Weaviate index
│   ├── clean_and_split.py      # Parse and chunk legal documents
│   ├── generator.py            # Gemini answer and quiz generation
│   ├── prompts.py              # Prompt templates
│   ├── rag_qa.py               # QA entry point
│   ├── rag_quiz.py             # Quiz CLI
│   ├── retriever_custom.py     # Hybrid retrieval and reranking
│   └── test_retriever.py       # Retriever smoke test
├── data/
│   ├── raw/                    # Raw legal text files
│   └── processed/              # Processed JSON chunks
├── docker/
│   └── docker-compose.yml      # Local Weaviate service
├── frontend/
│   ├── app.py                  # Streamlit application
│   └── assets/                 # UI images
├── .env.example                # Environment variable template
├── .gitignore
├── requirements.txt
└── README.md
```

## Setup

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Set your Gemini API key in `.env`:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. Start Weaviate

```bash
docker compose -f docker/docker-compose.yml up -d
```

For older Docker Compose installations:

```bash
docker-compose -f docker/docker-compose.yml up -d
```

### 5. Process data and build the index

```bash
python backend/clean_and_split.py
python backend/build_index.py
```

### 6. Run the application

Streamlit UI:

```bash
streamlit run frontend/app.py
```

CLI QA:

```bash
python backend/rag_qa.py
```

Quiz generation:

```bash
python backend/rag_quiz.py
```

Retriever test:

```bash
python backend/test_retriever.py
```



## Credits

This repository is for the CS529 group project at UIT.

- **Nguyen Thanh Tung:** implemented the core RAG pipeline, data processing, hybrid retrieval, reranking, answer generation, evaluation.
- **Team members:** contributed to benchmark creation, quiz generation, demo web app development.

## References

- [Weaviate Documentation](https://weaviate.io/developers/weaviate)
- [Gemini API Documentation](https://ai.google.dev/gemini-api/docs)
- [Alibaba-NLP/gte-multilingual-base](https://huggingface.co/Alibaba-NLP/gte-multilingual-base)
- [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)
