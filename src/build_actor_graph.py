from __future__ import annotations

import argparse
from pathlib import Path

from wiki_graph_common import (
    WikipediaClient,
    build_actor_nodes,
    crawl_edges_for_nodes,
    log,
    save_manifest,
)


USER_AGENT = "GraphVisualizationActor/1.0 (Codex)"
SEED_CATEGORIES = [
    "Category:21世紀日本の男優",
    "Category:21世紀日本の女優",
]
ACTOR_CATEGORY_KEYWORDS = ("俳優", "男優", "女優", "子役")
CACHE_PREFIX = "actor_graph"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build actor social graph data.")
    parser.add_argument("--target-size", type=int, default=2000)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--save-every", type=int, default=100)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    data_root = project_root / "data" / "actor"
    cache_dir = data_root / "cache"
    output_dir = data_root / "outputs"

    client = WikipediaClient(cache_dir=cache_dir, user_agent=USER_AGENT, pause=0.4)
    log(f"[dataset/start] dataset=actor target_size={args.target_size}")
    nodes = build_actor_nodes(
        client=client,
        cache_prefix=CACHE_PREFIX,
        seed_categories=SEED_CATEGORIES,
        actor_category_keywords=ACTOR_CATEGORY_KEYWORDS,
        target_size=args.target_size,
    )
    log(f"[dataset/end] dataset=actor nodes={len(nodes)}")
    outgoing_links = crawl_edges_for_nodes(
        client=client,
        nodes=nodes,
        links_cache_path=cache_dir / f"{CACHE_PREFIX}_links_{args.target_size}.json",
        output_dir=output_dir,
        batch_size=args.batch_size,
        save_every=args.save_every,
        dataset_name="actor",
    )
    save_manifest(
        output_dir,
        {
            "dataset": "actor",
            "target_size": args.target_size,
            "final_node_count": len(nodes),
            "cached_source_count": len(outgoing_links),
            "outputs": ["nodes.csv", "edges.csv", "manifest.json"],
        },
    )


if __name__ == "__main__":
    main()
