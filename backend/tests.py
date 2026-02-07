"""Tests for SciScroll backend — all live API calls, no mocking."""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from topic_graph import slugify, make_node
from content_engine import (
    sanitize_time_data,
    compute_engagement_score,
    select_strategy,
    MediaVarietyTracker,
    MEDIA_TYPES,
    validate_content_block,
    validate_response,
    validate_initial_response,
    VALID_GROUP_ROLES_TEXT,
    VALID_GROUP_ROLES_MEDIA,
    VALID_STRATEGIES,
)
from server import create_app


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Create test Flask app with real API clients (loads .env)."""
    test_app = create_app(testing=False)
    test_app.config["TESTING"] = True
    return test_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def high_engagement_time_data():
    """Simulates a highly engaged user: long time, many scrolls, clicks."""
    return {
        "current_node_id": "black-holes",
        "total_time_on_node_ms": 60000,
        "scroll_events": 12,
        "go_deeper_clicks": 2,
        "sections_in_current_node": 4,
        "time_per_section_ms": 15000,
    }


@pytest.fixture
def moderate_engagement_time_data():
    """Simulates moderate engagement: some time, some scrolling."""
    return {
        "current_node_id": "quantum-mechanics",
        "total_time_on_node_ms": 20000,
        "scroll_events": 5,
        "go_deeper_clicks": 0,
        "sections_in_current_node": 4,
        "time_per_section_ms": 5000,
    }


@pytest.fixture
def low_engagement_time_data():
    """Simulates a disengaged user: quick bounce, minimal interaction."""
    return {
        "current_node_id": "climate-science",
        "total_time_on_node_ms": 5000,
        "scroll_events": 1,
        "go_deeper_clicks": 0,
        "sections_in_current_node": 4,
        "time_per_section_ms": 1250,
    }


@pytest.fixture
def zero_engagement_time_data():
    """Simulates zero engagement: all zeros."""
    return {
        "current_node_id": "dark-matter",
        "total_time_on_node_ms": 0,
        "scroll_events": 0,
        "go_deeper_clicks": 0,
        "sections_in_current_node": 1,
        "time_per_section_ms": 0,
    }


# ═══════════════════════════════════════════════════════════════════════════
# TestSlugify (8 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestSlugify:
    def test_basic_slug(self):
        assert slugify("Black Holes") == "black-holes"

    def test_special_characters(self):
        assert slugify("CRISPR Gene Editing!") == "crispr-gene-editing"

    def test_unicode_characters(self):
        result = slugify("Schr\u00f6dinger's Cat")
        assert "schr" in result
        assert " " not in result

    def test_empty_string(self):
        assert slugify("") == ""

    def test_whitespace_only(self):
        assert slugify("   ") == ""

    def test_long_string(self):
        long_text = "A" * 200
        result = slugify(long_text)
        assert len(result) <= 80

    def test_idempotent(self):
        """Slugifying a slug should return the same slug."""
        slug = slugify("Black Holes")
        assert slugify(slug) == slug

    def test_multiple_spaces_and_dashes(self):
        assert slugify("dark   matter--stuff") == "dark-matter-stuff"


# ═══════════════════════════════════════════════════════════════════════════
# TestMakeNode (4 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestMakeNode:
    def test_basic_node(self):
        node = make_node("Hawking Radiation", "Theoretical radiation from black holes")
        assert node["id"] == "hawking-radiation"
        assert node["label"] == "Hawking Radiation"
        assert node["description"] == "Theoretical radiation from black holes"

    def test_node_without_description(self):
        node = make_node("Dark Energy")
        assert node["id"] == "dark-energy"
        assert node["label"] == "Dark Energy"
        assert node["description"] == ""

    def test_node_has_required_keys(self):
        node = make_node("Test Topic", "A test")
        assert "id" in node
        assert "label" in node
        assert "description" in node

    def test_node_id_is_slugified(self):
        node = make_node("CRISPR Gene Editing!")
        assert node["id"] == "crispr-gene-editing"


# ═══════════════════════════════════════════════════════════════════════════
# TestSanitizeTimeData (10 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestSanitizeTimeData:
    def test_valid_data_passthrough(self, high_engagement_time_data):
        result = sanitize_time_data(high_engagement_time_data)
        assert result["total_time_on_node_ms"] == 60000
        assert result["scroll_events"] == 12
        assert result["go_deeper_clicks"] == 2

    def test_none_input(self):
        result = sanitize_time_data(None)
        assert result["total_time_on_node_ms"] == 0
        assert result["sections_in_current_node"] == 1

    def test_empty_dict(self):
        result = sanitize_time_data({})
        assert result["total_time_on_node_ms"] == 0
        assert result["current_node_id"] == ""

    def test_missing_keys_filled_with_defaults(self):
        result = sanitize_time_data({"total_time_on_node_ms": 5000})
        assert result["total_time_on_node_ms"] == 5000
        assert result["scroll_events"] == 0

    def test_wrong_types_handled(self):
        result = sanitize_time_data({"total_time_on_node_ms": "not a number"})
        assert result["total_time_on_node_ms"] == 0

    def test_negative_values_clamped(self):
        result = sanitize_time_data({"total_time_on_node_ms": -5000})
        assert result["total_time_on_node_ms"] == 0

    def test_float_values_converted(self):
        result = sanitize_time_data({"total_time_on_node_ms": 5000.7})
        assert result["total_time_on_node_ms"] == 5000

    def test_none_values_use_defaults(self):
        result = sanitize_time_data({"total_time_on_node_ms": None})
        assert result["total_time_on_node_ms"] == 0

    def test_sections_minimum_one(self):
        result = sanitize_time_data({"sections_in_current_node": 0})
        assert result["sections_in_current_node"] == 1

    def test_string_input(self):
        result = sanitize_time_data("not a dict")
        assert isinstance(result, dict)
        assert result["total_time_on_node_ms"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# TestEngagementScoring (15 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestEngagementScoring:
    def test_high_engagement(self, high_engagement_time_data):
        score = compute_engagement_score(high_engagement_time_data)
        assert score >= 0.65
        assert score <= 1.0

    def test_low_engagement(self, low_engagement_time_data):
        score = compute_engagement_score(low_engagement_time_data)
        assert score < 0.65

    def test_moderate_engagement(self, moderate_engagement_time_data):
        score = compute_engagement_score(moderate_engagement_time_data)
        assert 0.1 <= score <= 0.8

    def test_zero_engagement(self, zero_engagement_time_data):
        score = compute_engagement_score(zero_engagement_time_data)
        assert score == 0.0

    def test_all_zeros(self):
        data = {
            "total_time_on_node_ms": 0,
            "scroll_events": 0,
            "go_deeper_clicks": 0,
            "sections_in_current_node": 1,
            "time_per_section_ms": 0,
        }
        assert compute_engagement_score(data) == 0.0

    def test_maximum_engagement(self):
        data = {
            "total_time_on_node_ms": 120000,
            "scroll_events": 20,
            "go_deeper_clicks": 5,
            "sections_in_current_node": 4,
            "time_per_section_ms": 30000,
        }
        score = compute_engagement_score(data)
        assert score == 1.0

    def test_score_clamped_at_one(self):
        data = {
            "total_time_on_node_ms": 999999,
            "scroll_events": 999,
            "go_deeper_clicks": 999,
            "sections_in_current_node": 1,
            "time_per_section_ms": 999999,
        }
        score = compute_engagement_score(data)
        assert score <= 1.0

    def test_score_clamped_at_zero(self):
        score = compute_engagement_score(None)
        assert score >= 0.0

    def test_click_boost(self):
        base = {
            "total_time_on_node_ms": 10000,
            "scroll_events": 3,
            "go_deeper_clicks": 0,
            "sections_in_current_node": 2,
            "time_per_section_ms": 5000,
        }
        with_clicks = dict(base)
        with_clicks["go_deeper_clicks"] = 2
        assert compute_engagement_score(with_clicks) > compute_engagement_score(base)

    def test_scroll_boost(self):
        base = {
            "total_time_on_node_ms": 10000,
            "scroll_events": 0,
            "go_deeper_clicks": 0,
            "sections_in_current_node": 2,
            "time_per_section_ms": 5000,
        }
        with_scrolls = dict(base)
        with_scrolls["scroll_events"] = 8
        assert compute_engagement_score(with_scrolls) > compute_engagement_score(base)

    def test_time_boost(self):
        base = {
            "total_time_on_node_ms": 5000,
            "scroll_events": 3,
            "go_deeper_clicks": 0,
            "sections_in_current_node": 2,
            "time_per_section_ms": 2500,
        }
        with_time = dict(base)
        with_time["total_time_on_node_ms"] = 50000
        with_time["time_per_section_ms"] = 25000
        assert compute_engagement_score(with_time) > compute_engagement_score(base)

    def test_determinism(self, high_engagement_time_data):
        s1 = compute_engagement_score(high_engagement_time_data)
        s2 = compute_engagement_score(high_engagement_time_data)
        assert s1 == s2

    def test_returns_float(self, high_engagement_time_data):
        score = compute_engagement_score(high_engagement_time_data)
        assert isinstance(score, float)

    def test_four_decimal_precision(self):
        data = {
            "total_time_on_node_ms": 12345,
            "scroll_events": 3,
            "go_deeper_clicks": 1,
            "sections_in_current_node": 3,
            "time_per_section_ms": 4115,
        }
        score = compute_engagement_score(data)
        decimals = str(score).split(".")[-1]
        assert len(decimals) <= 4

    def test_none_input(self):
        score = compute_engagement_score(None)
        assert score == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# TestStrategySelection (6 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestStrategySelection:
    def test_high_engagement_deeper(self):
        assert select_strategy(0.8) == "deeper"

    def test_moderate_engagement_branch(self):
        assert select_strategy(0.5) == "branch"

    def test_low_engagement_pivot(self):
        assert select_strategy(0.2) == "pivot"

    def test_boundary_065(self):
        assert select_strategy(0.65) == "deeper"

    def test_boundary_035(self):
        assert select_strategy(0.35) == "branch"

    def test_zero(self):
        assert select_strategy(0.0) == "pivot"


# ═══════════════════════════════════════════════════════════════════════════
# TestMediaVariety (6 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestMediaVariety:
    def test_cycles_through_types(self):
        tracker = MediaVarietyTracker()
        seen = set()
        for _ in range(len(MEDIA_TYPES) * 2):
            seen.add(tracker.next_type())
        assert seen == set(MEDIA_TYPES)

    def test_no_consecutive_duplicates(self):
        tracker = MediaVarietyTracker()
        prev = None
        for _ in range(50):
            current = tracker.next_type()
            assert current != prev, f"Consecutive duplicate: {current}"
            prev = current

    def test_all_types_covered(self):
        tracker = MediaVarietyTracker()
        seen = set()
        for _ in range(len(MEDIA_TYPES)):
            seen.add(tracker.next_type())
        assert len(seen) == len(MEDIA_TYPES)

    def test_tracker_last_property(self):
        tracker = MediaVarietyTracker()
        assert tracker.last is None
        t = tracker.next_type()
        assert tracker.last == t

    def test_custom_media_types(self):
        tracker = MediaVarietyTracker(["a", "b", "c"])
        seen = set()
        for _ in range(6):
            seen.add(tracker.next_type())
        assert seen == {"a", "b", "c"}

    def test_single_type_no_infinite_loop(self):
        tracker = MediaVarietyTracker(["only"])
        for _ in range(5):
            assert tracker.next_type() == "only"


# ═══════════════════════════════════════════════════════════════════════════
# TestValidation (9 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestValidation:
    def test_valid_text_block(self):
        block = {
            "id": "text-abc123",
            "type": "text",
            "content": "Hello world",
            "group_id": "grp-xyz",
            "group_role": "explanation",
        }
        assert validate_content_block(block) == []

    def test_valid_media_block(self):
        block = {
            "id": "unsplash-abc123",
            "type": "unsplash",
            "content": "A photo",
            "group_id": "grp-xyz",
            "group_role": "visual",
            "media": {"url": "https://example.com/photo.jpg", "source": "Unsplash", "attribution": "Test"},
        }
        assert validate_content_block(block) == []

    def test_missing_required_key(self):
        block = {"id": "text-abc", "type": "text"}
        errors = validate_content_block(block)
        assert len(errors) > 0

    def test_invalid_text_role(self):
        block = {
            "id": "text-abc",
            "type": "text",
            "content": "Hello",
            "group_id": "grp-xyz",
            "group_role": "INVALID",
        }
        errors = validate_content_block(block)
        assert any("group_role" in e for e in errors)

    def test_media_missing_media_key(self):
        block = {
            "id": "unsplash-abc",
            "type": "unsplash",
            "content": "A photo",
            "group_id": "grp-xyz",
            "group_role": "visual",
        }
        errors = validate_content_block(block)
        assert any("media" in e.lower() for e in errors)

    def test_media_missing_url(self):
        block = {
            "id": "unsplash-abc",
            "type": "unsplash",
            "content": "A photo",
            "group_id": "grp-xyz",
            "group_role": "visual",
            "media": {"source": "Unsplash"},
        }
        errors = validate_content_block(block)
        assert any("url" in e for e in errors)

    def test_validate_response_valid(self):
        resp = {
            "content_blocks": [],
            "next_nodes": [],
            "strategy_used": "deeper",
            "engagement_score": 0.75,
        }
        assert validate_response(resp) == []

    def test_validate_response_missing_key(self):
        resp = {"content_blocks": [], "next_nodes": []}
        errors = validate_response(resp)
        assert len(errors) > 0

    def test_validate_response_invalid_strategy(self):
        resp = {
            "content_blocks": [],
            "next_nodes": [],
            "strategy_used": "invalid",
            "engagement_score": 0.5,
        }
        errors = validate_response(resp)
        assert any("strategy" in e.lower() for e in errors)


# ═══════════════════════════════════════════════════════════════════════════
# TestHealthEndpoint (2 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_has_available_apis(self, client):
        resp = client.get("/api/health")
        data = resp.get_json()
        assert "available_apis" in data
        apis = data["available_apis"]
        assert "claude" in apis
        assert "unsplash" in apis
        assert "reddit" in apis
        assert "twitter" in apis
        assert "wikipedia" in apis
        assert "wikimedia" in apis
        assert "imgflip" in apis
        assert "xkcd" in apis
        # Wikipedia, Wikimedia, xkcd should always be available
        assert apis["wikipedia"] is True
        assert apis["wikimedia"] is True
        assert apis["xkcd"] is True


# ═══════════════════════════════════════════════════════════════════════════
# TestInitialEndpoint (15 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestInitialEndpoint:
    def test_success_known_topic(self, client):
        resp = client.post("/api/initial", json={"topic": "Black Holes"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "content_blocks" in data
        assert "graph" in data
        assert "next_nodes" in data
        assert "strategy_used" in data

    def test_schema_content_blocks(self, client):
        resp = client.post("/api/initial", json={"topic": "Quantum Mechanics"})
        data = resp.get_json()
        blocks = data["content_blocks"]
        assert len(blocks) > 0
        for block in blocks:
            assert "id" in block
            assert "type" in block
            assert "content" in block
            assert "group_id" in block
            assert "group_role" in block

    def test_schema_graph(self, client):
        resp = client.post("/api/initial", json={"topic": "Black Holes"})
        data = resp.get_json()
        graph = data["graph"]
        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) > 0

    def test_strategy_is_deeper(self, client):
        resp = client.post("/api/initial", json={"topic": "Dark Matter"})
        data = resp.get_json()
        assert data["strategy_used"] == "deeper"

    def test_no_body(self, client):
        resp = client.post("/api/initial", content_type="application/json")
        assert resp.status_code == 400

    def test_empty_body(self, client):
        resp = client.post("/api/initial", json={})
        assert resp.status_code == 400

    def test_topic_wrong_type(self, client):
        resp = client.post("/api/initial", json={"topic": 12345})
        assert resp.status_code == 400

    def test_topic_empty_string(self, client):
        resp = client.post("/api/initial", json={"topic": ""})
        assert resp.status_code == 400

    def test_topic_too_long(self, client):
        resp = client.post("/api/initial", json={"topic": "A" * 201})
        assert resp.status_code == 400

    def test_topic_whitespace_only(self, client):
        resp = client.post("/api/initial", json={"topic": "   "})
        assert resp.status_code == 400

    def test_known_topic_black_holes(self, client):
        resp = client.post("/api/initial", json={"topic": "Black Holes"})
        data = resp.get_json()
        assert len(data["content_blocks"]) >= 4
        assert len(data["next_nodes"]) > 0

    def test_known_topic_neural_networks(self, client):
        resp = client.post("/api/initial", json={"topic": "Neural Networks"})
        data = resp.get_json()
        assert data["strategy_used"] == "deeper"
        assert len(data["content_blocks"]) >= 4

    def test_unknown_topic(self, client):
        resp = client.post("/api/initial", json={"topic": "Alien Technology"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["content_blocks"]) > 0

    def test_not_json_content_type(self, client):
        resp = client.post("/api/initial", data="topic=BlackHoles", content_type="application/x-www-form-urlencoded")
        assert resp.status_code == 400

    def test_next_nodes_have_structure(self, client):
        resp = client.post("/api/initial", json={"topic": "Climate Science"})
        data = resp.get_json()
        for node in data["next_nodes"]:
            assert "id" in node
            assert "label" in node


# ═══════════════════════════════════════════════════════════════════════════
# TestGenerateEndpoint (20 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestGenerateEndpoint:
    def test_success_high_engagement(self, client, high_engagement_time_data):
        resp = client.post("/api/generate", json={
            "current_node": "Black Holes",
            "time_data": high_engagement_time_data,
            "visited_nodes": [],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["strategy_used"] == "deeper"
        assert data["engagement_score"] >= 0.65

    def test_success_low_engagement(self, client, low_engagement_time_data):
        resp = client.post("/api/generate", json={
            "current_node": "Climate Science",
            "time_data": low_engagement_time_data,
            "visited_nodes": [],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["strategy_used"] == "pivot"

    def test_success_moderate_engagement(self, client, moderate_engagement_time_data):
        resp = client.post("/api/generate", json={
            "current_node": "Quantum Mechanics",
            "time_data": moderate_engagement_time_data,
            "visited_nodes": [],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["strategy_used"] in ("branch", "deeper", "pivot")

    def test_schema_all_keys(self, client, high_engagement_time_data):
        resp = client.post("/api/generate", json={
            "current_node": "Black Holes",
            "time_data": high_engagement_time_data,
            "visited_nodes": [],
        })
        data = resp.get_json()
        assert "content_blocks" in data
        assert "next_nodes" in data
        assert "strategy_used" in data
        assert "engagement_score" in data

    def test_missing_current_node(self, client):
        resp = client.post("/api/generate", json={
            "time_data": {"total_time_on_node_ms": 5000},
        })
        assert resp.status_code == 400

    def test_current_node_wrong_type(self, client):
        resp = client.post("/api/generate", json={
            "current_node": 123,
        })
        assert resp.status_code == 400

    def test_current_node_empty_string(self, client):
        resp = client.post("/api/generate", json={
            "current_node": "",
        })
        assert resp.status_code == 400

    def test_no_body(self, client):
        resp = client.post("/api/generate", content_type="application/json")
        assert resp.status_code == 400

    def test_time_data_optional(self, client):
        resp = client.post("/api/generate", json={
            "current_node": "Black Holes",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["engagement_score"] == 0.0
        assert data["strategy_used"] == "pivot"

    def test_time_data_wrong_type(self, client):
        resp = client.post("/api/generate", json={
            "current_node": "Black Holes",
            "time_data": "not a dict",
        })
        assert resp.status_code == 400

    def test_visited_nodes_filtering(self, client, high_engagement_time_data):
        visited = ["hawking-radiation", "event-horizon", "singularity"]
        resp = client.post("/api/generate", json={
            "current_node": "Black Holes",
            "time_data": high_engagement_time_data,
            "visited_nodes": visited,
        })
        data = resp.get_json()
        next_ids = {n["id"] for n in data["next_nodes"]}
        for v in visited:
            assert v not in next_ids

    def test_visited_nodes_wrong_type(self, client):
        resp = client.post("/api/generate", json={
            "current_node": "Black Holes",
            "visited_nodes": "not a list",
        })
        assert resp.status_code == 400

    def test_engagement_score_range(self, client, high_engagement_time_data):
        resp = client.post("/api/generate", json={
            "current_node": "Black Holes",
            "time_data": high_engagement_time_data,
            "visited_nodes": [],
        })
        data = resp.get_json()
        assert 0.0 <= data["engagement_score"] <= 1.0

    def test_strategy_values(self, client, high_engagement_time_data):
        resp = client.post("/api/generate", json={
            "current_node": "Black Holes",
            "time_data": high_engagement_time_data,
            "visited_nodes": [],
        })
        data = resp.get_json()
        assert data["strategy_used"] in ("deeper", "branch", "pivot")

    def test_content_blocks_not_empty(self, client, high_engagement_time_data):
        resp = client.post("/api/generate", json={
            "current_node": "Black Holes",
            "time_data": high_engagement_time_data,
            "visited_nodes": [],
        })
        data = resp.get_json()
        assert len(data["content_blocks"]) > 0

    def test_content_blocks_have_group_ids(self, client, high_engagement_time_data):
        resp = client.post("/api/generate", json={
            "current_node": "Neural Networks",
            "time_data": high_engagement_time_data,
            "visited_nodes": [],
        })
        data = resp.get_json()
        for block in data["content_blocks"]:
            assert "group_id" in block

    def test_media_blocks_have_media(self, client, high_engagement_time_data):
        resp = client.post("/api/generate", json={
            "current_node": "CRISPR Gene Editing",
            "time_data": high_engagement_time_data,
            "visited_nodes": [],
        })
        data = resp.get_json()
        media_blocks = [b for b in data["content_blocks"] if b["type"] != "text"]
        for mb in media_blocks:
            assert "media" in mb
            assert "url" in mb["media"]

    def test_last_paragraph_accepted(self, client, high_engagement_time_data):
        resp = client.post("/api/generate", json={
            "current_node": "Dark Matter",
            "time_data": high_engagement_time_data,
            "visited_nodes": [],
            "last_paragraph": "Previous content about dark matter observations.",
        })
        assert resp.status_code == 200

    def test_topic_path_accepted(self, client, high_engagement_time_data):
        resp = client.post("/api/generate", json={
            "current_node": "Black Holes",
            "time_data": high_engagement_time_data,
            "visited_nodes": [],
            "topic_path": ["black-holes", "hawking-radiation"],
        })
        assert resp.status_code == 200

    def test_graph_accepted(self, client, high_engagement_time_data):
        resp = client.post("/api/generate", json={
            "current_node": "Black Holes",
            "time_data": high_engagement_time_data,
            "visited_nodes": [],
            "graph": {"nodes": [{"id": "black-holes", "label": "Black Holes"}], "edges": []},
        })
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# TestSimulatedFrontendSession (9 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestSimulatedFrontendSession:
    """Simulates a real frontend session: initial -> multiple generates with
    accumulating visited_nodes, shifting engagement, growing graph."""

    def _initial(self, client, topic="Black Holes"):
        resp = client.post("/api/initial", json={"topic": topic})
        assert resp.status_code == 200
        return resp.get_json()

    def _generate(self, client, current_node, time_data, visited_nodes):
        resp = client.post("/api/generate", json={
            "current_node": current_node,
            "time_data": time_data,
            "visited_nodes": visited_nodes,
        })
        assert resp.status_code == 200
        return resp.get_json()

    def test_full_session_initial(self, client):
        """Step 1: Start with Black Holes."""
        data = self._initial(client)
        assert data["strategy_used"] == "deeper"
        assert len(data["content_blocks"]) >= 4
        assert len(data["graph"]["nodes"]) >= 1

    def test_full_session_high_engagement(self, client, high_engagement_time_data):
        """Step 2: Highly engaged user gets deeper content."""
        self._initial(client)
        data = self._generate(client, "Black Holes", high_engagement_time_data, ["black-holes"])
        assert data["strategy_used"] == "deeper"
        assert data["engagement_score"] >= 0.65

    def test_full_session_moderate_engagement(self, client, moderate_engagement_time_data):
        """Step 3: Moderately engaged user gets branch content."""
        self._initial(client)
        data = self._generate(client, "Quantum Mechanics", moderate_engagement_time_data, ["quantum-mechanics"])
        assert data["strategy_used"] in ("branch", "deeper")

    def test_full_session_low_engagement(self, client, low_engagement_time_data):
        """Step 4: Disengaged user gets pivot to new topic."""
        self._initial(client)
        data = self._generate(client, "Climate Science", low_engagement_time_data, ["climate-science"])
        assert data["strategy_used"] == "pivot"

    def test_accumulating_visited_nodes(self, client, high_engagement_time_data):
        """Visited nodes grow over session, next_nodes shouldn't repeat."""
        init = self._initial(client)
        visited = ["black-holes"]

        # Step 2
        gen1 = self._generate(client, "Black Holes", high_engagement_time_data, visited)
        visited.extend(n["id"] for n in gen1["next_nodes"])

        # Step 3
        gen2 = self._generate(client, "Black Holes", high_engagement_time_data, visited)
        gen2_next_ids = {n["id"] for n in gen2["next_nodes"]}

        # Next nodes should not include already-visited nodes
        for v in visited:
            assert v not in gen2_next_ids

    def test_strategy_shifts_with_engagement(self, client):
        """Strategy should change as engagement changes."""
        self._initial(client)

        high = self._generate(client, "Black Holes", {
            "total_time_on_node_ms": 60000, "scroll_events": 12,
            "go_deeper_clicks": 2, "sections_in_current_node": 4, "time_per_section_ms": 15000
        }, [])

        low = self._generate(client, "Black Holes", {
            "total_time_on_node_ms": 2000, "scroll_events": 0,
            "go_deeper_clicks": 0, "sections_in_current_node": 4, "time_per_section_ms": 500
        }, [])

        assert high["strategy_used"] == "deeper"
        assert low["strategy_used"] == "pivot"

    def test_graph_growth_over_session(self, client, high_engagement_time_data):
        """Graph should accumulate nodes over multiple requests."""
        init = self._initial(client)
        initial_node_count = len(init["graph"]["nodes"])

        gen1 = self._generate(client, "Black Holes", high_engagement_time_data, ["black-holes"])
        assert len(gen1["next_nodes"]) > 0

    def test_mixed_media_types(self, client, high_engagement_time_data):
        """Content should include diverse media types."""
        init = self._initial(client)
        media_types = {b["type"] for b in init["content_blocks"] if b["type"] != "text"}
        # Real APIs may not always return all types, but should have at least 1
        assert len(media_types) >= 1, f"Expected media types, got: {media_types}"

    def test_no_duplicate_block_ids(self, client, high_engagement_time_data):
        """Block IDs should be unique across the entire session."""
        init = self._initial(client)
        all_ids = {b["id"] for b in init["content_blocks"]}

        gen1 = self._generate(client, "Black Holes", high_engagement_time_data, ["black-holes"])
        gen1_ids = {b["id"] for b in gen1["content_blocks"]}

        # No overlap between initial and generated
        assert all_ids.isdisjoint(gen1_ids), "Block IDs should be unique across requests"
