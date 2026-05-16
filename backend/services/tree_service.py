"""
Passive tree node scoring and pathfinding service.

Given a build request (skill, ascendancy, class, options), scores every node
in the passive tree using build_weights.py and returns a list of recommended
node IDs via a greedy best-first pathfinder from the class starting node.
"""

import json
import os
from functools import lru_cache
from collections import defaultdict

from services.build_weights import (
    CLASS_START_MAP, POINT_CAPS, ASCENDANCY_POINT_CAPS, ASCENDANCY_TREE_MAP,
    get_weights, load_ascendancy_node_rules,
)

DATA_PATH  = os.path.join(os.path.dirname(__file__), "..", "data", "SkillTreeCore.json")
REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "pob_codes", "reports")

# Minimum adoption % to target a notable in the weight-based fallback path.
REAL_DATA_MIN_PCT = 33.0


@lru_cache(maxsize=1)
def _load_tree() -> dict:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)



def _load_passive_report(ascendancy: str, experience_level: str, skill: str = "") -> dict | None:
    """Load passive report — skill-specific first, ascendancy fallback."""
    candidates = []
    if skill:
        skill_slug = skill.lower().replace(" ", "_")
        candidates.append(os.path.join(REPORT_DIR, f"{skill_slug}_{experience_level}_passives.json"))
    candidates.append(os.path.join(REPORT_DIR, f"{ascendancy.lower()}_{experience_level}_passives.json"))
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
    """Build bidirectional adjacency map from node Connections (main tree only)."""
    main_tree_ids = {int(nid) for nid, n in nodes.items() if _is_main_tree_node(n)}
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


def _score_node(
    stats: dict,
    weights: dict,
    offense_ratio: float,
) -> float:
    """Score a single node's stats against build weights.
    Returns 0.0 if stats is not a dict (e.g. new SkillTreeCore uses list of strings)."""
    if not isinstance(stats, dict):
        return 0.0
    score = 0.0
    defense_ratio = 1.0 - offense_ratio
    for stat_key, value in stats.items():
        if stat_key not in weights:
            continue
        w = weights[stat_key]
        goal_mult = (w["boss"] + w["map"]) / 2.0
        stat_score = value * (w.get("base", 0.0) + w["offense"] * offense_ratio + w["defense"] * defense_ratio) * goal_mult
        score += stat_score
    return score


def _score_node_offense_only(stats: dict, weights: dict) -> float:
    """Score using only the offense component — base and defense weights are ignored.
    Purely defensive nodes (evasion, life, resistances) score exactly 0.
    Returns 0.0 if stats is not a dict (new SkillTreeCore uses list of strings)."""
    if not isinstance(stats, dict):
        return 0.0
    score = 0.0
    for stat_key, value in stats.items():
        if stat_key not in weights:
            continue
        w = weights[stat_key]
        goal_mult = (w["boss"] + w["map"]) / 2.0
        score += value * w["offense"] * goal_mult
    return score


def _bfs_paths(start: int, adj: dict[int, set[int]]) -> dict[int, list[int]]:
    """
    BFS from start node. Returns shortest path (as list of node IDs) to every
    reachable node. Path includes start and destination.
    """
    from collections import deque
    visited = {start: [start]}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for neighbour in adj.get(current, set()):
            if neighbour not in visited:
                visited[neighbour] = visited[current] + [neighbour]
                queue.append(neighbour)
    return visited


def _recommend_ascendancy_nodes(
    ascendancy: str,
    nodes: dict,
    class_start_id: int,
    weights: dict,
    offense_defense_ratio: float,
    point_cap: int,
) -> list[int]:
    """
    Allocate ascendancy points within the player's ascendancy sub-tree.

    Respects ascendancy_node_rules.yaml:
    - free_nodes: zero-cost junction nodes (included in path but don't consume a point)
    - exclusive_groups: when one node in a group is allocated, all others are blocked
    """
    # tree_tag is only used for ascendancy_node_rules.yaml lookups (which still use
    # the old "Ranger1" style keys). Node filtering uses the ascendancy name directly
    # because the 0_4 tree stores the full name ("Deadeye") in the Ascendancy field.
    tree_tag = ASCENDANCY_TREE_MAP.get(ascendancy)

    # Load special-case rules for this ascendancy
    all_rules = load_ascendancy_node_rules()
    rules = all_rules.get(tree_tag or "", {})
    free_nodes: set[int] = rules.get("free_nodes", set())
    exclusive_groups: list[frozenset[int]] = rules.get("exclusive_groups", [])

    # Collect all nodes belonging to this ascendancy sub-tree.
    # The 0_4 tree uses the full ascendancy name ("Deadeye", "Pathfinder", etc.)
    # directly in the Ascendancy field — not the old "Ranger1" style tags.
    asc_nodes = {
        int(nid): n
        for nid, n in nodes.items()
        if n.get("Ascendancy") == ascendancy and n.get("Type", 0) != 4
    }
    if not asc_nodes:
        return []

    # Build adjacency within the ascendancy sub-tree
    asc_ids = set(asc_nodes)
    adj: dict[int, set[int]] = defaultdict(set)
    for node_id, node in asc_nodes.items():
        for neighbour_str in (node.get("Connections") or {}):
            neighbour = int(neighbour_str)
            if neighbour in asc_ids:
                adj[node_id].add(neighbour)
                adj[neighbour].add(node_id)

    # Find the entry node: the ascendancy node connected to the class start
    main_adj_of_start = set()
    for nid, node in nodes.items():
        if int(nid) == class_start_id:
            for neighbour_str in (node.get("Connections") or {}):
                main_adj_of_start.add(int(neighbour_str))

    entry_candidates = asc_ids & main_adj_of_start
    entry_node = next(iter(entry_candidates)) if entry_candidates else next(iter(asc_ids))

    # Score ascendancy nodes (free_nodes score 0 since they cost nothing)
    node_scores: dict[int, float] = {}
    for node_id, node in asc_nodes.items():
        if node_id in free_nodes:
            continue
        stats = node.get("Stats") or {}
        if not stats:
            continue
        score = _score_node(stats, weights, offense_defense_ratio)
        if score > 0:
            node_scores[node_id] = score

    if not node_scores:
        return []

    # BFS from entry node within the ascendancy sub-tree
    from collections import deque
    visited: dict[int, list[int]] = {entry_node: [entry_node]}
    queue: deque = deque([entry_node])
    while queue:
        current = queue.popleft()
        for neighbour in adj.get(current, set()):
            if neighbour not in visited:
                visited[neighbour] = visited[current] + [neighbour]
                queue.append(neighbour)

    def _point_cost(path: list[int], allocated: set[int]) -> int:
        """Count unallocated non-free nodes in path."""
        return sum(1 for n in path if n not in allocated and n not in free_nodes)

    # Blocked nodes: nodes excluded by exclusive group choices already made
    blocked: set[int] = set()

    # Greedy allocation within ascendancy budget
    # entry_node is always free (like the class start on the main tree)
    allocated: set[int] = {entry_node}
    result: list[int] = [entry_node]
    remaining = point_cap

    candidates = list(node_scores.keys())

    while remaining > 0 and candidates:
        scored: list[tuple[float, int, list[int]]] = []
        for node_id in candidates:
            if node_id in allocated or node_id in blocked:
                continue
            path = visited.get(node_id)
            if path is None:
                continue
            cost = _point_cost(path, allocated)
            if cost == 0 or cost > remaining:
                continue
            vpp = node_scores[node_id] / cost
            scored.append((vpp, node_id, path))

        if not scored:
            break

        scored.sort(key=lambda x: x[0], reverse=True)
        _, best_node, best_path = scored[0]

        cost = _point_cost(best_path, allocated)
        if cost > remaining:
            break

        new_nodes = [n for n in best_path if n not in allocated]
        for n in new_nodes:
            allocated.add(n)
            result.append(n)
        remaining -= cost  # only count non-free nodes

        # Block the other options in any exclusive group that best_node belongs to
        for group in exclusive_groups:
            if best_node in group:
                blocked |= group - {best_node}

        candidates = [n for n in candidates if n not in allocated and n not in blocked]

    return result


def _is_grenade_only(node: dict) -> bool:
    """True when every stat on the node is grenade-specific — can't benefit a bow build."""
    stats = node.get("Stats") or {}
    return bool(stats) and all("grenade" in key.lower() for key in stats)



LEAGUE_OFFENSE_RATIO: dict[str, float] = {
    "sc":     0.65,   # softcore — players push DPS, death is cheap
    "ssf":    0.55,   # solo self-found — can't buy defensive gear, more balanced
    "hc":     0.45,   # hardcore — permadeath, defence matters
    "hcssf":  0.35,   # HC SSF — most constrained, tankiest builds
}


def recommend_nodes(
    skill: str,
    ascendancy: str,
    class_name: str,
    league_type: str = "sc",
    experience_level: str = "league_starter",
) -> list[int]:
    """
    Return a list of recommended passive node IDs for the given build.
    Returns empty list if no weights are registered for this skill/ascendancy.
    """
    offense_defense_ratio = LEAGUE_OFFENSE_RATIO.get(league_type, 0.6)

    tree = _load_tree()
    nodes: dict = tree.get("Nodes", {})
    starting_nodes: dict = tree.get("StartingNodes", {})

    poe1_class = CLASS_START_MAP.get(class_name)
    if not poe1_class or poe1_class not in starting_nodes:
        return []

    start_id = int(starting_nodes[poe1_class])

    # ── Real-data path ────────────────────────────────────────────────────────
    if USE_REAL_DATA:
        report = _load_passive_report(ascendancy, experience_level, skill=skill)
        if report and report.get("builds_analysed", 0) >= 10:
            weights = get_weights(skill, ascendancy, class_name)
            if weights:
                # Offense-only scoring: base and defense weights are ignored so
                # evasion/resistance nodes score exactly 0 and are never targeted.
                node_scores: dict[int, float] = {}
                for node_id_str, node in nodes.items():
                    node_id = int(node_id_str)
                    if not _is_main_tree_node(node):
                        continue
                    stats = node.get("Stats") or {}
                    if not stats:
                        continue
                    score = _score_node_offense_only(stats, weights)
                    if score > 0:
                        node_scores[node_id] = score

                if node_scores:
                    from collections import deque as _deque

                    adj = _build_adjacency(nodes)
                    paths_from_start = _bfs_paths(start_id, adj)
                    point_cap = POINT_CAPS.get(experience_level, 45)

                    # Filter to notables actually taken by real builds at >= REAL_DATA_MIN_PCT.
                    # Cross-reference with offense-only scoring so only damage-relevant
                    # nodes that real players take are targeted.
                    high_pct_names: set[str] = {
                        n["name"] for n in report.get("top_notables", [])
                        if n["pct"] >= REAL_DATA_MIN_PCT
                    }

                    notable_ids = sorted(
                        [nid for nid, score in node_scores.items()
                         if nodes.get(str(nid), {}).get("Type") in (1, 2)
                         and nid in paths_from_start
                         and nodes.get(str(nid), {}).get("Name", "") in high_pct_names],
                        key=lambda nid: node_scores[nid], reverse=True,
                    )[:20]

                    allocated: set[int] = {start_id}
                    result_nodes: list[int] = []
                    remaining = point_cap
                    current_source = start_id

                    # After the first pick is made, notables within this many
                    # hops of start get a heavy VPP penalty — forces the path
                    # to go deep before clustering back near start.
                    NEAR_START_HOPS = 10

                    while remaining > 0 and notable_ids:
                        paths_from_source = _bfs_paths(current_source, adj)

                        best_vpp = -1.0
                        best_target = -1
                        for nid in notable_ids:
                            if nid in allocated:
                                continue
                            path = paths_from_source.get(nid)
                            if not path:
                                continue
                            unallocated = [n for n in path if n not in allocated]
                            cost = len(unallocated)
                            if cost == 0 or cost > remaining:
                                continue
                            vpp = node_scores[nid] / cost
                            # After leaving start, penalise notables that are
                            # physically close to start — avoids re-clustering.
                            if current_source != start_id:
                                hops = len(paths_from_start.get(nid, [])) - 1
                                if 0 < hops < NEAR_START_HOPS:
                                    vpp *= 0.1
                            if vpp > best_vpp:
                                best_vpp = vpp
                                best_target = nid

                        if best_target == -1:
                            break

                        path = paths_from_source[best_target]
                        new_nodes = [n for n in path if n not in allocated]
                        if len(new_nodes) > remaining:
                            notable_ids = [t for t in notable_ids if t != best_target]
                            continue
                        for n in new_nodes:
                            allocated.add(n)
                            if n != start_id:
                                result_nodes.append(n)
                        remaining -= len(new_nodes)
                        current_source = best_target
                        notable_ids = [t for t in notable_ids if t != best_target]


                    asc_cap = ASCENDANCY_POINT_CAPS.get(experience_level, 6)
                    asc_nodes: list[int] = _recommend_ascendancy_nodes(
                        ascendancy=ascendancy,
                        nodes=nodes,
                        class_start_id=start_id,
                        weights=weights,
                        offense_defense_ratio=offense_defense_ratio,
                        point_cap=asc_cap,
                    )
                    return result_nodes + asc_nodes

    # ── Weight-based fallback ─────────────────────────────────────────────────
    weights = get_weights(skill, ascendancy, class_name)
    if not weights:
        return []

    point_cap = POINT_CAPS.get(experience_level, 45)
    adj = _build_adjacency(nodes)

    # Score main-tree nodes only (no ascendancy sub-trees, no masteries)
    node_scores: dict[int, float] = {}
    for node_id_str, node in nodes.items():
        node_id = int(node_id_str)
        if not _is_main_tree_node(node):
            continue
        stats = node.get("Stats") or {}
        if not stats:
            continue
        score = _score_node(stats, weights, offense_defense_ratio)
        if score > 0:
            node_scores[node_id] = score

    if not node_scores:
        return []

    # BFS to get shortest paths from start to every node
    paths_from_start = _bfs_paths(start_id, adj)

    # Compute value-per-point for each reachable scored node
    # Value-per-point = node_score / path_cost
    # path_cost = number of nodes in path (including travel nodes that have score 0)
    candidates: list[tuple[float, int, list[int]]] = []
    for node_id, score in node_scores.items():
        path = paths_from_start.get(node_id)
        if path is None:
            continue
        path_cost = len(path)  # includes start node
        if path_cost == 0:
            continue
        vpp = score / path_cost
        candidates.append((vpp, node_id, path))

    # Greedy allocation: pick best value-per-point, allocate its full path,
    # recompute remaining budget, repeat
    allocated: set[int] = {start_id}
    result_nodes: list[int] = []
    remaining = point_cap

    while remaining > 0 and candidates:
        # Recompute vpp with current allocated set (path cost = unallocated nodes in path)
        scored: list[tuple[float, int, list[int]]] = []
        for _, node_id, path in candidates:
            if node_id in allocated:
                continue
            unallocated_in_path = [n for n in path if n not in allocated]
            cost = len(unallocated_in_path)
            if cost == 0 or cost > remaining:
                continue
            score = node_scores[node_id]
            vpp = score / cost
            scored.append((vpp, node_id, path))

        if not scored:
            break

        scored.sort(key=lambda x: x[0], reverse=True)
        _, best_node, best_path = scored[0]

        new_nodes = [n for n in best_path if n not in allocated]
        if len(new_nodes) > remaining:
            break

        for n in new_nodes:
            allocated.add(n)
            if n != start_id:
                result_nodes.append(n)
        remaining -= len(new_nodes)

        # Remove allocated node from candidates
        candidates = [(vpp, nid, p) for vpp, nid, p in candidates if nid not in allocated]

    # Ascendancy point allocation (separate pool)
    asc_cap = ASCENDANCY_POINT_CAPS.get(experience_level, 6)
    asc_nodes = _recommend_ascendancy_nodes(
        ascendancy=ascendancy,
        nodes=nodes,
        class_start_id=start_id,
        weights=weights,
        offense_defense_ratio=offense_defense_ratio,
        point_cap=asc_cap,
    )

    return result_nodes + asc_nodes


def _stitch_nodes(
    target_ids: list[int],
    start_id: int,
    adj: dict[int, set[int]],
    node_costs: dict[int, float] | None = None,
) -> tuple[list[int], list[int]]:
    """
    Ensure every node in target_ids is reachable from start_id.

    Uses Dijkstra weighted by adoption rate when node_costs is provided:
    high-adoption nodes (frequently walked by real builds) have low cost and
    are preferred; rarely-taken nodes have high cost and are avoided.
    Falls back to unweighted BFS when no cost map is given.

    Returns:
        reachable_targets  — subset of target_ids that were successfully connected
        connectors         — travel nodes added to bridge targets to the start
    """
    import heapq

    DEFAULT_COST = 50.0   # cost for nodes not in the frequency data at all

    target_set    = set(target_ids)
    connected     = {start_id}
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
        for node in path[1:-1]:
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
) -> list[int]:
    """
    Remove connector nodes that are not strictly necessary for connectivity.

    For each non-popular node (sorted lowest adoption first), check whether
    all popular nodes remain reachable from start if that node is removed.
    If yes — it's redundant (there's an alternative path) and gets dropped.

    This resolves competing paths: e.g. if node 328 was added to reach
    Feathered Fletching, but Feathered Fletching is also reachable via
    the higher-adoption 34612 path, node 328 gets removed.
    """
    from collections import deque

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
    # (highest cost = most likely to be on a weak detour path)
    candidates = sorted(
        [n for n in highlighted if n not in popular_set and n != start_id],
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


def recommend_nodes_branched(
    skill: str,
    ascendancy: str,
    class_name: str,
    league_type: str = "sc",
    experience_level: str = "league_starter",
    top_n: int = 100,
) -> dict:
    """
    Return {"core": list[int], "connectors": list[int], "branches": [], "builds_analysed": int}.

    Takes the top_n most-allocated node IDs from real PoB data, then stitches
    them all back to the class start node via BFS, adding the minimum set of
    intermediate travel nodes ("connectors") so the tree is always fully connected.
    """
    tree = _load_tree()
    nodes: dict          = tree.get("Nodes", {})
    starting_nodes: dict = tree.get("StartingNodes", {})

    report = _load_passive_report(ascendancy, experience_level, skill=skill)
    if not report or report.get("builds_analysed", 0) < 10:
        flat = recommend_nodes(skill, ascendancy, class_name, league_type, experience_level)
        return {"core": flat, "connectors": [], "branches": [], "builds_analysed": 0}

    start_id = int(starting_nodes.get(class_name, 0))

    # Collect top_n popular nodes (ordered by adoption rate — most taken first)
    popular_ids: list[int] = []
    for entry in report.get("top_nodes", []):
        if len(popular_ids) >= top_n:
            break
        nid = entry["id"]
        if nodes.get(str(nid)):
            popular_ids.append(nid)

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

    # Build main-tree adjacency and stitch all popular nodes back to start
    adj = _build_adjacency(nodes)
    connected_targets, connectors = _stitch_nodes(popular_ids, start_id, adj, node_costs)

    # Jewel sockets are high-value allocations — promote them from connector
    # to core regardless of whether they appeared in the top_n frequency list.
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

    return {
        "core":             all_nodes,
        "connectors":       [],
        "branches":         [],
        "builds_analysed":  report.get("builds_analysed", 0),
    }
