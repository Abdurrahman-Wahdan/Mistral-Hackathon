"""
Simplified Qwen3-Embedding-8B implementation for LangChain.

Clean, straightforward implementation without complex base classes.
Optimized for Apple Silicon (MPS) and compatible with LangChain Embeddings interface.
"""

import torch
import logging
import warnings
from typing import List
from sentence_transformers import SentenceTransformer
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", message=".*torch.utils.checkpoint.*")


class Qwen3Embedding(Embeddings):
    """
    Qwen3-Embedding-8B model for semantic embeddings.

    Args:
        model_name: Model identifier (default: "qwen3-8b")
        device: Device to use ("auto", "mps", "cpu")
        batch_size: Batch size for encoding (default: 16)
        normalize_embeddings: Whether to L2 normalize (default: True)
        max_tokens: Max sequence length (default: 32768)
        dimensions: Expected embedding dimensions (default: 4096)
    """

    def __init__(
        self,
        model_name: str = "qwen3-8b",
        device: str = "auto",
        batch_size: int = 16,
        normalize_embeddings: bool = True,
        max_tokens: int = 32768,
        dimensions: int = 4096,
        **kwargs
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self.max_tokens = max_tokens
        self.dimensions = dimensions
        self.device = self._determine_device(device)
        self.model_id = "Qwen/Qwen3-Embedding-8B"
        self._model: SentenceTransformer = None

        logger.info(f"Initialized Qwen3Embedding on device: {self.device}")

    def _determine_device(self, device_config: str) -> str:
        """Determine the best available device."""
        if device_config == "auto":
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                logger.info("Using MPS (Apple Silicon GPU)")
                return "mps"
            else:
                logger.info("Using CPU")
                return "cpu"
        else:
            return device_config

    def _load_model(self) -> None:
        """Lazy load the model on first use."""
        if self._model is not None:
            return

        logger.info(f"Loading {self.model_id} on {self.device}...")

        try:
            self._model = SentenceTransformer(
                self.model_id,
                device=self.device,
                trust_remote_code=True,
            )
            self._model.max_seq_length = self.max_tokens
            logger.info(f"Successfully loaded {self.model_id}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise RuntimeError(f"Could not load {self.model_id}: {e}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        if not texts:
            return []

        self._load_model()

        try:
            with torch.no_grad():
                embeddings = self._model.encode(
                    texts,
                    batch_size=self.batch_size,
                    convert_to_tensor=True,
                    normalize_embeddings=self.normalize_embeddings,
                    show_progress_bar=False,
                )

                if embeddings.device.type != "cpu":
                    embeddings = embeddings.cpu()

                return embeddings.tolist()

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise RuntimeError(f"Failed to generate embeddings: {e}")

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text."""
        embeddings = self.embed_documents([text])
        return embeddings[0] if embeddings else []

    def __repr__(self) -> str:
        return f"Qwen3Embedding(device={self.device}, dims={self.dimensions})"
