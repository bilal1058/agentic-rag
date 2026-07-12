# RAG Chatbot

A simple conversational RAG chatbot built with Python, LangChain, Groq, and OpenRouter.

## Features

- Loads documents from multiple sources
  - PDF
  - Web page
  - Markdown
  - CSV
- Splits documents into chunks
- Creates and persists a Chroma vector store
- Supports provider switching between Groq and OpenRouter
- Interactive chat loop with source citations

## Project Structure

- `app.py` – main application logic
- `requirements.txt` – Python dependencies
- `docs/` – sample input documents
- `.env.example` – environment variable template
- `.gitignore` – repository ignore rules

## Setup

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. Copy `.env.example` to `.env` and fill in your keys.

## Environment Variables

Create a `.env` file with values similar to:

```env
GROQ_API_KEY=your_groq_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
HF_TOKEN=your_huggingface_token_here
USER_AGENT=rag-chatbot/0.1
```

## Run

```powershell
python app.py
```

## Notes

- The app uses the local `docs/` folder for sample data.
- The vector database is stored in `./chroma_db`.
- Use `/switch` in the interactive chat to toggle between Groq and OpenRouter providers.
