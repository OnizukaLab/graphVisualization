from __future__ import annotations

import argparse
from pathlib import Path

from wiki_graph_common import (
    WikipediaClient,
    build_politician_nodes,
    crawl_edges_for_nodes,
    save_manifest,
)


USER_AGENT = "GraphVisualizationPolitician/1.0 (Codex)"
LIST_PAGE_TITLE = "衆議院議員一覧"
LIST_SECTION_MARKER = "== 議員一覧 =="
EXCLUDED_TITLES = {
    "北海道",
    "比例北海道ブロック",
    "自由民主党",
    "日本維新の会",
    "国民民主党",
    "日本共産党",
    "参政党",
    "れいわ新選組",
    "衆議院",
    "衆議院議員",
    "小選挙区",
    "比例代表",
    "重複立候補",
    "議長",
    "副議長",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build politician social graph data.")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--save-every", type=int, default=100)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    data_root = project_root / "data" / "politician"
    cache_dir = data_root / "cache"
    output_dir = data_root / "outputs"

    client = WikipediaClient(cache_dir=cache_dir, user_agent=USER_AGENT, pause=0.5)
    nodes = build_politician_nodes(
        client=client,
        list_page_title=LIST_PAGE_TITLE,
        list_section_marker=LIST_SECTION_MARKER,
        excluded_titles=EXCLUDED_TITLES,
        cache_path=cache_dir / "shugiin_member_nodes.json",
    )
    outgoing_links = crawl_edges_for_nodes(
        client=client,
        nodes=nodes,
        links_cache_path=cache_dir / "shugiin_links.json",
        output_dir=output_dir,
        batch_size=args.batch_size,
        save_every=args.save_every,
        dataset_name="politician",
    )
    save_manifest(
        output_dir,
        {
            "dataset": "politician",
            "top_page": LIST_PAGE_TITLE,
            "final_node_count": len(nodes),
            "cached_source_count": len(outgoing_links),
            "outputs": ["nodes.csv", "edges.csv", "manifest.json"],
        },
    )


if __name__ == "__main__":
    main()
