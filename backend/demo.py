#!/usr/bin/env python3
"""
Quick content quality tester for SciScroll.

Usage:
    python demo.py                          # All 6 topics × 3 strategies
    python demo.py "Black Holes"            # Single topic, all 3 strategies
    python demo.py "Black Holes" deeper     # Single topic, single strategy
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from server import create_app
from api_clients import get_available_apis

# ── ANSI colors (degrade gracefully) ─────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
WHITE = "\033[97m"

STRATEGY_COLOR = {"deeper": GREEN, "branch": YELLOW, "pivot": RED}

# ── Pre-built engagement data ─────────────────────────────────────────────

TIME_DATA = {
    "deeper": {
        "current_node_id": "",
        "total_time_on_node_ms": 60000,
        "scroll_events": 12,
        "go_deeper_clicks": 2,
        "sections_in_current_node": 4,
        "time_per_section_ms": 15000,
    },
    "branch": {
        "current_node_id": "",
        "total_time_on_node_ms": 25000,
        "scroll_events": 5,
        "go_deeper_clicks": 0,
        "sections_in_current_node": 4,
        "time_per_section_ms": 6250,
    },
    "pivot": {
        "current_node_id": "",
        "total_time_on_node_ms": 3000,
        "scroll_events": 1,
        "go_deeper_clicks": 0,
        "sections_in_current_node": 4,
        "time_per_section_ms": 750,
    },
}

ALL_TOPICS = [
    "Black Holes",
    "Quantum Mechanics",
    "CRISPR Gene Editing",
    "Dark Matter",
    "Climate Science",
    "Neural Networks",
]


def print_header(app):
    """Print mode and API availability."""
    apis = get_available_apis(app.api_clients)
    claude_available = app.api_clients["claude"].is_available
    if claude_available:
        mode = f"{GREEN}LIVE (Claude orchestrating){RESET}"
    else:
        mode = f"{RED}NO CLAUDE KEY — will fail{RESET}"

    api_str = ""
    for name, avail in apis.items():
        icon = f"{GREEN}+{RESET}" if avail else f"{DIM}-{RESET}"
        api_str += f"  {name} {icon}"

    print(f"\n{BOLD}{WHITE}{'=' * 60}{RESET}")
    print(f"{BOLD}{WHITE}  SciScroll Demo{RESET}")
    print(f"{BOLD}{WHITE}{'=' * 60}{RESET}")
    print(f"  Mode: {mode}")
    print(f"  APIs:{api_str}")
    print()


def truncate(text, length=100):
    """Truncate text for display."""
    if not text:
        return ""
    text = text.replace("\n", " ")
    return text[:length] + "..." if len(text) > length else text


def print_blocks(data, label):
    """Pretty-print content blocks grouped by group_id."""
    strategy = data.get("strategy_used", "?")
    score = data.get("engagement_score", "n/a")
    color = STRATEGY_COLOR.get(strategy, WHITE)

    score_str = f" (score: {score})" if isinstance(score, (int, float)) else ""
    print(f"{BOLD}{color}── {label} | Strategy: {strategy}{score_str} {'─' * 30}{RESET}")

    blocks = data.get("content_blocks", [])

    # Group by group_id
    groups = {}
    for b in blocks:
        gid = b.get("group_id", "ungrouped")
        groups.setdefault(gid, []).append(b)

    for i, (gid, group_blocks) in enumerate(groups.items(), 1):
        print(f"  {DIM}[{i}]{RESET}")
        for b in group_blocks:
            btype = b["type"].upper()
            role = b.get("group_role", "")
            content = b.get("content", "")

            if b["type"] == "text":
                print(f"      {CYAN}{btype}{RESET} ({role}): {truncate(content, 120)}")
            else:
                media = b.get("media", {})
                url = media.get("url", "")
                source = media.get("source", "")
                # Show a short version of the URL
                short_url = url.split("?")[0] if url else ""
                extra = ""
                if media.get("title"):
                    extra = f' — "{truncate(media["title"], 50)}"'
                elif media.get("text"):
                    extra = f' — "{truncate(media["text"], 50)}"'
                elif media.get("alt_text"):
                    extra = f' — "{truncate(media["alt_text"], 50)}"'
                print(f"      {MAGENTA}{btype}{RESET} ({role}): {source}{extra}")
                print(f"        {DIM}{short_url}{RESET}")

    # Next nodes
    next_nodes = data.get("next_nodes", [])
    if next_nodes:
        labels = [n.get("label", n.get("id", "?")) for n in next_nodes]
        print(f"  {BOLD}-> Next:{RESET} {', '.join(labels)}")

    # Graph info (initial only)
    graph = data.get("graph")
    if graph:
        n_nodes = len(graph.get("nodes", []))
        n_edges = len(graph.get("edges", []))
        print(f"  {DIM}Graph: {n_nodes} nodes, {n_edges} edges{RESET}")

    print()


def run_demo(client, topic, strategies):
    """Run demo for a topic with specified strategies."""

    # Step 1: Initial content
    resp = client.post("/api/initial", json={"topic": topic})
    if resp.status_code != 200:
        print(f"  {RED}ERROR: /api/initial returned {resp.status_code}: {resp.get_json()}{RESET}")
        return

    init_data = resp.get_json()
    print_blocks(init_data, f"{topic} | INITIAL")

    # Step 2: Generate for each strategy
    visited = [topic.lower().replace(" ", "-")]

    for strategy in strategies:
        td = dict(TIME_DATA[strategy])
        td["current_node_id"] = visited[0]

        resp = client.post("/api/generate", json={
            "current_node": topic,
            "time_data": td,
            "visited_nodes": visited,
            "last_paragraph": init_data["content_blocks"][0]["content"] if init_data["content_blocks"] else "",
        })

        if resp.status_code != 200:
            print(f"  {RED}ERROR: /api/generate returned {resp.status_code}: {resp.get_json()}{RESET}")
            continue

        gen_data = resp.get_json()
        print_blocks(gen_data, topic)

        # Accumulate visited nodes
        for n in gen_data.get("next_nodes", []):
            nid = n.get("id", "")
            if nid and nid not in visited:
                visited.append(nid)


def main():
    args = sys.argv[1:]

    # Parse args
    topic_filter = None
    strategy_filter = None

    if len(args) >= 1:
        topic_filter = args[0]
    if len(args) >= 2:
        strategy_filter = args[1]
        if strategy_filter not in ("deeper", "branch", "pivot"):
            print(f"{RED}Invalid strategy: {strategy_filter}. Must be deeper/branch/pivot{RESET}")
            sys.exit(1)

    # Determine what to run
    topics = [topic_filter] if topic_filter else ALL_TOPICS
    strategies = [strategy_filter] if strategy_filter else ["deeper", "branch", "pivot"]

    # Create app and client
    app = create_app(testing=False)

    if not app.api_clients["claude"].is_available:
        print(f"{RED}ERROR: ANTHROPIC_API_KEY is not set. Demo requires a live Claude API key.{RESET}")
        print(f"{DIM}Set it in .env or export ANTHROPIC_API_KEY=sk-...{RESET}")
        sys.exit(1)

    client = app.test_client()

    print_header(app)

    for topic in topics:
        run_demo(client, topic, strategies)

    print(f"{BOLD}{WHITE}{'=' * 60}{RESET}")
    print(f"  Done. Tested {len(topics)} topic(s) x {len(strategies)} strategy(ies)")
    print(f"{BOLD}{WHITE}{'=' * 60}{RESET}\n")


if __name__ == "__main__":
    main()
