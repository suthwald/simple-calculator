Extracting structured rules from messy Confluence pages is a classic engineering headache. Atlassian Document Format (ADF) to Markdown conversions often create brittle outputs, and relying on header levels for chunking will always fail when the authors aren't strictly disciplined with their formatting.
Since your primary bottlenecks are structural (bad headings, formatting spillovers, and sequencing), the solution requires moving away from rigid, rule-based text parsing and leaning into semantic, context-aware processing.
Here are a few robust approaches to redesign your pipeline and extract high-quality rules.
### Strategy 1: The "Zero-Chunking" Large Context Bypass (Recommended)
If your SDLC document is under 1-2 million tokens (which is highly likely for a single Confluence page or even a tree of pages), the most effective approach is to bypass chunking entirely. Chunking was historically necessary for small context windows, but it inherently destroys the global sequence and context.
 * **The Approach:** Pass the raw Markdown (or even the raw ADF JSON) into a model with a massive context window in a single prompt.
 * **The Extraction:** Use structured data generation (like Pydantic models in Python) to force the LLM to output a strict JSON list of rules.
 * **Why it fixes your problems:** The LLM evaluates the entire document at once. It ignores broken headings and markdown spillovers because it relies on the *semantic meaning* of the text rather than formatting markers to understand what constitutes a rule.
### Strategy 2: The Two-Pass "Cleaner & Extractor" Pipeline
If you must chunk (e.g., for cost control or pipeline constraints), you need to fix the unstructured data *before* you chunk it. You can implement a two-pass LLM workflow.
**Pass 1: The Document Sanitizer**
Feed the raw, messy markdown to an LLM with instructions specifically targeting your formatting issues:
 * "Reconstruct this document to have a logical, sequential header hierarchy (H1, H2, H3)."
 * "Fix any broken markdown code blocks. Ensure code snippets are properly fenced and regular text is outside the fences."
 * "Do not summarize or delete content; only fix the structural formatting."
**Pass 2: Semantic Chunking & Extraction**
Once you have a sanitized markdown file, abandon header-based chunking. Instead, use **Semantic Chunking**.
 * This groups text based on meaning (using embeddings) rather than structural tags.
 * When extracting rules chunk-by-chunk, inject a "Global Context" string into the prompt (a 3-sentence summary of the whole page) so the extractor understands where the current chunk fits in the overall SDLC sequence.
### Strategy 3: Multi-Agent Extraction Workflow
You can treat this as a specialized data pipeline where different "agents" handle specific types of messiness in the document.
 1. **Parsing Agent:** Handles the ADF to Markdown conversion, specifically trained to flag and fix macro spillovers.
 2. **Structuring Agent:** Reads the full text and generates an outline/sequence map of the SDLC phases (Requirements, Design, Testing, etc.), regardless of how the headers are formatted.
 3. **Extraction Agent:** Iterates through the text, using the sequence map as a guide, to pull out actionable rules.
 4. **Validation Agent:** Evaluates the extracted rules against a quality threshold before saving to SQLite. It checks: *Is this rule actionable? Is it tied to a specific SDLC phase? Is it distinct from previously extracted rules?*
### Database Schema Considerations
To ensure the rules you store are genuinely "good quality," your SQLite schema should enforce rigorous metadata. Instead of just storing the text, extract into a structure like:
 * rule_id (Primary Key)
 * sdlc_phase (e.g., "Code Review", "Deployment")
 * rule_statement (The actionable best practice)
 * original_context (A snippet of the source text for traceablity)
 * confidence_score (LLM-generated score on how explicit the rule was in the text)
To help narrow down the best architecture for your setup: roughly how large is this Confluence page (in terms of word count or estimated tokens), and do you have access to models with large context windows?




You hit the nail right on the head. This is the exact architectural bottleneck of large-context models.
While a model like Gemini 1.5 Pro can ingest up to 2 million tokens of *input* context (easily swallowing a massive Confluence page), the *output* token limit is typically capped at around 8,192 tokens. If you have 500 rules, and you are extracting them into a structured JSON schema with a rule_statement, sdlc_phase, and original_context, you will crash into that output ceiling long before the response finishes.
Here is how you engineer around the output limit while still preserving the global context of the document.
### 1. The Contextual Pagination Pattern
You still pass the entire Confluence document in a single prompt to maintain the global context, but you programmatically instruct the LLM to return the results in batches.
 * **Call 1:** "Read this entire document. Extract all rules found *only* in the first 30% of the text. Output as a JSON list."
 * **Call 2:** "Read this entire document. Extract all rules found from the 30% mark to the 60% mark."
Alternatively, you can paginate by logical domain if the document has a predictable flow: "Extract all rules related *only* to Testing and Deployment phases." This keeps the massive input context intact but strictly throttles the output payload.
### 2. The Map-Reduce Agent Workflow (Most Robust)
If you are already orchestrating AI agents or using a development kit to build your pipeline, a map-reduce pattern is the most resilient approach for massive rule sets.
 * **Step 1: Map (The Indexer Call).** Send the whole document and ask the LLM to simply output a high-level table of contents or an "index of rule categories" found in the text. This uses massive input but generates a very short output.
 * **Step 2: Reduce (The Extraction Calls).** Spawn parallel extraction tasks. Pass the entire document to multiple LLM calls simultaneously, but assign each call a specific section from your generated index.
   * *Task A:* "Given this full document, extract only the rules for section A."
   * *Task B:* "Given this full document, extract only the rules for section B."
 * **Step 3: Aggregate.** Collect the outputs from the parallel runs, validate them against your schema, and write them directly into your SQLite database.
### 3. Threshold-Based Semantic Chunking
If passing the whole document multiple times becomes too slow or costly, you have to chunk—but you chunk by token count and semantic overlap, not by Atlassian headers.
 * Slice the Markdown document into rigid 10,000-token chunks, completely ignoring where the headers fall.
 * To ensure you don't cut a rule in half, create a 1,000-token overlap between chunks (e.g., Chunk 1 is tokens 0–10,000; Chunk 2 is tokens 9,000–19,000).
 * Process each chunk individually for extraction.
 * Add a post-processing step before inserting into SQLite to deduplicate any rules that were extracted twice because they fell within the overlapping overlap zones.
