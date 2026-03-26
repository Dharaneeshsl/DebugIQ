import networkx as nx
from typing import List, Dict

class RootCauseAnalyzer:
    def __init__(self):
        self.graph = nx.DiGraph()

    def build_temporal_graph(self, failures: List[Dict]):
        """
        Build a temporal graph from a list of failures.
        Failures should be sorted by timestamp.
        """
        self.graph.clear()
        
        # Sort failures by timestamp
        sorted_failures = sorted(failures, key=lambda x: x.get("timestamp", ""))
        
        for i, f in enumerate(sorted_failures):
            fid = f["id"]
            self.graph.add_node(fid, module=f["module"], category=f["category"], severity=f["severity"])
            
            # Connect to previous failures within a small time window (simulated causality)
            for j in range(max(0, i-3), i):
                prev_fid = sorted_failures[j]["id"]
                self.graph.add_edge(prev_fid, fid)
                
    def analyze_root_cause(self, target_failure_id: int) -> List[Dict]:
        """
        Find potential root causes for a specific failure by traversing backwards
        in the temporal graph to find severe nodes that might have triggered it.
        """
        if target_failure_id not in self.graph:
            return []
            
        ancestors = list(nx.ancestors(self.graph, target_failure_id))
        subgraph = self.graph.subgraph(ancestors)
        
        causes = []
        for node in subgraph.nodes():
            node_data = self.graph.nodes[node]
            # Heuristic: severe errors upstream are likely root causes
            if node_data["severity"] in ["FATAL", "ERROR", "WARNING"]:
                try:
                    path_len = nx.shortest_path_length(self.graph, source=node, target=target_failure_id)
                except nx.NetworkXNoPath:
                    path_len = 999
                    
                causes.append({
                    "id": node,
                    "module": node_data["module"],
                    "category": node_data["category"],
                    "severity": node_data["severity"],
                    "distance": path_len
                })
                
        # Sort by distance (closer is often more directly causal)
        return sorted(causes, key=lambda x: x["distance"])
