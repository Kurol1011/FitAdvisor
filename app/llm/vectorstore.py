from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.document_loaders import TextLoader
from langchain.docstore.document import Document
import os

EMBED_MODEL = 'text-embedding-3-small'

def build_faiss_index(docs_folder: str = 'data/docs'):
    loader = TextLoader(docs_folder)
    docs = loader.load()
    embedder = OpenAIEmbeddings()
    index = FAISS.from_documents(docs, embedder)
    index.save_local('faiss_index')
    return index

def get_retriever():
    try:
        embedder = OpenAIEmbeddings()
        index = FAISS.load_local('faiss_index', embedder)
        return index.as_retriever(search_kwargs={'k': 6})
    except Exception as e:
        raise RuntimeError('Не найден индекс. Постройте индекс с помощью build_faiss_index')