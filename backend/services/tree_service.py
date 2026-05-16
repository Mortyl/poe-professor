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
    """Exclude ascendancy sub-tree nodes and masteries from pathfinding."""
    return not node.get("Ascendancy") and node.get("Type", 0) != 4


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


def recommend_nodes_branched(
    skill: str,
    ascendancy: str,
    class_name: str,
    league_type: str = "sc",
    experience_level: str = "league_starter",
    top_n: int = 100,
) -> dict:
    """
    Return {"core": list[int], "branches": [], "builds_analysed": int}.

    Takes the top_n most-allocated node IDs from real PoB build data and
    returns them directly — no scoring, no pathfinding, just raw frequency.
    """
    tree = _load_tree()
    nodes: dict = tree.get("Nodes", {})

    report = _load_passive_report(ascendancy, experience_level, skill=skill)
    if not report or report.get("builds_analysed", 0) < 10:
        flat = recommend_nodes(skill, ascendancy, class_name, league_type, experience_level)
        return {"core": flat, "branches": [], "builds_analysed": 0}

    node_ids: list[int] = []
    for entry in report.get("top_nodes", []):
        if len(node_ids) >= top_n:
            break
        nid = entry["id"]
        if nodes.get(str(nid)):          # exists in current tree
            node_ids.append(nid)

    return {
        "core": node_ids,
        "branches": [],
        "builds_analysed": report.get("builds_analysed", 0),
    }
