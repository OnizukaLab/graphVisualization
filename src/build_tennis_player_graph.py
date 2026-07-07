from __future__ import annotations

import argparse
from pathlib import Path

from wiki_graph_common import (
    WikipediaClient,
    build_list_section_nodes,
    crawl_edges_for_nodes,
    save_manifest,
)


USER_AGENT = "GraphVisualizationTennisPlayer/1.0 (Codex)"
API_URL = "https://en.wikipedia.org/w/api.php"
LIST_PAGE_TITLE = "List of male singles tennis players"
LIST_SECTION_MARKER = "== List =="
CATEGORY_KEYWORDS = (
    "male tennis players",
    "men's singles tennis players",
)
EXCLUDED_TITLES = {
    "Association of Tennis Professionals",
    "ATP Tour",
    "ATP rankings",
    "A. Wallis Myers",
    "Grand Slam",
    "Olympic Games",
    "Year-end championships",
    "List of male singles tennis players",
}
EXCLUDED_SUFFIXES = (
    "(country)",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build tennis player social graph data.")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--save-every", type=int, default=100)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    data_root = project_root / "data" / "tennisPlayer"
    cache_dir = data_root / "cache"
    output_dir = data_root / "outputs"

    client = WikipediaClient(
        cache_dir=cache_dir,
        user_agent=USER_AGENT,
        pause=0.5,
        api_url=API_URL,
    )
    nodes = build_list_section_nodes(
        client=client,
        dataset_name="tennisPlayer",
        list_page_title=LIST_PAGE_TITLE,
        list_section_marker=LIST_SECTION_MARKER,
        excluded_titles=EXCLUDED_TITLES,
        category_keywords=CATEGORY_KEYWORDS,
        cache_path=cache_dir / "tennis_player_nodes.json",
        excluded_suffixes=EXCLUDED_SUFFIXES,
    )
    outgoing_links = crawl_edges_for_nodes(
        client=client,
        nodes=nodes,
        links_cache_path=cache_dir / "tennis_player_links.json",
        output_dir=output_dir,
        batch_size=args.batch_size,
        save_every=args.save_every,
        dataset_name="tennisPlayer",
    )
    save_manifest(
        output_dir,
        {
            "dataset": "tennisPlayer",
            "top_page": LIST_PAGE_TITLE,
            "final_node_count": len(nodes),
            "cached_source_count": len(outgoing_links),
            "outputs": ["nodes.csv", "edges.csv", "manifest.json"],
        },
    )


if __name__ == "__main__":
    main()
