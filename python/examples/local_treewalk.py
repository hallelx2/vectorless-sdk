"""Use the Vectorless Python SDK against a LOCAL engine (or the all-in-one
Docker image) with bring-your-own-key.

Run a local engine first, e.g.:

    docker run -p 7654:7654 halleluyaholudele/vectorless        # keyless; pass key per request
    # or: engine --local                                        # from the engine repo

Then:

    export VECTORLESS_LLM_KEY=<your GLM key>     # z.ai / GLM by default
    python examples/local_treewalk.py path/to/document.pdf "your question"

The SDK points at the local engine, ingests the document, waits for it to
become queryable, and asks via the page-based "treewalk" strategy — getting a
cited answer in one round-trip. The API key is sent per request (BYOK), so the
engine never needs it baked into its environment.
"""
import os
import sys

from vectorless import VectorlessClient

ENGINE_URL = os.environ.get("VECTORLESS_BASE_URL", "http://localhost:7654")
LLM_KEY = os.environ.get("VECTORLESS_LLM_KEY", "")


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python examples/local_treewalk.py <document> <question>")
        return 2
    doc_path, question = sys.argv[1], sys.argv[2]
    if not LLM_KEY:
        print("set VECTORLESS_LLM_KEY to your LLM provider key (BYOK)")
        return 2

    client = VectorlessClient(base_url=ENGINE_URL)
    print(f"engine: {ENGINE_URL}")

    print(f"ingesting {doc_path} …")
    ing = client.ingest_document(doc_path)
    doc = client.wait_for_ready(ing.document_id, timeout=300)
    print(f"ready: {doc.id} — {doc.title!r}")

    print(f"asking: {question!r}")
    ans = client.answer_treewalk(
        doc.id,
        question,
        # BYOK: supply your key per request. provider/base_url/model inherit
        # the engine's defaults (GLM via z.ai) when omitted.
        llm_key=LLM_KEY,
    )

    print("\n" + "=" * 60)
    print("ANSWER:", ans.answer)
    print(
        f"confidence={ans.confidence}  hops={ans.hops_taken}  model={ans.model}"
        + (f"  cost=${ans.usage.cost_usd:.4f}" if ans.usage else "")
    )
    for c in ans.citations:
        pages = f"pp.{c.start_page}-{c.end_page}" if c.start_page else "section"
        print(f"  [{pages}] {c.quote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
