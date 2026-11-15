from typing import Dict, List, Tuple
import numpy as np
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA


def cluster_embeddings(embeddings: np.ndarray) -> Tuple[List[int], List[Dict]]:
    if len(embeddings) == 0:
        return [], []

    dbscan = DBSCAN(eps=0.3, min_samples=2, metric="cosine")
    labels = dbscan.fit_predict(embeddings)

    noise_ratio = float(np.sum(labels == -1)) / len(labels)
    if noise_ratio > 0.5:
        k = min(5, len(np.unique(embeddings, axis=0)))
        kmeans = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = kmeans.fit_predict(embeddings)

    dimensions = min(2, *embeddings.shape)
    if len(embeddings) == 1 or np.allclose(embeddings, embeddings[0]):
        coords = np.zeros((len(embeddings), 2))
    else:
        projected = PCA(n_components=dimensions).fit_transform(embeddings)
        coords = np.pad(projected, ((0, 0), (0, 2 - dimensions)))

    points = []
    for idx, (x, y) in enumerate(coords):
        points.append({
            "failure_id": idx,
            "x": float(x),
            "y": float(y),
            "cluster_id": int(labels[idx]),
        })

    return [int(l) for l in labels], points
