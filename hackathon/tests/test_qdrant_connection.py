#!/usr/bin/env python3
"""
Qdrant smoke test:
1) Validate connection with URL/API key
2) Create a test collection with EMBEDDING_DIMENSIONS
3) Verify collection metadata
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load env files directly (without relying on shell `source` parsing).
load_dotenv(REPO_ROOT / ".env", override=False)
load_dotenv(PROJECT_ROOT / ".env", override=False)

from config.settings import settings


def _fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Qdrant connectivity + collection creation smoke test")
    parser.add_argument(
        "--collection",
        default=None,
        help="Optional collection name. Defaults to qdrant_dim_test_<dims>_<timestamp>",
    )
    args = parser.parse_args()

    qdrant_url = settings.QDRANT_URL
    qdrant_api_key = settings.QDRANT_API_KEY or None
    dimensions = int(settings.EMBEDDING_DIMENSIONS)

    if not qdrant_url:
        return _fail("QDRANT_API_URL/QDRANT_URL is not set")

    collection_name = args.collection or f"qdrant_dim_test_{dimensions}_{int(time.time())}"

    print(f"Connecting to Qdrant: {qdrant_url}")
    print(f"Using dimensions: {dimensions}")
    print(f"Target collection: {collection_name}")

    try:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=20.0)
        health = client.get_collections()
        print(f"Connection OK. Existing collections: {len(health.collections)}")
    except Exception as exc:
        return _fail(f"Connection failed: {exc}")

    try:
        exists = client.collection_exists(collection_name=collection_name)
        if not exists:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=qmodels.VectorParams(size=dimensions, distance=qmodels.Distance.COSINE),
            )
            print("Collection created.")
        else:
            print("Collection already exists, skipping create.")
    except Exception as exc:
        return _fail(f"Collection creation failed: {exc}")

    try:
        info = client.get_collection(collection_name=collection_name)
        actual_size = info.config.params.vectors.size
        actual_distance = str(info.config.params.vectors.distance)
        if actual_size != dimensions:
            return _fail(
                f"Collection exists but dimensions mismatch. Expected {dimensions}, got {actual_size}"
            )
        print(f"Collection verified. size={actual_size}, distance={actual_distance}")
    except Exception as exc:
        return _fail(f"Collection verification failed: {exc}")

    print("SUCCESS: Qdrant connection and collection setup are working.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
