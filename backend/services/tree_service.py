"""
Passive tree node pathfinding service.

Node recommendations are driven entirely by real poe.ninja adoption data.
recommend_nodes_branched() is the sole entry point used by build_service.py.
"""

import json
import os
import yaml
from functools import lru_cache
from collections import defaultdict

DATA_PATH   = os.path.join(os.path.dirname(__file__), "..", "data", "SkillTreeCore.json")
REPORT_DIR  = os.path.join(os.path.dirname(__file__), "..", "pob_codes", "reports")
BUILDS_DIR  = os.path.join(os.path.dirname(__file__), "..", "knowledge", "builds")

# PoE2 class name → SkillTreeCore.json StartingNodes key
CLASS_START_MAP = {
    "Warrior":   "Marauder",
    "Ranger":    "Ranger",
    "Sorceress": "Witch",
    "Monk":      "Shadow",
    "Mercenary": "Duelist",
    "Huntress":  "Templar",
    "Witch":     "Witch",
    "Druid":     "Templar",
}

# Ascendancy name → SkillTreeCore.json Ascendancy field value
ASCENDANCY_TREE_MAP = {
    "Deadeye":             "Ranger1",
    "Pathfinder":          "Ranger3",
    "Warbringer":          "Warrior1",
    "Titan":               "Warrior2",
    "Stormweaver":         "Sorceress1",
    "Chronomancer":        "Sorceress2",
    "Invoker":             "Monk2",
    "Acolyte of Chayula":  "Monk3",
    "Witchhunter":         "Mercenary2",
    "Gemling Legionnaire": "Mercenary3",
    "Blood Mage":          "Witch2",
    "Infernalist":         "Witch1",
    "Lich":                "Witch3",
    "Amazon":              "Huntress1",
    "Spirit Walker":       "Huntress3",
    "Oracle":              "Druid1",
    "Shaman":              "Druid2",
}


@lru_cache(maxsize=1)
def _load_ascendancy_node_rules() -> dict:
    path = os.path.join(BUILDS_DIR, "ascendancy_node_rules.yaml")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    result: dict = {}
    for tree_tag, rules in raw.items():
        result[tree_tag] = {
            "free_nodes": set(int(n) for n in (rules.get("free_nodes") or [])),
            "excluded_nodes": set(int(n) for n in (rules.get("excluded_nodes") or [])),
            "exclusive_groups": [
                frozenset(int(n) for n in group)
                for group in (rules.get("exclusive_groups") or [])
            ],
        }
    return result


@lru_cache(maxsize=1)
def _load_tree() -> dict:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)



def _load_passive_report(ascendancy: str, skill: str = "") -> dict | None:
    """Load passive heatmap — per-combo first, fall back to legacy filenames.

    Filename precedence (most specific → most legacy):
      1. {skill}_{ascendancy}_league_starter_passives.json — current per-combo format
      2. {skill}_league_starter_passives.json              — legacy skill-only (polluted
         across ascendancies; here for back-compat until all combos re-analysed)
      3. {ascendancy}_league_starter_passives.json         — ancient ascendancy-only fallback
    """
    asc_slug = ascendancy.lower()
    candidates = []
    if skill:
        skill_slug = skill.lower().replace(" ", "_")
        candidates.append(os.path.join(REPORT_DIR, f"{skill_slug}_{asc_slug}_league_starter_passives.json"))
        candidates.append(os.path.join(REPORT_DIR, f"{skill_slug}_league_starter_passives.json"))
    candidates.append(os.path.join(REPORT_DIR, f"{asc_slug}_league_starter_passives.json"))
    for path in candidates:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    return None


def _is_main_tree_node(node: dict) -> bool:
    """Exclude ascendancy sub-tree nodes and non-allocatable mastery nodes.

    In the 0_4 tree, Type 4 = Jewel Socket (allocatable, has Connections).
    In the 0_3 tree, Type 4 = Mastery (non-allocatable, no Connections).
    We distinguish by whether the node has any Connections rather than by Type.
    """
    if node.get("Ascendancy"):
        return False
    if node.get("Type") == 4 and not node.get("Connections"):
        return False  # non-allocatable mastery node
    return True


def _build_adjacency(nodes: dict) -> dict[int, set[int]]:
    """Build bidirectional adjacency map from node Connections (main tree only).

    Connections are stored one-sidedly in the tree JSON — a jewel socket node
    may have an empty Connections dict even though other nodes point to it.
    We first collect all IDs that appear as connection targets so those nodes
    are not falsely excluded as mastery nodes.
    """
    # Pass 1: collect every node ID that is the target of any connection edge.
    referenced_as_target: set[int] = set()
    for n in nodes.values():
        for conn_id in (n.get("Connections") or {}):
            referenced_as_target.add(int(conn_id))

    # Pass 2: main-tree IDs — exclude ascendancy sub-trees and true mastery nodes.
    # A Type-4 node is a mastery (non-allocatable) only when it has NO connections
    # of its own AND is not referenced as a target by any other node.
    main_tree_ids: set[int] = {
        int(nid) for nid, n in nodes.items()
        if not n.get("Ascendancy")
        and not (
            n.get("Type") == 4
            and not n.get("Connections")
            and int(nid) not in referenced_as_target
        )
    }

    adj: dict[int, set[int]] = defaultdict(set)
    for node_id_str, node in nodes.items():
        node_id = int(node_id_str)
        if node_id not in main_tree_ids:
            continue
        for neighbour_str in (node.get("Connections") or {}):
            neighbour = int(neighbour_str)
            if neighbour not in main_tree_ids:
                continue
            adj[node_id].add(neighbour)
            adj[neighbour].add(node_id)
    return dict(adj)



def _stitch_nodes(
    target_ids: list[int],
    start_id: int,
    adj: dict[int, set[int]],
    node_costs: dict[int, float] | None = None,
    initial_connected: set[int] | None = None,
    max_connectors: int | None = None,
    attribute_nodes: set[int] | None = None,
    max_attribute_connectors: int | None = None,
) -> tuple[list[int], list[int]]:
    """
    Ensure every node in target_ids is reachable from start_id.

    Uses Dijkstra weighted by adoption rate when node_costs is provided:
    high-adoption nodes (frequently walked by real builds) have low cost and
    are preferred; rarely-taken nodes have high cost and are avoided.
    Falls back to unweighted BFS when no cost map is given.

    initial_connected: treat these nodes as already reachable (e.g. the full
    core set when stitching optional nodes — routes to nearest core node).

    max_connectors: if set, skip any target whose shortest path requires more
    than this many intermediate travel nodes.

    attribute_nodes / max_attribute_connectors: if both set, skip any target
    whose path passes through more than max_attribute_connectors pure attribute
    nodes (e.g. "+5 to any Attribute" filler nodes). Allows real small nodes
    (damage, speed, etc.) to count toward max_connectors without penalty.

    Returns:
        reachable_targets  — subset of target_ids that were successfully connected
        connectors         — travel nodes added to bridge targets to the start
    """
    import heapq

    DEFAULT_COST = 50.0   # cost for nodes not in the frequency data at all

    target_set    = set(target_ids)
    connected: set[int] = {start_id}
    if initial_connected:
        connected |= initial_connected
    connector_set: set[int] = set()
    connectors:   list[int] = []
    reachable:    list[int] = []

    for target in target_ids:
        if target in connected:
            reachable.append(target)
            continue

        # Dijkstra from target outward — stop when we pop a connected node
        dist:   dict[int, float] = {target: 0.0}
        parent: dict[int, int]   = {target: -1}
        heap = [(0.0, target)]
        found: int | None = None

        while heap:
            d, cur = heapq.heappop(heap)
            if d > dist.get(cur, float("inf")):
                continue          # stale heap entry
            if cur in connected:
                found = cur
                break
            for nb in adj.get(cur, set()):
                cost     = node_costs.get(nb, DEFAULT_COST) if node_costs else 1.0
                new_dist = d + cost
                if new_dist < dist.get(nb, float("inf")):
                    dist[nb]   = new_dist
                    parent[nb] = cur
                    heapq.heappush(heap, (new_dist, nb))

        if found is None:
            continue  # node unreachable from tree — skip

        # Trace path: found → ... → target via parent chain, then reverse
        path: list[int] = []
        cur = found
        while cur != -1:
            path.append(cur)
            cur = parent.get(cur, -1)
        path.reverse()  # [target, ..., found]

        # path[0] = target, path[-1] = found (already connected)
        # path[1:-1] = new connector nodes
        connector_path = path[1:-1]

        if max_connectors is not None and len(connector_path) > max_connectors:
            continue  # too many connectors total — skip this target

        if (attribute_nodes is not None and max_attribute_connectors is not None):
            attr_count = sum(1 for n in connector_path if n in attribute_nodes)
            if attr_count > max_attribute_connectors:
                continue  # too many pure attribute filler nodes — skip this target

        for node in connector_path:
            connected.add(node)
            if node not in target_set and node not in connector_set:
                connector_set.add(node)
                connectors.append(node)

        connected.add(target)
        reachable.append(target)

    return reachable, connectors


def _remove_redundant_connectors(
    all_nodes: list[int],
    start_id: int,
    adj: dict[int, set[int]],
    popular_set: set[int],
    node_costs: dict[int, float],
    keep_pct_threshold: float = 35.0,
) -> list[int]:
    """
    Remove connector nodes that are not strictly necessary for connectivity.

    For each non-popular node (sorted lowest adoption first), check whether
    all popular nodes remain reachable from start if that node is removed.
    If yes — it's redundant (there's an alternative path) and gets dropped.

    Nodes above keep_pct_threshold adoption are never removed even if technically
    redundant — a connector at 40% is a path real builds genuinely walk and
    should stay on the tree regardless of alternative routes.
    """
    from collections import deque

    # Convert costs back to pct for the threshold check (cost = 1/pct)
    def cost_to_pct(cost: float) -> float:
        return (1.0 / cost * 100.0) if cost > 0 else 0.0

    highlighted = set(all_nodes)
    highlighted.add(start_id)

    def all_popular_reachable_without(excluded: int) -> bool:
        reachable: set[int] = set()
        queue = deque([start_id])
        reachable.add(start_id)
        while queue:
            cur = queue.popleft()
            for nb in adj.get(cur, set()):
                if nb in highlighted and nb != excluded and nb not in reachable:
                    reachable.add(nb)
                    queue.append(nb)
        return all(p in reachable for p in popular_set if p in highlighted)

    # Process non-popular connectors in order of lowest adoption first
    # (highest cost = most likely to be on a weak detour path).
    # Skip nodes above the keep threshold — they're popular enough to always keep.
    candidates = sorted(
        [n for n in highlighted
         if n not in popular_set
         and n != start_id
         and cost_to_pct(node_costs.get(n, 50.0)) < keep_pct_threshold],
        key=lambda n: node_costs.get(n, 50.0),
        reverse=True,
    )

    for n in candidates:
        if n not in highlighted:
            continue
        if all_popular_reachable_without(n):
            highlighted.discard(n)

    highlighted.discard(start_id)
    return list(highlighted)


def _prune_leaves(
    all_nodes: list[int],
    start_id: int,
    adj: dict[int, set[int]],
    node_costs: dict[int, float],
    budget: int,
    protected: set[int] | None = None,
) -> list[int]:
    """
    Iteratively remove the weakest leaf node (highest cost = lowest adoption)
    from the highlighted set until total nodes <= budget.
    A leaf has exactly one highlighted neighbour — removing it disconnects nothing.
    Start node and any node in `protected` (selected destination notables) are
    never removed — only connector/travel nodes can be pruned away.
    """
    protected = protected or set()
    highlighted = set(all_nodes)
    highlighted.add(start_id)

    h_adj: dict[int, set[int]] = {
        nid: {nb for nb in adj.get(nid, set()) if nb in highlighted}
        for nid in highlighted
    }

    while len(highlighted) > budget + 1:  # +1 for start_id
        leaves = [
            nid for nid in highlighted
            if nid != start_id
            and nid not in protected
            and len(h_adj.get(nid, set())) <= 1
        ]
        if not leaves:
            break
        worst = max(leaves, key=lambda n: node_costs.get(n, 50.0))
        highlighted.discard(worst)
        for nb in list(h_adj.get(worst, set())):
            h_adj[nb].discard(worst)
        h_adj.pop(worst, None)

    highlighted.discard(start_id)
    return list(highlighted)


def _strip_connector_leaves(
    all_nodes: list[int],
    start_id: int,
    adj: dict[int, set[int]],
    popular_set: set[int],
) -> list[int]:
    """
    Remove any non-popular leaf nodes that are dead ends after pruning.

    When _prune_leaves stops at the budget it may leave connector trails
    dangling (e.g. travel nodes that only existed to reach a notable that
    was itself just pruned). This pass iteratively removes any leaf that is
    not a popular destination, cleaning up those orphaned tails without
    touching popular nodes or mid-path connectors.
    """
    highlighted = set(all_nodes)
    highlighted.add(start_id)
    h_adj: dict[int, set[int]] = {
        nid: {nb for nb in adj.get(nid, set()) if nb in highlighted}
        for nid in highlighted
    }

    changed = True
    while changed:
        changed = False
        for nid in list(highlighted):
            if nid == start_id or nid in popular_set:
                continue
            if len(h_adj.get(nid, set())) <= 1:
                highlighted.discard(nid)
                for nb in list(h_adj.get(nid, set())):
                    h_adj[nb].discard(nid)
                h_adj.pop(nid, None)
                changed = True

    highlighted.discard(start_id)
    return list(highlighted)


def _asc_propagate_free(allocated: set, adj: dict, free_ids: set) -> set:
    """Auto-allocate any free ascendancy nodes adjacent to the current allocated set."""
    result = set(allocated)
    changed = True
    while changed:
        changed = False
        for fn in free_ids:
            if fn not in result:
                for nb in adj.get(fn, set()):
                    if nb in result:
                        result.add(fn)
                        changed = True
                        break
    return result


def _asc_paid_neighbors(allocated: set, adj: dict, excluded: set, free_ids: set) -> set:
    """Paid nodes one step from the allocated set (not already allocated, not excluded, not free)."""
    result = set()
    for nid in allocated:
        for nb in adj.get(nid, set()):
            if nb not in allocated and nb not in excluded and nb not in free_ids:
                result.add(nb)
    return result


def _recommend_asc_tiers(
    ascendancy: str,
    nodes: dict,
    free_node_ids: set,
    asc_node_data: list,
    exclusive_groups: list,
    excluded_node_ids: set | None = None,
) -> list:
    """
    Returns a flat ordered list of paid ascendancy node IDs in tier order.
    Each adjacent pair [a, b] represents one spend:
      - tier1 = gold, tier2 = green, tier3 = blue, tier4 = red

    Endpoints are identified by node type (Notable=1, Keystone=2) rather than
    by whether they open further paid neighbours — this handles chains like
    9798→24868→33736→61991 where 24868 is a valid endpoint even though 33736
    follows it.

    When a notable is directly adjacent to the allocated set (e.g. via a free
    gateway node), it is selected as a single-node allocation and emitted twice
    [n, n] to maintain the pair structure the frontend expects.

    Free nodes (entry + YAML free_nodes) are auto-propagated at zero cost and
    are NOT included in the returned list.
    """
    # Build bidirectional adjacency within this ascendancy's sub-tree only.
    asc_ids = {
        int(nid) for nid, n in nodes.items()
        if n.get("Ascendancy") == ascendancy and n.get("Type", 0) != 4
    }
    adj: dict = defaultdict(set)
    for nid_str, n in nodes.items():
        nid = int(nid_str)
        if nid not in asc_ids:
            continue
        for conn_str in n.get("Connections", {}):
            conn = int(conn_str)
            if conn in asc_ids:
                adj[nid].add(conn)
                adj[conn].add(nid)

    adoption = {e["id"]: e.get("pct", 0.0) for e in asc_node_data}

    # Seed from the entry node (named after the ascendancy), then propagate free.
    entry_id = next(
        (e["id"] for e in asc_node_data if e.get("name", "").lower() == ascendancy.lower()),
        None,
    )
    allocated: set = {entry_id} if entry_id else set()
    allocated = _asc_propagate_free(allocated, adj, free_node_ids)

    # Exclusive group lookup.
    node_to_group: dict = {}
    for gi, group in enumerate(exclusive_groups):
        for nid in group:
            node_to_group[nid] = gi

    # Pre-populate excluded with permanently blocked nodes from YAML.
    excluded: set = set(excluded_node_ids or set())

    tier_nodes: list = []

    for _round in range(4):
        candidates = _asc_paid_neighbors(allocated, adj, excluded, free_node_ids)
        # Record which nodes are already adjacent BEFORE trying any n1, so we
        # can restrict n2 to nodes that are genuinely newly opened by n1 and
        # not already reachable via the existing allocated set.
        pre_candidates = set(candidates)
        best_pair  = None
        best_score = -1.0

        for n1 in candidates:
            n1_type = nodes.get(str(n1), {}).get("Type", 0)

            # ── Single-node allocation: notable/keystone ───────────────────
            # n1 is a notable/keystone directly adjacent to the allocated set
            # (e.g. reachable via a free gateway node).  Select it alone.
            if n1_type in {1, 2}:
                score = adoption.get(n1, 0.0)
                if score > best_score:
                    best_score = score
                    best_pair  = (n1, None)
                continue   # don't also try n1 as a travel gateway

            # ── Single-node allocation: Type-0 terminal ─────────────────────
            # Some ascendancy nodes are small (Type 0) but are dead-ends within
            # the ascendancy sub-tree because their connections lead only back to
            # already-allocated nodes or outside the ascendancy into the main tree
            # (e.g. "Path of the Sorceress" / "Path of the Warrior" in Pathfinder).
            # These have no valid n2 so they must be selected alone.
            temp_single  = _asc_propagate_free(allocated | {n1}, adj, free_node_ids)
            new_from_n1  = _asc_paid_neighbors(temp_single, adj, excluded, free_node_ids) - pre_candidates
            if not new_from_n1:
                # n1 opens no new nodes — it is a terminal, select as single-node
                score = adoption.get(n1, 0.0)
                if score > best_score:
                    best_score = score
                    best_pair  = (n1, None)
                continue   # no valid n2 exists for a terminal node

            # ── Pair allocation: n1 = travel, n2 = notable/keystone ────────
            temp1 = _asc_propagate_free(allocated | {n1}, adj, free_node_ids)
            n2_all = _asc_paid_neighbors(temp1, adj, excluded, free_node_ids)

            # n2 must be newly opened by n1 — exclude nodes already adjacent
            # to the allocated set before n1 was added (avoids cross-path
            # confusion where a node reachable via a free gateway appears as
            # a valid n2 for an unrelated travel node).
            n2_candidates = n2_all - pre_candidates

            # Block exclusive alternatives of n1 from being chosen as n2.
            n1_gi = node_to_group.get(n1)
            if n1_gi is not None:
                n2_candidates -= set(exclusive_groups[n1_gi]) - {n1}

            for n2 in n2_candidates:
                n2_type = nodes.get(str(n2), {}).get("Type", 0)
                if n2_type in {1, 2}:
                    # Notable or keystone — always a valid endpoint regardless
                    # of further connections (handles chains like 24868→33736→61991).
                    pass
                else:
                    # Type 0 (small/travel): only valid as endpoint if it is
                    # a terminal node that opens no further paid branches.
                    # This handles cases like Deadeye's Point Blank / Far Shot
                    # which are Type 0 but connect only back to the already-free
                    # Projectile Proximity Specialisation node.
                    temp2     = _asc_propagate_free(temp1 | {n2}, adj, free_node_ids)
                    new_nodes = temp2 - temp1
                    has_new   = any(
                        nb not in temp2 and nb not in excluded and nb not in free_node_ids
                        for nid in new_nodes
                        for nb  in adj.get(nid, set())
                    )
                    if has_new:
                        continue  # n2 opens further branches — not a terminal endpoint

                score = max(adoption.get(n1, 0.0), adoption.get(n2, 0.0))
                if score > best_score:
                    best_score = score
                    best_pair  = (n1, n2)

        # Stop if nothing viable.
        if best_pair is None:
            break

        n1, n2 = best_pair
        if n2 is None:
            # Single-node: emit the node twice to preserve the [travel, endpoint]
            # pair structure that the frontend uses for tier colouring.
            tier_nodes.extend([n1, n1])
            allocated = _asc_propagate_free(allocated | {n1}, adj, free_node_ids)
            gi = node_to_group.get(n1)
            if gi is not None:
                for alt in exclusive_groups[gi]:
                    if alt != n1:
                        excluded.add(alt)
        else:
            tier_nodes.extend([n1, n2])
            allocated = _asc_propagate_free(allocated | {n1, n2}, adj, free_node_ids)
            for nid in (n1, n2):
                gi = node_to_group.get(nid)
                if gi is not None:
                    for alt in exclusive_groups[gi]:
                        if alt != nid:
                            excluded.add(alt)

    return tier_nodes


def recommend_nodes_branched(
    skill: str,
    ascendancy: str,
    class_name: str,
    league_type: str = "sc",
    top_n: int = 35,
    optional_n: int = 6,
) -> dict:
    """
    Return {"core": list[int], "optional": list[int], "connectors": list[int], "branches": [], "builds_analysed": int}.

    Takes the top_n most-allocated node IDs from real PoB data (rendered gold),
    then the next optional_n notables (rendered teal), stitching all back to the
    class start node via Dijkstra weighted by adoption rate.
    """
    tree = _load_tree()
    nodes: dict          = tree.get("Nodes", {})
    starting_nodes: dict = tree.get("StartingNodes", {})

    report = _load_passive_report(ascendancy, skill=skill)
    if not report or report.get("builds_analysed", 0) < 10:
        return {"core": [], "optional": [], "asc_nodes": [], "connectors": [], "branches": [], "builds_analysed": 0}

    start_id = int(starting_nodes.get(class_name, 0))

    # Rule 4: only target Notable (1), Keystone (2), and Jewel Socket (3/4) nodes
    # as stitching destinations. Type 0 travel/attribute nodes are mandatory
    # path nodes but never destinations — the algorithm will walk through them
    # automatically when connecting destinations, so they never become dead-end
    # leaf branches.
    DESTINATION_TYPES = {1, 2, 3, 4}

    # Split nodes by pick-rate threshold: >= 30% adoption → gold, < 30% → teal.
    # top_n / optional_n act as safety caps so neither set grows unbounded.
    MIN_GOLD_PCT = 30.0
    popular_ids:  list[int] = []
    optional_ids: list[int] = []
    for entry in report.get("top_nodes", []):
        if len(popular_ids) >= top_n and len(optional_ids) >= optional_n:
            break
        nid = entry["id"]
        pct = entry.get("pct", 0.0)
        node_data = nodes.get(str(nid))
        if not node_data or node_data.get("Type", 0) not in DESTINATION_TYPES:
            continue
        if pct >= MIN_GOLD_PCT and len(popular_ids) < top_n:
            popular_ids.append(nid)
        elif pct < MIN_GOLD_PCT and len(optional_ids) < optional_n:
            optional_ids.append(nid)

    if not popular_ids or not start_id:
        return {
            "core": popular_ids,
            "connectors": [],
            "branches": [],
            "builds_analysed": report.get("builds_analysed", 0),
        }

    # Build node cost map: high adoption = low cost (preferred path).
    # Nodes not in the report get a very high cost so the algorithm strongly
    # prefers routing through nodes that real builds actually walked through.
    node_costs: dict[int, float] = {}
    for entry in report.get("top_nodes", []):
        pct = max(entry["pct"], 0.1) / 100.0   # floor at 0.1% to avoid div/0
        node_costs[entry["id"]] = 1.0 / pct

    # Build main-tree adjacency and stitch all popular nodes back to start.
    # Jewel sockets are stitched separately with a connector cap so a distant
    # socket doesn't drag in a long chain of travel nodes (same rule as teal pass).
    adj = _build_adjacency(nodes)
    JEWEL_TYPES = {3, 4}
    popular_notables = [nid for nid in popular_ids
                        if nodes.get(str(nid), {}).get("Type", 0) not in JEWEL_TYPES]
    popular_jewels   = [nid for nid in popular_ids
                        if nodes.get(str(nid), {}).get("Type", 0) in JEWEL_TYPES]

    connected_targets, connectors = _stitch_nodes(popular_notables, start_id, adj, node_costs)

    # Stitch jewel sockets from the nearest already-connected node, capped at 5 connectors.
    jewel_base = set(connected_targets) | set(connectors) | {start_id}
    jewel_targets, jewel_connectors = _stitch_nodes(
        popular_jewels, start_id, adj, node_costs,
        initial_connected=jewel_base,
        max_connectors=5,
    )
    connected_targets = connected_targets + jewel_targets
    connectors        = connectors + jewel_connectors

    # Jewel sockets that arrived via connectors were already capped above;
    # promote any remaining jewel sockets found in the connector list.
    promoted:            list[int] = []
    remaining_connectors: list[int] = []
    for nid in connectors:
        node_data = nodes.get(str(nid), {})
        if node_data.get("Type") in (3, 4) and not node_data.get("Ascendancy"):
            promoted.append(nid)
        else:
            remaining_connectors.append(nid)

    # Redundancy removal: drop any connector node that isn't strictly needed
    # for connectivity. If a popular node is reachable via two paths, the
    # lower-adoption path's connectors get removed, keeping only the better route.
    popular_set = set(popular_ids)
    all_nodes = connected_targets + promoted + remaining_connectors
    all_nodes = _remove_redundant_connectors(all_nodes, start_id, adj, popular_set, node_costs)

    # Prune weak leaf destinations until total allocated nodes <= budget.
    # With Rule 4 active, leaves are always Notables/Keystones/Jewel Sockets
    # (never mid-path attribute nodes), so this correctly trims the least-adopted
    # destinations rather than stranding important nodes.
    all_nodes = _prune_leaves(all_nodes, start_id, adj, node_costs, budget=150, protected=popular_set)
    # After pruning, connector tails whose target notable was just pruned are
    # left as dead ends. Strip them regardless of budget — only popular nodes
    # (notables/keystones/jewels) are protected from removal here.
    all_nodes = _strip_connector_leaves(all_nodes, start_id, adj, popular_set)

    # Stitch the optional (teal) notables using the completed core as the
    # already-connected set so they route to the nearest core node rather
    # than all the way back to the class start.
    # Rule: max 5 connectors total, but at most 3 of those may be pure attribute
    # filler nodes (+5 to any Attribute / +Str/Dex/Int) with LOW adoption.
    # Attribute nodes that real builds walk through (adoption >= 15%) are treated
    # as legitimate travel nodes and don't count against the attribute cap.
    ATTR_FILLER_THRESHOLD = 15.0  # % adoption below which an attribute node is "filler"
    attribute_node_ids: set[int] = {
        int(nid) for nid, n in nodes.items()
        if n.get("Name") == "Attribute" or (
            isinstance(n.get("Stats"), list)
            and n.get("Stats")
            and all(
                any(kw in s.lower() for kw in ("attribute", "strength", "dexterity", "intelligence"))
                and not any(kw in s.lower() for kw in ("damage", "speed", "resist", "life", "mana", "evasion", "armour", "critical", "flask"))
                for s in n["Stats"]
            )
        )
    }
    # Only penalise low-adoption attribute nodes — high-adoption ones are real
    # travel nodes that builds genuinely walk and shouldn't inflate the cap.
    filler_attribute_node_ids: set[int] = {
        nid for nid in attribute_node_ids
        if nid not in node_costs or (1.0 / node_costs[nid] * 100.0) < ATTR_FILLER_THRESHOLD
    }
    core_set = set(all_nodes) | {start_id}
    opt_targets, opt_connectors = _stitch_nodes(
        optional_ids, start_id, adj, node_costs,
        initial_connected=core_set,
        max_connectors=5,
        attribute_nodes=filler_attribute_node_ids,
        max_attribute_connectors=3,
    )
    # Keep only nodes that aren't already in core (avoid double-highlighting).
    optional_nodes: list[int] = [
        n for n in (opt_targets + opt_connectors)
        if n not in core_set
    ]

    # Ascendancy nodes — path-aware tiered allocation.
    tree_tag = ASCENDANCY_TREE_MAP.get(ascendancy)
    asc_rules        = _load_ascendancy_node_rules().get(tree_tag, {}) if tree_tag else {}
    yaml_free        = set(asc_rules.get("free_nodes", []))
    yaml_excluded    = set(asc_rules.get("excluded_nodes", []))
    asc_node_data    = report.get("top_asc_nodes", [])
    entry_ids        = {e["id"] for e in asc_node_data if e.get("name", "").lower() == ascendancy.lower()}
    free_node_ids    = yaml_free | entry_ids
    exclusive_groups: list = asc_rules.get("exclusive_groups", [])

    asc_paid = _recommend_asc_tiers(
        ascendancy=ascendancy,
        nodes=nodes,
        free_node_ids=free_node_ids,
        asc_node_data=asc_node_data,
        exclusive_groups=exclusive_groups,
        excluded_node_ids=yaml_excluded,
    )  # no min_adoption threshold — pick all 4 tiers regardless of low %
    asc_free = [e["id"] for e in asc_node_data if e["id"] in free_node_ids]

    return {
        "core":             all_nodes,              # main tree only — free asc nodes not highlighted
        "optional":         optional_nodes,
        "asc_nodes":        asc_paid,               # ordered paid nodes for tiered colouring
        "connectors":       [],
        "branches":         [],
        "builds_analysed":  report.get("builds_analysed", 0),
    }
