# Viva preparation: Member 2 module

## Rules for answering
1. Say what is **implemented**, what is **tested**, and what is **not yet proven**. The honest answer is the strong answer.
2. Never claim an accuracy number, "the AI understands Bharatanatyam", or that the whole NrityaGuru app is finished.
3. Standard techniques (RAG, DTW, MLP, embeddings) are not your invention. Your contribution is the application-specific integration.

## One-minute pitch
"My module is the knowledge and AI layer of NrityaGuru. Facts about mudras live in a PostgreSQL knowledge base with a source and a verification status
on every record. When a learner types a sentence, I extract candidate concepts, retrieve only supported records, and ask Gemini to explain them in
beginner language; its answer is validated against what was retrieved, and if anything fails the learner still gets the retrieved facts. For feedback,
I take structured results from the evaluation module, turn them into numbered evidence, and let Gemini phrase feedback that must cite that evidence;
it is never allowed to invent an error. Everything is labelled as practice assistance, not expert judgement."

## Five-minute demo (works without a Gemini key)
```bash
docker compose up -d db && cd backend && source .venv/bin/activate
python -m app.db.init_db && python -m app.db.seed && uvicorn app.main:app --reload     # second terminal for the curls
curl -s -X POST localhost:8000/api/tutor/explain -H "Content-Type: application/json" -d '{"text":"Krishna is singing and dancing in the garden."}'
```
Point out: nothing is invented for Krishna/garden: "no supported reference". Then:
```bash
curl -s -X POST localhost:8000/api/tutor/explain -H "Content-Type: application/json" -d '{"text":"The river and the clouds","include_unverified":true}'
curl -s -X POST localhost:8000/api/feedback/generate -H "Content-Type: application/json" -d '{"session_id":"mock-session-mismatch"}'
```
Point out: `verification_status: source_cited`, the limitations list, `is_mock: true`, and "the cause cannot be stated" for the mismatch session. Say clearly that the evaluation data is mock.

## Questions and answers

### Project and architecture
**1. What does your module do, and what does it not do?** It stores and retrieves verified Bharatanatyam knowledge, explains it with Gemini (RAG), and turns the evaluation module's structured results into grounded feedback. It does not capture video, extract landmarks, train the MLP or run DTW; those belong to teammates and I only define a contract for their output.
**2. Describe the architecture.** FastAPI routers call services; services call repositories (SQLAlchemy) and one Gemini client; Pydantic schemas define every request, response and contract. Only `gemini_client.py` talks to Gemini; only repositories write SQL.
**3. Why that separation?** Each part can be tested with fakes (a fake Gemini, an in-memory store), and a change in one place (for example the Gemini SDK) does not ripple through the code.
**4. What is original in your work?** Not the algorithms. The contribution is the integration: provenance-aware retrieval, guards that stop invented details, and feedback that is limited to evidence the evaluation module actually produced.

### RAG
**5. What is RAG and why use it?** Retrieval-Augmented Generation: fetch trusted facts first, then ask the language model to explain only those. It keeps knowledge in an auditable database that can be corrected by editing rows, instead of trusting the model's memory.
**6. Explain your flow.** Validate text -> extract concepts -> retrieve from PostgreSQL (mapping > exact name > alias > listed usage) -> build a bounded prompt -> Gemini -> parse JSON -> check shape (Pydantic) -> check claims against retrieved records -> response, always including the retrieved records.
**7. Why not fine-tune a model?** There is no large labelled text dataset, fine-tuning would bake facts into weights where they cannot be audited or corrected, and it costs time and money. A tiny curated knowledge base fits RAG.
**8. What exactly is sent to Gemini?** A prompt with the learner text (quoted as data), the retrieved records (name, meaning, usages, status, source, limitations, allowed ids), and rules. Never the whole database, never keys.
**9. What if nothing is retrieved?** Gemini is not called. The answer says no supported reference was found and that this does not prove none exists. This is how "Krishna is singing and dancing in the garden" is handled today.
**10. Does RAG remove hallucination?** No, it reduces it. The model can still misword a retrieved fact. That is why there are grounding checks, a fallback, and a human review sheet; faithfulness of wording is not measured yet.

### Gemini
**11. Which model and SDK, and how did you decide?** The `google-genai` SDK and `gemini-3.8-flash`. I read Google's release notes (Oct 2026): `gemini-2.5-flash` still exists but access is limited to existing users since 18 Sep 2026, and new projects are told to use newer models. The model id is one setting. I could not run the real API in my environment, so `python -m scripts.smoke_gemini` is the proof on a real machine.
**12. Why no `temperature`?** Google's docs say `temperature`, `top_p` and `top_k` are deprecated and ignored on current models, so sending them would only mislead.
**13. How do you handle Gemini failures?** Every exception is classified (timeout, rate limit, unavailable, bad key/model, empty reply) into a safe code with no upstream text; the service then returns the retrieved knowledge (tutor) or the evidence-only findings (feedback). No blind retry: it costs quota and the fallback is useful.
**14. Why ask for JSON and validate yourself instead of a structured-output feature?** Fewer dependencies on SDK details, and the grounding checks are needed anyway: a schema cannot say whether a cited id was really retrieved.
**15. How is the API key protected?** Environment variable only, `SecretStr` so it never prints, used in one file, never returned by any endpoint, never logged; `.env` is git-ignored and a static check scans for leaked keys.

### Embeddings
**16. What are embeddings and why not use them now?** Vectors that place similar texts close together, so "stream" can find "river". With three seed records, misses come from missing data, not vocabulary, and embeddings always return a nearest neighbour, which could produce a confident mudra for a word that has no supported mapping, the failure my rules forbid.
**17. When would you add them, and how?** With hundreds of verified records and a labelled query set that shows real synonym misses. Use pgvector inside the same PostgreSQL (no separate vector database), cosine similarity, top-k, and show results as a separate "possibly related" tier, never as a verified mapping.
**18. How would you evaluate that?** Recall@k on the labelled set, plus checking that unsupported words still return nothing.

### PostgreSQL
**19. Explain the schema.** `sources` -> `mudras`/`movements` -> `concept_mappings` (one concept can map to several records), and `practice_sessions` -> `evaluation_results` (one) and `feedback` (many). Foreign keys, unique names, and CHECK constraints (a mapping needs a target; a session has exactly one reference). Deleting a session cascades.
**20. Why JSON(B) for results?** The contracts are versioned and always read whole; they are re-validated with Pydantic on every read, so a corrupted row is rejected, not trusted. The few fields used in queries are real columns.
**21. Why not PostgreSQL full-text search?** Not needed at this size; exact/alias/usage matching is easier to reason about and portable to the SQLite used in tests. Revisit when free-text search is needed.
**22. How do you avoid SQL injection?** SQLAlchemy parameterised queries only. The one raw statement is the constant `SELECT 1`; a static check fails if SQL is built from a string.
**23. What did you not verify?** The models have been exercised on SQLite in tests, not on PostgreSQL itself.

### FastAPI and Pydantic
**24. Why FastAPI?** Automatic validation from Pydantic models, generated `/docs`, dependency injection (which also makes tests easy by overriding dependencies), and central exception handlers.
**25. Where is Pydantic used?** Request bodies, response models, settings (`pydantic-settings`), the evaluation contract, and the structure Gemini must return.
**26. Give examples of constraints.** Text 1-1000 characters; confidence 0-1; frame intervals must be ordered; exactly one of mudra/movement id; session ids match a pattern; `SecretStr` for secrets.
**27. A testing anecdote.** During final review I found that 15 API tests overrode dependencies that the endpoint no longer used after a refactor, so they would have failed. I added a static check that compares test overrides with the dependencies routes really use.

### Hallucination and feedback guards
**28. How do you stop Gemini inventing errors in feedback?** Code builds numbered evidence facts from fields the evaluation module supplied. Gemini must cite those ids. Its text is rejected if it cites an unknown id, names a body part or video/camera word the evidence does not contain, or uses a number not in the evidence. Limitations are attached by code, not by the model.
**29. What are the weaknesses?** The guards are heuristics: they do not catch a wrong mudra name or distorted wording, they are English only, and they may reject harmless text (the safe direction).
**30. How would you measure faithfulness?** A human review sheet (relevance 1-5, faithful Y/N) filled by me and my teacher over a labelled set. I do not report a percentage because 11 cases built on 3 unverified records cannot support one.
**31. Why is the evidence-only fallback useful?** The learner still sees the findings in plain templates when Gemini is down, rate limited, or rejected by the guards.

### Evaluation evidence
**32. What do MLP and DTW tell you, and what not?** The MLP gives a predicted label among the classes it was trained on (it cannot recognise unseen classes). DTW gives an alignment cost to a reference sequence; it does not say what is wrong, and a low distance is not proof of a perfect performance.
**33. What is in your contract?** Session id, reference id, expected and predicted labels with optional confidence, DTW summary, deviation records (only what the evaluation module detected), landmark quality, warnings, schema version. It is a proposal: I still need the evaluation teammate to confirm label names, deviations and delivery.
**34. Why a trusted store and a session id instead of the browser sending results?** A learner or attacker could fake evidence and make the feedback say anything. The browser sends only a session id; results are read from the database and re-validated.
**35. What does the system say for a mismatch with no detail?** That the result did not match and that no finger or joint difference was identified, so the cause cannot be stated. It never guesses a finger.
**36. How are mock results kept from passing as real?** `is_mock` flag, MOCK text, rejected if they come from a real store, never saved or reused.

### Security and privacy
**37. Biggest gap?** There is no authentication. Anyone with a session id can read its feedback; until login exists, ids must be unguessable (UUID4). Also no TLS in the repository, an in-memory rate limiter, and no retention policy.
**38. What do you store?** Session ids, the practised reference, structured evaluation results, generated feedback. No video, no images, no names, no learner free text. `delete_session()` removes a session and, by cascade, its results and feedback.
**39. What about prompt injection?** Learner and evaluation text are quoted as data with angle brackets neutralised and the rules say to ignore instructions inside them; output must still pass the citation and invented-detail guards. It reduces the risk but cannot eliminate it.

### Testing and honesty
**40. How did you test, and what has not been run?** 477 tests exist. 270 were executed in my environment against small stand-ins for pytest and pydantic (the real libraries could not be installed there), and all passed; 207 (database, HTTP, strict Pydantic constraints, SDK, live) are written but not yet run. Eleven static checks also pass and were shown to catch deliberately injected faults. Nothing has been run against the real Gemini API.
**41. What accuracy does the system have?** None is reported: no model of mine was trained or evaluated, and the knowledge base has three unverified seed records.
**42. Is your knowledge base correct?** Not yet verified. The three mudras come from a Wikipedia list (a secondary source) and are marked `source_cited`, not `verified`; they stay hidden by default until checked against the primary text or a teacher.
**43. Why only three mudras?** I only added records I could source; fabricating records to look complete would break the project's own rules. The structure is ready to grow as records are verified.

### Trade-offs and future work
**44. Top three trade-offs.** (a) Reject suspicious AI text and show plainer fallback wording instead of risking an invented error. (b) A small deterministic extractor instead of an LLM extractor: predictable but limited vocabulary. (c) No embeddings or full-text search now: simpler and safer, less flexible.
**45. What next?** Verify records with a teacher and add practice instructions and reference images; agree the contract with the evaluation teammate; add authentication and TLS; run the full test suite and a human faithfulness review; consider semantic retrieval only if measured to help.

## Glossary
RAG: retrieve facts, then generate from them. Grounding: every claim traceable to retrieved or supplied data. Embedding: a vector representing meaning. DTW: dynamic time warping, an alignment cost between two sequences. MLP: multilayer perceptron classifier. Fingerprint: a hash of the evidence used to decide whether stored feedback is still valid. JSONB: PostgreSQL's binary JSON type. Fallback: the safe answer built from templates when AI text is unavailable or rejected.

## Never say
"The AI watched the video." "The system is accurate." "The mudra meanings are verified." "Every word has a mudra." "RAG removes hallucination." "NrityaGuru is finished."
