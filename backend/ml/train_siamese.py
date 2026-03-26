"""
Minimal training pipeline for Siamese contrastive model.
Uses synthetic pairs built from message templates to illustrate the workflow.
"""
from typing import List, Tuple
import random

import torch
from torch.utils.data import DataLoader, Dataset

from nlp.embeddings import generate_embeddings
from ml.siamese_network import SiameseNetwork, ContrastiveLoss


TEMPLATES = {
    "timeout": [
        "timeout waiting for response",
        "no response from slave",
        "request timed out",
    ],
    "protocol": [
        "protocol violation invalid handshake",
        "axi ordering violated",
        "invalid state transition detected",
    ],
    "mismatch": [
        "data mismatch expected value",
        "compare fail mismatch detected",
        "scoreboard mismatch",
    ],
}


def _build_pairs(num_pairs: int = 200) -> Tuple[List[str], List[str], List[int]]:
    left = []
    right = []
    labels = []
    keys = list(TEMPLATES.keys())
    for _ in range(num_pairs):
        if random.random() < 0.5:
            key = random.choice(keys)
            a = random.choice(TEMPLATES[key])
            b = random.choice(TEMPLATES[key])
            label = 1
        else:
            k1, k2 = random.sample(keys, 2)
            a = random.choice(TEMPLATES[k1])
            b = random.choice(TEMPLATES[k2])
            label = 0
        left.append(a)
        right.append(b)
        labels.append(label)
    return left, right, labels


class PairDataset(Dataset):
    def __init__(self, left: List[str], right: List[str], labels: List[int]):
        self.left = left
        self.right = right
        self.labels = labels

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int):
        return self.left[idx], self.right[idx], self.labels[idx]


def train(epochs: int = 3, batch_size: int = 16):
    left, right, labels = _build_pairs()
    dataset = PairDataset(left, right, labels)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    model = SiameseNetwork(input_dim=768)
    criterion = ContrastiveLoss(margin=1.0)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    model.train()
    for epoch in range(epochs):
        epoch_loss = 0.0
        for l_text, r_text, lbl in loader:
            emb_l = generate_embeddings(list(l_text))
            emb_r = generate_embeddings(list(r_text))
            emb_l = torch.tensor(emb_l, dtype=torch.float32)
            emb_r = torch.tensor(emb_r, dtype=torch.float32)
            lbl_t = torch.tensor(lbl, dtype=torch.float32).view(-1, 1)

            optimizer.zero_grad()
            out1, out2 = model(emb_l, emb_r)
            loss = criterion(out1, out2, lbl_t)
            loss.backward()
            optimizer.step()
            epoch_loss += float(loss.item())
        print(f"Epoch {epoch+1}: loss={epoch_loss:.4f}")

    return model


if __name__ == "__main__":
    train()
