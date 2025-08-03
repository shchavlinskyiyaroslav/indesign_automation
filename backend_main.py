import json
from typing import List

import cv2
import numpy as np
import openai
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
import os

from sqlalchemy.orm import Session

from clip_classifier import ClipImageClassifier
from db import get_db, TemplateModel, Template

app = FastAPI()

def build_extraction_prompt(fields: list, input_text: str) -> str:
    """
    fields: list of fields
    input_text: unstructured input text
    """
    field_list = "\n".join([f"- {name}" for name in fields])
    json_template = "{\n" + ",\n".join([f'  "{name}": "..."' for name in fields]) + "\n}"

    prompt = f"""
        You are an intelligent field extractor.
        
        Your task is to extract structured information from the unstructured input text below.
        
        Extract the following fields. If any field is missing or unclear in the text, return `null` for that field.
        This is for a real estate advertisement. 
        
        Fields to extract:
        {field_list}
        
        Output the result as a valid JSON object like this:
        {json_template}
        
        --- Begin Input ---
        {input_text}
        --- End Input ---
        """
    return prompt.strip()

openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_KEY"))
clip = ClipImageClassifier()

def truncate_fields(fields_dict, max_length=100):
    """Truncate string values in a dict if they're too long."""
    truncated = {}
    for k, v in fields_dict.items():
        if isinstance(v, str) and len(v) > max_length:
            truncated[k] = v[:max_length] + "…"
        else:
            truncated[k] = v
    return truncated

@app.post("/upload-template/")
async def upload_template(
        metadata: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    content = await metadata.read()
    try:
        data = json.loads(content)
        for obj in data:
            template = Template(**obj)
            img_count = (len(template.model_dump()['property_images'] or []) + len(template.model_dump()['logos'] or []) +
                         (1 if template.model_dump()['realtor']['photo'] else 0))
            text_count = len(template.model_dump()['text_fields'] or []) + 3  # 3 for realtor's name, address and email

            db_template = TemplateModel(
                name=template.template_name,
                data=template.model_dump(),  # store full nested JSON as dict
                img_count=img_count,
                text_count=text_count
            )

            db.add(db_template)
            db.commit()
            db.refresh(db_template)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid JSON structure: {str(e)}")


@app.post("/select-template/")
async def select_template(
        text_file: UploadFile = File(...),
        images: List[UploadFile] = File(...),
        name: str = Form(...),
        email: str = Form(...),
        address: str = Form(...),
        db: Session = Depends(get_db)
   ):
    try:
        content = await text_file.read()
        decoded = content.decode("utf-8")
        text_chars = len(decoded)
        text_fields = 4 if text_chars > 0 else 3 # for name, description field ( if exists ) , email, address
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read text file: {e}")

    results = []
    property_images = 0
    property_images_list = []

    realtor_photos = 0
    realtor_images_list = []

    logos = 0
    logo_images = []

    # classifying images that user uploads
    for img in images:
        # Load image bytes into memory
        content = await img.read()
        file_bytes = np.asarray(bytearray(content), dtype=np.uint8)
        img_np = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        # Classify using CLIP
        label, score = clip.classify(img_np)

        if clip.is_logo_related(label): logos += 1; logo_images.append(img.filename)
        if clip.is_person_related(label): realtor_photos += 1; realtor_images_list.append(img.filename)
        if clip.is_house_related(label): property_images += 1; property_images_list.append(img.filename)

        results.append({
            "filename": img.filename,
            "label": label,
            "score": round(score, 4),
            "category": (
                "house" if clip.is_house_related(label) else
                "logo" if clip.is_logo_related(label) else
                "person" if clip.is_person_related(label) else
                "other"
            )
        })
    # images cannot be generated. Text can be ( for example, headers, titles, etc ). So we need to check whether no.
    # of images are close

    image_count = len(images)

    all_templates = db.query(TemplateModel).all()

    def score(template):
        return abs(template.img_count - image_count)

    sorted_templates = sorted(all_templates, key=score)
    penalties = []
    for template in sorted_templates:
        penalty = 0
        template_data = Template(**template.data)
        if len(template_data.property_images) != property_images:
            penalty += abs(len(template_data.property_images) - property_images)
        if len(template_data.logos) != logos:
            penalty += abs(len(template_data.logos ) - logos)
        if ((not template_data.realtor.photo  and realtor_photos)
                or (realtor_photos and not template_data.realtor.photo)):
            penalty += 1

        penalties.append(penalty)

    best_match = sorted_templates[penalties.index(min(penalties))]



    # Currently, all images of property are assigned randomly. We can decide whether intelligent image assignment is
    # necessary later. All images of logo and realtor is put into proper fields

    try:

       completion = openai_client.chat.completions.create(
           model="gpt-4o-mini",
           messages=[{"role": "user", "content": build_extraction_prompt(
               best_match.data["text_fields"],
               decoded
           )}],
           temperature=0.3,
       )
       gpt_result = completion.choices[0].message.content.strip()
       assigned_fields = json.loads(gpt_result)
       # injecting remaining fields
       assigned_fields = {**assigned_fields, **dict(zip(best_match.data["property_images"],property_images_list)),
                          **dict(zip(best_match.data["logos"],logo_images)),
                          **dict(zip([best_match.data['realtor']['photo']],realtor_images_list)),
           best_match.data['realtor']['name']: name,
                          best_match.data['realtor']['email']: email,
                          best_match.data['realtor']['address']: address,
                          "template_name": best_match.name
                          }


    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GPT data extraction failed: {e}")

    return assigned_fields

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=2500)