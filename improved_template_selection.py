#!/usr/bin/env python3
"""
Improved template selection algorithm that considers multiple factors
"""

import json
from typing import List, Dict, Any, Tuple
from db import SessionLocal, TemplateModel, TextFieldModel

class ImprovedTemplateSelector:
    def __init__(self, db_session):
        self.db = db_session
    
    def select_best_template(self, property_images: int, logos: int, realtor_photos: int) -> Tuple[TemplateModel, Dict[str, Any]]:
        """
        Select the best template based on multiple scoring factors
        """
        all_templates = self.db.query(TemplateModel).all()
        if not all_templates:
            raise ValueError("No templates available")
        
        # Calculate scores for each template
        template_scores = []
        for template in all_templates:
            score_data = self._calculate_template_score(
                template, property_images, logos, realtor_photos
            )
            template_scores.append((template, score_data))
        
        # Sort by total score (lower is better)
        template_scores.sort(key=lambda x: x[1]['total_score'])
        
        best_template, best_score = template_scores[0]
        
        return best_template, {
            'template': best_template,
            'score': best_score,
            'all_scores': [(t.template_name, s['total_score']) for t, s in template_scores[:3]]
        }
    
    def _calculate_template_score(self, template: TemplateModel, property_images: int, logos: int, realtor_photos: int) -> Dict[str, Any]:
        """
        Calculate a comprehensive score for a template
        """
        t_prop_imgs = len(template.property_images or [])
        t_logos = len(template.logos or [])
        t_realtor_photo = 1 if template.realtor_photo else 0
        
        # 1. Image Distribution Score (most important)
        # Perfect match = 0, each mismatch = penalty
        property_penalty = abs(t_prop_imgs - property_images)
        logo_penalty = abs(t_logos - logos)
        realtor_penalty = abs(t_realtor_photo - realtor_photos)
        
        distribution_score = property_penalty + logo_penalty + realtor_penalty
        
        # 2. Total Image Count Score (secondary)
        t_total = t_prop_imgs + t_logos + t_realtor_photo
        input_total = property_images + logos + realtor_photos
        total_count_penalty = abs(t_total - input_total)
        
        # 3. Template Flexibility Score (bonus for templates that can handle variations)
        # Templates with more text fields are more flexible
        text_fields_count = len(template.text_fields or [])
        flexibility_bonus = -min(text_fields_count * 0.1, 1.0)  # Max bonus of 1.0
        
        # 4. Realtor Photo Compatibility Score
        realtor_compatibility = 0
        if realtor_photos > 0 and not template.realtor_photo:
            realtor_compatibility = 2  # Penalty for having realtor photos but no slot
        elif realtor_photos == 0 and template.realtor_photo:
            realtor_compatibility = 1  # Minor penalty for having slot but no photos
        
        # 5. Image Capacity Score (penalty for having too many required images)
        capacity_penalty = 0
        if t_total > input_total:
            capacity_penalty = (t_total - input_total) * 0.5
        
        # Calculate total score
        total_score = (
            distribution_score * 3 +  # Most important factor
            total_count_penalty * 2 +  # Secondary factor
            realtor_compatibility * 2 +  # Important for realtor photos
            capacity_penalty +  # Minor penalty for excess capacity
            flexibility_bonus  # Bonus for flexibility
        )
        
        return {
            'total_score': total_score,
            'distribution_score': distribution_score,
            'property_penalty': property_penalty,
            'logo_penalty': logo_penalty,
            'realtor_penalty': realtor_penalty,
            'total_count_penalty': total_count_penalty,
            'realtor_compatibility': realtor_compatibility,
            'capacity_penalty': capacity_penalty,
            'flexibility_bonus': flexibility_bonus,
            'template_stats': {
                'property_images': t_prop_imgs,
                'logos': t_logos,
                'realtor_photo': t_realtor_photo,
                'total_images': t_total,
                'text_fields': text_fields_count
            }
        }

def test_improved_selection():
    """Test the improved template selection with various scenarios"""
    
    db = SessionLocal()
    selector = ImprovedTemplateSelector(db)
    
    scenarios = [
        {"name": "5 property images, 0 logos, 0 realtor photos", "property_images": 5, "logos": 0, "realtor_photos": 0},
        {"name": "3 property images, 1 logo, 1 realtor photo", "property_images": 3, "logos": 1, "realtor_photos": 1},
        {"name": "1 property image, 0 logos, 0 realtor photos", "property_images": 1, "logos": 0, "realtor_photos": 0},
        {"name": "4 property images, 1 logo, 0 realtor photos", "property_images": 4, "logos": 1, "realtor_photos": 0},
        {"name": "2 property images, 0 logos, 1 realtor photo", "property_images": 2, "logos": 0, "realtor_photos": 1},
    ]
    
    print("=== IMPROVED TEMPLATE SELECTION TEST ===")
    
    for scenario in scenarios:
        print(f"\nScenario: {scenario['name']}")
        print(f"Input: {scenario['property_images']} property, {scenario['logos']} logos, {scenario['realtor_photos']} realtor")
        
        try:
            best_template, score_data = selector.select_best_template(
                scenario['property_images'], 
                scenario['logos'], 
                scenario['realtor_photos']
            )
            
            print(f"Selected: {best_template.template_name}")
            print(f"Score: {score_data['score']['total_score']:.2f}")
            print(f"Template has: {score_data['score']['template_stats']['property_images']} property, {score_data['score']['template_stats']['logos']} logos, realtor_photo={'Yes' if score_data['score']['template_stats']['realtor_photo'] else 'No'}")
            
            print("Top 3 candidates:")
            for i, (name, score) in enumerate(score_data['all_scores']):
                print(f"  {i+1}. {name}: {score:.2f}")
                
        except Exception as e:
            print(f"Error: {e}")
    
    db.close()

if __name__ == "__main__":
    test_improved_selection()
