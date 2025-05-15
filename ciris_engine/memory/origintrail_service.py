import os, uuid, asyncio, aiohttp, logging
from typing import Dict, Any
try:
    from ..services.base import Service
except ImportError:
    # Fallback for direct execution
    from ciris_engine.services.base import Service

DKG_URL   = os.getenv("DKG_GRAPHQL", "http://node0.ciris.ai:8900/graphql")
ENV_CTX   = "did:vld:env#graph"
TTL_HOURS = int(os.getenv("TASK_GRAPH_TTL", 48))

log = logging.getLogger("OriginTrail")

class MemoryOp:
    """Envelope placed on the OriginTrailService queue."""
    def __init__(self, kind: str, triples: str, ctx: str | None = None):
        self.kind    = kind      # 'publish' | 'query' | 'delete'
        self.triples = triples
        self.ctx     = ctx

def json_to_rdf(json_data: Dict[str, Any], base_uri: str) -> str:
    """Convert JSON structure to RDF n-triples format."""
    triples = []
    
    def add_triple(subject: str, predicate: str, obj: Any):
        if isinstance(obj, (str, int, float, bool)):
            obj_str = f'"{obj}"'
            if isinstance(obj, str) and '\n' in obj:
                obj_str = f'"""{obj}"""'
            triples.append(f"<{subject}> <{predicate}> {obj_str} .")
        elif isinstance(obj, dict):
            new_subject = f"{subject}/{predicate.split('/')[-1]}"
            triples.append(f"<{subject}> <{predicate}> <{new_subject}> .")
            for k, v in obj.items():
                add_triple(new_subject, f"http://schema.org/{k}", v)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                add_triple(subject, predicate, {f"item_{i}": item})
    
    for key, value in json_data.items():
        add_triple(base_uri, f"http://schema.org/{key}", value)
    
    return "\n".join(triples)

class OriginTrailService(Service):
    """Persists CIRIS memory graphs in our private paranet."""
    def __init__(self):
        super().__init__()
        self.session = None
        self.queue = None
        self.running = False

    async def start(self):
        self.session = aiohttp.ClientSession()
        self.queue = asyncio.Queue()
        self.running = True
        asyncio.create_task(self._worker())
        log.info("OriginTrailService started")
        return self

    # ── public helpers used by MemoryHandler ──
    async def publish_task_graph(self, triples: str) -> str:
        ctx = f"did:vld:task:{uuid.uuid4()}#graph"
        await self.queue.put(MemoryOp("publish", triples, ctx))
        return ctx

    async def link_env(self, task_ctx: str):
        triple = (
            f"<{task_ctx}> "
            f"https://w3id.org/ciris#dependsOn "
            f"<{ENV_CTX}> ."
        )
        await self.queue.put(MemoryOp("publish", triple, ENV_CTX))

    async def query(self, ctx: str):
        fut = asyncio.get_running_loop().create_future()
        await self.queue.put(MemoryOp("query", "", ctx))
        return await fut            # resolved by worker

    async def delete(self, ctx: str):
        await self.queue.put(MemoryOp("delete", "", ctx))

    async def stop(self):
        self.running = False
        if self.session:
            await self.session.close()
        if self.queue:
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

    # ── internal worker ──
    async def _worker(self):
        while self.running:
            op: MemoryOp = await self.queue.get()
            try:
                if op.kind == "publish":
                    await self._publish(op.triples, op.ctx)
                elif op.kind == "query":
                    await self._query(op.ctx)
                elif op.kind == "delete":
                    await self._delete(op.ctx)
            except Exception as e:
                log.error(f"OriginTrail operation failed: {e}")
            finally:
                self.queue.task_done()

    # ── GraphQL helpers ──
    async def _publish(self, triples: str, ctx: str):
        gql = {
            "query": """
              mutation($c:String!,$d:String!){
                publishDataset(dataset:{
                  context:$c,
                  dataFormat:"application/n-triples",
                  content:$d
                }){datasetId}}
            """,
            "variables": {"c": ctx, "d": triples},
        }
        try:
            async with self.session.post(DKG_URL, json=gql) as response:
                if response.status != 200:
                    log.error(f"GraphQL request failed with status {response.status}")
                    return
                result = await response.json()
                if "errors" in result:
                    log.error(f"GraphQL errors: {result['errors']}")
        except Exception as e:
            log.error(f"Network error: {e}")

    async def _query(self, ctx: str):
        gql = {
            "query": """
              query($c:String!){
                dataset(context:$c){ content }
              }""",
            "variables": {"c": ctx},
        }
        try:
            async with self.session.post(DKG_URL, json=gql) as response:
                if response.status != 200:
                    log.error(f"GraphQL request failed with status {response.status}")
                    return
                result = await response.json()
                if "errors" in result:
                    log.error(f"GraphQL errors: {result['errors']}")
                return result
        except Exception as e:
            log.error(f"Network error: {e}")
            return {}

    async def _delete(self, ctx: str):
        gql = {
            "query": """
              mutation($c:String!){
                unpublishDataset(context:$c)
              }""",
            "variables": {"c": ctx},
        }
        try:
            async with self.session.post(DKG_URL, json=gql) as response:
                if response.status != 200:
                    log.error(f"GraphQL request failed with status {response.status}")
                    return
                result = await response.json()
                if "errors" in result:
                    log.error(f"GraphQL errors: {result['errors']}")
        except Exception as e:
            log.error(f"Network error: {e}")

async def main():
    """Demo inserting and querying book data."""
    book_json = {
        "book": {
            "title": "The Lord of the Rings",
            "author": {
                "name": "J.R.R. Tolkien",
                "birthdate": "1892-01-03",
                "nationality": "British"
            },
            "publisher": {
                "name": "George Allen & Unwin",
                "location": "London"
            },
            "publication_date": "1954-07-29",
            "isbn": "978-0-261-10236-9",
            "language": "en",
            "pages": 1178,
            "genres": ["Fantasy", "Adventure"],
            "summary": "The Lord of the Rings is an epic high-fantasy novel written by English author and scholar J.R.R. Tolkien. The story began as a sequel to Tolkien's 1937 children's book The Hobbit, but eventually developed into a much larger work. Written in stages between 1937 and 1949, The Lord of the Rings is one of the best-selling novels ever written, with over 150 million copies sold."
        }
    }

    service = OriginTrailService()
    await service.start()
    
    try:
        # Convert JSON to RDF
        rdf_triples = json_to_rdf(book_json, "did:vld:book:lotr")
        print("Generated RDF:\n", rdf_triples)
        
        # Publish to DKG
        ctx = await service.publish_task_graph(rdf_triples)
        print(f"\nPublished with context: {ctx}")
        
        # Query back
        print("\nQuerying data...")
        result = await service.query(ctx)
        print("Query result:", result)
        
    except Exception as e:
        log.error(f"Operation failed: {e}")
    finally:
        await service.stop()

if __name__ == "__main__":
    asyncio.run(main())
