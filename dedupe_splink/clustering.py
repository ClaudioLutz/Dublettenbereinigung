import networkx as nx
import pandas as pd

def cluster_edges(edges_df: pd.DataFrame, id_col_l: str = "unique_id_l", id_col_r: str = "unique_id_r") -> pd.DataFrame:
    """
    Cluster edges using Connected Components (Union-Find) via NetworkX.
    Returns a DataFrame mapping unique_id -> cluster_id.
    """
    if edges_df.empty:
        return pd.DataFrame(columns=["unique_id", "cluster_id"])

    # Create graph
    G = nx.from_pandas_edgelist(edges_df, source=id_col_l, target=id_col_r)

    # Connected components
    # nx.connected_components returns a generator of sets
    components = list(nx.connected_components(G))

    # Map to dataframe
    # We want stability? Connected components are deterministic for a given set of edges.
    # To make cluster_id stable-ish, we can use the min(unique_id) as the cluster_id,
    # or just enumerate.
    # User asked for "stable cluster_id (duplicate groups)".
    # Usually this means if I run it again on same data, I get same IDs?
    # Or if I add data, existing IDs don't change much?
    # Min ID is a good proxy for stability if IDs are stable.

    cluster_map = []
    for i, comp in enumerate(components):
        # Sort component to find min ID
        comp_list = sorted(list(comp))
        cluster_id = comp_list[0] # Use min ID as cluster ID
        for node in comp_list:
            cluster_map.append({"unique_id": node, "cluster_id": cluster_id})

    return pd.DataFrame(cluster_map)
