#!/usr/bin/env python3
"""
Simple test to check the improved template selection
"""

import requests
import json
from io import BytesIO

def test_simple():
    # Create a simple test image (1x1 pixel PNG)
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
    
    # Test with 5 property images (no logos, no realtor photos)
    form_data = {
        'name': 'John Smith',
        'email': 'john.smith@realestate.com',
        'address': '123 Main St, City, State 12345'
    }
    
    files = {
        'text_file': ('description.txt', BytesIO(b'Beautiful 3-bedroom house for sale.'), 'text/plain')
    }
    
    # Add 5 property images
    for i in range(5):
        files[f'images'] = (f'property_{i+1}.jpg', BytesIO(png_data), 'image/jpeg')
    
    try:
        print("Testing with 5 property images, 0 logos, 0 realtor photos...")
        response = requests.post('http://localhost:2500/select-template/', data=form_data, files=files)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Selected template: {result['template_name']}")
            print(f"Output: {result['output']}")
            
            debug = result.get('debug', {})
            print(f"Debug keys: {list(debug.keys())}")
            
            if 'chosen_template' in debug:
                chosen = debug['chosen_template']
                print(f"Chosen template keys: {list(chosen.keys())}")
                if 'selection_score' in chosen:
                    print(f"Selection score: {chosen['selection_score']}")
            
            if 'template_ranking' in debug:
                print("Top 3 candidates:")
                for i, candidate in enumerate(debug['template_ranking']):
                    print(f"  {i+1}. {candidate['template_name']}: {candidate['score']:.2f}")
            
            # Show image stats
            if 'image_stats' in debug:
                stats = debug['image_stats']
                print(f"Image stats: {stats['property_images']} property, {stats['logos']} logos, {stats['realtor_photos']} realtor")
                
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple()
