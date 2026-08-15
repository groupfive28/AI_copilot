"""
embedding.py
------------
Similarity computation between two face embeddings.

ArcFace embeddings from InsightFace are L2-normalised, so cosine similarity
reduces to a simple dot product. Kept as an explicit cosine function anyway
so the pipeline stays correct even if a future model isn't pre-normalised.
"""

import numpy as np


def cosine_similarity(embedding_a: np.ndarray, embedding_b: np.ndarray) -> float:
    if embedding_a is None or embedding_b is None:
        raise ValueError("Cannot compute similarity: one or both embeddings are None")

    a = embedding_a / (np.linalg.norm(embedding_a) + 1e-10)
    b = embedding_b / (np.linalg.norm(embedding_b) + 1e-10)
    return float(np.dot(a, b))
