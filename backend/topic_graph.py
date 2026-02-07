"""
Predefined topic/subtopic knowledge graph for SciScroll.

6 main topics, ~80 total nodes. Each node has an id (slug), label,
description, and connections to deeper/branch/pivot subtopics.
"""

import re


def slugify(text):
    """Convert text to a URL-safe slug."""
    if not text or not text.strip():
        return ""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    s = s.strip("-")
    if len(s) > 80:
        s = s[:80].rsplit("-", 1)[0]
    return s


def _node(label, description):
    return {"id": slugify(label), "label": label, "description": description}


# ── All nodes in the graph ──────────────────────────────────────────────

NODES = {}

def _register(*nodes):
    for n in nodes:
        NODES[n["id"]] = n


# ── Black Holes ─────────────────────────────────────────────────────────

_register(
    _node("Black Holes", "Regions of spacetime where gravity is so strong nothing can escape"),
    _node("Hawking Radiation", "Theoretical radiation emitted by black holes due to quantum effects near the event horizon"),
    _node("Event Horizon", "The boundary beyond which nothing can return from a black hole"),
    _node("Singularity", "The infinitely dense point at the center of a black hole"),
    _node("Spaghettification", "The stretching of objects into thin shapes in extreme gravitational fields"),
    _node("Accretion Disks", "Rotating disks of matter spiraling into a black hole, emitting intense radiation"),
    _node("Stellar Collapse", "The gravitational collapse of a massive star at the end of its life"),
    _node("Neutron Stars", "Extremely dense remnants of massive stars composed almost entirely of neutrons"),
    _node("Gravitational Waves", "Ripples in spacetime caused by accelerating massive objects"),
    _node("General Relativity", "Einstein's theory describing gravity as the curvature of spacetime"),
    _node("Spacetime Curvature", "The bending of the four-dimensional fabric of the universe by mass and energy"),
    _node("Gravitational Lensing", "The bending of light from distant objects by massive foreground objects"),
)

# ── Quantum Mechanics ───────────────────────────────────────────────────

_register(
    _node("Quantum Mechanics", "The physics of particles at the atomic and subatomic scale"),
    _node("Wave-Particle Duality", "The concept that quantum entities exhibit both wave and particle properties"),
    _node("Quantum Entanglement", "A phenomenon where particles become correlated regardless of distance"),
    _node("Uncertainty Principle", "Heisenberg's limit on simultaneously knowing position and momentum"),
    _node("Superposition", "A quantum system existing in multiple states simultaneously until measured"),
    _node("Quantum Tunneling", "Particles passing through energy barriers they classically could not surmount"),
    _node("Decoherence", "The loss of quantum coherence through interaction with the environment"),
    _node("Quantum Computing", "Computing that exploits quantum phenomena like superposition and entanglement"),
    _node("Particle Physics", "The study of fundamental particles and forces of nature"),
    _node("Quantum Field Theory", "The framework combining quantum mechanics and special relativity"),
    _node("Standard Model", "The theoretical framework describing all known fundamental particles and forces except gravity"),
    _node("Condensed Matter", "The study of the physical properties of condensed phases of matter"),
)

# ── CRISPR Gene Editing ─────────────────────────────────────────────────

_register(
    _node("CRISPR Gene Editing", "A revolutionary tool for editing DNA sequences with precision"),
    _node("Cas9 Protein", "The molecular scissors that cuts DNA at a location specified by guide RNA"),
    _node("Guide RNA", "The programmable RNA molecule that directs Cas9 to its target DNA sequence"),
    _node("Off-Target Effects", "Unintended edits at sites similar to the target sequence"),
    _node("Gene Drives", "Genetic systems that spread a modified gene through a population"),
    _node("Base Editing", "A CRISPR variant that changes individual DNA letters without cutting the double strand"),
    _node("Prime Editing", "A search-and-replace genome editing approach with greater precision than Cas9"),
    _node("Synthetic Biology", "Designing and building new biological parts, devices, and systems"),
    _node("Epigenetics", "Heritable changes in gene expression that do not involve changes to the DNA sequence"),
    _node("Stem Cells", "Undifferentiated cells capable of developing into many different cell types"),
    _node("Genetic Disorders", "Diseases caused by abnormalities in an organism's genome"),
    _node("Immunotherapy", "Treating disease by activating or suppressing the immune system"),
    _node("Protein Folding", "The process by which a protein chain acquires its functional three-dimensional structure"),
)

# ── Dark Matter ─────────────────────────────────────────────────────────

_register(
    _node("Dark Matter", "Invisible matter making up about 27% of the universe's mass-energy"),
    _node("WIMPs", "Weakly Interacting Massive Particles, leading dark matter candidates"),
    _node("Dark Energy", "The mysterious force accelerating the expansion of the universe"),
    _node("Galaxy Rotation Curves", "Evidence for dark matter from the unexpected rotational speeds of galaxies"),
    _node("Bullet Cluster", "A galaxy cluster collision providing direct evidence for dark matter"),
    _node("Axions", "Hypothetical light particles proposed as dark matter candidates"),
    _node("Cosmic Microwave Background", "The thermal radiation left over from the Big Bang"),
    _node("Big Bang", "The prevailing cosmological model for the origin of the universe"),
    _node("Antimatter", "Matter composed of antiparticles with opposite charge to normal matter"),
    _node("Neutrinos", "Nearly massless particles that rarely interact with matter"),
    _node("Cosmic Inflation", "The rapid exponential expansion of the early universe"),
    _node("Hubble Tension", "The discrepancy in measurements of the universe's expansion rate"),
)

# ── Climate Science ─────────────────────────────────────────────────────

_register(
    _node("Climate Science", "The study of long-term weather patterns and Earth's climate system"),
    _node("Greenhouse Effect", "The trapping of heat by atmospheric gases warming Earth's surface"),
    _node("Carbon Cycle", "The circulation of carbon among the atmosphere, oceans, soil, and organisms"),
    _node("Ice Core Data", "Climate records preserved in layers of glacial ice spanning hundreds of thousands of years"),
    _node("Climate Models", "Mathematical simulations of the climate system used for projections"),
    _node("Albedo Effect", "The reflection of solar radiation back into space by surfaces like ice and clouds"),
    _node("Thermohaline Circulation", "Global ocean current system driven by temperature and salinity differences"),
    _node("Ocean Acidification", "The decrease in ocean pH caused by absorption of atmospheric CO2"),
    _node("Renewable Energy", "Energy from sources that are naturally replenished like solar, wind, and hydro"),
    _node("Atmospheric Chemistry", "The study of chemical compositions and reactions in Earth's atmosphere"),
    _node("Permafrost", "Permanently frozen ground containing vast stores of organic carbon"),
    _node("Biodiversity Loss", "The decline in the variety of life on Earth driven by human activities"),
    _node("Geoengineering", "Large-scale interventions to counteract climate change effects"),
)

# ── Neural Networks ─────────────────────────────────────────────────────

_register(
    _node("Neural Networks", "Computing systems inspired by biological neural networks in the brain"),
    _node("Backpropagation", "The algorithm for training neural networks by propagating error gradients backward"),
    _node("Convolutional Layers", "Neural network layers that detect spatial patterns using learnable filters"),
    _node("Transformers", "Attention-based architecture that revolutionized natural language processing"),
    _node("Attention Mechanism", "A technique allowing models to focus on relevant parts of the input"),
    _node("Activation Functions", "Mathematical functions that introduce nonlinearity into neural networks"),
    _node("Gradient Descent", "The optimization algorithm used to minimize loss during training"),
    _node("Reinforcement Learning", "Learning through trial and error using rewards and penalties"),
    _node("NLP", "Natural Language Processing: enabling machines to understand human language"),
    _node("Computer Vision", "Enabling machines to interpret and understand visual information"),
    _node("Generative AI", "AI systems that create new content including text, images, and code"),
    _node("Robotics", "The design and operation of robots, often combining AI with physical systems"),
    _node("Neuromorphic Computing", "Computing architectures modeled on the structure of biological brains"),
)


# ── Topic graph edges ───────────────────────────────────────────────────
# Maps each main topic → {deeper: [...], branch: [...], pivot: [...]}

TOPIC_GRAPH = {
    "black-holes": {
        "deeper": ["hawking-radiation", "event-horizon", "singularity", "spaghettification", "accretion-disks", "stellar-collapse"],
        "branch": ["neutron-stars", "gravitational-waves", "general-relativity", "spacetime-curvature", "gravitational-lensing"],
        "pivot": ["quantum-mechanics", "crispr-gene-editing", "neural-networks", "climate-science"],
    },
    "quantum-mechanics": {
        "deeper": ["wave-particle-duality", "quantum-entanglement", "uncertainty-principle", "superposition", "quantum-tunneling", "decoherence"],
        "branch": ["quantum-computing", "particle-physics", "quantum-field-theory", "standard-model", "condensed-matter"],
        "pivot": ["black-holes", "crispr-gene-editing", "dark-matter", "climate-science"],
    },
    "crispr-gene-editing": {
        "deeper": ["cas9-protein", "guide-rna", "off-target-effects", "gene-drives", "base-editing", "prime-editing"],
        "branch": ["synthetic-biology", "epigenetics", "stem-cells", "genetic-disorders", "immunotherapy", "protein-folding"],
        "pivot": ["dark-matter", "neural-networks", "quantum-mechanics", "climate-science"],
    },
    "dark-matter": {
        "deeper": ["wimps", "gravitational-lensing", "dark-energy", "galaxy-rotation-curves", "bullet-cluster", "axions"],
        "branch": ["cosmic-microwave-background", "big-bang", "antimatter", "neutrinos", "cosmic-inflation", "hubble-tension"],
        "pivot": ["crispr-gene-editing", "neural-networks", "climate-science", "quantum-mechanics"],
    },
    "climate-science": {
        "deeper": ["greenhouse-effect", "carbon-cycle", "ice-core-data", "climate-models", "albedo-effect", "thermohaline-circulation"],
        "branch": ["ocean-acidification", "renewable-energy", "atmospheric-chemistry", "permafrost", "biodiversity-loss", "geoengineering"],
        "pivot": ["black-holes", "quantum-mechanics", "crispr-gene-editing", "neural-networks"],
    },
    "neural-networks": {
        "deeper": ["backpropagation", "convolutional-layers", "transformers", "attention-mechanism", "activation-functions", "gradient-descent"],
        "branch": ["reinforcement-learning", "nlp", "computer-vision", "generative-ai", "robotics", "neuromorphic-computing"],
        "pivot": ["quantum-mechanics", "crispr-gene-editing", "black-holes", "climate-science"],
    },
}

# All 6 main topic IDs
MAIN_TOPICS = list(TOPIC_GRAPH.keys())


def get_node(node_id):
    """Get a node by its slug ID. Returns None if not found."""
    return NODES.get(node_id)


def get_subtopics(topic_id, strategy):
    """Get subtopic node IDs for a given topic and strategy.

    Returns a list of node IDs, or empty list if topic/strategy not found.
    """
    topic_edges = TOPIC_GRAPH.get(topic_id, {})
    return topic_edges.get(strategy, [])


def get_subtopic_nodes(topic_id, strategy, exclude=None):
    """Get full node dicts for subtopics, excluding already-visited node IDs.

    Args:
        topic_id: The parent topic slug
        strategy: "deeper", "branch", or "pivot"
        exclude: Set or list of node IDs to filter out

    Returns:
        List of node dicts with id, label, description
    """
    exclude = set(exclude or [])
    ids = get_subtopics(topic_id, strategy)
    result = []
    for nid in ids:
        if nid not in exclude:
            node = get_node(nid)
            if node:
                result.append(node)
    return result


def find_topic_for_node(node_id):
    """Find which main topic a subtopic belongs to.

    Returns the main topic ID, or None if the node IS a main topic or not found.
    """
    for main_id, edges in TOPIC_GRAPH.items():
        for strategy_nodes in edges.values():
            if node_id in strategy_nodes:
                return main_id
    return None


def get_all_node_ids():
    """Return a set of all registered node IDs."""
    return set(NODES.keys())
