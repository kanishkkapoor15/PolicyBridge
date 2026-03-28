# PolicyBridge

Full-stack agentic compliance conversion platform for migrating company policies to Irish & EU law compliance.

## Architecture

- **Backend**: Python, FastAPI, LangGraph (multi-agent orchestration), ChromaDB (RAG)
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS
- **LLM**: Tensorix API (DeepSeek R1 for reasoning, DeepSeek Chat v3.1 for conversation)

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- Tensorix API key

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export TENSORIX_API_KEY=your_key
python main.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Docker
```bash
cp .env.example .env
# Edit .env with your API key
docker-compose up
```

## Project Structure

```
├── backend/
│   ├── agents/          # LangGraph agent implementations
│   ├── graph/           # Workflow definition and state schema
│   ├── knowledge_base/  # Irish/EU legal corpus (markdown)
│   ├── rag/             # ChromaDB + embeddings
│   ├── api/             # FastAPI routes
│   ├── models/          # Pydantic models
│   └── utils/           # Document parsing, diff, export
├── frontend/
│   ├── app/             # Next.js App Router pages
│   ├── components/      # React components
│   └── lib/             # API client, types
└── docker-compose.yml
```

## Implementation Status

- [x] Step 1: Project scaffolding
- [x] Step 2: Knowledge base
- [ ] Step 3: RAG pipeline
- [ ] Step 4: LangGraph workflow
- [ ] Step 5: Agent implementations
- [ ] Step 6: FastAPI routes
- [ ] Step 7: Frontend UI
- [ ] Step 8: Docker integration
