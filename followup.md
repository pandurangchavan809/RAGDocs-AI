# RAGDocs AI: Follow-up Questions and Advanced RAG Guide

Use this after [interview.md](interview.md). That file explains the project. This one prepares you for the deeper questions that come next.

**How to read the answers:**
- Answers are written in the first person, so you can say them in your own words.
- **In my project** describes what the code does today.
- **What I'd do** describes an improvement that isn't built yet. Keep the two separate when you speak.
- Don't memorise the wording. Learn the reasoning, because interviewers follow up on the reasoning.

## How to answer any deep question

Use this order, and it will work even for a topic you only partly know:

1. **Define it** in one sentence.
2. **Say why it exists:** what problem does it solve?
3. **State the trade-off:** what does it cost?
4. **Connect it to your project:** do you use it, and why or why not?

If you don't know something, say: "I haven't implemented that. My understanding is X, and I'd validate it by testing Y." That is far stronger than guessing.

---

## Part 1: Follow-ups on your resume bullets

**Q1. Walk me through what happens when I ask a question.**

> The route validates the question and model, and checks that any selected documents belong to the user. It then opens a Server-Sent Events stream. I make sure the documents are indexed, embed the question once, and use that vector for MMR and similarity search in the user's Chroma store. I remove duplicates, filter low-quality chunks and keep six. The prompt combines strict rules, the last five exchanges, those chunks and the question. The chosen model streams tokens to the browser, and at the end I save the question, answer and sources to MySQL.

**Q2. What do you mean by page-level source citations?**

> Each chunk stores its file name and page number as metadata, and the UI lists these for each answer. To be precise, they show what was retrieved, not proof that the model used each one. To make them true citations, I'd require inline references such as `[Source 2]` and validate them after generation.

**Q3. How is per-user isolation implemented?**

> Each user has separate folders for files and vectors, named by user id. The id comes from the signed JWT, never from the request body, and selected document ids are checked for ownership. Physical separation means a forgotten metadata filter can't leak another user's chunks. The cost is many small stores, which is harder to run at scale.

**Q4. Have you found a weakness in that isolation?**

> Yes. Folders are keyed by database user id. When I temporarily switched from MySQL to SQLite, ids restarted at 1, so a local user's folder could have collided with a different MySQL user 1. I caught it before switching back and moved that data aside. A better design keys storage by a random UUID that never gets reused.

**Q5. Explain the automatic re-indexing.**

> The collection name includes the embedding model and an index version, and each chunk stores that version. Before answering, I check whether each in-scope document has current vectors. If not, I re-extract the stored PDF and rebuild them. So changing the embedding model or chunking logic needs no migration script. The cost is one lookup per document on each question, and the first question after a change can be slow.

**Q6. Why did you integrate several LLM providers?**

> Mainly for resilience, because one provider's outage shouldn't stop answers. It also lets me compare models on identical context. Nebius has an OpenAI-compatible API, so only the base URL and key differ, while Gemini needs its own SDK. One function hides those differences.

**Q7. How does your fallback work, and what are its limits?**

> Auto tries the primary, then the secondary, if the first fails or returns nothing before its first token. After a token has been sent I don't fall back, because the user has already read that text and two models could contradict each other. Limits: it doesn't detect a wrong answer, and it doesn't protect retrieval, since embeddings always use Gemini.

**Q8. Why SSE and not WebSockets?**

> After the question is sent, data flows one way, so SSE fits. It runs over normal HTTP and is simple to implement. WebSockets are better for two-way traffic, such as live collaboration. I read the stream with `fetch` because `EventSource` can't send POST bodies or an `Authorization` header.

**Q9. What happens if the user stops an answer?**

> The browser aborts the request. The server notices on its next failed write, the generator closes, and nothing is saved, so a partial answer never enters history or memory. A few more tokens may already have been generated and billed.

**Q10. Why two JWTs?**

> The access token travels with every request, so its 15-minute life limits damage if it leaks. The 30-day refresh token goes only to one route and renews access silently. Requests that fail together share a single refresh, so there's no refresh storm. The weakness is that I can't revoke a refresh token on the server. For production I'd add rotation with reuse detection and HttpOnly cookies.

**Q11. Why did you turn off model thinking?**

> In grounded answering, the context provides the facts, and hidden reasoning delays the first word. In one test, Nemotron's first word arrived in 0.81 s instead of 2.43 s. That's a single prompt, not a benchmark. The risk is weaker multi-step reasoning across chunks, which I'd measure with an evaluation set.

**Q12. What was the hardest part?**

> Give a real story from your own work. Good structure: the symptom, how you narrowed it down, the root cause, the fix, and what you changed afterwards so it can't recur.

---

## Part 2: MMR in depth

**Q13. What is MMR?**

> Maximal Marginal Relevance selects results that are both relevant to the query and different from what's already selected. It addresses redundancy: pure similarity search often returns several near-identical passages, which waste limited context.

**Q14. Give the formula and explain each term.**

```text
MMR = argmax [ λ · sim(d, q)  −  (1 − λ) · max sim(d, s) ]
       d in candidates not yet selected        s in selected
```

- `sim(d, q)`: how relevant the candidate is to the query.
- `max sim(d, s)`: how similar the candidate is to the closest chunk already selected. This is the redundancy penalty.
- `λ`: the balance. At 1 it is pure relevance, and at 0 it is pure diversity.

**Q15. Work through an example.**

Use my `λ = 0.65`, with three candidates:

| Chunk | Similarity to query | Note |
|---|---:|---|
| A | 0.90 | Most relevant |
| B | 0.88 | Almost a copy of A (similarity to A = 0.95) |
| C | 0.75 | Different topic (similarity to A = 0.30) |

- **Step 1:** nothing is selected yet, so the most relevant chunk wins: **A**.
- **Step 2, score B:** `0.65 × 0.88 − 0.35 × 0.95 = 0.572 − 0.3325 = 0.2395`
- **Step 2, score C:** `0.65 × 0.75 − 0.35 × 0.30 = 0.4875 − 0.105 = 0.3825`

**C wins**, even though it's less similar to the query. Pure similarity search would have chosen B and added almost nothing new.

**Q16. How exactly does it run in your project?**

> I pass the query vector with `k=6`, `fetch_k=18` and `lambda_mult=0.65`. Chroma returns the 18 nearest candidates along with their embeddings. Then `langchain-chroma` runs MMR in Python, computing cosine similarity, and greedily selects 6. The candidate search uses Chroma's distance metric, which I haven't changed from the L2 default, and the selection step uses cosine.

**Q17. What's the cost of MMR?**

> Fetching candidates is a normal vector search. Selection compares each remaining candidate with the query and the selected chunks, roughly `O(k × fetch_k)` comparisons for small values, and returning embeddings adds some data transfer. With 18 candidates this is negligible, and the embedding API and LLM are far slower.

**Q18. How do `k`, `fetch_k` and `λ` interact?**

- **`fetch_k` is the ceiling.** MMR can only choose from those candidates, so a relevant chunk missing from the pool can never be selected.
- **`fetch_k` too small** leaves little room for diversity. If it equals `k`, MMR only reorders the same chunks.
- **`fetch_k` too large** can let weakly related chunks in, especially with a low `λ`.
- **`λ`** should be tuned on evaluation data, not picked by feel. Mine, 0.65, is a judgement call that leans towards relevance.

**Q19. When does MMR hurt?**

> When repeated evidence matters, such as a precise fact confirmed by several passages, MMR may replace a relevant chunk with a less relevant one. It also doesn't truly understand diversity, because it only sees embedding distance. Two passages can use different wording yet say the same thing, or use similar wording yet disagree.

**Q20. MMR or a reranker?**

> They solve different problems. A reranker improves relevance by reading the query and passage together. MMR reduces redundancy using the existing embeddings. They can be combined: over-fetch, rerank, then apply a diversity step. MMR is free and fast. A reranker costs latency and usually gives the bigger quality gain.

**Q21. Does MMR guarantee coverage across documents?**

> No. It balances similarity, with no concept of a document. All six chunks can still come from one file. For "compare A and B", I'd retrieve per document and allot places to each.

**Q22. In your code, what does the similarity search add after MMR?**

> Very little. MMR's results come first and the list is cut to six, so similarity results are effectively a fallback when MMR fails or returns too few after filtering. If asked, I'd remove it or merge properly with rank fusion. Pointing this out yourself shows you understand your own pipeline.

---

## Part 3: Embeddings and vector search

**Q23. What are embeddings, and why do they work for search?**

> An embedding maps text to a vector, trained so that similar meanings sit close together. Search then becomes finding nearest vectors. It matches meaning, not just words, so "car repair cost" can find "automobile maintenance expenses".

**Q24. Cosine, dot product or Euclidean?**

| Metric | Measures | Use when |
|---|---|---|
| Cosine | Angle only | Length shouldn't matter, as is typical for text |
| Dot product | Angle and length | Length carries meaning, or vectors are unit length |
| Euclidean (L2) | Straight-line distance | The model or system expects it |

> For unit-length vectors, all three give the same ranking, because `‖a − b‖² = 2 − 2(a·b)`. Generally, use the metric the embedding model was designed for.

**Q25. Why must the query and documents use the same embedding model?**

> Each model builds its own vector space, so distances between two models' vectors mean nothing. Even if the dimensions match, the results would be useless. That's why my collection name includes the model name.

**Q26. Are more dimensions better?**

> Not automatically. They can hold more detail but use more memory and slow comparisons. My model outputs 3072 dimensions, about 12 KB of raw storage per vector at 4 bytes per value. Some models support shortened vectors, known as Matryoshka embeddings, and I'd test whether a smaller size keeps recall.

**Q27. Why not scan every vector?**

> Exact search compares against every vector, which grows linearly and becomes slow with millions of vectors. Approximate nearest neighbour (ANN) indexes trade a small amount of recall for a huge speed gain.

**Q28. Explain HNSW.**

> Hierarchical Navigable Small World is a layered graph. Upper layers have few nodes and long links, and lower layers are dense. Search starts at the top, moves towards the query, and drops down layer by layer. It's like taking a highway, then main roads, then local streets.

| Parameter | Effect when increased |
|---|---|
| `M` (links per node) | Better recall, more memory |
| `efConstruction` | Better index quality, slower build |
| `efSearch` | Better recall, slower queries |

> Chroma uses HNSW, and I've kept its defaults.

**Q29. How does HNSW compare with IVF and PQ?**

- **HNSW:** fast with high recall, but memory-hungry. Deletes and updates are harder.
- **IVF:** groups vectors into clusters and searches only the nearest. It uses less memory, but a match can be missed when it sits in an unsearched cluster.
- **PQ (product quantization):** compresses vectors heavily, which saves a lot of memory but loses precision.
- **Combined:** IVF-PQ is common at very large scale, often with a reranking step on the original vectors.

**Q30. What is metadata pre-filtering versus post-filtering?**

> Pre-filtering restricts the search to matching items first, which guarantees `k` valid results if enough exist, but it can be slower with graph indexes. Post-filtering searches first and then removes non-matches, so strict filters may leave few results. Modern vector databases use filter-aware search to reduce this problem. In my project, selected documents are applied as a Chroma `$in` filter on `document_id`.

**Q31. Why do you add prefixes such as `task: question answering`?**

> Questions and passages look different, and task hints can bring them closer. Some models have an official task setting or a recommended format. I haven't measured the benefit in this project, so I'd compare it on an evaluation set and check the model's documentation.

**Q32. What is embedding drift, and how would you handle a model upgrade?**

> Upgrading a model makes old vectors incompatible. I'd build a new index alongside the old one, evaluate it, switch traffic, then remove the old one. My versioned collection names give me the separation, but my re-indexing is lazy, so there's no gradual switch or evaluation yet.

---

## Part 4: Chunking

**Q33. How do you choose chunk size?**

> It depends on the document type, query type and embedding model. Smaller chunks give precise matching with less context, and larger chunks give more context with blurrier embeddings. I use up to 1050 characters, chosen by judgement. The right way is to test several sizes against an evaluation set using retrieval recall.

**Q34. Compare chunking strategies.**

| Strategy | Idea | Best for | Cost |
|---|---|---|---|
| Fixed-size | Split by length | Simple baselines | Cuts through ideas |
| Sentence-based (mine) | Whole sentences up to a limit | General prose | Ignores document structure |
| Recursive | Split by paragraphs, then sentences, then words | General default | Slightly more logic |
| Structure-aware | Split by headings and sections | Reports, manuals, legal text | Needs reliable parsing |
| Semantic | Split where embedding similarity drops | Mixed-topic text | More embedding calls |
| Parent-child | Match small chunks, return larger parents | Precision with context | More storage and logic |
| Sentence window | Match a sentence, return its neighbours | Exact-fact questions | More logic at retrieval |
| Late chunking | Embed the document, then pool by chunk | References across chunks | Needs a long-context model |

**Q35. What problem does contextual retrieval solve?**

> A chunk like "revenue grew 3%" loses meaning alone: whose revenue, and when? Contextual retrieval adds a short, LLM-generated description of where the chunk fits before embedding it. It usually improves retrieval, but it adds an LLM call per chunk at indexing time, though prompt caching can reduce that.

**Q36. Why is your overlap one sentence?**

> It keeps some continuity without much duplicate storage. Too much overlap inflates the index and returns near-duplicates, which then use up retrieval slots.

**Q37. How would you handle tables, images and scanned pages?**

> - **Tables:** extract with a layout-aware parser, store as Markdown, and embed a short description.
> - **Images and charts:** generate a description with a vision model, and store the link to the original.
> - **Scanned pages:** run OCR only on pages with no text layer.
>
> My project handles none of these today. Scanned PDFs are rejected, and my filters can drop short table text.

**Q38. Why do you keep the page number in metadata?**

> It enables citations and lets the user verify an answer quickly. Other useful metadata includes section title, date and document type, which also allow filtering.

---

## Part 5: Advanced retrieval

**Q39. What is hybrid search, and why use it?**

> Hybrid search combines keyword and vector retrieval. Vector search understands meaning but can miss exact terms such as `INV-2024-0091`. BM25 finds exact terms but misses synonyms. Together they cover each other's weaknesses.

**Q40. Explain BM25.**

> BM25 scores a document using three ideas. Rare query terms count more. Repeating a term helps, but with diminishing returns. Long documents are normalised so they don't win just by containing more words. Its typical parameters are `k1`, around 1.2 to 2.0, for term saturation and `b`, around 0.75, for length normalisation.

**Q41. How do you merge keyword and vector results?**

> Reciprocal Rank Fusion is the common choice, because it uses ranks, and BM25 and vector scores aren't on comparable scales.

```text
RRF score = sum of 1 / (k + rank)      k is usually 60
```

> A chunk ranked 1st by vectors and 3rd by BM25 scores `1/61 + 1/63 = 0.0323`. A chunk ranked 2nd by vectors only scores `1/62 = 0.0161`. So agreement between the two methods is rewarded.

**Q42. What is a reranker?**

> It's a second-stage model that reads the query and each candidate together and scores relevance. A typical flow is to retrieve 50, rerank and keep 5 or 6. It's accurate because it sees word interactions, but it's too slow to run across a whole corpus. That's why it's applied only to a shortlist.

**Q43. Bi-encoder, cross-encoder or ColBERT?**

| Type | How it works | Speed | Accuracy |
|---|---|---|---|
| Bi-encoder | One vector per query and passage | Fastest | Good |
| ColBERT (late interaction) | One vector per token, matched at query time | Medium, with more storage | Very good |
| Cross-encoder | Reads the pair together | Slowest | Often best |

**Q44. What is query rewriting, and when do you need it?**

> It turns a question into a better search query. The main case is a follow-up: "what about its budget?" becomes "What was the Lighthouse Project's budget?" My project currently embeds the raw question, so follow-ups can retrieve poorly. Rewriting is the fix, at the cost of one fast LLM call.

**Q45. Compare HyDE, multi-query and RAG-Fusion.**

- **HyDE:** generate a hypothetical answer and embed that, because an answer looks more like a passage than a question does. It helps with short or vague questions. A wrong guess can mislead retrieval.
- **Multi-query:** generate several rephrasings, search each, and combine the results. It improves recall, at the cost of more calls.
- **RAG-Fusion:** multi-query with results merged using RRF.

**Q46. What is query decomposition?**

> It breaks a complex question into smaller ones. "Compare the budgets of projects A and B" becomes one search for each, then a combined answer. It handles comparison questions that a single search would serve badly.

**Q47. What is multi-hop retrieval?**

> It's when an answer requires connecting facts across passages, where the second search depends on the first result. For example, "What's the budget of the project led by Asha?" needs the project name first. Options include iterative retrieval, agents and knowledge graphs. My one-shot retrieval doesn't support it.

**Q48. Explain self-querying.**

> An LLM converts natural language into a semantic query plus metadata filters. "Reports from 2024 about hiring" becomes a search for "hiring" with `year = 2024`. It's precise when metadata is good, but the generated filters must be validated.

**Q49. What is hierarchical retrieval, and what is RAPTOR?**

> Hierarchical retrieval searches summaries first, then details. RAPTOR clusters chunks, summarises the clusters, and repeats, building a tree. Queries can then match at the right level, which helps with broad questions that individual chunks can't answer. The cost is extra LLM work at indexing time, and re-summarising when content changes.

**Q50. What is GraphRAG, and when would you use it?**

> GraphRAG extracts entities and relationships into a knowledge graph, often with community summaries. It's strong on relationship questions and whole-dataset themes. It's more expensive to build and maintain, and extraction errors spread, so I'd start with hybrid search and reranking and only add a graph if evaluation shows a real need.

**Q51. Explain Corrective RAG and Self-RAG.**

- **Corrective RAG (CRAG):** a grader checks retrieved documents. If they're weak, the system refines or searches elsewhere before answering.
- **Self-RAG:** the model is trained to decide when to retrieve and to judge its own output with special reflection tokens.

> Both add a quality check around retrieval. My simple version would be a relevance threshold plus a "not found" reply.

**Q52. What is agentic RAG?**

> An agent decides what to do: which tool to use, whether to search again, and when it has enough. It suits multi-step questions and multiple sources. It costs more latency and money, it's harder to debug, and failures can compound. For single-document questions, a fixed pipeline is cheaper and more predictable.

**Q53. How do you detect that retrieval found nothing relevant?**

> Use a similarity threshold, calibrated on labelled data because scores vary by model. Reranker scores are often easier to threshold. A small LLM grader is another option. My project has no threshold, so the prompt is my only safeguard. That's one of my planned improvements.

---

## Part 6: Scaling scenarios

**Q54. What changes at 100 documents?**

> Search stays fast, but relevance gets harder, because similar content competes for six places and MMR only sees 18 candidates. I'd raise candidates to about 50, add BM25 and a reranker, and cap chunks per document. Ingestion would also need batching. About 12,500 chunks at my measured 0.64 s per call is roughly 2.2 hours in series, which is an estimate.

**Q55. What about 1 million documents?**

- **Storage:** a distributed vector database such as Qdrant or Milvus, partitioned by tenant.
- **Files:** object storage in place of local disk.
- **Ingestion:** queues, parallel workers, batched embeddings, and resumable jobs.
- **Retrieval:** route to the right subset first using metadata or document summaries.
- **Cost:** consider compression, caching, and tuned approximate search.

**Q56. Vectors per tenant, or one shared index?**

| Approach | Strength | Weakness |
|---|---|---|
| Separate store per user (mine) | Strong isolation | Many small stores; hard to scale or query centrally |
| Shared index with tenant filter | Efficient at scale | One missed filter can leak data |
| Namespaces or partitions | Good balance | Depends on database support |

**Q57. How would you speed up ingestion?**

> Embed in batches, process in background workers with retries, show progress, and hash content to skip unchanged documents and duplicates. Today, my upload is synchronous, with one call per chunk.

**Q58. How do you handle document updates and deletes?**

> Use stable ids and versions. For updates, either replace chunks atomically or write the new version and switch over. For deletes, remove the SQL row, file and vectors together, using a background job with retries, since three stores can't share one transaction. My project has no delete feature yet.

**Q59. How would you reduce latency?**

> First measure each stage. My UI shows real timings for embedding, retrieval and time to first token. Then stream output, cache repeated work, use a fast model for simple queries, and send fewer chunks after reranking. Perceived speed depends mostly on time to the first word.

**Q60. How does semantic caching work, and what's the risk?**

> It reuses an answer when a new question's embedding is close to a past one. The risk is a false match: "revenue in 2023" and "revenue in 2024" are very similar yet need different answers. So I'd use a strict threshold, scope the cache by user and document version, and clear it when documents change.

**Q61. How would you reduce LLM cost?**

> Send fewer, better chunks. Route easy questions to cheaper models. Cache responses and use provider prompt caching for repeated prompt parts. Limit output length. Track tokens per stage first, so you fix the real cost.

---

## Part 7: Generation and prompts

**Q62. How do you reduce hallucination, and can you eliminate it?**

> Not fully. I use retrieval grounding, an answer-only-from-context rule, low temperature and visible sources. I'd add a relevance threshold, required citations, and a post-generation check that each claim is supported by the context.

**Q63. Does low temperature make answers correct?**

> No. It reduces randomness, not error. A model can repeat the same wrong answer every time.

**Q64. Does chunk order in the prompt matter?**

> It can. Models may pay less attention to the middle of long contexts, sometimes called the "lost in the middle" effect. One mitigation is to put the strongest chunks at the start and end. With only about 6300 characters, or roughly 1500 tokens, this matters less for me.

**Q65. How many chunks should you send?**

> Enough to contain the answer, but no more. Too few misses facts, and too many add cost and noise. Evaluate on your own data. Mine is fixed at six, whereas an adaptive design would cut off using a relevance score.

**Q66. Stuff, map-reduce or refine?**

- **Stuff (mine):** put all chunks in one prompt. Simple and cheap, but limited by context size.
- **Map-reduce:** process chunks separately, then combine. Good for summarising many documents, but costs more calls and can lose connections.
- **Refine:** improve the answer chunk by chunk. Often thorough, but it's slow and order-sensitive.

**Q67. How do you handle conflicting sources?**

> Pass dates and titles as metadata, and instruct the model to report the disagreement with sources instead of quietly choosing. My prompt has no rule for this today.

**Q68. How do you handle conversation memory in RAG?**

> There are two separate needs: rewriting the follow-up for retrieval, and giving the model recent context. I do only the second, with the last five exchanges. I don't filter memory by topic or document, so old context can influence a new question. I'd add conversations, summarisation of long histories, and question rewriting.

**Q69. What is prompt injection in RAG, and how do you defend against it?**

> Text inside a retrieved document can contain instructions aimed at the model. No method fully stops it, so defence is layered: delimit context as untrusted data, limit what the model can do, scan documents, and check outputs. In my app, the model has no tools and only sees that user's documents, which limits the damage, but it could still distort an answer.

---

## Part 8: Evaluation

**Q70. How do you evaluate a RAG system?**

> Evaluate retrieval and generation separately. Build a test set of real questions with known correct passages, including unanswerable and multi-document questions. Then run it on every change to chunking, retrieval or prompts. My project has no automated evaluation yet, and it's the first thing I'd add.

**Q71. Explain retrieval metrics.**

| Metric | Meaning | Example |
|---|---|---|
| Recall@k | Share of relevant chunks found in the top k | 2 of 4 relevant found = 0.5 |
| Precision@k | Share of top k that are relevant | 2 of 6 relevant = 0.33 |
| Hit rate@k | Share of questions with at least one relevant result | 90 of 100 = 0.9 |
| MRR | Average of 1 / rank of the first correct result | First correct at rank 3 = 0.33 |
| nDCG@k | Ranking quality, rewarding good results near the top | Used with graded relevance |

**Q72. Explain generation metrics.**

- **Faithfulness:** are the answer's claims supported by the context?
- **Answer relevance:** does it address the question?
- **Context precision:** is the retrieved context focused?
- **Context recall:** does the context contain what a correct answer needs?

> Tools such as RAGAS, TruLens and DeepEval can help score these. LLM-based scores can themselves be wrong, so I'd also review samples by hand.

**Q73. The answer is wrong. How do you debug it?**

1. **Extraction:** is the fact in the extracted text?
2. **Chunking:** did it survive cleaning, and is it intact in a chunk?
3. **Retrieval:** was it retrieved? If not, check the query, model and `k`.
4. **Ranking:** did it make the final six?
5. **Prompt:** did it reach the model?
6. **Generation:** did the model ignore or misread it?

> This order matters, because changing the model can't fix a fact that never reached it.

**Q74. Why not judge quality just by trying a few questions?**

> A few examples hide regressions, since a change can fix one question and break ten others. A fixed test set gives a comparable result for each change.

**Q75. How would you monitor quality in production?**

> Log each stage's latency, tokens, retrieved chunk ids and scores, and the model used. Collect thumbs up or down feedback, track "not found" rates, and periodically score samples. Add real failures to the test set, and watch for privacy when storing questions and documents.

---

## Part 9: Security and compliance

**Q76. What are the main security risks in RAG?**

- **Cross-user data leakage** through missing access filters
- **Prompt injection** through documents
- **Sensitive data** sent to external model providers
- **Permission drift,** when source access changes but the index doesn't
- **Abuse and cost attacks** from unlimited API use

**Q77. How would you enforce document permissions in a company?**

> Store access rules as metadata from the source system, enforce them in the retrieval filter on the server, and sync changes quickly. Never rely on the prompt to enforce permissions, because the model must not receive what the user can't see.

**Q78. How would you handle personal or sensitive data?**

> Classify and redact it before indexing where possible, use providers with suitable data agreements or self-hosted models, encrypt data at rest and in transit, limit logging, and define retention. Deletion must cover the files, vectors, caches and logs.

**Q79. Is your demo account safe?**

> It's safe for its purpose: normal user rights only, no access to other users' data, and a visible warning against private uploads. Its risks are that it's a shared space and has no rate limit, so someone could spend my API credit. Before wider use, I'd add rate limits and temporary per-visitor workspaces.

---

## Part 10: System design

**Q80. Design RAG for a company with 10 million documents.**

Answer in this order:

1. **Clarify:** document types, query types, latency target, permissions and freshness.
2. **Ingestion:** connectors, queue, parsing, OCR, chunking, enrichment, batched embedding.
3. **Storage:** object storage, relational metadata, and a distributed vector and keyword index.
4. **Query:** rewrite, route, apply permission filters, run hybrid search, rerank.
5. **Generation:** model routing, streaming, citations, fallback, caching.
6. **Quality:** evaluation set, monitoring and feedback.
7. **Safety:** access control, injection defences, audit logs and rate limits.

**Q81. RAG, fine-tuning, or a long-context model?**

| Approach | Best when | Weakness |
|---|---|---|
| RAG | Data changes often or needs citations and access control | Quality depends on retrieval |
| Fine-tuning | You need a specific style, format or behaviour | Weak for changing facts, and retraining is costly |
| Long-context prompt | A few small documents | Higher cost and latency; poor at large scale |

**Q82. Should you use a framework such as LangChain or LlamaIndex?**

> They speed up prototypes and offer many integrations. Custom code gives transparency and control. I used only LangChain's Chroma integration and embeddings interface, so I could see and debug each step. For a large team, I might use a framework's retrieval components, but I'd still evaluate them, because defaults aren't always right for your data.

**Q83. When is RAG the wrong choice?**

> When the answer needs exact calculation over structured data, SQL or a tool is better. For general knowledge that needs no private data, retrieval adds cost for no benefit. And when documents are poor quality, RAG gives confident answers based on bad input.

**Q84. If you had one more week on this project, what would you do?**

> Day 1: build an evaluation set and get baseline metrics. Days 2 and 3: add hybrid search and reranking, and measure the change. Day 4: add question rewriting and a relevance threshold. Day 5: move ingestion to background jobs with batching. I'd start with evaluation so that every later change can be proven.

---

## Part 11: Rapid-fire revision

| Term | One-line answer |
|---|---|
| RAG | Retrieve relevant data at question time, and use it as context for the model |
| Embedding | A vector representing meaning |
| Chunking | Splitting documents into searchable pieces |
| ANN | Fast approximate nearest-neighbour search |
| HNSW | Layered graph index for ANN |
| MMR | Selects relevant and non-redundant results |
| BM25 | Keyword ranking method |
| Hybrid search | Keyword plus vector search |
| RRF | Merges rankings using rank positions |
| Reranker | A slower, more accurate second-stage scorer |
| Cross-encoder | Reads query and passage together |
| ColBERT | Matches token-level vectors at query time |
| HyDE | Embeds a generated hypothetical answer |
| Multi-query | Searches several rephrasings |
| RAG-Fusion | Multi-query merged with RRF |
| Parent-child | Matches small chunks, returns larger parents |
| Contextual retrieval | Adds LLM-generated context to chunks before indexing |
| RAPTOR | Tree of recursive cluster summaries |
| GraphRAG | Retrieval using an entity and relationship graph |
| CRAG | Grades retrieval, and corrects it if weak |
| Agentic RAG | An agent plans retrieval steps and tools |
| Recall@k | Share of relevant items found in the top k |
| MRR | Rewards a correct result appearing early |
| nDCG | Scores overall ranking quality |
| Faithfulness | Whether the answer is supported by context |
| Prompt injection | Malicious instructions hidden in input or documents |
| Semantic cache | Reuses answers for similar questions |
| SSE | One-way server-to-browser event stream over HTTP |

## Your project's key numbers

| Item | Value |
|---|---|
| Chunk size and overlap | Up to 1050 characters, 1 sentence |
| Embedding | `gemini-embedding-2`, 3072 dimensions |
| MMR | `k=6`, `fetch_k=18`, `λ=0.65` |
| Similarity search | `k=8` |
| Context | Up to 6 chunks |
| Memory | Last 5 exchanges |
| Temperature and max tokens | 0.1 and 1536 |
| LLMs | 4 models across Nebius, Gemini and OpenAI |
| Thinking | Off for all models |
| Tokens | Access 15 minutes, refresh 30 days |

## What your project does not have

Don't claim any of these unless you build them: reranking, hybrid or BM25 search, a relevance threshold, query rewriting, automated evaluation, OCR, table extraction, inline citation checks, document deletion, separate conversations, or rate limiting.

You can still discuss all of them confidently as "what I'd add next, and why".
