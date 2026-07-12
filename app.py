import os
import warnings

warnings.filterwarnings(
    "ignore",
    message=r"`langchain-community` is being sunset.*",
    category=DeprecationWarning,
)

os.environ.setdefault("USER_AGENT", "rag-chatbot/0.1")

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader, UnstructuredMarkdownLoader
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openrouter import ChatOpenRouter
from langchain_community.document_loaders import CSVLoader


try:
    from langchain_classic.chains.combine_documents import create_stuff_documents_chain
    from langchain_classic.chains.retrieval import create_retrieval_chain
    from langchain_classic.chains.history_aware_retriever import create_history_aware_retriever
except ImportError:
    from langchain.chains.combine_documents import create_stuff_documents_chain
    from langchain.chains.retrieval import create_retrieval_chain
    from langchain.chains.history_aware_retriever import create_history_aware_retriever

# Load environment variables
load_dotenv()

# --- Step 1: Initialize LLM and Embeddings ---

def get_llm(provider="groq"):
    """Return a chat model based on the specified provider."""
    if provider == "openrouter":
        return ChatOpenRouter(
            model="meta-llama/llama-3.3-70b-instruct",
            temperature=0,
        )
    else:
        return ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0,
            max_tokens=1024,
        )

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


# --- Step 2: Load Documents from Multiple Sources ---

def load_documents():
    all_docs = []

    # Load PDF
    pdf_path = "./docs/sample.pdf"
    if os.path.exists(pdf_path):
        pdf_loader = PyPDFLoader(pdf_path)
        pdf_docs = pdf_loader.load()
        for doc in pdf_docs:
            doc.metadata["source_type"] = "pdf"
        all_docs.extend(pdf_docs)
        print(f"Loaded {len(pdf_docs)} document(s) from PDF")

    # Load Web Page
    web_url = "https://python.langchain.com/docs/concepts/retrieval/"
    web_loader = WebBaseLoader(web_url)
    web_docs = web_loader.load()
    for doc in web_docs:
        doc.metadata["source_type"] = "web"
    all_docs.extend(web_docs)
    print(f"Loaded {len(web_docs)} document(s) from web")

    # Load Markdown
    md_path = "./docs/sample.md"
    if os.path.exists(md_path):
        md_loader = UnstructuredMarkdownLoader(md_path, mode="single", strategy="fast")
        md_docs = md_loader.load()
        for doc in md_docs:
            doc.metadata["source_type"] = "markdown"
        all_docs.extend(md_docs)
        print(f"Loaded {len(md_docs)} document(s) from markdown")

    csv_path = "./docs/data.csv"
    if os.path.exists(csv_path):
        csv_loader = CSVLoader(file_path=csv_path)
        csv_docs = csv_loader.load()
        for doc in csv_docs:
            doc.metadata["source_type"] = "csv"
        all_docs.extend(csv_docs)
        print(f"Loaded {len(csv_docs)} document(s) from CSV")

    return all_docs


def create_vector_store(documents):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split into {len(chunks)} chunks")
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory="./chroma_db",
        collection_name="multi_source_rag",
    )
    print("Vector store created and persisted to ./chroma_db")
    return vector_store


# --- Step 4: Build Conversational RAG Chain ---

def build_rag_chain(vector_store, llm):
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})

    # Prompt for contextualizing the question based on chat history
    contextualize_q_prompt = ChatPromptTemplate.from_messages([
        ("system", 
         "Given a chat history and the latest user question which might "
         "reference context in the chat history, formulate a standalone "
         "question which can be understood without the chat history. "
         "Do NOT answer the question, just reformulate it if needed and "
         "otherwise return it as is."),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    # Prompt for answering questions with retrieved context
    qa_prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a helpful assistant that answers questions based on the "
         "provided context. Use the following pieces of retrieved context to "
         "answer the question. If you don't know the answer or the context "
         "doesn't contain relevant information, say that you don't know. "
         "Always cite which source document your answer came from.\n\n"
         "Context:\n{context}"),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )

    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

        # Add message history
    store = {}

    def get_session_history(session_id: str) -> BaseChatMessageHistory:
        if session_id not in store:
            store[session_id] = ChatMessageHistory()
        return store[session_id]

    conversational_rag_chain = RunnableWithMessageHistory(
        rag_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="answer",
    )

    return conversational_rag_chain

# --- Step 5: Interactive Chat Interface ---

def format_sources(source_docs):
    if not source_docs:
        return "No sources found."
    sources = []
    for i, doc in enumerate(source_docs, 1):
        # Extract metadata fields for display
        source_type = doc.metadata.get("source_type", "unknown")
        source = doc.metadata.get("source", "unknown")
        # Show first 100 characters as a preview snippet
        snippet = doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
        sources.append(f"  [{i}] ({source_type}) {source}\n      \"{snippet}\"")
    return "\n".join(sources)

def chat():
    print("Loading documents...")
    documents = load_documents()

    if not documents:
        print("No documents loaded. Please add files to the docs/ folder.")
        return

    print("\nBuilding vector store...")
    vector_store = create_vector_store(documents)

    current_provider = "groq"
    llm = get_llm(current_provider)

    print("\nBuilding RAG chain...")
    chain = build_rag_chain(vector_store, llm)

    # Use a fixed session ID so chat history persists within this run
    session_id = "default_session"

    print("\n" + "=" * 50)
    print("Multi-Source RAG Chatbot Ready!")
    print("Ask questions about your documents.")
    print("Type 'quit' to exit.")
    print("=" * 50 + "\n")
    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        # Inside your chat loop, add this before the main chain.invoke() call:
        if user_input.lower() == "/switch":
            current_provider = "openrouter" if current_provider == "groq" else "groq"
            llm = get_llm(current_provider)
            chain = build_rag_chain(vector_store, llm)
            print(f"Switched to {current_provider}")
            continue
        # Invoke the chain with session config for message history
        response = chain.invoke(
            {"input": user_input},
            config={"configurable": {"session_id": session_id}},
        )

        print(f"\nAssistant: {response['answer']}")
        print(f"\nSources:")
        print(format_sources(response.get("context", [])))
        print()

if __name__ == "__main__":
    chat()