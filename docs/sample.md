# LangChain Overview

LangChain is a framework for developing applications powered by large language models (LLMs).

## Key Features

- **Document Loaders**: Load data from various sources including PDFs, web pages, databases, and APIs.
- **Text Splitters**: Break large documents into smaller chunks optimized for embedding and retrieval.
- **Vector Stores**: Store and search document embeddings using databases like Chroma, Pinecone, or FAISS.
- **Chains**: Compose multiple LLM calls and tools into reusable workflows.
- **Agents**: Create autonomous systems that can use tools and make decisions.

## Use Cases

LangChain is commonly used for:
1. Question answering over documents (RAG)
2. Chatbots with memory
3. Summarization pipelines
4. Data extraction from unstructured text

## Architecture

A typical LangChain RAG application follows this flow:
Documents -> Loader -> Splitter -> Embeddings -> Vector Store -> Retriever -> LLM -> Answer