from __future__ import annotations

import csv
import json
import re
import sys
import time
from collections import deque
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set

LOCAL_PACKAGES = Path(__file__).resolve().parents[1] / ".packages"
if LOCAL_PACKAGES.exists():
    sys.path.insert(0, str(LOCAL_PACKAGES))

import requests
from requests import exceptions as requests_exceptions


DEFAULT_API_URL = "https://ja.wikipedia.org/w/api.php"
WIKILINK_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")


def log(message: str) -> None:
    print(message, flush=True)


def now_ts() -> float:
    return time.time()


class WikipediaClient:
    def __init__(
        self,
        cache_dir: Path,
        user_agent: str,
        pause: float = 0.5,
        max_retries: int = 6,
        api_url: str = DEFAULT_API_URL,
    ) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.pause = pause
        self.max_retries = max_retries
        self.api_url = api_url
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def request(self, params: Dict[str, object]) -> Dict[str, object]:
        response = None
        for attempt in range(self.max_retries):
            payload = dict(params)
            payload["maxlag"] = 5
            try:
                response = self.session.post(self.api_url, data=payload, timeout=60)
            except (requests_exceptions.ConnectionError, requests_exceptions.Timeout):
                time.sleep((attempt + 1) * 5.0)
                continue
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = float(retry_after) if retry_after else (attempt + 1) * 5.0
                time.sleep(wait_seconds)
                continue
            if response.status_code == 200:
                time.sleep(self.pause)
                data = response.json()
                if "error" in data:
                    code = data["error"].get("code")
                    if code in {"maxlag", "ratelimited"} and attempt + 1 < self.max_retries:
                        time.sleep((attempt + 1) * 5.0)
                        continue
                    raise RuntimeError(f"Wikipedia API error: {data['error']}")
                return data
            time.sleep((attempt + 1) * 0.5)
        if response is not None:
            response.raise_for_status()
        raise RuntimeError("Wikipedia API request failed")

    def fetch_page_content(self, title: str) -> str:
        return self.fetch_page_contents([title]).get(title, "")

    def fetch_page_contents(self, titles: Sequence[str]) -> Dict[str, str]:
        if not titles:
            return {}
        params = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "revisions",
            "titles": "|".join(titles),
            "rvprop": "content",
            "rvslots": "main",
            "redirects": 1,
        }
        data = self.request(params)
        contents: Dict[str, str] = {}
        for page in data["query"]["pages"]:
            revisions = page.get("revisions", [])
            content = ""
            if revisions:
                content = revisions[0].get("slots", {}).get("main", {}).get("content", "")
            contents[page["title"]] = content
        return contents

    def fetch_page_categories(self, titles: Sequence[str]) -> Dict[str, List[str]]:
        if not titles:
            return {}
        params = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "categories",
            "titles": "|".join(titles),
            "cllimit": "max",
            "clshow": "!hidden",
            "redirects": 1,
        }
        data = self.request(params)
        categories_by_title: Dict[str, List[str]] = {}
        for page in data["query"]["pages"]:
            categories_by_title[page["title"]] = [category["title"] for category in page.get("categories", [])]
        return categories_by_title

    def fetch_section_links(self, title: str, section_heading: str) -> List[str]:
        sections_data = self.request(
            {
                "action": "parse",
                "format": "json",
                "page": title,
                "prop": "sections",
                "redirects": 1,
            }
        )
        section_index = None
        for section in sections_data.get("parse", {}).get("sections", []):
            if section.get("line", "").strip() == section_heading:
                section_index = section.get("index")
                break
        if section_index is None:
            raise RuntimeError(f"Section not found: {title} / {section_heading}")

        links_data = self.request(
            {
                "action": "parse",
                "format": "json",
                "page": title,
                "prop": "links",
                "section": section_index,
                "redirects": 1,
            }
        )
        links: Set[str] = set()
        for link in links_data.get("parse", {}).get("links", []):
            if link.get("ns") == 0:
                links.add(link["*"].replace("_", " "))
        return sorted(links)

    def fetch_category_neighbors(self, category: str, cache_prefix: str) -> Dict[str, List[str]]:
        cache_path = self.cache_dir / f"{cache_prefix}_category_{abs(hash(category))}.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        pages: Set[str] = set()
        subcategories: Set[str] = set()
        parents: Set[str] = set()

        cmcontinue = None
        while True:
            params = {
                "action": "query",
                "format": "json",
                "list": "categorymembers",
                "cmtitle": category,
                "cmlimit": "max",
                "cmtype": "page|subcat",
            }
            if cmcontinue:
                params["cmcontinue"] = cmcontinue
            data = self.request(params)
            for member in data["query"]["categorymembers"]:
                if member["ns"] == 0:
                    pages.add(member["title"])
                elif member["ns"] == 14:
                    subcategories.add(member["title"])
            cmcontinue = data.get("continue", {}).get("cmcontinue")
            if not cmcontinue:
                break

        clcontinue = None
        while True:
            params = {
                "action": "query",
                "format": "json",
                "prop": "categories",
                "titles": category,
                "cllimit": "max",
                "clshow": "!hidden",
            }
            if clcontinue:
                params["clcontinue"] = clcontinue
            data = self.request(params)
            for page in data["query"]["pages"].values():
                for parent in page.get("categories", []):
                    parents.add(parent["title"])
            clcontinue = data.get("continue", {}).get("clcontinue")
            if not clcontinue:
                break

        result = {
            "pages": sorted(pages),
            "subcategories": sorted(subcategories),
            "parents": sorted(parents),
        }
        cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result


def batched(items: Iterable[str], size: int) -> Iterable[List[str]]:
    batch: List[str] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def extract_wikilinks(content: str) -> List[str]:
    links: Set[str] = set()
    for match in WIKILINK_PATTERN.findall(content):
        target = match.split("|", 1)[0].split("#", 1)[0].strip()
        if not target or ":" in target:
            continue
        links.add(target.replace("_", " "))
    return sorted(links)


def save_graph_csvs(output_dir: Path, nodes: Sequence[str], outgoing_links: Dict[str, List[str]]) -> None:
    node_set = set(nodes)
    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / "nodes.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Id", "Label"])
        for node in nodes:
            writer.writerow([node, node])

    with (output_dir / "edges.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Source", "Target", "Type"])
        for source in nodes:
            for target in sorted(set(outgoing_links.get(source, [])) & node_set):
                if source != target:
                    writer.writerow([source, target, "Directed"])


def save_manifest(output_dir: Path, payload: Dict[str, object]) -> None:
    (output_dir / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def count_edges(nodes: Sequence[str], outgoing_links: Dict[str, List[str]]) -> int:
    node_set = set(nodes)
    total = 0
    for source in nodes:
        total += sum(1 for target in set(outgoing_links.get(source, [])) if target in node_set and target != source)
    return total


def build_actor_nodes(
    client: WikipediaClient,
    cache_prefix: str,
    seed_categories: Sequence[str],
    actor_category_keywords: Sequence[str],
    target_size: int,
) -> List[str]:
    cache_path = client.cache_dir / f"{cache_prefix}_actors_{target_size}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    def is_actor_category(title: str) -> bool:
        return title.startswith("Category:") and any(keyword in title for keyword in actor_category_keywords)

    actors: List[str] = []
    seen_actors: Set[str] = set()
    visited_categories: Set[str] = set()
    queue = deque(seed_categories)
    started = now_ts()

    while queue and len(seen_actors) < target_size:
        category = queue.popleft()
        if category in visited_categories or not is_actor_category(category):
            continue
        cat_started = now_ts()
        visited_categories.add(category)
        log(f"[category/start] category={category} visited={len(visited_categories)} actors={len(actors)} queue={len(queue)}")
        neighbors = client.fetch_category_neighbors(category, cache_prefix)
        for actor in neighbors["pages"]:
            if actor not in seen_actors:
                seen_actors.add(actor)
                actors.append(actor)
                if len(seen_actors) >= target_size:
                    break
        for related in neighbors["subcategories"] + neighbors["parents"]:
            if related not in visited_categories and is_actor_category(related):
                queue.append(related)
        cache_path.write_text(json.dumps(actors[:target_size], ensure_ascii=False, indent=2), encoding="utf-8")
        log(
            f"[category/end] category={category} actors={len(actors)} queue={len(queue)} "
            f"elapsed_sec={time.time() - cat_started:.1f} total_elapsed_sec={time.time() - started:.1f}"
        )
        if len(seen_actors) >= target_size:
            break

    return actors[:target_size]


def build_politician_nodes(
    client: WikipediaClient,
    list_page_title: str,
    list_section_marker: str,
    excluded_titles: Set[str],
    cache_path: Path,
) -> List[str]:
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    started = now_ts()
    log(f"[dataset/start] dataset=politician top_page={list_page_title}")
    section_heading = list_section_marker.replace("=", "").strip()
    links = client.fetch_section_links(list_page_title, section_heading)
    candidates = [
        title for title in links
        if title not in excluded_titles and not title.endswith("ブロック") and not title.endswith("区")
    ]
    candidates = sorted(dict.fromkeys(candidates))
    log(f"[dataset/candidates] dataset=politician candidates={len(candidates)}")

    members: List[str] = []
    for batch_index, batch in enumerate(batched(candidates, 20), start=1):
        batch_started = now_ts()
        log(f"[variant/start] dataset=politician variant=category_filter batch_index={batch_index} batch_size={len(batch)}")
        categories_by_title = client.fetch_page_categories(batch)
        for title, categories in categories_by_title.items():
            if any("衆議院議員" in category for category in categories):
                members.append(title)
        log(
            f"[variant/end] dataset=politician variant=category_filter batch_index={batch_index} "
            f"accepted_so_far={len(members)} elapsed_sec={time.time() - batch_started:.1f}"
        )

    ordered = sorted(dict.fromkeys(members))
    cache_path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[dataset/end] dataset=politician nodes={len(ordered)} elapsed_sec={time.time() - started:.1f}")
    return ordered


def build_list_section_nodes(
    client: WikipediaClient,
    dataset_name: str,
    list_page_title: str,
    list_section_marker: str,
    excluded_titles: Set[str],
    category_keywords: Sequence[str],
    cache_path: Path,
    excluded_suffixes: Sequence[str] = (),
) -> List[str]:
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    started = now_ts()
    section_heading = list_section_marker.replace("=", "").strip()
    lowered_keywords = tuple(keyword.lower() for keyword in category_keywords)

    log(f"[dataset/start] dataset={dataset_name} top_page={list_page_title}")
    links = client.fetch_section_links(list_page_title, section_heading)
    candidates = [
        title
        for title in links
        if title not in excluded_titles and not any(title.endswith(suffix) for suffix in excluded_suffixes)
    ]
    candidates = sorted(dict.fromkeys(candidates))
    log(f"[dataset/candidates] dataset={dataset_name} candidates={len(candidates)}")

    members: List[str] = []
    for batch_index, batch in enumerate(batched(candidates, 20), start=1):
        batch_started = now_ts()
        log(
            f"[variant/start] dataset={dataset_name} variant=category_filter "
            f"batch_index={batch_index} batch_size={len(batch)}"
        )
        categories_by_title = client.fetch_page_categories(batch)
        for title, categories in categories_by_title.items():
            normalized_categories = [category.lower() for category in categories]
            if any(keyword in category for keyword in lowered_keywords for category in normalized_categories):
                members.append(title)
        log(
            f"[variant/end] dataset={dataset_name} variant=category_filter batch_index={batch_index} "
            f"accepted_so_far={len(members)} elapsed_sec={time.time() - batch_started:.1f}"
        )

    ordered = sorted(dict.fromkeys(members))
    cache_path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[dataset/end] dataset={dataset_name} nodes={len(ordered)} elapsed_sec={time.time() - started:.1f}")
    return ordered


def crawl_edges_for_nodes(
    client: WikipediaClient,
    nodes: Sequence[str],
    links_cache_path: Path,
    output_dir: Path,
    batch_size: int,
    save_every: int,
    dataset_name: str,
) -> Dict[str, List[str]]:
    outgoing_links: Dict[str, List[str]] = json.loads(links_cache_path.read_text(encoding="utf-8")) if links_cache_path.exists() else {}
    missing = [node for node in nodes if node not in outgoing_links]
    total_missing = len(missing)
    started = now_ts()
    log(f"[crawl/start] dataset={dataset_name} total_nodes={len(nodes)} missing_sources={total_missing} batch_size={batch_size}")

    done = 0
    for batch_index, batch in enumerate(batched(missing, batch_size), start=1):
        batch_started = now_ts()
        log(
            f"[batch/start] dataset={dataset_name} batch_index={batch_index} "
            f"batch_size={len(batch)} done={done} remaining={total_missing - done}"
        )
        contents = client.fetch_page_contents(batch)
        outgoing_links.update({title: extract_wikilinks(content) for title, content in contents.items()})
        done += len(batch)
        log(
            f"[batch/end] dataset={dataset_name} batch_index={batch_index} done={done}/{total_missing} "
            f"batch_elapsed_sec={time.time() - batch_started:.1f} total_elapsed_sec={time.time() - started:.1f}"
        )
        if done % save_every == 0 or done == total_missing:
            links_cache_path.write_text(json.dumps(outgoing_links, ensure_ascii=False), encoding="utf-8")
            save_graph_csvs(output_dir, nodes, outgoing_links)
            log(
                f"[checkpoint] dataset={dataset_name} cached_sources={len(outgoing_links)} "
                f"edges={count_edges(nodes, outgoing_links)} total_elapsed_sec={time.time() - started:.1f}"
            )

    links_cache_path.write_text(json.dumps(outgoing_links, ensure_ascii=False), encoding="utf-8")
    save_graph_csvs(output_dir, nodes, outgoing_links)
    log(
        f"[crawl/end] dataset={dataset_name} cached_sources={len(outgoing_links)} "
        f"edges={count_edges(nodes, outgoing_links)} total_elapsed_sec={time.time() - started:.1f}"
    )
    return outgoing_links
