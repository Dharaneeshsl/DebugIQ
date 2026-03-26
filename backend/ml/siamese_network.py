import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from typing import List

class ContrastiveLoss(nn.Module):
    def __init__(self, margin=1.0):
        super(ContrastiveLoss, self).__init__()
        self.margin = margin

    def forward(self, embedding1, embedding2, label):
        # label: 1 if similar, 0 if dissimilar
        euclidean_distance = nn.functional.pairwise_distance(embedding1, embedding2, keepdim=True)
        loss_contrastive = torch.mean((label) * torch.pow(euclidean_distance, 2) +
                                      (1 - label) * torch.pow(torch.clamp(self.margin - euclidean_distance, min=0.0), 2))
        return loss_contrastive

class SiameseNetwork(nn.Module):
    def __init__(self, input_dim=768, hidden_dim=256):
        super(SiameseNetwork, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_dim, int(hidden_dim/2))

    def forward_once(self, x):
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x

    def forward(self, input1, input2):
        output1 = self.forward_once(input1)
        output2 = self.forward_once(input2)
        return output1, output2

class DummyDataset(Dataset):
    def __init__(self, num_samples=100, input_dim=768):
        self.data1 = torch.randn(num_samples, input_dim)
        self.data2 = torch.randn(num_samples, input_dim)
        self.labels = torch.randint(0, 2, (num_samples, 1), dtype=torch.float32)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.data1[idx], self.data2[idx], self.labels[idx]

def train_simclr_stub(epochs=2):
    """
    Stub for a training pipeline using the contrastive Siamese network.
    Useful for offline training when deploying to production.
    """
    dataset = DummyDataset()
    dataloader = DataLoader(dataset, batch_size=16, shuffle=True)
    
    model = SiameseNetwork(input_dim=768)
    criterion = ContrastiveLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    model.train()
    for epoch in range(epochs):
        for data1, data2, label in dataloader:
            optimizer.zero_grad()
            output1, output2 = model(data1, data2)
            loss = criterion(output1, output2, label)
            loss.backward()
            optimizer.step()
        print(f"Epoch {epoch+1} finished. Last custom loss: {loss.item()}")
    return model

if __name__ == "__main__":
    train_simclr_stub()
