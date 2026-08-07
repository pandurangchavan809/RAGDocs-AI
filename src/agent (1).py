import re
from typing import List, Dict, Any, Set

from config import settings
from llm_client import call_llm, LLMUnavailableError
from src.retrieve import retrieve
from src.acronym_db import AcronymDB
from src.acronym_resolver import AcronymResolver


class AgenticSearch:
    def __init__(self):
        self.db = AcronymDB()
        self.resolver = AcronymResolver(self.db)

    def _call_eval_llm(self, prompt: str, system: str = "") -> str:
        """Sufficiency-evaluation calls. Chain: TASK_AGENT_EVAL_ROUTES in
        .env -- deliberately never includes LLM_PRIMARY (Qwen3.6). Fast,
        cheap model only; Qwen3.6's reasoning overhead has no business
        here."""
        return call_llm(task="AGENT_EVAL", prompt=prompt, system=system, max_tokens=settings.max_new_tokens)

    def _call_answer_llm(self, prompt: str, system: str = "", preferred_route: str | None = None) -> str:
        """Final-answer generation only. Chain: TASK_RAG_ANSWER_ROUTES in
        .env, Qwen3.6 (LLM_PRIMARY, kind=openai_chat) first, falling back
        to Secondary/Local. This is the ONLY call site in the whole app
        that ever reaches Qwen3.6. call_llm's _call_openai_chat sends the
        real OpenAI-format body (model/messages/max_tokens/temperature) --
        no custom payload shape -- and llm_client strips any <think> trace
        before this method ever sees the text."""
        return call_llm(
            task="RAG_ANSWER",
            prompt=prompt,
            system=system,
            max_tokens=settings.rag_answer_max_new_tokens,
            preferred_route=preferred_route,
        )

    def _extract_acronyms(self, text: str) -> Set[str]:
        """Extract alphanumeric tokens of length >= 2 that are in the database."""
        tokens = re.findall(r"[A-Za-z0-9+\-]{2,}", text)
        db_acronyms = {str(e.get("acronym") or "").strip().lower() for e in self.db.all()}
        found = set()
        for t in tokens:
            t_clean = t.strip()
            if t_clean.lower() in db_acronyms:
                # Find the matching case from the database
                for e in self.db.all():
                    val = str(e.get("acronym") or "").strip()
                    if val.lower() == t_clean.lower():
                        found.add(val)
                        break
        return found

    def _get_acronym_definitions(self, acronyms: Set[str], context: str) -> str:
        """Resolve a set of acronyms using the database and format them as context."""
        defs = []
        for ac in acronyms:
            try:
                res = self.resolver.resolve(acronym=ac, context=context)
                if res.get("status") == "auto_selected":
                    meaning = res.get("selected", {}).get("meaning") or {}
                    full = meaning.get("fullForm", "")
                    desc = meaning.get("description", "")
                    line = f"- {ac} = {full}"
                    if desc:
                        line += f" ({desc})"
                    defs.append(line)
                elif res.get("status") in ("needs_user_choice", "needs_user_provide"):
                    top2 = res.get("top2") or []
                    if top2:
                        best = top2[0].get("meaning") or {}
                        full = best.get("fullForm", "")
                        desc = best.get("description", "")
                        line = f"- {ac} = {full} [Estimated]"
                        if desc:
                            line += f" ({desc})"
                        defs.append(line)
            except Exception as e:
                print(f"[AgenticSearch] Error resolving acronym {ac}: {e}")

        if not defs:
            return ""
        return "Acronym Definitions:\n" + "\n".join(defs) + "\n\n"

    def local_fallback_generate(self, query: str, hits: list) -> str:
        """Rule-based local fallback response generator when LLM is down."""
        tokens = re.findall(r"[A-Za-z0-9+\-]{2,}", query)

        attr_mapping = {
            "display": ["display", "screen", "resolution", "display_support"],
            "cpu": ["cpu", "core", "kryo", "processor"],
            "gpu": ["gpu", "adreno", "graphics"],
            "memory": ["memory", "ram", "dram", "lpddr"],
            "storage": ["storage", "ufs", "emmc", "flash"],
            "bandwidth": ["bandwidth", "memory width", "gb/s"],
            "tops": ["tops", "ai performance", "tflops", "macs"],
            "pmic": ["pmic", "power management"],
            "isp": ["isp", "spectra", "camera"],
            "video encode": ["video encode", "encoder"],
            "video decode": ["video decode", "decoder", "playback"],
            "network": ["network", "modem", "connectivity", "5g", "wifi"],
            "security": ["security", "safety", "asil"]
        }

        target_attributes = []
        q_lower = query.lower()
        for attr, keys in attr_mapping.items():
            for k in keys:
                if k in q_lower:
                    target_attributes.append(attr)
                    break

        best_answer = None
        source_tag = "[System Acronym DB p.1]"
        matched_acronym = None

        for h in hits:
            text = h.get("text", "")
            doc_id = h.get("doc_id", "System Acronym DB")
            pages = h.get("pages", "1")
            tag = f"[{doc_id} p.{pages}]"

            attributes = {}
            if "Attributes:" in text:
                lines = text.split("\n")
                for line in lines:
                    if "=" in line:
                        parts = line.split("=", 1)
                        attributes[parts[0].strip().lower()] = parts[1].strip()

            for target in target_attributes:
                for key, val in attributes.items():
                    if target in key or key in target:
                        best_answer = f"The {attributes.get('full form', doc_id)} features/supports {val}. {tag}"
                        source_tag = tag
                        matched_acronym = attributes.get('acronym')
                        break
                if best_answer:
                    break

            if best_answer:
                break

        if not best_answer and hits:
            h0 = hits[0]
            text0 = h0.get("text", "")
            doc_id0 = h0.get("doc_id", "System Acronym DB")
            pages0 = h0.get("pages", "1")
            source_tag = f"[{doc_id0} p.{pages0}]"

            full_form = ""
            desc = ""
            for line in text0.split("\n"):
                if line.startswith("Full Form:"):
                    full_form = line.split(":", 1)[1].strip()
                elif line.startswith("Description:"):
                    desc = line.split(":", 1)[1].strip()

            if full_form and desc:
                best_answer = f"The {full_form} is {desc}. {source_tag}"
            else:
                clean_text = text0.split("Attributes:")[0].strip()
                best_answer = f"{clean_text}. {source_tag}"

        if not best_answer:
            best_answer = "Not found in the provided documents."

        return best_answer

    def run(self, query: str, history_context: str | None = None) -> Dict[str, Any]:
        """Synchronous wrapper for run_yield to preserve backward compatibility."""
        res = {}
        for step in self.run_yield(query, history_context):
            if "answer" in step:
                res = step
        return res

    def run_yield(self, query: str, history_context: str | None = None, resolved_expansion: str = "",
                  preferred_model: str | None = None):
        """Run the reasoning, retrieval, and generation loop yielding status updates in real-time.

        preferred_model: optional route name from the UI model picker
        (e.g. 'LLM_PRIMARY', 'LLM_SECONDARY', 'LLM_LOCAL'). Used ONLY for
        the final answer-generation call below -- the sufficiency-eval
        calls always use TASK_AGENT_EVAL_ROUTES regardless of this choice.
        """
        msg = f"Starting agentic loop for query: '{query}'"
        print(f"\n[AgenticSearch] {msg}")
        yield {"status": msg}

        # Keep track of retrieved candidate chunks
        all_hits = []
        seen_texts = set()

        current_query = query
        iteration = 0
        resolved_acronyms = []
        if resolved_expansion:
            resolved_acronyms.append(resolved_expansion)

        while iteration < settings.agent_max_iterations:
            iteration += 1
            msg_loop = f"Iteration {iteration}/{settings.agent_max_iterations}: Analyzing search parameters"
            print(f"[AgenticSearch] {msg_loop}")
            yield {"status": msg_loop}

            # Step 1: Retrieve document chunks
            msg_ret = f"Iteration {iteration}/{settings.agent_max_iterations}: Retrieving document specification passages"
            print(f"[AgenticSearch] {msg_ret}")
            yield {"status": msg_ret}

            hits = retrieve(current_query, verbose=(iteration == 1))
            new_hits_added = 0
            for h in hits:
                val = h.get("text")
                txt = "" if (val is None or (isinstance(val, float) and val != val)) else str(val).strip()
                h["text"] = txt
                if txt not in seen_texts:
                    seen_texts.add(txt)
                    all_hits.append(h)
                    new_hits_added += 1

            print(f"[AgenticSearch] Retrieved {len(hits)} candidates, added {new_hits_added} unique chunks.")

            if hits:
                top_sources = ", ".join([f"{h.get('doc_id')} (p.{h.get('pages')})" for h in hits[:3]])
                yield {"status": f"Iteration {iteration}/{settings.agent_max_iterations}: Retrieved top sources: {top_sources}"}

            if not all_hits:
                msg_empty = f"Iteration {iteration}/{settings.agent_max_iterations}: No document chunks retrieved."
                yield {"status": msg_empty}
                break

            # Format current context for evaluation
            context_block = ""
            for i, h in enumerate(all_hits, 1):
                context_block += f"Passage {i} (Score: {h.get('score', 0.0):.3f}):\n{h.get('text', '')}\n\n"

            # Step 2: Evaluate sufficiency
            msg_eval = f"Iteration {iteration}/{settings.agent_max_iterations}: Evaluating if context is sufficient to answer"
            print(f"[AgenticSearch] {msg_eval}")
            yield {"status": msg_eval}

            eval_prompt = (
                "You are an information sufficiency evaluator. Analyze the user question and the retrieved passages.\n\n"
                f"Question: {query}\n\n"
                f"Retrieved Passages:\n{context_block}"
                "Task:\n"
                "Determine if the retrieved passages contain sufficient, concrete, and exact facts to answer the question fully and accurately.\n"
                "- If the passages are for a different product model, variant, or version than requested (e.g. they describe 'SA8155P' but the query asks about 'SA8195P'), you MUST write 'NO' and suggest a search query targeting the correct model version.\n"
                "- If the passages list a specification block but omit the requested parameter, write 'NO' and suggest a refined search query.\n"
                "Reply with exactly 'YES' or 'NO' on the first line.\n"
                "If you write 'NO' and believe that searching with different keywords would find the information, write on the second line exactly: SEARCH: <new keywords> (e.g. SEARCH: SA8195P LPDDR4X memory).\n"
                "If you write 'NO' and believe you need the definition or full form of any acronym (e.g. SA8775P, CPU, etc.) to understand the query or verify the specifications, write on another line exactly: NEED_ACRONYM: <acronym>."
            )

            try:
                eval_response = self._call_eval_llm(eval_prompt, system="Reply with YES or NO.")
                lines = [l.strip() for l in eval_response.split("\n") if l.strip()]
                decision = lines[0].upper() if lines else "YES"
            except Exception as e:
                print(f"[AgenticSearch] Sufficiency evaluation failed: {e}. Defaulting to YES.")
                decision = "YES"
                eval_response = "YES"
                lines = ["YES"]

            print(f"[AgenticSearch] Evaluation response:\n{eval_response}")

            # Check if model requested an acronym resolution
            needed_acronym = None
            if "NEED_ACRONYM:" in eval_response.upper():
                for line in lines:
                    if line.upper().startswith("NEED_ACRONYM:"):
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            needed_acronym = parts[1].strip().strip("'\"`[]")
                            break

            if needed_acronym:
                msg_acr_req = f"Model requested acronym definition for: '{needed_acronym}'"
                print(f"[AgenticSearch] {msg_acr_req}")
                yield {"status": msg_acr_req}

                # Check if it was already resolved
                already_resolved = False
                for r in resolved_acronyms:
                    if needed_acronym.lower() in r.lower():
                        already_resolved = True
                        break

                if not already_resolved:
                    res = self.resolver.resolve(acronym=needed_acronym, context=query)
                    if res.get("status") == "auto_selected":
                        meaning = res.get("selected", {}).get("meaning") or {}
                        expanded = f"{needed_acronym} = {meaning.get('fullForm','')}".strip()
                        if meaning.get("description"):
                            expanded += f" — {meaning.get('description','')}"
                        resolved_acronyms.append(expanded)
                        msg_auto = f"Acronym '{needed_acronym}' auto-resolved: '{expanded}'"
                        print(f"[AgenticSearch] {msg_auto}")
                        yield {"status": msg_auto}
                        # Do another iteration with this acronym context!
                        continue
                    else:
                        # Yield HITL choice back to the frontend
                        from src.hitl_acronym_flow import hitl_flow
                        pending = hitl_flow.create(
                            acronym=needed_acronym,
                            context=query,
                            top2=res.get("top2") or [],
                            status=(
                                "needs_user_choice"
                                if res.get("status") == "needs_user_choice"
                                else "needs_user_provide"
                            ),
                        )
                        yield {
                            "acronym_hitl": {
                                "acronym": needed_acronym,
                                "policy": res.get("policy"),
                                "top2": pending.top2,
                                "status": res.get("status"),
                                "pending_token": pending.token,
                            }
                        }
                        return

            if "YES" in decision:
                msg_yes = f"Iteration {iteration}/{settings.agent_max_iterations}: Sufficient context found. Proceeding to generation."
                print(f"[AgenticSearch] {msg_yes}")
                yield {"status": msg_yes}
                break

            # If NO, check if there is a refined query suggested
            search_query = None
            for line in lines[1:]:
                if line.upper().startswith("SEARCH:"):
                    search_query = line[7:].strip()
                    break

            if search_query:
                msg_retry = f"Iteration {iteration}/{settings.agent_max_iterations}: Context insufficient. Retrying search with: '{search_query}'"
                print(f"[AgenticSearch] {msg_retry}")
                yield {"status": msg_retry}
                current_query = search_query
            else:
                msg_no_query = f"Iteration {iteration}/{settings.agent_max_iterations}: Context insufficient, but no search keywords suggested."
                print(f"[AgenticSearch] {msg_no_query}")
                yield {"status": msg_no_query}
                break

        # Generate answer using LLM
        # Build final prompt
        context_blocks = []
        for h in all_hits:
            doc_id = h.get("doc_id", "?")
            pages = h.get("pages", "?")
            context_blocks.append(f"[{doc_id} p.{pages}] (score: {h.get('score', 0.0):.3f})\n{h.get('text', '')}")

        final_context = "\n\n".join(context_blocks)

        system_prompt = (
            "You are a technical-documentation assistant for automotive and semiconductor spec sheets. "
            "Answer the user's question using ONLY the context passages, each tagged like [Some Doc p.15].\n\n"
            "- If the passages list specific configurations for different product models (e.g. '2x8GBytes for SA8195P', '2x4GBytes for SA8155P'), you MUST match the target model from the user's query and extract its exact configurations (e.g. 'For SA8195P, it has 2x8GBytes LPDDR4X memory').\n"
            "- NEVER use generic or pre-trained knowledge. If the text says '2x8GBytes' for SA8195P, do not report 'up to 32GB'.\n"
            "- When a passage contains \"Attributes=...\", treat it as multiple key-value pairs.\n"
            "- ALWAYS match the user's query to the EXACT attribute key (e.g., \"Video Encode\", \"Video Decode\").\n"
            "- Extract ONLY the value corresponding to that exact attribute.\n"
            "- NEVER mix values from different attributes, even if they appear in the same row.\n"
            "- If multiple attributes are present, ignore all others and return only the matching one.\n\n"
            "A \"table\" or \"table row\" passage is an extracted table; columns labelled 0, 1, 2 are unnamed "
            "columns from the source file -- infer their meaning from the values. The answer may span more "
            "than one passage.\n\n"
            "Reply like a knowledgeable colleague answering the question out loud:\n"
            "- Write complete, natural sentences. Begin by naming the subject, e.g. \"The SA7255P supports ...\".\n"
            "- Report values EXACTLY as written -- every number, unit and part number unchanged. Weave them "
            "into your wording; never paste raw table fragments, column dumps, or run-together text.\n"
            "- EXCEPTION: if the user is asking to compare multiple items/models/rows against several "
            "attributes (a genuinely tabular comparison), present that comparison as a clean Markdown "
            "table using standard pipe syntax, e.g.:\n"
            "  | Attribute | SA7255P | SA8195P |\n"
            "  |---|---|---|\n"
            "  | CPU | ... | ... |\n"
            "  Only use a table for genuinely multi-row/multi-column comparisons -- a single value or a "
            "short list still gets a normal sentence, not a one-row table.\n"
            "- If the question matches several items, variants, rows or models, list EACH one with its own "
            "value -- do not collapse them into a single figure. Completeness beats brevity here.\n"
            "- Report only what each passage states. Do not aggregate, average, total, or reduce several "
            "distinct values to one, and never write \"up to\", \"around\" or \"about\" unless the passage itself "
            "uses that word or gives that range.\n"
            "- Where the extraction lost spacing (e.g. \"16MP4xCSI2\"), write it cleanly (\"16 MP, 4x CSI-2\") "
            "without changing any value.\n"
            "- Cite using the bracketed tag that precedes each passage, copied verbatim, e.g. [Some Doc p.15].\n"
            "- If the answer is not in the passages, reply exactly: Not found in the provided documents.\n\n"
            "Be as brief as the question allows, but never drop a value to stay short. Cite ONLY the bracketed "
            "tags -- never invent a citation or refer to a passage by number."
        )

        hist_block = "" if not history_context else f"Conversation memory (cache):\n{history_context}\n\n"

        # Format acronym context if any were resolved
        acronym_context = ""
        if resolved_acronyms:
            acronym_context = "Acronym Definitions:\n" + "\n".join([f"- {r}" for r in resolved_acronyms]) + "\n\n"

        user_prompt = (
            f"{hist_block}"
            f"{acronym_context}"
            f"Context (passages ordered most relevant first):\n{final_context}\n\n"
            f"Question: {query}"
        )

        msg_final = "Generating final response..."
        yield {"status": msg_final}

        try:
            final_answer = self._call_answer_llm(user_prompt, system=system_prompt, preferred_route=preferred_model)
        except Exception as e:
            print(f"[AgenticSearch] Final generation LLM failed: {e}. Using local_fallback_generate.")
            final_answer = self.local_fallback_generate(query, all_hits)

        # Build the final source view
        sources = []
        for i, h in enumerate(all_hits, 1):
            val = h.get("text")
            t = "" if (val is None or (isinstance(val, float) and val != val)) else str(val).strip()
            sources.append({
                "rank": i,
                "score": round(float(h.get("score", 0.0)), 3),
                "doc_id": h.get("doc_id", "?"),
                "pages": h.get("pages") if isinstance(h.get("pages"), (str, int)) else "p.?",
                "kind": h.get("kind", "text"),
                "text": t[:600] + (" ..." if len(t) > 600 else ""),
            })

        yield {
            "answer": final_answer,
            "sources": sources
        }
