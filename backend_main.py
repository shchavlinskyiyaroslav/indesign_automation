import json
from typing import List, Dict, Any
import cv2
import numpy as np
import openai
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
import os

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clip_classifier import ClipImageClassifier
from db import get_db, TemplateModel, Template, TextFieldModel
from helpers import build_truncation_prompt, build_extraction_prompt

app = FastAPI()
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_KEY"))
clip = ClipImageClassifier()


def truncate_text_if_needed(text: str, target_max_length: int, current_iteration: int = 1):
    """Truncate a text string using llm if it's too long."""
    if len(text) > target_max_length and current_iteration < 4:
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": build_truncation_prompt(
                text
            )}],
            temperature=0.3,
        )
        gpt_result = completion.choices[0].message.content.strip()
        return truncate_text_if_needed(gpt_result, target_max_length, current_iteration+1)
    else:
        return text


@app.post("/upload-template/")
async def upload_template(
        metadata: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    raw = await metadata.read()
    try:
        payload = json.loads(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    if not isinstance(payload, list) or not payload:
        raise HTTPException(status_code=400, detail="Body must be a non-empty JSON array")

    accepted = 0
    duplicates = 0
    errors: List[Dict[str, Any]] = []

    for i, obj in enumerate(payload):
        try:
            # 1) Validate strictly with Pydantic
            t = Template(**obj)

            # 2) Compute counts
            realtor = t.realtor or None
            logos = t.logos or []
            images = t.property_images or []
            img_count = len(logos) + len(images) + (1 if (realtor and (realtor.photo or "").strip()) else 0)

            realtor_name = (realtor.name.strip() if (realtor and realtor.name) else None) if realtor else None
            realtor_info = (realtor.info.strip() if (realtor and realtor.info) else None) if realtor else None

            realtor_texts = sum(1 for v in (realtor_name, realtor_info) if v)
            text_count = len(t.text_fields) + realtor_texts

            # 3) Create parent row
            db_template = TemplateModel(
                template_name=t.template_name,
                output=t.output,
                realtor_name=realtor_name,
                realtor_info=realtor_info,
                realtor_photo=(realtor.photo.strip() if (realtor and realtor.photo) else None) if realtor else None,
                logos=list(logos),
                property_images=list(images),
                img_count=img_count,
                text_count=text_count,
            )

            db.add(db_template)
            db.flush()  # obtain db_template.id before adding children

            # 4) Add text fields (children)
            children = []
            for name, spec in t.text_fields.items():
                # enforce clean key
                key = name.strip()
                if not key:
                    continue
                children.append(
                    TextFieldModel(
                        template_id=db_template.id,
                        name=key,
                        approx_length=spec.approx_length,
                        format=spec.format.strip(),
                    )
                )

            if children:
                db.add_all(children)

            # 5) Commit this item (isolate duplicates/violations)
            db.commit()
            accepted += 1

        except IntegrityError as ie:
            db.rollback()
            # assume UNIQUE(template_name) conflict => duplicate
            duplicates += 1
            errors.append(
                {"index": i, "template_name": obj.get("template_name"), "error": "duplicate", "detail": str(ie.orig)})
        except Exception as e:
            db.rollback()
            errors.append(
                {"index": i, "template_name": obj.get("template_name"), "error": "invalid_item", "detail": str(e)})

    return {
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": len(errors),
        "errors": errors,
    }


@app.post("/select-template/")
async def select_template(
        text_file: UploadFile = File(...),
        images: List[UploadFile] = File(...),
        name: str = Form(...),
        email: str = Form(...),
        address: str = Form(...),
        db: Session = Depends(get_db)
):
    # 1) Read text payload
    try:
        content = await text_file.read()
        decoded = content.decode("utf-8")
        # injecting address into decoded text description

        decoded += f"\n Property address: {address}"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read text file: {e}")

    # 2) Classify images via CLIP
    results = []
    property_images = 0
    property_images_list: List[str] = []

    realtor_photos = 0
    realtor_images_list: List[str] = []

    logos = 0
    logo_images: List[str] = []

    for img in images:
        try:
            raw = await img.read()
            file_bytes = np.asarray(bytearray(raw), dtype=np.uint8)
            img_np = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

            label, score = clip.classify(img_np)

            if clip.is_logo_related(label):
                logos += 1
                logo_images.append(img.filename)
            if clip.is_person_related(label):
                realtor_photos += 1
                realtor_images_list.append(img.filename)
            if clip.is_house_related(label):
                property_images += 1
                property_images_list.append(img.filename)

            results.append({
                "filename": img.filename,
                "label": label,
                "score": round(float(score), 4),
                "category": (
                    "house" if clip.is_house_related(label) else
                    "logo" if clip.is_logo_related(label) else
                    "person" if clip.is_person_related(label) else
                    "other"
                )
            })
        except Exception as e:
            # If one image fails, continue; you can choose to hard-fail instead.
            results.append({
                "filename": img.filename,
                "error": f"classification_failed: {e}"
            })

    image_count = len(images)

    # 3) Load all templates from DB (normalized schema)
    all_templates: List[TemplateModel] = db.query(TemplateModel).all()
    if not all_templates:
        raise HTTPException(status_code=404, detail="No templates available")

    # Improved template selection algorithm
    def calculate_template_score(t: TemplateModel) -> float:
        """Calculate comprehensive score for template matching"""
        t_prop_imgs = len(t.property_images or [])
        t_logos = len(t.logos or [])
        t_realtor_photo = 1 if t.realtor_photo else 0
        
        # 1. Image Distribution Score (most important)
        property_penalty = abs(t_prop_imgs - property_images)
        logo_penalty = abs(t_logos - logos)
        realtor_penalty = abs(t_realtor_photo - realtor_photos)
        distribution_score = property_penalty + logo_penalty + realtor_penalty
        
        # 2. Total Image Count Score (secondary)
        t_total = t_prop_imgs + t_logos + t_realtor_photo
        input_total = property_images + logos + realtor_photos
        total_count_penalty = abs(t_total - input_total)
        
        # 3. Template Flexibility Score (bonus for templates with more text fields)
        text_fields_count = len(t.text_fields or [])
        flexibility_bonus = -min(text_fields_count * 0.1, 1.0)  # Max bonus of 1.0
        
        # 4. Realtor Photo Compatibility Score
        realtor_compatibility = 0
        if realtor_photos > 0 and not t.realtor_photo:
            realtor_compatibility = 2  # Penalty for having realtor photos but no slot
        elif realtor_photos == 0 and t.realtor_photo:
            realtor_compatibility = 1  # Minor penalty for having slot but no photos
        
        # 5. Image Capacity Score (penalty for having too many required images)
        capacity_penalty = 0
        if t_total > input_total:
            capacity_penalty = (t_total - input_total) * 0.5
        
        # Calculate total score (lower is better)
        total_score = (
            distribution_score * 3 +  # Most important factor
            total_count_penalty * 2 +  # Secondary factor
            realtor_compatibility * 2 +  # Important for realtor photos
            capacity_penalty +  # Minor penalty for excess capacity
            flexibility_bonus  # Bonus for flexibility
        )
        
        return total_score

    # Sort templates by score (lower is better)
    template_scores = [(t, calculate_template_score(t)) for t in all_templates]
    template_scores.sort(key=lambda x: x[1])
    
    # Pick best match
    best_match: TemplateModel = template_scores[0][0]
    
    # Debug: Print template selection info
    print(f"DEBUG: Selected template {best_match.template_name} with score {template_scores[0][1]:.2f}")
    print(f"DEBUG: Top 3 candidates: {[(t.template_name, score) for t, score in template_scores[:3]]}")

    # 4) Rebuild text_fields dict from child rows for prompt
    #    Each child has: name, approx_length, format
    children: List[TextFieldModel] = (
        db.query(TextFieldModel)
        .filter(TextFieldModel.template_id == best_match.id)
        .all()
    )
    best_match_text_fields: Dict[str, Dict[str, Any]] = {
        c.name: {"approx_length": c.approx_length, "format": c.format}
        for c in children
        if c.name and c.name.strip()
    }

    if not best_match_text_fields:
        # You can decide to allow empty text fields; here we enforce at least one
        raise HTTPException(status_code=422, detail=f"Template '{best_match.template_name}' has no text fields")

    # 5) Ask GPT to extract/assign text values for text_fields
    try:
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": build_extraction_prompt(
                best_match_text_fields,  # strict dict: {field: {approx_length, format}}
                decoded
            )}],
            temperature=0.3,
        )
        gpt_result = completion.choices[0].message.content.strip()
        print(gpt_result)
        assigned_fields = json.loads(gpt_result)  # Expecting dict: { field_name: "value", ... }
        for field in assigned_fields:
            for template_field in best_match_text_fields:
                if field == template_field and assigned_fields[field] is not None:
                    max_size = best_match_text_fields[template_field]["approx_length"]
                    assigned_fields[field] = truncate_text_if_needed(assigned_fields[field], max_size)

        if not isinstance(assigned_fields, dict):
            raise ValueError("Model did not return a JSON object mapping field names to values")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GPT data extraction failed: {e}")

    # 6) Build realtor text field injection mapping
    #    We stored the *field keys* (not values) in the flattened columns.
    realtor_name_key = (best_match.realtor_name or "").strip() if best_match.realtor_name else None
    realtor_info_key = (best_match.realtor_info or "").strip() if best_match.realtor_info else None
    realtor_photo_key = (best_match.realtor_photo or "").strip() if best_match.realtor_photo else None

    # Handle cases where name/address keys are the same placeholder (e.g., "realtor_info")
    if realtor_name_key and realtor_info_key == realtor_name_key:
        realtor_text_map = {
            realtor_name_key: f"{name}\n{email}"
        }
    else:
        realtor_text_map = {
            realtor_name_key: name,
            realtor_info_key: email,
        }

    # 7) Image assignments
    prop_img_fields: List[str] = list(best_match.property_images or [])
    logo_fields: List[str] = list(best_match.logos or [])

    prop_assignment = dict(zip(prop_img_fields, property_images_list))
    logo_assignment = dict(zip(logo_fields, logo_images))
    realtor_photo_assignment = (
        {realtor_photo_key: realtor_images_list[0]} if (realtor_photo_key and realtor_images_list) else {}
    )

    # 8) Final payload
    response = {
        "fields": {
            **assigned_fields,  # from GPT (text field values)
            **prop_assignment,  # property images
            **logo_assignment,  # logos
            **realtor_photo_assignment,  # realtor photo
            **realtor_text_map,  # realtor text fields
        },
        "output": best_match.output,
        "template_name": best_match.template_name,
        "debug": {
            "chosen_template": {
                "template_name": best_match.template_name,
                "img_count": best_match.img_count,
                "text_count": best_match.text_count,
                "n_text_fields": len(best_match_text_fields),
                "selection_score": template_scores[0][1],  # Score of selected template
            },
            "image_stats": {
                "input_total": image_count,
                "property_images": property_images,
                "logos": logos,
                "realtor_photos": realtor_photos,
            },
            "template_ranking": [
                {"template_name": t.template_name, "score": score} 
                for t, score in template_scores[:3]  # Top 3 candidates
            ],
            "classification": results,  # optional: per-image classification summary
        }
    }

    return response


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=2500)
