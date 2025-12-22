from operator import itemgetter
from ddtrace import patch_all
patch_all(llm_providers=["langchain"])
from ddtrace import tracer
import nltk
from nltk.tokenize import word_tokenize
nltk.download('punkt')
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


def initialize_vector_store():
    
    # A. Load the Markdown File
    # This reads your 50+ policies file
    loader = UnstructuredMarkdownLoader("db/policies.md")
    raw_documents = loader.load()

    # B. Split Text into Chunks
    # We use a small chunk size (500 chars) to catch specific policy headers
    # Overlap (50 chars) ensures we don't cut a sentence in half
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", " ", ""] # Try to split by paragraphs first
    )
    documents = text_splitter.split_documents(raw_documents)
    #print(f"Split into {len(documents)} chunks.")

    # C. Initialize Embeddings (Vertex AI)
    # This converts your text chunks into number lists (vectors)
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # D. Create the Store (In-Memory)
    # This creates a search index in your RAM
    vectorstore = InMemoryVectorStore.from_documents(
        documents=documents,
        embedding=embeddings
    )
    return vectorstore


# Define the RAG Chain
def format_docs(docs):
    # Helper to join the retrieved chunks into one string
    content = "\n\n".join(doc.page_content for doc in docs)
    tokens = word_tokenize(content)
    current_span = tracer.current_span()
    if current_span:
        current_span.set_metric("rag.context_size", len(tokens))
    return "\n\n".join(doc.page_content for doc in docs)

def get_rag_chain(retriever, model, prompt):
    rag_chain = (
    {"context": itemgetter("question") | retriever | format_docs, "question": itemgetter("question")}
    | prompt
    | model
    )
    return rag_chain