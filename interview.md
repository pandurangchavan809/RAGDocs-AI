# RAGDocs AI: Interview Guide

Use this to explain the project and to defend its design under deep questioning. Answers are written in the first person, so you can say them aloud in your own words.

Three rules for using it:
- Separate what the project does from what you would add. Interviewers test this by asking follow-ups.
- Admit limitations before you're asked. It shows judgement.
- Don't quote a benchmark or price you haven't checked. Figures here are either read from the code, measured once on this machine, or marked as estimates.

## Part 1: Explaining the project

### 30-second version

> RAGDocs is a full-stack RAG application for PDFs. Users upload documents, and I extract, clean and chunk the text, embed it with Gemini, and store it in a per-user Chroma database. For each question I retrieve the most relevant chunks using MMR, build a grounded prompt, and generate an answer with a model from Nebius, Gemini or OpenAI. The user gets the answer along with the file and page it came from.

### 2-minute version

> The frontend is React with Vite and Tailwind, and the backend is Flask with SQLAlchemy and JWT authentication.
>
> Ingestion runs when a PDF is uploaded. I save the file under a UUID name, read each page with PyPDF2, and clean the text by rebuilding broken lines and removing low-signal fragments. Then I build sentence-based chunks of up to 1050 characters, with one sentence of overlap. Each chunk is embedded and stored in Chroma with metadata such as document id and page number.
>
> On each question, I first make sure the in-scope documents are indexed. Then I run MMR, with `k=6` and `fetch_k=18`, to get relevant but varied chunks. I remove duplicates, filter noise and keep six. The prompt contains strict rules, the last five exchanges, those chunks and the question.
>
> Generation goes through a provider layer. Auto tries the primary model and falls back to the secondary if it fails before its first token, while a model the user chooses has no fallback. Temperature is 0.1 and model thinking is off. Progress steps and answer tokens stream to the browser over Server-Sent Events, then the answer and sources are saved to SQL and displayed with their citations.

### What makes it more than a demo

- Per-user isolation across SQL, files and vectors
- Index versioning with automatic re-indexing
- Multi-provider generation with fallback
- Source attribution down to the page

### What it is not

It isn't production-ready at scale. Ingestion is synchronous, there is no automated evaluation, and retrieval has no reranking or keyword search. Part 11 covers how I would close those gaps.

## Part 2: Exact numbers to remember

| Item | Value | Where |
|---|---|---|
| Chunk size | Max 1050 characters | `pdf_service.split_text` |
| Overlap | 1 sentence | `pdf_service.split_text` |
| Paragraph minimum | 10 words | `normalize_pdf_text` |
| Chunk minimum | 18 words | `is_meaningful_text` |
| Minimum letter ratio | 45% | `is_meaningful_text` |
| Embedding model | `gemini-embedding-2` | `.env` |
| Embedding size | 3072 dimensions (measured) | Live call |
| Embedding latency | About 0.64 s per call (5 calls, one machine) | Live call |
| MMR | `k=6`, `fetch_k=18`, `lambda_mult=0.65` | `chat_service` |
| Similarity search | `k=8` | `chat_service` |
| Final context | Up to 6 chunks, so about 6300 characters at most | `chat_service` |
| Source excerpt | 260 characters | `build_source_payload` |
| Prompt memory | Last 5 Q&A pairs | `get_recent_memory` |
| History shown | Last 20 | `routes/chat.py` |
| Temperature | 0.1 | `.env` |
| Max output tokens | 1536 | `.env` |
| Thinking | Off: Nebius `enable_thinking: false`, Gemini `thinking_budget=0` | `llm_service`, `gemini_service` |
| Streaming | SSE, `POST /api/chat/stream` | `routes/chat.py` |
| LLM timeout | 45 s, no SDK retries | `llm_service` |
| Upload limit | 20 MB | `config.py` |
| Access token lifetime | 15 minutes | `config.py` |
| Refresh token lifetime | 30 days | `config.py` |
| gunicorn timeout | 120 s | `Procfile` |

`top_p`, frequency penalty and presence penalty aren't set, so providers use their defaults.

## Part 3: Why each technology

**Why Flask and not FastAPI or Django?**
> Flask is small and explicit, and this API needs only a few routes. Django brings an admin and ORM conventions I didn't need. FastAPI would give me async support and automatic validation, and it would be my choice for streaming and many slow concurrent LLM calls. That is a real advantage I gave up, since each request here ties up a worker.

**Why React with Vite?**
> The chat interface has lots of changing state, so a component model fits well. Vite gives a fast dev server and a simple build.

**Why Tailwind with no component library?**
> It keeps the design consistent and the bundle free of unused components. The trade-off is that I wrote my own dialog and picker, including keyboard handling.

**Why Chroma and not Pinecone, FAISS, Qdrant or pgvector?**

| Option | Strength | Why not here |
|---|---|---|
| Chroma | Local, persistent, metadata filters, easy setup | Chosen. Weak for multi-server deployment as I use it |
| FAISS | Very fast library | I'd have to build persistence and metadata filtering myself |
| Pinecone | Managed and scalable | Paid external service, unnecessary at this size |
| Qdrant | Strong filtering, scales well | Extra server to run. My likely next step |
| pgvector | Vectors beside relational data | I'd need Postgres, and this project uses MySQL |

**Why LangChain in such a small role?**
> I use only `langchain-chroma` and the `Embeddings` interface. I wrote retrieval, prompting and fallback myself because each step stays visible and easy to debug, and I don't depend on a framework's hidden prompts. The trade-off is writing more code myself.

**Why PyPDF2?**
> It's simple and handles page-by-page text. Honest point: PyPDF2 is no longer developed, because work moved to `pypdf`, so I'd migrate. For complex layouts or tables I'd evaluate PyMuPDF or `pdfplumber`.

**Why JWT and not sessions?**
> JWTs are stateless, which suits a separate frontend and API. The trade-off is that tokens are hard to revoke before they expire, so I keep access tokens short and use a refresh token to renew them.

**Why two tokens?**
> The access token goes with every request, so it's the most exposed, and a 15-minute lifetime limits the damage if it leaks. The refresh token goes only to `/auth/refresh` and lasts 30 days, so users stay logged in. The library rejects each token type on the other's routes.

**Does renewal slow the app down?**
> Normal requests pay nothing. Renewal runs only after a 401, about once per 15 minutes of use. Parallel failures share one refresh promise, so startup's several requests cause one call, not several.

**What are the weaknesses of your refresh design?**
> I don't rotate refresh tokens or keep a server-side blocklist, so a stolen one works for up to 30 days, and logout only clears the browser. Storing it in `localStorage` also exposes it to XSS. For production I'd use an HttpOnly cookie, rotation with reuse detection, and a revocation table. That adds one database check per refresh, not per request.

**Why SQL as well as a vector database?**
> Accounts and history need constraints and exact queries, while vectors need similarity search. Each store does what it's good at. The cost is keeping them in step, which `ensure_documents_indexed` handles.

**Why MySQL and SQLite?**
> SQLAlchemy lets the same models run on both. SQLite needs no setup for local work, and MySQL supports concurrent use in production.

## Part 4: Why these LLMs

**Why three providers?**
> One provider is a single point of failure for generation. Separate providers give independent failure domains, and users can compare answers on the same retrieved context.

**Why Nebius?**
> It serves open-weight models through an OpenAI-compatible API, so I reuse one client by changing the base URL and key. It also gives me non-closed models without running GPUs.

**Why Nemotron as primary and Gemini as secondary?**
> Nemotron Lightning is a fast model for this kind of grounded answering, where the context does most of the work. Gemini is the natural fallback: a different provider, and the key already has to be present for embeddings.

Before saying this, confirm it's your reasoning, and be ready with measured latency and cost figures, because the repo contains no benchmarks.

**Why Qwen and gpt-4.1 as manual choices?**
> They give a larger open-weight option and a widely known closed model to compare against. Neither is in the Auto chain, which keeps fallback simple and predictable.

**Why embed with Gemini even when another model answers?**
> Embedding and generation are independent. The only rule is that documents and queries must use the same embedding model. Changing it per question would make vectors incomparable. The downside is that Gemini is required for all retrieval.

**Why temperature 0.1 and not 0?**
> Grounded answering needs consistency rather than creativity, so I keep it low. The difference between 0 and 0.1 is small. The value should really be chosen through evaluation.

**What does low temperature not do?**
> It doesn't prevent hallucination. It reduces randomness. A model can consistently give the same wrong answer.

**Why turn thinking off?**
> Retrieval already supplies the facts, so grounded answering rarely needs long hidden reasoning, and that reasoning delays the first word and can add cost. In one test, Nemotron sent 280 reasoning chunks by default and none with `enable_thinking: false`, and its first word came in 0.81 s instead of 2.43 s. That's a single short prompt, so it shows direction, not a benchmark. The trade-off is weaker results on questions needing multi-step reasoning across chunks. I'd check that with an evaluation set.

**Does each provider disable it the same way?**
> No. Nebius takes `chat_template_kwargs`, passed through the OpenAI SDK's `extra_body`. Gemini 2.5 takes a thinking budget of 0. `gpt-4.1` has no thinking mode, so I send nothing.

**Does fallback handle a bad answer?**
> No. It triggers only on an exception or an empty reply before the first token. A confident wrong answer doesn't trigger it, and that would need answer checking.

**Why does fallback stop after the first token?**
> Text the user has already read can't be taken back, and mixing two models in one answer could contradict itself. A mid-answer failure shows an error and saves nothing.

## Part 5: RAG fundamentals

**What is RAG?**
> Retrieval-Augmented Generation fetches relevant information at question time and gives it to the model as context. It allows answers from private, changing data without training a model.

**RAG or fine-tuning?**
> RAG is for knowledge that changes or must be cited. Fine-tuning changes behaviour, such as style or format. Fine-tuning a model on my documents wouldn't give page citations or handle a new upload immediately. The two can be combined.

**Why not send the whole PDF to the model?**
> Cost and latency grow with size, context windows are finite, and irrelevant text can reduce quality. With many documents it stops being possible at all. Large context windows reduce this problem for single short documents, but they don't remove it.

**What is an embedding?**
> A list of numbers representing meaning, so texts with similar meaning sit close together. It enables finding "car repair costs" from "automobile maintenance expenses" despite no shared words.

**Cosine similarity, dot product or Euclidean distance?**
> Cosine compares direction, dot product also includes length, and Euclidean measures straight-line distance. For unit-length vectors all three give the same ranking. My code doesn't set a metric, so Chroma's default, L2, applies.

**Bi-encoder or cross-encoder?**
> A bi-encoder embeds question and document separately, so vectors can be pre-computed and searched quickly. A cross-encoder reads the pair together, which is more accurate but too slow for every document. That's why a common design retrieves with a bi-encoder and reranks with a cross-encoder.

**What is HNSW?**
> A layered graph for approximate nearest-neighbour search. It reaches close matches quickly by moving through the graph, trading a small loss of recall for far less work than checking every vector. Chroma uses it.

**Why do documents and queries get different prefixes in my code?**
> Questions and passages are written differently, so task hints can help. I haven't measured the effect on this project, so I'd test it instead of assuming.

## Part 6: Chunking

**Why 1050 characters?**
> It's large enough for a complete idea and small enough to keep a focused embedding. Six chunks also fit comfortably in the prompt. I chose it by judgement, not experiment, so I'd validate it with an evaluation set.

**Too small or too large?**
> Too small loses context, so the embedding is precise but the passage is incomplete. Too large mixes topics, which blurs the embedding and uses more prompt space.

**Why sentence-based?**
> Fixed-size splitting can cut a sentence in half, which harms both the embedding and the passage shown to the model.

**What does overlap do?**
> It keeps context across chunk boundaries. It also adds some duplication, which I handle by removing identical chunk ids. Near-duplicate text is what MMR helps with.

**Why chunk per page?**
> Each chunk maps to exactly one page, so citations are exact. The weakness is that text crossing a page break is separated.

**Other strategies you know?**
> - **Semantic chunking:** split where meaning changes.
> - **Structure-based:** split by headings and sections.
> - **Parent-child:** search small chunks but return the larger parent.
> - **Late chunking:** embed the document first, then pool by chunk.
>
> For long reports I'd try parent-child or structure-based chunking first.

**What's the danger in your cleaning filters?**
> They remove noise, but paragraphs under 10 words are dropped and chunks under 18 words are rejected. Short tables, lists and headings can vanish, so a fact in a table may never be indexed. I'd add table-aware extraction.

**Single sentence longer than 1050 characters?**
> It becomes one oversized chunk, because the code never splits within a sentence. This is uncommon, and it's easy to add a hard limit.

## Part 7: Retrieval

**Explain MMR.**
> Maximal Marginal Relevance picks results one at a time, scoring each candidate as `lambda * similarity(candidate, query) - (1 - lambda) * max similarity(candidate, already selected)`. At `lambda=0.65` it favours relevance while still penalising repetition. It takes 18 candidates and selects 6.

**When does MMR hurt?**
> When redundancy is useful, such as when several passages all confirm one precise fact. Then it may swap a relevant chunk for a less relevant but different one.

**What is the similarity search doing?**
> In practice it's a fallback. MMR results come first and the list is cut to 6, so similarity results rarely reach the prompt unless MMR fails or returns fewer. Both searches reuse one query embedding, so it's cheap, but I'd either remove it or merge the two lists properly with reciprocal rank fusion. This is a good thing to point out yourself.

**What is hybrid search?**
> Combining vector search with keyword search such as BM25. Vectors capture meaning and BM25 catches exact terms like invoice numbers. Results are usually merged with reciprocal rank fusion, which uses rank positions so that the two score scales don't need to match. This project doesn't have it.

**What is reranking?**
> A second, more accurate pass. For example, retrieve 50, rerank with a cross-encoder, and keep 6. This often gives a large quality gain for little code, though it adds latency.

**Query rewriting, HyDE and multi-query?**
> - **Rewriting:** turn a follow-up into a standalone question.
> - **HyDE:** generate a hypothetical answer and embed that, since it looks more like a document than a question does.
> - **Multi-query:** create several versions of the question and combine the results.
>
> All add latency and cost per question. I'd add rewriting first because my retrieval ignores chat history.

**How do metadata filters work here?**
> Selected documents become `{"document_id": {"$in": [...]}}`, stored as strings. The route first checks that those ids belong to the user. Filtering narrows the search and improves precision when the user knows which file matters.

## Part 8: Deep scenario questions

**1. 100 documents: what happens to relevance?**
> Search stays fast, but relevance is the risk. Similar wording across documents competes for six places, and MMR sees only 18 candidates. Good passages can be missed, or one document can dominate. I'd raise candidates to about 50, add BM25 and a reranker, and cap chunks per document.

**2. 100 documents: what's the total cost of ingestion?**
> At 50 pages each and about 2.5 chunks per page, that's about 12,500 chunks. At my measured 0.64 s per call, serial embedding takes about 2.2 hours (estimate). I'd use batch embedding calls, a job queue and progress reporting.

**3. 100 documents: what slows down each question?**
> With no selection, `ensure_documents_indexed` makes one `store.get` per document for each question. I'd store index status in SQL and only check when it changes.

**4. A million documents?**
> Local Chroma per user is no longer suitable. I'd move to a distributed vector database such as Qdrant or Milvus, with partitioning by tenant, async ingestion workers, object storage for files, caching, and tuned approximate search. I'd also use document-level routing to narrow the search first.

**5. "Summarise all my documents."**
> Six chunks can't do this, and the current system would give a partial answer that could look complete. This is a global question, and similarity search handles local ones. I'd detect the intent and use stored document summaries with map-reduce, or hierarchical retrieval such as RAPTOR.

**6. "Compare document A and document B."**
> Nothing guarantees chunks from both. All six could come from A. I'd retrieve separately per document and allot places to each.

**7. The answer is in a table.**
> Text extraction may flatten rows, and my filters may drop them. I'd use table-aware extraction, store tables as Markdown, and add a description for embedding.

**8. Two documents disagree.**
> The prompt has no rule for this, so the model may choose one silently. I'd pass dates and titles as metadata, and instruct the model to show both claims with sources.

**9. The user asks something off-topic.**
> Retrieval still returns six chunks, because scores are discarded. The prompt is my only protection. I'd add a score threshold, calibrated on test data, and return "not found" without calling the model. That saves money and removes a risk of invention.

**10. A follow-up: "What about its budget?"**
> The model sees history, but search uses only those raw words, so it may find the wrong passage. I'd rewrite the question using the history before retrieval.

**11. History pollutes a new topic.**
> Memory is always the last five exchanges, even if the user has changed documents or topics. A previous answer could influence a new one. Separate conversations and memory filtering would fix it.

**12. A new document was just uploaded.**
> It's available as soon as the upload completes, because indexing is synchronous. This is the benefit of RAG over training. The cost is that the user waits.

**13. A document gets replaced.**
> There's no replace feature. A new upload creates a separate document, so old and new can both be retrieved until the user deletes the old one. Deletion removes vectors, then the file, then the SQL row. I'd add versioning so replacing is a single step.

**14. Embedding fails halfway through upload.**
> The SQL row is already saved, and the request returns an error. Because chunk ids are stable and re-indexing deletes old vectors first, the next question repairs it. But the user sees an error for a document that's still listed. A status column would be better.

**15. Chroma data is lost.**
> PDFs remain on disk, so the next question re-embeds them automatically. Vectors are rebuildable, which costs only time and API calls. If uploads are lost too, that data has to be uploaded again.

**16. Gemini is down.**
> Retrieval fails, so every question fails, even with Nebius and OpenAI working. Fallback protects only generation. Protecting retrieval would need a second embedding index, since vectors from different models can't be mixed.

**17. Retrieved context is right but the answer is wrong.**
> Debug in stages. First check extraction and whether the fact was indexed. Then check whether it was retrieved. Then look at the prompt and generation. Logging each stage with evaluation scores makes this quick. I don't have that logging yet, so I'd add it.

**18. Answers got worse after a change.**
> Without an evaluation set I can't prove why, which is the reason to build one first. Then I'd compare retrieval and answer metrics before and after, changing one variable at a time.

**19. Latency is too high. Where does it go?**
> The step card already shows real timings for embedding, retrieval and time to first token. In one test run those were about 690 ms, 55 ms and 1.1 s, so the LLM and embedding call dominated on a one-chunk document. The document check before them isn't timed yet, and it grows with document count. Streaming improves perceived speed, since waiting for the first word is what users notice most.

**20. Costs are too high.**
> Use semantic or exact-match caching, send fewer chunks after reranking, and route simple questions to cheaper models. Check token usage per stage before changing anything.

**21. Multiple users at the same time.**
> One sync gunicorn worker handles one request at a time, and a streaming answer holds it until the last token, so a long chat or upload blocks others. I'd use threaded or async workers, move ingestion to a queue, and consider an async framework.

**24. The user presses Stop. What happens to the provider call?**
> The browser aborts the fetch. The server notices when its next write fails, which closes the generator, so nothing is saved and the answer doesn't enter memory. Detection can lag slightly, so a few extra tokens may be generated and billed.

**25. Is every streamed piece one token?**
> No. Providers decide their chunk size. I measured about 5 characters per chunk for `gpt-4.1`, 8 for Nemotron, 10 for Qwen, and about 125 for Gemini. I release Gemini's blocks word by word with a 12 ms gap, so that pacing is added by me, while the text is real. The word pacing adds a small delay, and I'd state that openly.

**22. Non-English documents or questions.**
> Multilingual embeddings can match across languages, but several parts assume English. `is_meaningful_text` counts only A to Z letters, so Hindi or Marathi text would be rejected as low quality. The sentence splitter also misses the Devanagari full stop. That's a real bug for these languages.

**23. Very large embedding dimensions: is 3072 good?**
> Larger vectors can hold more detail but use more memory and take longer to compare. At 4 bytes per value, each vector takes about 12 KB of raw storage. Some models can shorten their output. I'd test whether a smaller size keeps recall.

## Part 9: Measuring quality

| Metric | Question it answers |
|---|---|
| Recall@k | Did the right passage appear in the top k? |
| Precision@k | How many retrieved passages were useful? |
| MRR | How high was the first correct passage? |
| nDCG | How good was the whole ranking? |
| Faithfulness | Is the answer supported by the context? |
| Answer relevance | Does the answer address the question? |
| Context precision and recall | Was the context focused and complete? |

**How would you evaluate this project?**
> Build 50 to 100 questions with known correct passages, including tricky and unanswerable ones. Measure retrieval and generation separately, using a tool like RAGAS or my own scripts, and run it on every change to chunking, retrieval or prompts. The current project has no automated evaluation. That's the first thing I'd add, because every tuning decision depends on it.

**Which metric comes first?**
> Retrieval recall, because the model can't use a passage it never receives.

## Part 10: Prompting and hallucination

**What prompting style is it?**
> Zero-shot instruction prompting with retrieved context. There are no examples. The rules say to answer only from the context, ignore fragments, say what's uncertain and not invent details.

**How do you reduce hallucination?**
> Retrieval grounding, a strict prompt, low temperature and visible sources. These reduce it but don't remove it, and I don't verify each claim against the context. Next steps would be a relevance threshold, inline citations and a faithfulness check.

**Are your citations proof the model used that source?**
> No. Sources are what was retrieved, not necessarily what was used. The prompt labels chunks as `[Source n]` but doesn't require inline references. I'd require them and validate that each one exists.

**What is prompt injection here?**
> A PDF could contain text like "ignore your instructions". Since retrieved text goes into the prompt, the model might obey it. The damage is limited because only that user's documents are used and the model has no tools. I'd add delimiters around context, and output checks. No method fully prevents it.

## Part 11: What I would improve, in order

1. **Evaluation set:** every other change depends on measurement.
2. **Background ingestion with batched embeddings:** removes slow uploads and timeouts.
3. **Reranking and hybrid search:** usually the largest relevance gain.
4. **Relevance threshold:** reliable "not found" answers.
5. **Question rewriting:** fixes follow-up retrieval.
6. **Separate conversations:** a basic product feature, and it stops old answers leaking into new topics.
7. **Shared file and vector storage:** one location that survives deployments and database changes.
8. **OCR and table extraction:** more document types.
9. **Observability:** latency, tokens and retrieval logs saved per stage.

## Part 12: Security

| Topic | Current state | Improvement |
|---|---|---|
| Passwords | Salted hashes through Werkzeug | Add strength rules; none are enforced today |
| Access control | User id from the token; document ids checked for ownership | Keep it |
| Vector isolation | Separate store per user | Keep it. Shared stores would need enforced tenant filters |
| Uploads | Name check, 20 MB limit, UUID storage name, `secure_filename` | Check file contents, not only the name, and add malware scanning |
| Tokens | Access and refresh tokens in `localStorage`, so readable by any XSS. No refresh rotation or revocation | HttpOnly cookies, rotation and a revocation table |
| XSS | React escapes text, and Markdown doesn't run raw HTML | Keep it, add a content security policy |
| Secrets | `.env` is ignored by git | Use a secret manager in production and rotate exposed keys |
| JWT secret | Falls back to a known default if unset | Refuse to start without one |
| Rate limits | None, so one user can run up API costs, and the public demo account makes this easier | Add per-user limits, especially on demo |
| Demo account | Public password and a shared workspace, on purpose, so reviewers can test quickly. It has normal user rights only, and can't reach other users' data | Give each visitor a temporary workspace with sample documents, and reset it regularly |
| Error messages | Raw exception text returned on chat failure | Log details, return a generic message |
| CORS | Controlled by environment; defaults to `*` if unset | Always set it in production |
| Debug mode | `python app.py` runs with `debug=True` | Never use it in production; `Procfile` uses gunicorn |

## Part 13: Backend and frontend questions

**Why an application factory?**
> It avoids global setup and circular imports, and it allows building the app with different settings for tests.

**Why separate routes and services?**
> Routes handle HTTP and services hold logic, so retrieval can be tested or changed without HTTP code.

**Why cache clients with `lru_cache`?**
> Building a client repeatedly wastes time. Caching reuses one per key and base URL. It also means environment changes need a restart.

**Why `pool_pre_ping` and `pool_recycle`?**
> Cloud databases close idle connections. Pre-ping tests a connection before use, and recycling replaces old ones.

**Why store sources as JSON text?**
> They're only ever read back with their message, so normalised tables aren't needed. Note that `mysql_schema.sql` uses JSON columns while the SQLAlchemy model uses Text, which is a small inconsistency to tidy up.

**Why does the UI show the question before the answer arrives?**
> It uses a `streaming` state so the screen responds immediately. If the request fails, the question goes back into the input so nothing is lost.

**Are the progress steps real?**
> Yes. Each step event is sent as that stage starts and finishes in the backend, with measured durations. To make embedding its own stage, I embed the question first and then search by vector.

**Why SSE and not WebSockets?**
> Chat streaming is one-way after the question is sent, and SSE works over plain HTTP with simple framing. WebSockets add connection management that I don't need.

**Why `fetch` and not `EventSource`?**
> `EventSource` supports only GET and can't set an `Authorization` header. `fetch` lets me POST the question with the JWT and read the response body as a stream.

**Why does the backend save only at the end?**
> A partial answer would pollute history and future prompt memory. Saving after the last token means stopped or failed answers leave nothing behind.

**Why `stream_with_context`?**
> Flask's request context normally ends once the route returns, but the generator runs after that and needs the database session.

**How does the picker avoid showing broken models?**
> The server lists only providers with keys, and validates the id on each request. A key can still be invalid, in which case the call fails with an error.

**Why is the frontend state in one hook and not Redux?**
> One screen with modest shared state doesn't justify it. As features grow, I'd split the hook or use a small store such as Zustand.

## Part 14: Questions that catch people out

**"You use LangChain, so is this a LangChain app?"**
> Only lightly. It's used for the Chroma integration and the embeddings interface. Retrieval, prompts and fallback are my own code.

**"Your interview notes say hybrid retrieval. Is it hybrid?"**
> No. MMR and similarity are both vector searches. Hybrid means vector plus keyword.

**"Do you rerank?"**
> No. MMR reorders for variety using the same embeddings. A reranker is a separate, more accurate model.

**"Does it remember everything?"**
> No. The prompt gets the last five exchanges, and there is no semantic memory.

**"Does the model learn from uploads?"**
> No. Nothing is trained. Text is retrieved and sent as context for each question.

**"Is your data private?"**
> Users are isolated from each other in this app, but chunks and questions are sent to external model and embedding providers. Each provider's data policy matters for sensitive documents.

**"What was your hardest bug?"**
> Answer from your own experience. Real ones from this project: CORS configuration during deployment, and a broken `chromadb` import caused by mismatched `opentelemetry` packages in a shared Python install, which a project virtual environment solved. Another good one: storage folders are keyed by database user id, so switching databases can make a different person share an old user's vectors.

## Part 15: Closing summary

> This project taught me the full RAG lifecycle: ingestion, chunking, embeddings, vector search, prompting, generation and citation. I also learned that most quality problems come from the data and retrieval stages, not the LLM call. It's a strong working system, and I know what it needs next: evaluation, better retrieval, and asynchronous ingestion.
