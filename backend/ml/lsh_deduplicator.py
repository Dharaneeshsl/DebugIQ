from datasketch import MinHash, MinHashLSH
import re
from typing import List, Tuple

def get_shingles(text: str, k=3) -> set:
    """Generate basic character/word n-grams"""
    words = re.sub(r'[^A-Za-z0-9]', ' ', text).lower().split()
    if len(words) < k:
        return set(words)
    res = []
    for i in range(len(words) - k + 1):
        chunk = []
        for j in range(k):
            chunk.append(words[i + j])
        res.append(' '.join(chunk))
    return set(res)

class FastDeduplicator:
    def __init__(self, threshold=0.8, num_perm=128):
        # We use MinHash LSH for extremely fast deduplication for large logs
        self.lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self.minhashes = {}
        self.next_id = 1
        self.num_perm = num_perm

    def _create_minhash(self, text: str) -> MinHash:
        m = MinHash(num_perm=self.num_perm)
        for d in get_shingles(text):
            m.update(d.encode('utf8'))
        return m

    def process_logs(self, logs: List[str]) -> Tuple[List[int], List[bool]]:
        """
        Process logs using LSH and return unique IDs and duplicate flags.
        For production load, this avoids the O(n^2) cosine similarity bottleneck.
        """
        unique_ids = []
        is_duplicate = []

        for log in logs:
            m = self._create_minhash(log)
            # Query the LSH
            result = self.lsh.query(m)
            if not result:
                # No duplicates found, insert this
                new_key = f"failure_{self.next_id}"
                self.lsh.insert(new_key, m)
                self.minhashes[new_key] = m
                unique_ids.append(self.next_id)
                is_duplicate.append(False)
                self.next_id += 1
            else:
                # Found a potential duplicate, map to its ID
                # Re-extract the original ID
                existing_key = result[0]
                existing_id = int(existing_key.split('_')[1])
                unique_ids.append(existing_id)
                is_duplicate.append(True)
                
        return unique_ids, is_duplicate
