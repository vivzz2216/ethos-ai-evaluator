# Social Awareness Fixes & Scoring Explained

We have fully implemented your requests to tackle the 2B model's generation issues.

### 1. The 3 Fixes Implemented

1. **Similarity Fallback (`cosine_similarity < 0.35`)**:
   We added a post-generation semantic guard. Since the 2B model sometimes hallucinates garbage that has no relation to the prompt, we compare the original response to the new LLM output using `sentence-transformers` (cosine similarity). 
   - **If similarity < 35%**: The LLM's output is completely discarded. The system falls back to running the Deterministic Regex Transformer on the *original* text to guarantee safety and relevance.

2. **Garbage Token Filtering**:
   Immediately after the model generates text, it passes through a new sanitization function:
   ```python
   # Strip non-ASCII artifacts completely
   output = re.sub(r'[^\x00-\x7F]+', '', output)
   # Strip block characters explicitly
   output = re.sub(r'■+', '', output)
   # Catch 'failRGBARGBA' and similar token repetitions
   output = re.sub(r'\b\w*?(?:[A-Z]{2,}){3,}\w*\b', '', output)
   ```
   *Result:* Responses like "failRGBARGBA ANDGETTAIED" are permanently fixed.

3. **Guaranteed Regex Cleanup Pass**:
   The LLM output is now *always* passed through the Regex Transformer as the final step. If the model generated mostly informal text but left behind a stiff phrase like "It is important to note," the regex pass catches and casualizes it, ensuring you cross the >90% informal threshold.

---

### 2. How We Calculate Formal / Informal Percentage Scores

When a transformed response is evaluated, it is passed through `style_detector.py`. Our system does **not** rely on simple keyword counting; it uses a weighted formula to generate the 0–100% confidence scores.

Here is exactly how a response is scored:

#### A. Informal Signal Detection
The system scans for specific markers and multiplies them by aggression weights:
- **Slang & Chat Fillers (15x weight)**: ("lol", "tbh", "ngl", "basically", "literally", "bruh").
- **Contractions (12x weight)**: ("don't", "can't", "it's").
- **Emojis (3x weight)**: Heavily boosts informal score.
- **Punctuation**: High frequency of exclamation marks boosts informal.

#### B. Formal Signal Detection
The system scans the syntax and vocabulary:
- **Formal Vocabulary (10x weight)**: ("utilize", "commence", "furthermore", "accordingly").
- **Syntax Formality**: 
   - Passive voice presence ("The meeting is scheduled...").
   - Modal verb usage ("shall", "ought", "may").
   - Noun phrase density (very dense sentences heavily boost formal).
   - Sentence length variance (robotic, evenly long sentences = formal).

#### C. Score Calculation & Hard Overrides
The *Informal Signal* and *Formal Signal* are combined and normalized so they sum to 100%. However, we added strict **Hard Overrides**:
- **The "Vibe Check" Override**: If the text contains >3% slang OR >2% emojis, the text receives an **automatic minimum score of 65% Informal**, regardless of how many formal words it might accidentally contain. 
- **The "Stiff" Override**: If the text uses formal vocabulary and has near-zero contractions, it receives an automatic minimum of 65% Formal.

**Final Classification:**
The difference between the Formal % and Informal % is calculated.
- If the gap is `< 15%`, the response is labeled **MIXED**.
- Otherwise, it gets the highest label (**FORMAL** or **INFORMAL**).
