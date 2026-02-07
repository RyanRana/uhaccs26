"""
External API client wrappers for SciScroll.

Each client: constructor takes optional credentials, has is_available property,
methods return None on failure (never raise to caller).
"""

import json
import logging
import os
import random

import requests

logger = logging.getLogger(__name__)


# ── Claude (Anthropic) ──────────────────────────────────────────────────

class ClaudeClient:
    """Wrapper for Anthropic's Claude Messages API."""

    def __init__(self, api_key=None):
        self._api_key = api_key
        self._client = None
        if api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=api_key)
            except Exception as e:
                logger.warning("Failed to initialize Anthropic client: %s", e)

    @property
    def is_available(self):
        return self._client is not None

    def generate(self, system_prompt, user_prompt, max_tokens=2048, model="claude-sonnet-4-5-20250929"):
        """Call Claude and return the text response. Returns None on failure."""
        if not self.is_available:
            return None
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error("Claude API error: %s", e)
            return None

    def generate_json(self, system_prompt, user_prompt, max_tokens=2048, model="claude-sonnet-4-5-20250929"):
        """Call Claude and parse the response as JSON. Returns None on failure."""
        text = self.generate(system_prompt, user_prompt, max_tokens, model)
        if text is None:
            return None
        try:
            # Claude may wrap JSON in markdown code blocks
            cleaned = text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = lines[1:]  # skip ```json
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines)
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Failed to parse Claude JSON response: %s", e)
            return None


# ── Unsplash ─────────────────────────────────────────────────────────────

class UnsplashClient:
    """Wrapper for Unsplash photo search API."""

    BASE_URL = "https://api.unsplash.com"

    def __init__(self, access_key=None):
        self._access_key = access_key

    @property
    def is_available(self):
        return self._access_key is not None

    def search_photos(self, query, per_page=5):
        """Search for photos. Returns media dict or None."""
        if not self.is_available:
            return None
        try:
            resp = requests.get(
                f"{self.BASE_URL}/search/photos",
                params={"query": query, "per_page": per_page, "orientation": "landscape"},
                headers={"Authorization": f"Client-ID {self._access_key}"},
                timeout=10,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if not results:
                return None
            photo = results[0]
            return {
                "url": photo["urls"]["regular"],
                "source": "Unsplash",
                "attribution": f"Photo by {photo['user']['name']} on Unsplash",
                "width": photo.get("width"),
                "height": photo.get("height"),
            }
        except Exception as e:
            logger.error("Unsplash API error: %s", e)
            return None


# ── Reddit ───────────────────────────────────────────────────────────────

class RedditClient:
    """Wrapper for Reddit search via OAuth2 (no PRAW dependency)."""

    TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
    SEARCH_URL = "https://oauth.reddit.com/search"
    DEFAULT_SUBREDDITS = ["science", "askscience", "EverythingScience", "Physics", "biology"]

    def __init__(self, client_id=None, client_secret=None, user_agent="SciScroll/1.0"):
        self._client_id = client_id
        self._client_secret = client_secret
        self._user_agent = user_agent
        self._token = None

    @property
    def is_available(self):
        return self._client_id is not None and self._client_secret is not None

    def _get_token(self):
        if self._token:
            return self._token
        try:
            resp = requests.post(
                self.TOKEN_URL,
                auth=(self._client_id, self._client_secret),
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": self._user_agent},
                timeout=10,
            )
            resp.raise_for_status()
            self._token = resp.json().get("access_token")
            return self._token
        except Exception as e:
            logger.error("Reddit token error: %s", e)
            return None

    def search_posts(self, query, limit=5):
        """Search Reddit for relevant science posts. Returns media dict or None."""
        if not self.is_available:
            return None
        token = self._get_token()
        if not token:
            return None
        try:
            subreddit_filter = " OR ".join(f"subreddit:{s}" for s in self.DEFAULT_SUBREDDITS)
            resp = requests.get(
                self.SEARCH_URL,
                params={"q": f"{query} ({subreddit_filter})", "sort": "relevance", "limit": limit, "type": "link"},
                headers={"Authorization": f"Bearer {token}", "User-Agent": self._user_agent},
                timeout=10,
            )
            resp.raise_for_status()
            posts = resp.json().get("data", {}).get("children", [])
            for post in posts:
                data = post.get("data", {})
                if data.get("score", 0) > 10:
                    return {
                        "url": f"https://reddit.com{data.get('permalink', '')}",
                        "source": f"r/{data.get('subreddit', 'science')}",
                        "attribution": f"Posted by u/{data.get('author', 'unknown')} in r/{data.get('subreddit', 'science')}",
                        "width": None,
                        "height": None,
                        "title": data.get("title", ""),
                        "score": data.get("score", 0),
                    }
            return None
        except Exception as e:
            logger.error("Reddit API error: %s", e)
            return None


# ── Twitter / X API v2 ──────────────────────────────────────────────────

class TwitterClient:
    """Wrapper for X API v2 recent tweet search."""

    SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"

    def __init__(self, bearer_token=None):
        self._bearer_token = bearer_token

    @property
    def is_available(self):
        return self._bearer_token is not None

    def search_tweets(self, query, max_results=10):
        """Search recent tweets. Returns media dict or None."""
        if not self.is_available:
            return None
        try:
            science_query = f"{query} (science OR research OR study) -is:retweet lang:en"
            resp = requests.get(
                self.SEARCH_URL,
                params={
                    "query": science_query,
                    "max_results": max_results,
                    "tweet.fields": "author_id,created_at,public_metrics,text",
                    "expansions": "author_id",
                    "user.fields": "name,username",
                },
                headers={"Authorization": f"Bearer {self._bearer_token}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            tweets = data.get("data", [])
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
            if not tweets:
                return None
            tweet = tweets[0]
            author = users.get(tweet.get("author_id"), {})
            metrics = tweet.get("public_metrics", {})
            return {
                "url": f"https://twitter.com/{author.get('username', 'unknown')}/status/{tweet['id']}",
                "source": "Twitter/X",
                "attribution": f"@{author.get('username', 'unknown')} ({author.get('name', '')})",
                "width": None,
                "height": None,
                "text": tweet.get("text", ""),
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
            }
        except Exception as e:
            logger.error("Twitter API error: %s", e)
            return None


# ── Wikipedia ────────────────────────────────────────────────────────────

class WikipediaClient:
    """Wrapper for Wikipedia MediaWiki API. No API key needed."""

    API_URL = "https://en.wikipedia.org/w/api.php"
    SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "SciScroll/1.0 (educational project)"})

    @property
    def is_available(self):
        return True

    def _try_page_image(self, title):
        """Try to get the main image for an exact Wikipedia article title."""
        try:
            resp = self._session.get(
                self.API_URL,
                params={
                    "action": "query",
                    "prop": "pageimages",
                    "format": "json",
                    "piprop": "original",
                    "titles": title,
                },
                timeout=10,
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for page in pages.values():
                original = page.get("original")
                if original:
                    return {
                        "url": original["source"],
                        "source": "Wikipedia",
                        "attribution": f"Image from Wikipedia article: {title}",
                        "width": original.get("width"),
                        "height": original.get("height"),
                    }
            return None
        except Exception as e:
            logger.error("Wikipedia image error for '%s': %s", title, e)
            return None

    def _search_title(self, query):
        """Use Wikipedia opensearch to fuzzy-match a query to a real article title."""
        try:
            resp = self._session.get(
                self.API_URL,
                params={
                    "action": "opensearch",
                    "search": query,
                    "limit": 1,
                    "namespace": 0,
                    "format": "json",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            # opensearch returns [query, [titles], [descriptions], [urls]]
            if len(data) >= 2 and data[1]:
                return data[1][0]
            return None
        except Exception as e:
            logger.error("Wikipedia opensearch error: %s", e)
            return None

    def get_page_image(self, topic):
        """Get the main image for a Wikipedia article. Returns media dict or None.

        Tries exact title first, then uses opensearch to resolve free-form
        queries to real article titles.
        """
        # Try exact title
        result = self._try_page_image(topic)
        if result:
            return result

        # Fuzzy search: resolve free-form query to a real article title
        resolved = self._search_title(topic)
        if resolved and resolved.lower() != topic.lower():
            result = self._try_page_image(resolved)
            if result:
                return result

        return None

    def get_summary(self, topic):
        """Get the plain text summary for a Wikipedia article. Returns string or None."""
        try:
            resp = self._session.get(
                f"{self.SUMMARY_URL}/{topic.replace(' ', '_')}",
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("extract")
        except Exception as e:
            logger.error("Wikipedia summary error: %s", e)
            return None


# ── Wikimedia Commons ────────────────────────────────────────────────────

class WikimediaClient:
    """Wrapper for Wikimedia Commons API for scientific diagrams and charts."""

    API_URL = "https://commons.wikimedia.org/w/api.php"

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "SciScroll/1.0 (educational project)"})

    @property
    def is_available(self):
        return True

    def search_diagrams(self, query, limit=10):
        """Search Wikimedia Commons for diagrams/charts. Returns media dict or None."""
        try:
            # Use more specific search to avoid unrelated images
            search_query = f'"{query}" filetype:svg OR filetype:png (diagram OR schematic OR illustration OR physics OR science)'
            resp = self._session.get(
                self.API_URL,
                params={
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": search_query,
                    "gsrnamespace": "6",  # File namespace
                    "gsrlimit": limit,
                    "prop": "imageinfo",
                    "iiprop": "url|size|extmetadata",
                    "format": "json",
                },
                timeout=10,
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            if not pages:
                # Fallback: simpler query without filetype filters
                resp = self._session.get(
                    self.API_URL,
                    params={
                        "action": "query",
                        "generator": "search",
                        "gsrsearch": f"{query} diagram",
                        "gsrnamespace": "6",
                        "gsrlimit": limit,
                        "prop": "imageinfo",
                        "iiprop": "url|size|extmetadata",
                        "format": "json",
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                pages = resp.json().get("query", {}).get("pages", {})

            import re
            # Filter out photos, logos, and unrelated images
            skip_keywords = ["photo", "photograph", "portrait", "logo", "flag",
                             "championship", "competition", "tournament", "award",
                             "ceremony", "screenshot", "map of"]
            for page in sorted(pages.values(), key=lambda p: p.get("index", 999)):
                title = page.get("title", "").lower()
                if any(kw in title for kw in skip_keywords):
                    continue
                imageinfo = page.get("imageinfo", [{}])[0]
                url = imageinfo.get("url")
                if url and any(url.lower().endswith(ext) for ext in (".svg", ".png", ".jpg", ".jpeg", ".gif")):
                    extmeta = imageinfo.get("extmetadata", {})
                    description = extmeta.get("ImageDescription", {}).get("value", "")
                    description = re.sub(r"<[^>]+>", "", description)[:200]
                    return {
                        "url": url,
                        "source": "Wikimedia Commons",
                        "attribution": f"Wikimedia Commons: {page.get('title', 'File')}",
                        "width": imageinfo.get("width"),
                        "height": imageinfo.get("height"),
                        "description": description,
                    }
            return None
        except Exception as e:
            logger.error("Wikimedia Commons error: %s", e)
            return None


# ── Imgflip (Memes) ─────────────────────────────────────────────────────

class ImgflipClient:
    """Wrapper for Imgflip meme API."""

    MEMES_URL = "https://api.imgflip.com/get_memes"
    CAPTION_URL = "https://api.imgflip.com/caption_image"

    def __init__(self, username=None, password=None):
        self._username = username
        self._password = password
        self._memes_cache = None

    @property
    def is_available(self):
        return self._username is not None and self._password is not None

    def _get_memes(self):
        if self._memes_cache:
            return self._memes_cache
        try:
            resp = requests.get(self.MEMES_URL, timeout=10)
            resp.raise_for_status()
            self._memes_cache = resp.json().get("data", {}).get("memes", [])
            return self._memes_cache
        except Exception as e:
            logger.error("Imgflip get_memes error: %s", e)
            return []

    def get_meme(self, topic, top_text=None, bottom_text=None):
        """Get or create a meme related to the topic. Returns media dict or None."""
        memes = self._get_memes()
        if not memes:
            return None

        # Pick a popular meme template (top 30 are most recognizable)
        template = random.choice(memes[:30]) if memes else None
        if not template:
            return None

        if self.is_available and top_text and bottom_text:
            try:
                resp = requests.post(
                    self.CAPTION_URL,
                    data={
                        "template_id": template["id"],
                        "username": self._username,
                        "password": self._password,
                        "text0": top_text,
                        "text1": bottom_text,
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                result = resp.json()
                if result.get("success"):
                    return {
                        "url": result["data"]["url"],
                        "source": "Imgflip",
                        "attribution": f"Meme template: {template['name']}",
                        "width": template.get("width"),
                        "height": template.get("height"),
                    }
            except Exception as e:
                logger.error("Imgflip caption error: %s", e)

        # Fallback: return the template image without captioning
        return {
            "url": template["url"],
            "source": "Imgflip",
            "attribution": f"Meme template: {template['name']}",
            "width": template.get("width"),
            "height": template.get("height"),
        }


# ── xkcd ─────────────────────────────────────────────────────────────────

class XkcdClient:
    """Wrapper for xkcd comics with a hardcoded science-topic index."""

    COMIC_URL = "https://xkcd.com/{num}/info.0.json"
    LATEST_URL = "https://xkcd.com/info.0.json"

    # Curated index of science-relevant xkcd comics by keyword
    SCIENCE_COMICS = {
        "black hole": [2135, 1758],
        "gravity": [681, 2735, 852],
        "quantum": [1240, 1861, 2735, 1591],
        "entanglement": [1591],
        "physics": [793, 669, 730, 1489],
        "space": [1356, 1939, 2333, 1110],
        "astronomy": [1758, 2360, 2014],
        "dna": [1605, 2131],
        "gene": [1605, 2131],
        "crispr": [2131],
        "biology": [2131, 1605, 1430],
        "evolution": [1605, 2300],
        "climate": [1732, 2500, 1321],
        "temperature": [1732, 2500],
        "carbon": [1732],
        "ocean": [1321, 2561],
        "neural network": [2173, 1838],
        "machine learning": [2173, 1838, 1425],
        "ai": [2173, 1838, 948],
        "computer": [2173, 1838, 378],
        "math": [55, 435, 2042, 687],
        "statistics": [2400, 552, 882],
        "chemistry": [2561, 435],
        "rocket": [1356, 2333],
        "planet": [2360, 1071],
        "star": [2360, 1758, 1071],
        "dark matter": [2135],
        "dark energy": [2135],
        "cosmology": [2135, 2360],
        "neutrino": [2360],
        "particle": [2360, 793],
        "energy": [1732, 2500, 1321],
        "robot": [2128, 948],
        "virus": [2287, 2355],
        "vaccine": [2515],
        "brain": [2173, 1838],
        "universe": [2135, 482, 1071],
    }

    # Group keywords by science domain for domain-aware fallback
    DOMAIN_KEYWORDS = {
        "physics": ["black hole", "gravity", "quantum", "entanglement", "physics",
                     "dark matter", "dark energy", "cosmology", "neutrino", "particle",
                     "energy", "space", "astronomy", "rocket", "planet", "star", "universe"],
        "biology": ["dna", "gene", "crispr", "biology", "evolution", "virus", "vaccine", "brain"],
        "climate": ["climate", "temperature", "carbon", "ocean"],
        "cs": ["neural network", "machine learning", "ai", "computer", "robot"],
        "math": ["math", "statistics", "chemistry"],
    }

    def __init__(self):
        self._latest_num = None

    @property
    def is_available(self):
        return True

    def _get_latest_num(self):
        if self._latest_num:
            return self._latest_num
        try:
            resp = requests.get(self.LATEST_URL, timeout=10)
            resp.raise_for_status()
            self._latest_num = resp.json()["num"]
            return self._latest_num
        except Exception:
            return 2900  # reasonable fallback

    def _fetch_comic(self, num):
        try:
            resp = requests.get(self.COMIC_URL.format(num=num), timeout=10)
            resp.raise_for_status()
            comic = resp.json()
            return {
                "url": comic["img"],
                "source": "xkcd",
                "attribution": f"xkcd #{comic['num']}: {comic['title']}",
                "width": None,
                "height": None,
                "alt_text": comic.get("alt", ""),
                "title": comic.get("title", ""),
            }
        except Exception as e:
            logger.error("xkcd fetch error for #%s: %s", num, e)
            return None

    def _get_domain_for_query(self, query_lower):
        """Determine which science domain a query belongs to."""
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw in query_lower:
                    return domain
        return None

    def _get_domain_comics(self, domain):
        """Get all comic numbers for a given science domain."""
        comics = set()
        if domain and domain in self.DOMAIN_KEYWORDS:
            for kw in self.DOMAIN_KEYWORDS[domain]:
                if kw in self.SCIENCE_COMICS:
                    comics.update(self.SCIENCE_COMICS[kw])
        return comics

    def search_comics(self, query):
        """Find a relevant xkcd comic by keyword matching. Returns media dict or None."""
        query_lower = query.lower()

        # Check all keywords — keyword must appear in the query (not reverse)
        matching_comics = set()
        for keyword, nums in self.SCIENCE_COMICS.items():
            if keyword in query_lower:
                matching_comics.update(nums)

        if matching_comics:
            comic_num = random.choice(list(matching_comics))
            return self._fetch_comic(comic_num)

        # Fallback: pick from same science domain only, not the entire index
        domain = self._get_domain_for_query(query_lower)
        domain_comics = self._get_domain_comics(domain)
        if domain_comics:
            return self._fetch_comic(random.choice(list(domain_comics)))

        # No domain match at all — return None instead of random comic
        return None


# ── Factory ──────────────────────────────────────────────────────────────

def create_api_clients():
    """Create all API clients from environment variables.

    Uses `or None` so empty strings from .env are treated as missing.
    """
    return {
        "claude": ClaudeClient(os.environ.get("ANTHROPIC_API_KEY") or None),
        "unsplash": UnsplashClient(os.environ.get("UNSPLASH_ACCESS_KEY") or None),
        "reddit": RedditClient(
            os.environ.get("REDDIT_CLIENT_ID") or None,
            os.environ.get("REDDIT_CLIENT_SECRET") or None,
            os.environ.get("REDDIT_USER_AGENT", "SciScroll/1.0"),
        ),
        "twitter": TwitterClient(os.environ.get("TWITTER_BEARER_TOKEN") or None),
        "wikipedia": WikipediaClient(),
        "wikimedia": WikimediaClient(),
        "imgflip": ImgflipClient(
            os.environ.get("IMGFLIP_USERNAME") or None,
            os.environ.get("IMGFLIP_PASSWORD") or None,
        ),
        "xkcd": XkcdClient(),
    }


def get_available_apis(api_clients):
    """Return a dict of API name → availability boolean."""
    return {name: client.is_available for name, client in api_clients.items()}
