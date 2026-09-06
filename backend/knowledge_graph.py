"""
Knowledge Graph layer for the Antelligence nanobot tumor simulation.

Provides a NetworkX-based knowledge graph that nanobots and the QueenNanobot
can use to:
  1. Store structured discoveries about the tumor microenvironment.
  2. Query grounded context before making LLM decisions.
  3. Export graph state as JSON for blockchain / IPFS attestation.
  4. Import peer discoveries from TumorIntel contract events.
"""

import json
import math
import time
from enum import Enum
from typing import Dict, List, Optional, Tuple

if __package__:
    from .chain.ipfs import compute_artifact_hash, pin_simulation
else:
    from chain.ipfs import compute_artifact_hash, pin_simulation

import networkx as nx


# ---------------------------------------------------------------------------
# Type enumerations
# ---------------------------------------------------------------------------

class NodeType(Enum):
    TUMOR_CELL       = "tumor_cell"
    INTEL_PIN        = "intel_pin"          # from TumorIntel contract
    VESSEL           = "vessel"
    IMMUNE_CELL      = "immune_cell"
    HYPOXIC_ZONE     = "hypoxic_zone"       # aggregated discovery
    STEM_CLUSTER     = "stem_cluster"       # aggregated discovery
    RESISTANT_REGION = "resistant_region"   # aggregated discovery
    KILL_ZONE        = "kill_zone"          # successful delivery zone


class EdgeType(Enum):
    ADJACENT_TO      = "adjacent_to"        # spatial proximity
    TARGETS          = "targets"            # nanobot targets cell
    DELIVERS_TO      = "delivers_to"        # nanobot delivered drug to cell
    CONFIRMS         = "confirms"           # intel pin confirmed by multiple bots
    DERIVED_FROM     = "derived_from"       # aggregated zone derived from observations
    NEAR_VESSEL      = "near_vessel"        # cell / zone near a vessel
    IMMUNE_ATTACKING = "immune_attacking"   # immune cell attacking cell


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _dist(a: tuple, b: tuple) -> float:
    """Euclidean distance between two 2-D or 3-D positions."""
    return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a[:2], b[:2])))


# ---------------------------------------------------------------------------
# Main knowledge-graph class
# ---------------------------------------------------------------------------

class TumorKnowledgeGraph:
    """
    NetworkX MultiDiGraph-backed knowledge graph for the tumor simulation.
    """

    def __init__(self, domain_size: float = 600.0, cluster_radius: float = 50.0):
        self.graph          = nx.MultiDiGraph()
        self.domain_size    = domain_size
        self.cluster_radius = cluster_radius
        self._node_counter  = 0
        self.created_at     = time.time()

        # Internal look-up tables for fast node retrieval
        self._tumor_cell_nodes: Dict[int, str]   = {}  # cell_id -> node_id
        self._vessel_nodes:     Dict[str, str]   = {}  # vessel_id -> node_id
        self._intel_pin_nodes:  Dict[int, str]   = {}  # pin_id -> node_id
        self._kill_zone_nodes:  List[str]        = []
        self._hypoxic_zone_nodes:   List[str]   = []
        self._stem_cluster_nodes:   List[str]   = []
        self._resistant_region_nodes: List[str] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_id(self, prefix: str) -> str:
        self._node_counter += 1
        return f"{prefix}_{self._node_counter}"

    def _zone_nodes_of_type(self, node_type: NodeType) -> List[str]:
        return [
            n for n, d in self.graph.nodes(data=True)
            if d.get("type") == node_type.value
        ]

    # ------------------------------------------------------------------
    # POPULATION METHODS
    # ------------------------------------------------------------------

    def add_tumor_cell(
        self,
        cell_id: int,
        position: tuple,
        phase: str,
        cell_type: str,
        resistance_level: float,
        accumulated_drug: float,
    ) -> str:
        """Add or update a tumor cell node. Returns the node id."""
        if cell_id in self._tumor_cell_nodes:
            node_id = self._tumor_cell_nodes[cell_id]
        else:
            node_id = self._next_id("tc")
            self._tumor_cell_nodes[cell_id] = node_id

        self.graph.add_node(
            node_id,
            type=NodeType.TUMOR_CELL.value,
            cell_id=cell_id,
            position=tuple(position[:2]),
            phase=phase,
            cell_type=cell_type,
            resistance_level=resistance_level,
            accumulated_drug=accumulated_drug,
            last_updated=time.time(),
        )
        return node_id

    def add_intel_pin(
        self,
        pin_id: int,
        position: tuple,
        pin_type: str,
        priority: int,
        reporter_nanobot: int,
        step: int,
    ) -> str:
        """
        Add an intel pin (from blockchain TumorIntel contract or local).
        Automatically adds a CONFIRMS edge to any zone within cluster_radius.
        """
        if pin_id in self._intel_pin_nodes:
            node_id = self._intel_pin_nodes[pin_id]
        else:
            node_id = self._next_id("ip")
            self._intel_pin_nodes[pin_id] = node_id

        self.graph.add_node(
            node_id,
            type=NodeType.INTEL_PIN.value,
            pin_id=pin_id,
            position=tuple(position[:2]),
            pin_type=pin_type,
            priority=priority,
            reporter_nanobot=reporter_nanobot,
            step=step,
            last_updated=time.time(),
        )

        # Auto-link to nearby zones
        zone_types = [
            NodeType.HYPOXIC_ZONE, NodeType.STEM_CLUSTER,
            NodeType.RESISTANT_REGION, NodeType.KILL_ZONE,
        ]
        for n, d in self.graph.nodes(data=True):
            if d.get("type") in {zt.value for zt in zone_types}:
                zone_pos = d.get("position", (0, 0))
                if _dist(position, zone_pos) <= self.cluster_radius:
                    self.graph.add_edge(
                        node_id, n,
                        type=EdgeType.CONFIRMS.value,
                    )

        return node_id

    def add_vessel(
        self,
        vessel_id: str,
        position: tuple,
        oxygen_supply: float,
        bbb_permeability: float,
    ) -> str:
        """Add a vessel node."""
        if vessel_id in self._vessel_nodes:
            node_id = self._vessel_nodes[vessel_id]
        else:
            node_id = self._next_id("vs")
            self._vessel_nodes[vessel_id] = node_id

        self.graph.add_node(
            node_id,
            type=NodeType.VESSEL.value,
            vessel_id=vessel_id,
            position=tuple(position[:2]),
            oxygen_supply=oxygen_supply,
            bbb_permeability=bbb_permeability,
            last_updated=time.time(),
        )
        return node_id

    def record_successful_delivery(
        self,
        nanobot_id: int,
        cell_id: int,
        position: tuple,
        drug_amount: float,
        step: int,
    ):
        """
        Record a successful drug delivery event.
        Creates/updates a KILL_ZONE node near this position and adds a
        DELIVERS_TO edge from the nanobot to the target cell.
        """
        pos2d = tuple(position[:2])

        # Find or create a kill-zone near this position
        kz_node = None
        for n in self._kill_zone_nodes:
            if self.graph.has_node(n):
                kz_pos = self.graph.nodes[n].get("position", (0, 0))
                if _dist(pos2d, kz_pos) <= self.cluster_radius:
                    kz_node = n
                    break

        if kz_node is None:
            kz_node = self._next_id("kz")
            self._kill_zone_nodes.append(kz_node)
            self.graph.add_node(
                kz_node,
                type=NodeType.KILL_ZONE.value,
                position=pos2d,
                delivery_count=0,
                total_drug=0.0,
                last_step=step,
                last_updated=time.time(),
            )

        # Accumulate delivery stats on the zone
        nd = self.graph.nodes[kz_node]
        nd["delivery_count"] = nd.get("delivery_count", 0) + 1
        nd["total_drug"]     = nd.get("total_drug",     0.0) + drug_amount
        nd["last_step"]      = step
        nd["last_updated"]   = time.time()

        # DELIVERS_TO edge: nanobot_id (no dedicated node) -> cell node
        nanobot_node_id = f"nb_{nanobot_id}"
        if not self.graph.has_node(nanobot_node_id):
            self.graph.add_node(
                nanobot_node_id,
                type="nanobot",
                nanobot_id=nanobot_id,
            )

        cell_node_id = self._tumor_cell_nodes.get(cell_id)
        if cell_node_id:
            self.graph.add_edge(
                nanobot_node_id,
                cell_node_id,
                type=EdgeType.DELIVERS_TO.value,
                drug_amount=drug_amount,
                step=step,
            )

    def record_target_acquired(
        self,
        nanobot_id: int,
        cell_id: int,
        position: tuple,
    ):
        """Record that a nanobot is targeting a specific cell. Adds TARGETS edge."""
        nanobot_node_id = f"nb_{nanobot_id}"
        if not self.graph.has_node(nanobot_node_id):
            self.graph.add_node(
                nanobot_node_id,
                type="nanobot",
                nanobot_id=nanobot_id,
            )

        cell_node_id = self._tumor_cell_nodes.get(cell_id)
        if cell_node_id:
            self.graph.add_edge(
                nanobot_node_id,
                cell_node_id,
                type=EdgeType.TARGETS.value,
                position=tuple(position[:2]),
                timestamp=time.time(),
            )

    # ------------------------------------------------------------------
    # ZONE AGGREGATION
    # ------------------------------------------------------------------

    def _cluster_cells(self, cells: list) -> List[List]:
        """
        Greedy nearest-neighbour clustering of cells into groups within
        self.cluster_radius of each other.  O(n^2), fine for <500 cells.

        Each cell is expected to have .position (tuple) and .resistance_level.
        """
        if not cells:
            return []

        unassigned = list(cells)
        clusters: List[List] = []

        while unassigned:
            seed = unassigned.pop(0)
            cluster = [seed]
            remaining = []
            for c in unassigned:
                if _dist(seed.position, c.position) <= self.cluster_radius:
                    cluster.append(c)
                else:
                    remaining.append(c)
            clusters.append(cluster)
            unassigned = remaining

        return clusters

    def _cluster_dicts(self, cell_dicts: list) -> List[List]:
        """
        Same as _cluster_cells but works on plain dicts with 'position' key.
        """
        if not cell_dicts:
            return []

        unassigned = list(cell_dicts)
        clusters: List[List] = []

        while unassigned:
            seed = unassigned.pop(0)
            cluster = [seed]
            remaining = []
            for c in unassigned:
                if _dist(seed["position"], c["position"]) <= self.cluster_radius:
                    cluster.append(c)
                else:
                    remaining.append(c)
            clusters.append(cluster)
            unassigned = remaining

        return clusters

    def _build_zones(
        self,
        cells: list,
        node_type: NodeType,
        node_prefix: str,
        existing_nodes_list: List[str],
        priority_multiplier: float = 1.0,
    ) -> List[str]:
        """
        Generic zone builder used by update_hypoxic_zones / update_stem_clusters
        / update_resistant_regions.

        Accepts objects that have .position and .resistance_level attributes,
        or plain dicts with the same keys.
        """
        if not cells:
            # Remove old zone nodes of this type
            for n in list(existing_nodes_list):
                if self.graph.has_node(n):
                    self.graph.remove_node(n)
            existing_nodes_list.clear()
            return []

        def _pos(cell):
            p = cell["position"] if isinstance(cell, dict) else cell.position
            return tuple(p[:2])

        def _res(cell):
            if isinstance(cell, dict):
                return cell.get("resistance_level", 0.0)
            return getattr(cell, "resistance_level", 0.0)

        # Cluster
        clusters = self._cluster_dicts(
            [{"position": _pos(c), "resistance_level": _res(c)} for c in cells]
        )

        # Remove old zone nodes
        for n in list(existing_nodes_list):
            if self.graph.has_node(n):
                self.graph.remove_node(n)
        existing_nodes_list.clear()

        zone_ids: List[str] = []
        for cluster in clusters:
            positions = [c["position"] for c in cluster]
            cx = sum(p[0] for p in positions) / len(positions)
            cy = sum(p[1] for p in positions) / len(positions)
            centroid = (cx, cy)

            avg_resistance = sum(c["resistance_level"] for c in cluster) / len(cluster)
            cell_count     = len(cluster)
            priority_score = cell_count * (1.0 + avg_resistance) * priority_multiplier

            zone_id = self._next_id(node_prefix)
            self.graph.add_node(
                zone_id,
                type=node_type.value,
                position=centroid,
                cell_count=cell_count,
                avg_resistance=avg_resistance,
                priority_score=priority_score,
                last_updated=time.time(),
            )
            zone_ids.append(zone_id)
            existing_nodes_list.append(zone_id)

        return zone_ids

    def update_hypoxic_zones(self, hypoxic_cells: list) -> List[str]:
        """
        Group hypoxic cells into spatial clusters within cluster_radius.
        Creates/updates HYPOXIC_ZONE nodes with centroid, cell_count,
        avg_resistance, priority_score.  Returns list of zone node ids.
        """
        return self._build_zones(
            hypoxic_cells,
            NodeType.HYPOXIC_ZONE,
            "hz",
            self._hypoxic_zone_nodes,
            priority_multiplier=1.0,
        )

    def update_stem_clusters(self, stem_cells: list) -> List[str]:
        """
        Same pattern for STEM_CELL type cells -> STEM_CLUSTER zones.
        Stem cells get priority_score *= 2.0.
        """
        return self._build_zones(
            stem_cells,
            NodeType.STEM_CLUSTER,
            "sc",
            self._stem_cluster_nodes,
            priority_multiplier=2.0,
        )

    def update_resistant_regions(self, resistant_cells: list) -> List[str]:
        """
        Same pattern for RESISTANT type cells -> RESISTANT_REGION zones.
        """
        return self._build_zones(
            resistant_cells,
            NodeType.RESISTANT_REGION,
            "rr",
            self._resistant_region_nodes,
            priority_multiplier=1.5,
        )

    # ------------------------------------------------------------------
    # QUERY METHODS
    # ------------------------------------------------------------------

    def _node_to_zone_dict(self, node_id: str, data: dict) -> dict:
        return {
            "node_id":       node_id,
            "type":          data.get("type"),
            "position":      data.get("position"),
            "cell_count":    data.get("cell_count", 0),
            "priority_score": data.get("priority_score", 0.0),
            "avg_resistance": data.get("avg_resistance", 0.0),
        }

    def get_high_priority_zones(self, max_results: int = 5) -> List[dict]:
        """
        Return list of zone dicts sorted by priority_score descending.
        Includes: node_id, type, position, cell_count, priority_score.
        """
        zone_types = {
            NodeType.HYPOXIC_ZONE.value,
            NodeType.STEM_CLUSTER.value,
            NodeType.RESISTANT_REGION.value,
            NodeType.KILL_ZONE.value,
        }
        zones = []
        for n, d in self.graph.nodes(data=True):
            if d.get("type") in zone_types:
                zones.append(self._node_to_zone_dict(n, d))

        zones.sort(key=lambda z: z["priority_score"], reverse=True)
        return zones[:max_results]

    def get_zones_near_position(self, position: tuple, radius: float) -> List[dict]:
        """Return all zone nodes within radius of position."""
        zone_types = {
            NodeType.HYPOXIC_ZONE.value,
            NodeType.STEM_CLUSTER.value,
            NodeType.RESISTANT_REGION.value,
            NodeType.KILL_ZONE.value,
        }
        result = []
        for n, d in self.graph.nodes(data=True):
            if d.get("type") in zone_types:
                zone_pos = d.get("position", (0, 0))
                if _dist(position, zone_pos) <= radius:
                    result.append(self._node_to_zone_dict(n, d))
        return result

    def get_confirmed_intel_pins(self, min_confirmations: int = 2) -> List[dict]:
        """
        Return intel_pin nodes that have at least min_confirmations
        outgoing CONFIRMS edges.
        """
        result = []
        for n, d in self.graph.nodes(data=True):
            if d.get("type") != NodeType.INTEL_PIN.value:
                continue
            confirms_count = sum(
                1 for _, _, ed in self.graph.out_edges(n, data=True)
                if ed.get("type") == EdgeType.CONFIRMS.value
            )
            if confirms_count >= min_confirmations:
                result.append({
                    "node_id":       n,
                    "pin_id":        d.get("pin_id"),
                    "position":      d.get("position"),
                    "pin_type":      d.get("pin_type"),
                    "priority":      d.get("priority"),
                    "confirmations": confirms_count,
                })
        return result

    def get_nanobot_context(
        self,
        nanobot_id: int,
        position: tuple,
        search_radius: float = 100.0,
    ) -> dict:
        """
        Build grounded context dict for LLM prompt injection.

        Returns:
          {
            "nearby_zones":     [...],
            "confirmed_intel":  [...],
            "peer_targets":     [...],
            "kill_zones":       [...],
            "nearest_vessel":   {...} or None,
            "graph_node_count": int,
            "last_updated":     float,
          }
        """
        pos2d = tuple(position[:2])

        # Nearby zones (all types)
        nearby_zones = self.get_zones_near_position(pos2d, search_radius)

        # Confirmed intel pins nearby
        confirmed_intel = [
            pin for pin in self.get_confirmed_intel_pins(min_confirmations=1)
            if _dist(pos2d, pin.get("position", (0, 0))) <= search_radius
        ]

        # Cells targeted by other nanobots (TARGETS edges from other nanobots)
        peer_targets = []
        my_node = f"nb_{nanobot_id}"
        for n, d in self.graph.nodes(data=True):
            if d.get("type") != "nanobot":
                continue
            if n == my_node:
                continue
            for _, target, ed in self.graph.out_edges(n, data=True):
                if ed.get("type") == EdgeType.TARGETS.value:
                    if self.graph.has_node(target):
                        td = self.graph.nodes[target]
                        tpos = td.get("position", (0, 0))
                        if _dist(pos2d, tpos) <= search_radius:
                            peer_targets.append({
                                "nanobot_node": n,
                                "cell_node":    target,
                                "position":     tpos,
                            })

        # Kill zones nearby
        kill_zones = []
        for n in self._kill_zone_nodes:
            if not self.graph.has_node(n):
                continue
            d = self.graph.nodes[n]
            kpos = d.get("position", (0, 0))
            if _dist(pos2d, kpos) <= search_radius:
                kill_zones.append({
                    "node_id":       n,
                    "position":      kpos,
                    "delivery_count": d.get("delivery_count", 0),
                    "total_drug":    d.get("total_drug", 0.0),
                })

        # Nearest vessel
        nearest_vessel = None
        best_dist = float("inf")
        for n, d in self.graph.nodes(data=True):
            if d.get("type") == NodeType.VESSEL.value:
                vpos = d.get("position", (0, 0))
                dist = _dist(pos2d, vpos)
                if dist < best_dist:
                    best_dist = dist
                    nearest_vessel = {
                        "node_id":         n,
                        "vessel_id":       d.get("vessel_id"),
                        "position":        vpos,
                        "oxygen_supply":   d.get("oxygen_supply"),
                        "bbb_permeability": d.get("bbb_permeability"),
                        "distance":        best_dist,
                    }

        return {
            "nearby_zones":     nearby_zones,
            "confirmed_intel":  confirmed_intel,
            "peer_targets":     peer_targets,
            "kill_zones":       kill_zones,
            "nearest_vessel":   nearest_vessel,
            "graph_node_count": self.graph.number_of_nodes(),
            "last_updated":     time.time(),
        }

    def get_queen_strategic_summary(self) -> dict:
        """
        Build strategic overview for Queen LLM decisions.

        Returns:
          {
            "total_nodes":         int,
            "hypoxic_zones":       [...sorted by priority...],
            "stem_clusters":       [...sorted by priority...],
            "resistant_regions":   [...sorted by priority...],
            "kill_zones":          [...],
            "confirmed_intel_pins": [...],
            "coverage_pct":        float,
            "recommended_targets": [...]   # top 3 highest priority zones
          }
        """
        def _nodes_of(ntype: NodeType) -> List[dict]:
            result = []
            for n, d in self.graph.nodes(data=True):
                if d.get("type") == ntype.value:
                    result.append(self._node_to_zone_dict(n, d))
            result.sort(key=lambda z: z["priority_score"], reverse=True)
            return result

        hypoxic_zones     = _nodes_of(NodeType.HYPOXIC_ZONE)
        stem_clusters     = _nodes_of(NodeType.STEM_CLUSTER)
        resistant_regions = _nodes_of(NodeType.RESISTANT_REGION)

        kill_zones = []
        for n in self._kill_zone_nodes:
            if self.graph.has_node(n):
                d = self.graph.nodes[n]
                kill_zones.append({
                    "node_id":       n,
                    "position":      d.get("position"),
                    "delivery_count": d.get("delivery_count", 0),
                    "total_drug":    d.get("total_drug", 0.0),
                })

        confirmed_intel = self.get_confirmed_intel_pins(min_confirmations=2)

        # Coverage: fraction of domain area with at least one tumor cell observed
        observed_cells = [
            d for _, d in self.graph.nodes(data=True)
            if d.get("type") == NodeType.TUMOR_CELL.value
        ]
        if observed_cells:
            tumor_area_approx = math.pi * (self.domain_size / 3) ** 2
            cell_area_each    = math.pi * (self.cluster_radius / 2) ** 2
            coverage_pct = min(100.0, len(observed_cells) * cell_area_each / tumor_area_approx * 100.0)
        else:
            coverage_pct = 0.0

        # Recommended targets: top 3 by priority across all zone types
        all_zones = hypoxic_zones + stem_clusters + resistant_regions
        all_zones.sort(key=lambda z: z["priority_score"], reverse=True)
        recommended = all_zones[:3]

        return {
            "total_nodes":          self.graph.number_of_nodes(),
            "hypoxic_zones":        hypoxic_zones,
            "stem_clusters":        stem_clusters,
            "resistant_regions":    resistant_regions,
            "kill_zones":           kill_zones,
            "confirmed_intel_pins": confirmed_intel,
            "coverage_pct":         round(coverage_pct, 2),
            "recommended_targets":  recommended,
        }

    # ------------------------------------------------------------------
    # PERSISTENCE
    # ------------------------------------------------------------------

    def to_json(self) -> dict:
        """
        Serialize graph to a JSON-safe dict using nx.node_link_data.
        Includes metadata: domain_size, cluster_radius, created_at,
        node_count, edge_count.
        """
        # nx.node_link_data may contain non-serialisable objects (e.g. enums).
        # We serialise by converting through json with a custom encoder.
        raw = nx.node_link_data(self.graph)

        def _make_serialisable(obj):
            if isinstance(obj, dict):
                return {k: _make_serialisable(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_make_serialisable(i) for i in obj]
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            return obj

        graph_data = _make_serialisable(raw)

        return {
            "metadata": {
                "domain_size":    self.domain_size,
                "cluster_radius": self.cluster_radius,
                "created_at":     self.created_at,
                "node_count":     self.graph.number_of_nodes(),
                "edge_count":     self.graph.number_of_edges(),
                "exported_at":    time.time(),
            },
            "graph": graph_data,
        }

    def from_json(self, data: dict):
        """Restore graph from serialised dict produced by to_json()."""
        meta = data.get("metadata", {})
        self.domain_size    = meta.get("domain_size",    self.domain_size)
        self.cluster_radius = meta.get("cluster_radius", self.cluster_radius)
        self.created_at     = meta.get("created_at",     self.created_at)

        graph_data = data.get("graph", {})
        self.graph = nx.node_link_graph(graph_data, multigraph=True, directed=True)

        # Rebuild internal look-up tables
        self._tumor_cell_nodes.clear()
        self._vessel_nodes.clear()
        self._intel_pin_nodes.clear()
        self._kill_zone_nodes.clear()
        self._hypoxic_zone_nodes.clear()
        self._stem_cluster_nodes.clear()
        self._resistant_region_nodes.clear()

        for n, d in self.graph.nodes(data=True):
            t = d.get("type")
            if t == NodeType.TUMOR_CELL.value and "cell_id" in d:
                self._tumor_cell_nodes[d["cell_id"]] = n
            elif t == NodeType.VESSEL.value and "vessel_id" in d:
                self._vessel_nodes[d["vessel_id"]] = n
            elif t == NodeType.INTEL_PIN.value and "pin_id" in d:
                self._intel_pin_nodes[d["pin_id"]] = n
            elif t == NodeType.KILL_ZONE.value:
                self._kill_zone_nodes.append(n)
            elif t == NodeType.HYPOXIC_ZONE.value:
                self._hypoxic_zone_nodes.append(n)
            elif t == NodeType.STEM_CLUSTER.value:
                self._stem_cluster_nodes.append(n)
            elif t == NodeType.RESISTANT_REGION.value:
                self._resistant_region_nodes.append(n)

    def to_ipfs_artifact(self) -> dict:
        """
        Export a compact summary suitable for IPFS pinning.
        Not the full graph — just zones, confirmed intel, kill zones, and stats.
        """
        summary = self.get_queen_strategic_summary()
        return {
            "zones": {
                "hypoxic_zones":     summary["hypoxic_zones"],
                "stem_clusters":     summary["stem_clusters"],
                "resistant_regions": summary["resistant_regions"],
            },
            "confirmed_intel": summary["confirmed_intel_pins"],
            "kill_zones":      summary["kill_zones"],
            "stats": {
                "total_nodes":     summary["total_nodes"],
                "coverage_pct":    summary["coverage_pct"],
                "recommended_targets": summary["recommended_targets"],
            },
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------
    # BLOCKCHAIN READ-BACK
    # ------------------------------------------------------------------

    def import_from_contract_events(self, intel_pins: list):
        """
        Import a list of intel pin dicts from TumorIntel contract getActivePins.

        Each pin dict:
          {pinId, x, y, pinType, priority, confirmations, isActive}

        Uint coordinates are converted back to floats using:
          float_coord = uint_coord - domain_size / 2
        """
        offset = self.domain_size / 2.0

        for pin in intel_pins:
            if not pin.get("isActive", True):
                continue

            pin_id     = pin.get("pinId", 0)
            x          = float(pin.get("x", 0)) - offset
            y          = float(pin.get("y", 0)) - offset
            pin_type   = str(pin.get("pinType", "unknown"))
            priority   = int(pin.get("priority", 0))
            confirmations = int(pin.get("confirmations", 0))

            node_id = self.add_intel_pin(
                pin_id=pin_id,
                position=(x, y),
                pin_type=pin_type,
                priority=priority,
                reporter_nanobot=-1,  # Unknown reporter (came from chain)
                step=-1,
            )

            # Store confirmation count from the contract
            if self.graph.has_node(node_id):
                self.graph.nodes[node_id]["contract_confirmations"] = confirmations

    def sync_from_chain(self, reader) -> int:
        """Seed the local KG from a ChainIntelReader-compatible object."""
        pins = reader.fetch_active_intel_pins()
        self.import_from_contract_events([
            pin.to_contract_pin_dict() if hasattr(pin, "to_contract_pin_dict") else dict(pin)
            for pin in pins
        ])
        return len(pins)

    def get_nearby_intel(self, position: tuple, radius: float) -> List[dict]:
        """Return active chain/local intel pins near a position, sorted by priority."""
        pos2d = tuple(position[:2])
        result = []
        for node_id, data in self.graph.nodes(data=True):
            if data.get("type") != NodeType.INTEL_PIN.value:
                continue
            pin_pos = data.get("position", (0, 0))
            distance = _dist(pos2d, pin_pos)
            if distance <= radius:
                result.append({
                    "node_id": node_id,
                    "pin_id": data.get("pin_id"),
                    "position": pin_pos,
                    "pin_type": data.get("pin_type"),
                    "priority": data.get("priority", 0),
                    "confirmations": data.get("contract_confirmations", 0),
                    "distance": distance,
                })
        result.sort(key=lambda pin: (pin["priority"], -pin["distance"]), reverse=True)
        return result

    def export_to_ipfs(self, backend: str = "dry-run") -> dict:
        """Export the KG summary as a pin-ready IPFS artifact."""
        artifact = self.to_ipfs_artifact()
        result = pin_simulation(
            config={"artifact_type": "knowledge_graph", "domain_size": self.domain_size},
            metrics={"node_count": self.graph.number_of_nodes(), "edge_count": self.graph.number_of_edges()},
            run_id=f"kg-{compute_artifact_hash(artifact)[:16]}",
            backend=backend,
        )
        result["knowledge_graph"] = artifact
        return result
