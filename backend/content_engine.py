"""
Core content engine for SciScroll.

Handles engagement scoring, strategy selection, content block generation
(live via Claude orchestration), and response validation.
"""

import json
import logging
import random
import uuid
from collections import deque

from topic_graph import slugify, make_node

logger = logging.getLogger(__name__)

# ── Media types ───────────────────────────────────────────────────────────
MEDIA_TYPES = ["unsplash", "wikipedia_image", "wikimedia", "reddit", "xkcd", "meme", "tweet"]

VALID_GROUP_ROLES_TEXT = {"explanation", "caption", "context", "funfact"}
VALID_GROUP_ROLES_MEDIA = {"visual", "diagram", "discussion", "humor", "social"}
VALID_STRATEGIES = {"deeper", "branch", "pivot"}


# ── Utility ───────────────────────────────────────────────────────────────

def _uid(prefix=""):
    """Generate a short unique ID with an optional prefix."""
    short = uuid.uuid4().hex[:8]
    return f"{prefix}-{short}" if prefix else short


def sanitize_time_data(time_data):
    """Sanitize and fill defaults for time_data from the frontend.

    Returns a clean dict with all required keys, safe types, and non-negative values.
    """
    defaults = {
        "current_node_id": "",
        "total_time_on_node_ms": 0,
        "scroll_events": 0,
        "go_deeper_clicks": 0,
        "sections_in_current_node": 1,
        "time_per_section_ms": 0,
    }
    if not isinstance(time_data, dict):
        return dict(defaults)

    result = {}
    for key, default_val in defaults.items():
        val = time_data.get(key, default_val)
        if key == "current_node_id":
            result[key] = str(val) if val is not None else ""
        else:
            try:
                val = int(val) if val is not None else default_val
            except (ValueError, TypeError):
                val = default_val
            result[key] = max(0, val)

    # sections must be at least 1 to avoid division by zero
    if result["sections_in_current_node"] < 1:
        result["sections_in_current_node"] = 1

    return result


# ── Engagement scoring ────────────────────────────────────────────────────

def compute_engagement_score(time_data):
    """Compute an engagement score from 0.0 to 1.0 based on time_data.

    Weighted formula:
    - 0.30 × time factor (30s = 0.5, 60s+ = 1.0)
    - 0.20 × scroll factor (capped at 10)
    - 0.30 × click factor (each click adds 0.5, capped at 1.0)
    - 0.20 × section-variance factor (time_per_section / total * sections)
    """
    td = sanitize_time_data(time_data)

    # Time factor: 0-60s maps to 0-1
    time_ms = td["total_time_on_node_ms"]
    time_factor = min(1.0, time_ms / 60000.0)

    # Scroll factor: 0-10 scrolls maps to 0-1
    scroll_factor = min(1.0, td["scroll_events"] / 10.0)

    # Click factor: each go_deeper_click adds 0.5, capped at 1.0
    click_factor = min(1.0, td["go_deeper_clicks"] * 0.5)

    # Section variance: how evenly time is distributed across sections
    sections = td["sections_in_current_node"]
    total_time = td["total_time_on_node_ms"]
    time_per_section = td["time_per_section_ms"]
    if total_time > 0 and sections > 0:
        expected_per_section = total_time / sections
        if expected_per_section > 0:
            variance_factor = min(1.0, time_per_section / expected_per_section)
        else:
            variance_factor = 0.0
    else:
        variance_factor = 0.0

    score = (
        0.30 * time_factor
        + 0.20 * scroll_factor
        + 0.30 * click_factor
        + 0.20 * variance_factor
    )

    return round(max(0.0, min(1.0, score)), 4)


def select_strategy(engagement_score):
    """Select a content strategy based on engagement score.

    >= 0.65 → "deeper"  (user is very engaged, go deeper into topic)
    0.35–0.65 → "branch" (moderate, show related topics)
    < 0.35 → "pivot"   (low engagement, switch to different topic)
    """
    if engagement_score >= 0.65:
        return "deeper"
    elif engagement_score >= 0.35:
        return "branch"
    else:
        return "pivot"


# ── Media variety tracking ────────────────────────────────────────────────

class MediaVarietyTracker:
    """Cycles through media types to ensure variety. No consecutive duplicates."""

    def __init__(self, media_types=None):
        self._types = list(media_types or MEDIA_TYPES)
        self._queue = deque(self._types)
        self._last = None

    def next_type(self):
        """Get the next media type, avoiding consecutive duplicates."""
        if not self._queue:
            shuffled = list(self._types)
            random.shuffle(shuffled)
            self._queue = deque(shuffled)

        media_type = self._queue.popleft()

        # Avoid consecutive duplicates
        attempts = 0
        while media_type == self._last and len(self._types) > 1 and attempts < len(self._types):
            self._queue.append(media_type)
            media_type = self._queue.popleft()
            attempts += 1

        self._last = media_type
        return media_type

    @property
    def last(self):
        return self._last



# ── Claude orchestration ─────────────────────────────────────────────────

CLAUDE_SYSTEM_PROMPT = """You are the content orchestrator for SciScroll, an infinite scientific knowledge graph explorer.

Your job is to decide what content to show the user next. You will receive:
- The current topic and subtopic
- The user's engagement level (0-1 score) and selected strategy (deeper/branch/pivot)
- Which external APIs are available
- The last paragraph the user read
- Which nodes the user has already visited

You must return a JSON object with this exact structure:
{
    "groups": [
        {
            "text": "A paragraph of educational content about the topic...",
            "media_request": {"type": "wikipedia_image", "query": "Black hole"},
            "group_role_text": "explanation",
            "group_role_media": "visual"
        }
    ],
    "next_nodes": [
        {"id": "hawking-radiation", "label": "Hawking Radiation", "description": "Theoretical radiation emitted by black holes due to quantum effects near the event horizon"},
        {"id": "event-horizon", "label": "Event Horizon", "description": "The boundary beyond which nothing can return from a black hole"}
    ]
}

NEXT_NODES RULES:
- Generate 2-4 next nodes that represent logical next topics for the user to explore
- Each node MUST have "id" (lowercase-hyphenated slug of the label), "label" (human-readable name), and "description" (one-sentence explanation)
- The "id" must be the slugified version of the label: lowercase, hyphens for spaces, no special characters, max 80 chars (e.g. "Hawking Radiation" → "hawking-radiation")
- When strategy is "deeper": next nodes should be specific subtopics or mechanisms within the current topic
- When strategy is "branch": next nodes should be related fields or adjacent concepts
- When strategy is "pivot": next nodes should be entirely different but interesting scientific topics
- Do NOT suggest nodes the user has already visited (see Visited Nodes list)
- Make descriptions scientifically accurate and specific, not generic

CONTENT DEPTH & FLOW:
- Generate 5-8 content groups per response
- When the strategy is "deeper", build on what the user has already read. Go into specific subtopics, mechanisms, and details — do NOT repeat introductory overviews. Reference the last_paragraph to create continuity.
- Create natural transitions between groups. The first group should connect to the last_paragraph, and each subsequent group should flow logically into the next.
- Each text paragraph should be 2-4 sentences, educational, engaging, and scientifically accurate.
- Progress through the topic: start with a transition from previous content, build through details, and end with a hook leading to the next nodes.

MEDIA QUERY FORMATS (critical for API success):
- "wikipedia_image": query MUST be a short Wikipedia article title (e.g. "Black hole", "CRISPR", "Neutron star"). NOT a sentence or description.
- "wikimedia": query should be 2-3 word science terms (e.g. "DNA structure", "galaxy diagram", "neural network").
- "xkcd": only request if the topic genuinely relates to a well-known xkcd theme (physics, math, CS, biology). Query should contain the core keyword (e.g. "gravity", "quantum", "evolution").
- "meme": include "top_text" and "bottom_text" fields in the media_request that are funny and specific to the current subtopic. Example: {"type": "meme", "query": "science meme", "top_text": "When you finally understand quantum tunneling", "bottom_text": "But then forget it immediately"}
- "tweet": query should be a specific scientific term or concept (e.g. "CRISPR gene editing", "black hole photo").
- "unsplash": descriptive search query for a relevant photo.

STRUCTURAL RULES:
- Each group has a text (can be null) and a media_request (can be null), but at least one must be non-null
- media_request.type must be one of: unsplash, wikipedia_image, wikimedia, reddit, xkcd, meme, tweet
- Only request media types that are marked as available
- group_role_text must be one of: explanation, caption, context, funfact
- group_role_media must be one of: visual, diagram, discussion, humor, social
- next_nodes: see NEXT_NODES RULES above for the required format
- Mix media types for variety — don't use the same media type twice in a row

STRATEGY BEHAVIOR:
- "deeper": detailed explanations, diagrams, Wikipedia images, charts. Go into mechanisms, equations, experiments. Build on visited nodes — don't rehash basics.
- "branch": connections to related topics, broader context. Show how the current topic relates to adjacent fields. Use varied media to illustrate connections.
- "pivot": fun, surprising, lighter content — use memes (with good captions!), comics, tweets. Still educational but with humor and novelty.

Return ONLY valid JSON, no markdown formatting."""


def generate_content_with_claude(
    topic_label,
    strategy,
    visited_nodes,
    last_paragraph,
    engagement_score,
    available_apis,
    claude_client,
):
    """Use Claude to decide the content mix and generate text.

    Returns a dict with "groups" and "next_nodes", or None on failure.
    """
    if not claude_client or not claude_client.is_available:
        return None

    # Filter available_apis to only ones that are True
    apis_available = [name for name, avail in available_apis.items() if avail and name != "claude"]

    # Map API names to media types
    api_to_media = {
        "unsplash": "unsplash",
        "wikipedia": "wikipedia_image",
        "wikimedia": "wikimedia",
        "reddit": "reddit",
        "xkcd": "xkcd",
        "imgflip": "meme",
        "twitter": "tweet",
    }
    available_media_types = [api_to_media[api] for api in apis_available if api in api_to_media]

    user_prompt = f"""Topic: {topic_label}
Strategy: {strategy}
Engagement Score: {engagement_score}
Visited Nodes: {json.dumps(list(visited_nodes or []))}
Last Paragraph: {last_paragraph or "None (first content)"}

Available media types: {json.dumps(available_media_types)}

Generate educational content following the {strategy} strategy.
Suggest 2-4 next_nodes the user hasn't visited yet."""

    result = claude_client.generate_json(CLAUDE_SYSTEM_PROMPT, user_prompt)
    if result and isinstance(result, dict) and "groups" in result:
        return result
    return None


def _clean_query_for_wikipedia(query, topic_label):
    """Clean a Claude-generated query for Wikipedia API compatibility.

    Wikipedia works best with short article-title-style queries.
    If the query is too long, fall back to the topic label.
    """
    # If query is already short and title-like, use it directly
    if len(query.split()) <= 3:
        return query

    # For longer queries, the topic label is usually a better Wikipedia title
    return topic_label


def _resolve_media(media_request, topic_label, api_clients):
    """Execute a media request from Claude's plan using real API clients.

    Returns a media dict or None if the API call fails.
    """
    if not media_request or not isinstance(media_request, dict):
        return None

    media_type = media_request.get("type", "unsplash")
    query = media_request.get("query", topic_label)
    result = None

    try:
        if media_type == "unsplash" and api_clients.get("unsplash"):
            result = api_clients["unsplash"].search_photos(query)
        elif media_type == "wikipedia_image" and api_clients.get("wikipedia"):
            # Clean the query to match Wikipedia article titles
            clean_query = _clean_query_for_wikipedia(query, topic_label)
            result = api_clients["wikipedia"].get_page_image(clean_query)
        elif media_type == "wikimedia" and api_clients.get("wikimedia"):
            result = api_clients["wikimedia"].search_diagrams(query)
        elif media_type == "reddit" and api_clients.get("reddit"):
            result = api_clients["reddit"].search_posts(query)
        elif media_type == "xkcd" and api_clients.get("xkcd"):
            result = api_clients["xkcd"].search_comics(query)
        elif media_type == "meme" and api_clients.get("imgflip"):
            # Pass Claude's generated captions to Imgflip
            top_text = media_request.get("top_text")
            bottom_text = media_request.get("bottom_text")
            result = api_clients["imgflip"].get_meme(query, top_text=top_text, bottom_text=bottom_text)
        elif media_type == "tweet" and api_clients.get("twitter"):
            result = api_clients["twitter"].search_tweets(query)
    except Exception as e:
        logger.warning("API call failed for %s: %s", media_type, e)

    # Reject placeholder/hallucinated URLs
    if result and isinstance(result, dict):
        url = result.get("url", "")
        if "placeholder" in url.lower():
            logger.warning("Rejected placeholder URL: %s", url)
            return None

    return result


def generate_content_blocks(
    topic_id,
    strategy,
    visited_nodes,
    last_paragraph,
    engagement_score,
    api_clients,
):
    """Generate content blocks using Claude orchestration + real APIs.

    Returns (content_blocks, next_nodes) tuple, or (None, None) on failure.
    """
    from api_clients import get_available_apis

    claude_client = api_clients.get("claude")
    available_apis = get_available_apis(api_clients)

    topic_label = topic_id.replace("-", " ").title()

    # Try Claude orchestration
    claude_plan = generate_content_with_claude(
        topic_label=topic_label,
        strategy=strategy,
        visited_nodes=visited_nodes,
        last_paragraph=last_paragraph,
        engagement_score=engagement_score,
        available_apis=available_apis,
        claude_client=claude_client,
    )

    if claude_plan is None:
        return None, None

    # Execute Claude's plan
    blocks = []
    groups = claude_plan.get("groups", [])

    for group_data in groups:
        group_id = _uid("grp")

        # Text block
        text = group_data.get("text")
        if text:
            text_block = {
                "id": _uid("text"),
                "type": "text",
                "content": text,
                "group_id": group_id,
                "group_role": group_data.get("group_role_text", "explanation"),
            }
            blocks.append(text_block)

        # Media block — skip if API returns nothing
        media_request = group_data.get("media_request")
        if media_request:
            media_type = media_request.get("type", "unsplash")
            media_data = _resolve_media(media_request, topic_label, api_clients)

            if media_data is not None:
                media_block = {
                    "id": _uid(media_type),
                    "type": media_type,
                    "content": f"{topic_label} — {media_type} content",
                    "group_id": group_id,
                    "group_role": group_data.get("group_role_media", "visual"),
                    "media": media_data,
                }
                blocks.append(media_block)

    # Next nodes from Claude's plan — now full dicts with id/label/description
    visited_set = set(visited_nodes or [])
    claude_next = claude_plan.get("next_nodes", [])
    next_nodes = []
    for node_data in claude_next:
        if isinstance(node_data, str):
            # Backward compat: bare slug string
            nid = node_data
            if nid not in visited_set:
                next_nodes.append(make_node(nid.replace("-", " ").title()))
        elif isinstance(node_data, dict):
            label = node_data.get("label", "")
            desc = node_data.get("description", "")
            nid = slugify(label) if label else node_data.get("id", "")
            if nid and nid not in visited_set:
                next_nodes.append({
                    "id": nid,
                    "label": label or nid.replace("-", " ").title(),
                    "description": desc,
                })

    # If Claude returned no valid nodes, generate generic ones
    if not next_nodes:
        label = topic_label
        next_nodes = [
            make_node(f"{label} Deep Dive", f"Explore {label} in greater detail"),
            make_node(f"Beyond {label}", f"Topics related to {label}"),
        ]

    return blocks, next_nodes


def generate_initial_content(topic_label, api_clients):
    """Generate initial content using Claude orchestration.

    Returns result dict or None on failure.
    """
    topic_id = slugify(topic_label)
    node = make_node(topic_label, f"Exploring {topic_label}")

    strategy = "deeper"
    blocks, next_nodes = generate_content_blocks(
        topic_id=topic_id,
        strategy=strategy,
        visited_nodes=[],
        last_paragraph=None,
        engagement_score=0.7,
        api_clients=api_clients,
    )

    if blocks is None:
        return None

    # Build initial graph
    graph = {
        "nodes": [{"id": node["id"], "label": node["label"]}],
        "edges": [],
    }
    for nn in next_nodes:
        if nn["id"] != node["id"]:
            graph["nodes"].append(nn)
            graph["edges"].append({"source": node["id"], "target": nn["id"]})

    return {
        "content_blocks": blocks,
        "graph": graph,
        "next_nodes": next_nodes,
        "strategy_used": strategy,
    }


# ── Validation ────────────────────────────────────────────────────────────

def validate_content_block(block):
    """Validate a single content block. Returns list of error strings."""
    errors = []
    if not isinstance(block, dict):
        return ["Block is not a dict"]

    required = ["id", "type", "content", "group_id", "group_role"]
    for key in required:
        if key not in block:
            errors.append(f"Missing key: {key}")

    if "type" in block:
        block_type = block["type"]
        if block_type == "text":
            if block.get("group_role") and block["group_role"] not in VALID_GROUP_ROLES_TEXT:
                errors.append(f"Invalid text group_role: {block['group_role']}")
        elif block_type in MEDIA_TYPES:
            if block.get("group_role") and block["group_role"] not in VALID_GROUP_ROLES_MEDIA:
                errors.append(f"Invalid media group_role: {block['group_role']}")
            if "media" not in block:
                errors.append("Media block missing 'media' key")
            elif not isinstance(block["media"], dict):
                errors.append("Media block 'media' is not a dict")
            else:
                if "url" not in block["media"]:
                    errors.append("Media block missing 'url'")
                if "source" not in block["media"]:
                    errors.append("Media block missing 'source'")
        else:
            errors.append(f"Unknown block type: {block_type}")

    return errors


def validate_response(response):
    """Validate a /api/generate response. Returns list of error strings."""
    errors = []
    if not isinstance(response, dict):
        return ["Response is not a dict"]

    required = ["content_blocks", "next_nodes", "strategy_used", "engagement_score"]
    for key in required:
        if key not in response:
            errors.append(f"Missing key: {key}")

    if "strategy_used" in response and response["strategy_used"] not in VALID_STRATEGIES:
        errors.append(f"Invalid strategy: {response['strategy_used']}")

    if "engagement_score" in response:
        score = response["engagement_score"]
        if not isinstance(score, (int, float)):
            errors.append("engagement_score is not a number")
        elif score < 0 or score > 1:
            errors.append(f"engagement_score out of range: {score}")

    if "content_blocks" in response:
        if not isinstance(response["content_blocks"], list):
            errors.append("content_blocks is not a list")
        else:
            for i, block in enumerate(response["content_blocks"]):
                block_errors = validate_content_block(block)
                for err in block_errors:
                    errors.append(f"content_blocks[{i}]: {err}")

    if "next_nodes" in response:
        if not isinstance(response["next_nodes"], list):
            errors.append("next_nodes is not a list")

    return errors


def validate_initial_response(response):
    """Validate a /api/initial response. Returns list of error strings."""
    errors = []
    if not isinstance(response, dict):
        return ["Response is not a dict"]

    required = ["content_blocks", "graph", "next_nodes", "strategy_used"]
    for key in required:
        if key not in response:
            errors.append(f"Missing key: {key}")

    if "strategy_used" in response and response["strategy_used"] != "deeper":
        errors.append(f"Initial strategy should be 'deeper', got: {response['strategy_used']}")

    if "graph" in response:
        graph = response["graph"]
        if not isinstance(graph, dict):
            errors.append("graph is not a dict")
        else:
            if "nodes" not in graph:
                errors.append("graph missing 'nodes'")
            elif not isinstance(graph["nodes"], list) or len(graph["nodes"]) == 0:
                errors.append("graph 'nodes' must be a non-empty list")
            if "edges" not in graph:
                errors.append("graph missing 'edges'")

    if "content_blocks" in response:
        if not isinstance(response["content_blocks"], list):
            errors.append("content_blocks is not a list")
        else:
            for i, block in enumerate(response["content_blocks"]):
                block_errors = validate_content_block(block)
                for err in block_errors:
                    errors.append(f"content_blocks[{i}]: {err}")

    if "next_nodes" in response:
        if not isinstance(response["next_nodes"], list):
            errors.append("next_nodes is not a list")

    return errors
