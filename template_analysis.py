#!/usr/bin/env python3
"""
Analysis of the template selection logic to understand why it always selects the same template
"""

import json
from db import SessionLocal, TemplateModel, TextFieldModel

def analyze_template_selection():
    """Analyze the current template selection logic"""
    
    db = SessionLocal()
    
    # Get all templates
    templates = db.query(TemplateModel).all()
    print(f"=== TEMPLATE ANALYSIS ===")
    print(f"Total templates in database: {len(templates)}")
    print()
    
    # Analyze each template
    for i, template in enumerate(templates):
        print(f"Template {i+1}: {template.template_name}")
        print(f"  Output: {template.output}")
        print(f"  Image count: {template.img_count}")
        print(f"  Text count: {template.text_count}")
        print(f"  Property images: {len(template.property_images or [])} - {template.property_images}")
        print(f"  Logos: {len(template.logos or [])} - {template.logos}")
        print(f"  Realtor photo: {template.realtor_photo}")
        print(f"  Realtor name field: {template.realtor_name}")
        print(f"  Realtor info field: {template.realtor_info}")
        
        # Get text fields
        text_fields = db.query(TextFieldModel).filter(TextFieldModel.template_id == template.id).all()
        print(f"  Text fields: {len(text_fields)}")
        for tf in text_fields:
            print(f"    - {tf.name}: max_length={tf.approx_length}, format='{tf.format[:50]}...'")
        print()
    
    # Simulate template selection with different scenarios
    print("=== TEMPLATE SELECTION SIMULATION ===")
    
    scenarios = [
        {"name": "5 property images, 0 logos, 0 realtor photos", "property_images": 5, "logos": 0, "realtor_photos": 0},
        {"name": "3 property images, 1 logo, 1 realtor photo", "property_images": 3, "logos": 1, "realtor_photos": 1},
        {"name": "1 property image, 0 logos, 0 realtor photos", "property_images": 1, "logos": 0, "realtor_photos": 0},
        {"name": "4 property images, 1 logo, 0 realtor photos", "property_images": 4, "logos": 1, "realtor_photos": 0},
    ]
    
    for scenario in scenarios:
        print(f"\nScenario: {scenario['name']}")
        print(f"Input: {scenario['property_images']} property, {scenario['logos']} logos, {scenario['realtor_photos']} realtor")
        
        # Simulate the current scoring logic
        image_count = scenario['property_images'] + scenario['logos'] + scenario['realtor_photos']
        
        # Sort by total image count first
        def score_by_total_images(t):
            return abs((t.img_count or 0) - image_count)
        
        sorted_templates = sorted(templates, key=score_by_total_images)
        
        # Calculate penalties
        penalties = []
        for t in sorted_templates:
            penalty = 0
            
            t_prop_imgs = t.property_images or []
            t_logos = t.logos or []
            
            if len(t_prop_imgs) != scenario['property_images']:
                penalty += abs(len(t_prop_imgs) - scenario['property_images'])
            
            if len(t_logos) != scenario['logos']:
                penalty += abs(len(t_logos) - scenario['logos'])
            
            has_realtor_photo_slot = bool((t.realtor_photo or "").strip()) if t.realtor_photo else False
            if (scenario['realtor_photos'] and not has_realtor_photo_slot) or (has_realtor_photo_slot and not scenario['realtor_photos']):
                penalty += 1
            
            penalties.append(penalty)
        
        # Show top 3 candidates
        print("Top 3 candidates:")
        for i in range(min(3, len(sorted_templates))):
            template = sorted_templates[i]
            penalty = penalties[i]
            print(f"  {i+1}. {template.template_name} (penalty: {penalty})")
            print(f"     - Template has: {len(template.property_images or [])} property, {len(template.logos or [])} logos, realtor_photo={'Yes' if template.realtor_photo else 'No'}")
            print(f"     - Total image count: {template.img_count}")
    
    db.close()

if __name__ == "__main__":
    analyze_template_selection()
