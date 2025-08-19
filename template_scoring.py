# selection_semantic.py
import numpy as np
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from .db import TemplateModel, TextFieldModel
from .models_embeddings import TextFieldEmbeddingModel

EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Reuse your earlier helpers:
# - extract_features_from_text(decoded)
# - image_fit_score(t, n_prop, n_logo, n_realtor_ph)
# - infer_expected_type(fmt): str -> {"price","address-ish","list-commas","free",...}
# - type_match(expected, val): Any -> [0..1]
# - value_length(val)

# Build the small set of semantic signals to cover many field variants
def build_signal_texts(extracted: Dict[str, Any]) -> Dict[str, str]:
    signals: Dict[str, str] = {}
    if extracted.get("headline"):
        signals["headline"] = extracted["headline"]
    # stats (collate)
    if any(extracted.get(k) is not None for k in ("beds", "baths", "sqft")):
        parts = []
        if extracted.get("beds") is not None: parts.append(f"{extracted['beds']} beds")
        if extracted.get("baths") is not None: parts.append(f"{extracted['baths']} baths")
        if extracted.get("sqft") is not None: parts.append(f"{extracted['sqft']} sqft")
        signals["stats"] = " | ".join(parts)
    if extracted.get("price"): signals["price"] = extracted["price"]
    if extracted.get("address"): signals["address"] = extracted["address"]
    if extracted.get("features"): signals["features"] = ", ".join(extracted["features"])
    if extracted.get("body"): signals["body"] = extracted["body"][:500]
    # a couple of strong first lines to help headline/tagline
    first_line = signals.get("headline") or ""
    if first_line: signals["headline_alt"] = first_line[:60]
    return signals

def cosine_sim(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    # A: [m, d], B: [n, d], both normalized
    return A @ B.T

def score_templates_semantic(
        db: Session,
        decoded_text: str,
        n_prop: int, n_logo: int, n_realtor_ph: int
) -> Tuple[TemplateModel, Dict[str, Any]]:
    # 1) Extract signals once
    extracted = extract_features_from_text(decoded_text)
    signal_texts = build_signal_texts(extracted)

    # 2) Embed signals once
    model = SentenceTransformer(EMBED_MODEL_NAME)
    sig_keys = list(signal_texts.keys())
    sig_vecs = model.encode([signal_texts[k] for k in sig_keys], normalize_embeddings=True)
    S = np.asarray(sig_vecs, dtype=np.float32)  # [Ns, d]

    # 3) Pull templates + field embeddings
    templates: List[TemplateModel] = db.query(TemplateModel).all()
    if not templates:
        raise ValueError("No templates")

    tf_emb_rows: List[TextFieldEmbeddingModel] = (
        db.query(TextFieldEmbeddingModel)
        .filter(TextFieldEmbeddingModel.template_id.in_([t.id for t in templates]))
        .all()
    )
    by_tid: Dict[int, List[TextFieldEmbeddingModel]] = {}
    for r in tf_emb_rows:
        by_tid.setdefault(r.template_id, []).append(r)

    # 4) Score each template
    scored = []
    debug_rows = []

    for t in templates:
        fields = by_tid.get(t.id, [])
        if not fields:
            continue

        # gather field vectors
        F = np.asarray([f.embedding for f in fields], dtype=np.float32)  # [Nf, d]
        sim = cosine_sim(F, S)  # [Nf, Ns]
        # best signal per field
        best_sig_idx = np.argmax(sim, axis=1)
        best_sim = sim[np.arange(sim.shape[0]), best_sig_idx]  # [Nf]

        # Coverage: how many fields exceed a sim threshold
        THRESH = 0.45  # tune
        covered = best_sim >= THRESH
        coverage = covered.mean() if len(covered) else 0.0

        # Length & format fit computed only for covered fields
        length_scores = []
        format_scores = []

        for i, frow in enumerate(fields):
            if not covered[i]:
                continue
            sig_key = sig_keys[best_sig_idx[i]]
            sig_val = signal_texts.get(sig_key, "")
            tgt_len = frow.approx_length or (len(frow.example_format) if frow.example_format else 32)

            # length fit
            mismatch = abs(value_length(sig_val) - tgt_len) / max(tgt_len, 1)
            length_scores.append(1.0 - min(mismatch, 1.0))

            # format/type fit
            expected = infer_expected_type(frow.example_format or "")
            format_scores.append(type_match(expected, sig_val))

        length_fit = sum(length_scores) / len(length_scores) if length_scores else 0.5
        format_fit = sum(format_scores) / len(format_scores) if format_scores else 0.5

        # Image fit from your earlier function
        img_fit = image_fit_score(t, n_prop, n_logo, n_realtor_ph)

        # Final weighted score (tuneable)
        final = 0.45 * coverage + 0.30 * img_fit + 0.15 * length_fit + 0.10 * format_fit
        scored.append((final, t))

        debug_rows.append({
            "template_name": t.template_name,
            "coverage": round(float(coverage), 3),
            "img_fit": round(float(img_fit), 3),
            "length_fit": round(float(length_fit), 3),
            "format_fit": round(float(format_fit), 3),
            "final": round(float(final), 3),
        })

    if not scored:
        raise ValueError("No scorable templates (missing field embeddings?)")

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    return best, {
        "best_score": round(float(best_score), 4),
        "scored": debug_rows[:10],
        "signals": signal_texts,
    }
