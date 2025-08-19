def truncate_fields(fields_dict, max_length=100):
    """Truncate string values in a dict if they're too long."""
    truncated = {}
    for k, v in fields_dict.items():
        if isinstance(v, str) and len(v) > max_length:
            truncated[k] = v[:max_length] + "…"
        else:
            truncated[k] = v
    return truncated


def build_truncation_prompt(text):
    return f"Shorten the following text: {text}. Return only the shortened text and nothing else"


def build_extraction_prompt(fields: list, input_text: str) -> str:
    """
    fields: list of fields
    input_text: unstructured input text
    """
    field_list = "\n".join(
        [f"- {name}, approx_size: {fields[name]['approx_length']}, format: {fields[name]['format']}" for name in
         fields])
    json_template = "{\n" + ",\n".join([f'  "{name}": "..."' for name in fields]) + "\n}"
    print(field_list)

    prompt = f"""
        You are an intelligent field extractor.


        Your job: extract structured info from the input text and return valid JSON.
        Each field has an `approx_size` which is a HARD MAXIMUM number of characters (count ALL characters including spaces and punctuation). 
        Do not exceed this maximum for ANY field. If you cannot fit within the limit, shorten the text using the rules below. 
        If a field is missing/unclear, return null for that field.

        Return result as raw text (no markdown code fences). Return ONLY a single valid JSON object.

        Fields to extract:
        {field_list}

        Output the result as a valid JSON object like this:
        {json_template}

        --- Begin Input ---
        {input_text}
        --- End Input ---

        ----------------
        SHORTENING RULES (apply in order, stop as soon as within limit)
        1) Remove filler/weasel words: very, really, quite, just, simply, extremely, truly, actually, unique, stunning, beautiful, amazing, spacious, lovely.
        2) Prefer concise synonyms/abbreviations (case-sensitive as shown):
           and → & ; with → w/ ; minutes → min ; approximately → approx ; including/includes → incl ; 
           apartment → apt ; property → prop ; features → feats ; near → nr
        3) Remove articles when safe: a, an, the.
        4) Remove parentheticals: text inside (...) including the parentheses.
        5) Compress whitespace: single spaces; remove spaces around separators like “|”, “/”, “–”, “-”, “,” where it helps readability.
        6) If still too long, truncate at a natural boundary (end of word), do NOT add ellipsis unless the format example shows it.
        7) NEVER exceed approx_size. If you cannot fit meaningful content, set the field to null.

        ----------------
        FORMATTING RULES
        - Count characters exactly, including spaces and punctuation.
        - Respect any delimiter/shape suggested by the field’s `format`. 
        - For `text_features`-style lines, keep the structure “<N> BED | <N> BATH” if present in the input; use integers only.
        - Use ASCII quotes only in JSON keys/values.
        - Do not pad with extra spaces to “use up” space.
        - If no data is available for a field, use null exactly (no quotes).

        """
    return prompt.strip()


