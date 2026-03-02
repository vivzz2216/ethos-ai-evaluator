"""
Tone Override System Prompts — v3 (Completion-Trigger Format)

IMPORTANT: v1 (abstract rules) and v2 (full persona + few-shot) both failed
on small 2B models. The model would echo the entire prompt header back instead
of generating a response, because:
  - The prompts were too long (> context budget left for generation)
  - 2B models don't follow complex roleplay meta-instructions reliably
  - The model saw "## SYSTEM:" and treated the whole thing as text to continue

FIX: Use a SHORT instruction + "Completion trigger" that forces the model to
START generating the answer, not repeat the instruction.

The key pattern is:
    [Short style instruction]
    [Original prompt]
    [Completion trigger phrase]:

The model continues after the trigger phrase, generating only the answer.
Examples:
    "Casual rewrite:" → model generates casual rewrite
    "Formal response:" → model generates formal response
"""

TONE_SYSTEM_PROMPTS = {

    # ─── FORMAL ──────────────────────────────────────────────────────────────────
    "formal": (
        "Rewrite the following in strictly formal English. "
        "Use professional vocabulary, complete sentences, no contractions, no slang, no emojis.\n\n"
        "Task: {prompt}\n\n"
        "Formal response:"
    ),

    # ─── INFORMAL ────────────────────────────────────────────────────────────────
    "informal": (
        "Rewrite the following in a very casual, friendly tone — like texting a close friend. "
        "Use contractions (don't, can't, it's), slang, short sentences, and emojis.\n\n"
        "Task: {prompt}\n\n"
        "Casual rewrite:"
    ),

    # ─── MIXED ───────────────────────────────────────────────────────────────────
    "mixed": (
        "Respond to the following in a balanced tone — professional but approachable. "
        "Use contractions where natural, keep it clear and warm.\n\n"
        "Task: {prompt}\n\n"
        "Balanced response:"
    ),
}

# Emergency retry prompts (used when first attempt is wrong style)
RETRY_PROMPTS = {
    "formal": (
        "Write a formal, professional response. No slang, no contractions, no emojis.\n\n"
        "Question: {prompt}\n\n"
        "Professional answer:"
    ),
    "informal": (
        "Write a short, casual reply like you're texting a friend. "
        "Use slang and emojis 🔥. Keep it brief.\n\n"
        "Question: {prompt}\n\n"
        "Casual reply:"
    ),
    "mixed": (
        "Answer in a friendly but professional tone.\n\n"
        "Question: {prompt}\n\n"
        "Response:"
    ),
}


def get_tone_system_prompt(style: str, prompt: str = "") -> str:
    """
    Get the completion-trigger tone prompt for the given style.

    Args:
        style:  'formal', 'informal', or 'mixed'
        prompt: The original user prompt to embed in the template

    Returns:
        Complete prompt string ready to send to the model.
        If prompt is empty, returns the template with placeholder.
    """
    template = TONE_SYSTEM_PROMPTS.get(style.lower(), TONE_SYSTEM_PROMPTS["formal"])
    if prompt:
        return template.format(prompt=prompt)
    return template


def get_retry_prompt(style: str, prompt: str = "") -> str:
    """
    Get the aggressive retry prompt for when the first attempt fails.
    """
    template = RETRY_PROMPTS.get(style.lower(), RETRY_PROMPTS["formal"])
    if prompt:
        return template.format(prompt=prompt)
    return template
