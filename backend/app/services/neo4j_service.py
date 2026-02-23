from __future__ import annotations

import logging
import uuid
from typing import Any

from neo4j import AsyncDriver

logger = logging.getLogger(__name__)

VALID_ENTITY_TYPES = {"Person", "Organization", "Topic", "Project", "Meeting"}
VALID_RELATIONSHIP_TYPES = {
    "ATTENDED", "DISCUSSED", "WORKS_AT", "KNOWS",
    "ASSIGNED_TO", "RELATES_TO", "MENTIONED_IN",
}


class Neo4jService:
    def __init__(self, driver: AsyncDriver) -> None:
        self.driver = driver

    async def create_entity(
        self, entity_type: str, entity_id: str, properties: dict[str, Any]
    ) -> dict[str, Any]:
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(f"Invalid entity type: {entity_type}")

        props = {k: v for k, v in properties.items() if v is not None}
        props["id"] = entity_id

        set_clause = ", ".join(f"e.{k} = ${k}" for k in props if k != "id")

        query = f"""
        MERGE (e:{entity_type} {{id: $id}})
        {f'SET {set_clause}' if set_clause else ''}
        RETURN e
        """

        async with self.driver.session() as session:
            result = await session.run(query, **props)
            record = await result.single()
            return dict(record["e"]) if record else {}

    async def create_relationship(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if rel_type not in VALID_RELATIONSHIP_TYPES:
            raise ValueError(f"Invalid relationship type: {rel_type}")

        props = properties or {}
        rel_id = props.pop("id", str(uuid.uuid4()))

        set_parts = ["r.id = $rel_id"]
        for k in props:
            set_parts.append(f"r.{k} = ${k}")

        query = f"""
        MATCH (a:{from_type} {{id: $from_id}})
        MATCH (b:{to_type} {{id: $to_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET {', '.join(set_parts)}
        RETURN r, type(r) as type
        """

        async with self.driver.session() as session:
            result = await session.run(
                query, from_id=from_id, to_id=to_id, rel_id=rel_id, **props
            )
            record = await result.single()
            if record:
                return {**dict(record["r"]), "type": record["type"]}
            return {}

    async def strengthen_relationship(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        rel_type: str,
        context: str | None = None,
        last_seen: str | None = None,
    ) -> dict[str, Any]:
        """Increment strength on an existing relationship, create if missing."""
        query = f"""
        MATCH (a:{from_type} {{id: $from_id}})
        MATCH (b:{to_type} {{id: $to_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        ON CREATE SET r.strength = 1, r.first_seen = $last_seen, r.last_seen = $last_seen, r.context = $context, r.id = $rel_id
        ON MATCH SET r.strength = coalesce(r.strength, 0) + 1, r.last_seen = $last_seen, r.context = $context
        RETURN r
        """

        async with self.driver.session() as session:
            result = await session.run(
                query,
                from_id=from_id,
                to_id=to_id,
                context=context or "",
                last_seen=last_seen or "",
                rel_id=str(uuid.uuid4()),
            )
            record = await result.single()
            return dict(record["r"]) if record else {}

    async def create_meeting_node(
        self, meeting_id: str, title: str, date: str
    ) -> dict[str, Any]:
        query = """
        MERGE (m:Meeting {id: $id})
        SET m.title = $title, m.date = $date
        RETURN m
        """
        async with self.driver.session() as session:
            result = await session.run(query, id=meeting_id, title=title, date=date)
            record = await result.single()
            return dict(record["m"]) if record else {}

    async def get_entity_connections(
        self, entity_id: str, depth: int = 1
    ) -> dict[str, Any]:
        query = """
        MATCH (e {id: $entity_id})-[r*1..""" + str(depth) + """]->(connected)
        WITH e, r, connected
        UNWIND r as rel
        RETURN
            labels(e)[0] as source_type, e.id as source_id,
            COALESCE(e.name, e.title, e.id) as source_name,
            type(rel) as rel_type, properties(rel) as rel_props,
            labels(connected)[0] as target_type, connected.id as target_id,
            COALESCE(connected.name, connected.title, connected.id) as target_name
        LIMIT 200
        """
        async with self.driver.session() as session:
            result = await session.run(query, entity_id=entity_id)
            records = [r async for r in result]

        nodes: dict[str, dict] = {}
        edges: list[dict] = []

        for record in records:
            src_id = record["source_id"]
            tgt_id = record["target_id"]

            if src_id not in nodes:
                nodes[src_id] = {
                    "id": src_id,
                    "label": record["source_name"] or src_id,
                    "type": record["source_type"].lower(),
                }
            if tgt_id not in nodes:
                nodes[tgt_id] = {
                    "id": tgt_id,
                    "label": record["target_name"] or tgt_id,
                    "type": record["target_type"].lower(),
                }

            edges.append({
                "id": f"{src_id}-{record['rel_type']}-{tgt_id}",
                "source": src_id,
                "target": tgt_id,
                "type": record["rel_type"],
                "properties": record["rel_props"] or {},
            })

        return {"nodes": list(nodes.values()), "edges": edges}

    async def get_graph_data(
        self, limit: int = 100, node_type: str | None = None
    ) -> dict[str, Any]:
        """Get nodes and edges for graph visualization, optionally filtered by type."""
        type_map = {
            "person": "Person",
            "organization": "Organization",
            "topic": "Topic",
            "project": "Project",
        }

        if node_type and node_type.lower() in type_map:
            label = type_map[node_type.lower()]
            node_query = f"""
            MATCH (n:{label})
            RETURN labels(n)[0] as type, n.id as id,
                   COALESCE(n.name, n.title, n.id) as name, properties(n) as props
            LIMIT $limit
            """
            edge_query = f"""
            MATCH (a:{label})-[r]->(b:{label})
            RETURN a.id as source, b.id as target, type(r) as type, properties(r) as props
            LIMIT $edge_limit
            """
        else:
            node_query = """
            MATCH (n)
            WHERE n:Person OR n:Organization OR n:Topic OR n:Project
            RETURN labels(n)[0] as type, n.id as id,
                   COALESCE(n.name, n.title, n.id) as name, properties(n) as props
            LIMIT $limit
            """
            edge_query = """
            MATCH (a)-[r]->(b)
            WHERE (a:Person OR a:Organization OR a:Topic OR a:Project OR a:Meeting)
              AND (b:Person OR b:Organization OR b:Topic OR b:Project OR b:Meeting)
            RETURN a.id as source, b.id as target, type(r) as type, properties(r) as props
            LIMIT $edge_limit
            """

        async with self.driver.session() as session:
            node_result = await session.run(node_query, limit=limit)
            node_records = [r async for r in node_result]

            edge_result = await session.run(edge_query, edge_limit=limit * 3)
            edge_records = [r async for r in edge_result]

        nodes = [
            {
                "id": r["id"],
                "label": r["name"] or r["id"],
                "type": r["type"].lower(),
                "properties": r["props"] or {},
            }
            for r in node_records
        ]

        node_ids = {n["id"] for n in nodes}
        edges = [
            {
                "id": f"{r['source']}-{r['type']}-{r['target']}",
                "source": r["source"],
                "target": r["target"],
                "type": r["type"],
                "properties": r["props"] or {},
            }
            for r in edge_records
            if r["source"] in node_ids and r["target"] in node_ids
        ]

        return {"nodes": nodes, "edges": edges}

    async def get_entity_with_neighbors(self, entity_id: str) -> dict[str, Any]:
        """Get an entity and all its immediate neighbors (depth 1, both directions)."""
        query = """
        MATCH (e {id: $entity_id})
        OPTIONAL MATCH (e)-[r_out]->(neighbor_out)
        OPTIONAL MATCH (e)<-[r_in]-(neighbor_in)
        WITH e,
             collect(DISTINCT {rel: r_out, node: neighbor_out, dir: 'out'}) as outs,
             collect(DISTINCT {rel: r_in, node: neighbor_in, dir: 'in'}) as ins
        RETURN e, labels(e)[0] as entity_type, properties(e) as entity_props,
               outs, ins
        """
        async with self.driver.session() as session:
            result = await session.run(query, entity_id=entity_id)
            record = await result.single()

        if not record:
            return {"entity": None, "neighbors": [], "edges": []}

        props = record["entity_props"]
        entity = {
            "id": entity_id,
            "label": props.get("name") or props.get("title") or entity_id,
            "type": record["entity_type"].lower(),
            "properties": dict(props),
        }

        neighbors: dict[str, dict] = {}
        edges: list[dict] = []

        for item in record["outs"]:
            rel = item["rel"]
            node = item["node"]
            if rel is None or node is None:
                continue
            nprops = dict(node)
            nid = nprops.get("id", "")
            if not nid:
                continue
            labels = list(node.labels) if hasattr(node, "labels") else []
            ntype = labels[0].lower() if labels else "unknown"
            neighbors[nid] = {
                "id": nid,
                "label": nprops.get("name") or nprops.get("title") or nid,
                "type": ntype,
                "properties": nprops,
            }
            edges.append({
                "id": f"{entity_id}-{rel.type}-{nid}",
                "source": entity_id,
                "target": nid,
                "type": rel.type,
                "properties": dict(rel),
            })

        for item in record["ins"]:
            rel = item["rel"]
            node = item["node"]
            if rel is None or node is None:
                continue
            nprops = dict(node)
            nid = nprops.get("id", "")
            if not nid:
                continue
            labels = list(node.labels) if hasattr(node, "labels") else []
            ntype = labels[0].lower() if labels else "unknown"
            neighbors[nid] = {
                "id": nid,
                "label": nprops.get("name") or nprops.get("title") or nid,
                "type": ntype,
                "properties": nprops,
            }
            edges.append({
                "id": f"{nid}-{rel.type}-{entity_id}",
                "source": nid,
                "target": entity_id,
                "type": rel.type,
                "properties": dict(rel),
            })

        return {
            "entity": entity,
            "neighbors": list(neighbors.values()),
            "edges": edges,
        }

    async def find_meetings_for_entity(self, entity_id: str) -> list[str]:
        query = """
        MATCH (e {id: $entity_id})-[:ATTENDED|MENTIONED_IN|DISCUSSED]->(m:Meeting)
        RETURN m.id as meeting_id
        UNION
        MATCH (e {id: $entity_id})<-[:ATTENDED|MENTIONED_IN|DISCUSSED]-(m:Meeting)
        RETURN m.id as meeting_id
        """
        async with self.driver.session() as session:
            result = await session.run(query, entity_id=entity_id)
            records = [r async for r in result]
            return [r["meeting_id"] for r in records]

    async def search_entities_by_name(self, name: str, limit: int = 10) -> list[dict]:
        query = """
        MATCH (e)
        WHERE (e:Person OR e:Organization OR e:Topic OR e:Project)
          AND toLower(e.name) CONTAINS toLower($name)
        RETURN labels(e)[0] as type, e.id as id, e.name as name
        LIMIT $limit
        """
        async with self.driver.session() as session:
            result = await session.run(query, name=name, limit=limit)
            records = [r async for r in result]
            return [
                {"id": r["id"], "name": r["name"], "type": r["type"].lower()}
                for r in records
            ]
