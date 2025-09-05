#!/usr/bin/env python3
"""
Test script to verify the improved template selection logic
"""

import requests
import json
import os
from io import BytesIO

def create_test_files():
    """Create test files for the API"""
    
    # Create a test text file
    text_content = """
    Beautiful 3-bedroom house for sale in downtown area.
    Features include hardwood floors, updated kitchen, and large backyard.
    Perfect for families looking for a modern home in a great neighborhood.
    Contact us for more details and scheduling a viewing.
    """
    
    # Create test image files (dummy data)
    test_images = []
    for i in range(5):  # 5 property images
        # Create a simple 1x1 pixel PNG
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
        test_images.append(('images', (f'property_{i+1}.jpg', BytesIO(png_data), 'image/jpeg')))
    
    return text_content, test_images

def test_template_selection():
    """Test the improved template selection with different scenarios"""
    
    base_url = "http://localhost:2500"
    
    scenarios = [
        {
            "name": "5 property images, 0 logos, 0 realtor photos",
            "property_images": 5,
            "logos": 0,
            "realtor_photos": 0,
            "expected_template": "A32-HavenTemplate_1page1prop-edited.indt"  # Should still be selected but with better reasoning
        },
        {
            "name": "3 property images, 1 logo, 1 realtor photo", 
            "property_images": 3,
            "logos": 1,
            "realtor_photos": 1,
            "expected_template": "A6-HavenTemplate_1page1prop.indt"  # Should be selected now
        },
        {
            "name": "4 property images, 1 logo, 0 realtor photos",
            "property_images": 4,
            "logos": 1,
            "realtor_photos": 0,
            "expected_template": "A32-HavenTemplate_1page1prop-edited.indt"  # Perfect match
        }
    ]
    
    print("=== TESTING IMPROVED TEMPLATE SELECTION ===")
    
    for scenario in scenarios:
        print(f"\n--- {scenario['name']} ---")
        
        # Create test files
        text_content, test_images = create_test_files()
        
        # Limit images based on scenario
        limited_images = test_images[:scenario['property_images']]
        
        # Prepare form data
        form_data = {
            'name': 'John Smith',
            'email': 'john.smith@realestate.com',
            'address': '123 Main St, City, State 12345'
        }
        
        # Prepare files
        files = {
            'text_file': ('description.txt', BytesIO(text_content.encode()), 'text/plain')
        }
        files.update(limited_images)
        
        try:
            response = requests.post(f"{base_url}/select-template/", data=form_data, files=files)
            
            if response.status_code == 200:
                result = response.json()
                selected_template = result['template_name']
                score = result['debug']['chosen_template']['selection_score']
                ranking = result['debug']['template_ranking']
                
                print(f"✅ Selected: {selected_template}")
                print(f"   Score: {score:.2f}")
                print(f"   Expected: {scenario['expected_template']}")
                print(f"   Match: {'✅' if selected_template == scenario['expected_template'] else '❌'}")
                
                print("   Top 3 candidates:")
                for i, candidate in enumerate(ranking):
                    print(f"     {i+1}. {candidate['template_name']}: {candidate['score']:.2f}")
                
                # Show image assignment
                print(f"   Image assignment:")
                for key, value in result['fields'].items():
                    if key.startswith('image_') or key.startswith('logo_'):
                        print(f"     {key}: {value}")
                        
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"   Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_template_selection()
