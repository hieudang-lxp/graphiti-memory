import os

from dotenv import load_dotenv

from graphiti_core import Graphiti
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")

LLM_MODEL = os.environ.get("LLM_MODEL", "hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "hf.co/nomic-ai/nomic-embed-text-v1.5-GGUF:Q4_K_M")
EMBED_DIM = int(os.environ.get("EMBED_DIM", "768"))

os.environ.setdefault("SEMAPHORE_LIMIT", "1")


def build_graphiti() -> Graphiti:
    llm_config = LLMConfig(
        api_key="ollama",
        model=LLM_MODEL,
        small_model=LLM_MODEL,
        base_url=OLLAMA_BASE_URL,
    )

    llm_client = OpenAIGenericClient(config=llm_config)

    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key="ollama",
            embedding_model=EMBED_MODEL,
            embedding_dim=EMBED_DIM,
            base_url=OLLAMA_BASE_URL,
        )
    )

    cross_encoder = OpenAIRerankerClient(client=llm_client, config=llm_config)

    return Graphiti(
        NEO4J_URI,
        NEO4J_USER,
        NEO4J_PASSWORD,
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=cross_encoder,
    )
