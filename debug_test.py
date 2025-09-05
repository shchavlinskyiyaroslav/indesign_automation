#!/usr/bin/env python3
"""
Debug test to check what's happening with the template selection
"""

import requests
import json
from io import BytesIO

def test_debug():
    # Create a simple test image (1x1 pixel PNG)
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
    
    text_content = 'Beautiful 3-bedroom house for sale in downtown area.'
    
    form_data = {
        'name': 'John Smith',
        'email': 'john.smith@realestate.com',
        'address': '123 Main St, City, State 12345'
    }
    
    files = {
        'text_file': ('description.txt', BytesIO(text_content.encode()), 'text/plain')
    }
    
    # Add 5 property images
    for i in range(5):
        files[f'images'] = (f'property_{i+1}.jpg', BytesIO(png_data), 'image/jpeg')
    
    try:
        response = requests.post('http://localhost:2500/select-template/', data=form_data, files=files)
        print(f'Status: {response.status_code}')
        
        if response.status_code == 200:
            result = response.json()
            print('Full response keys:', list(result.keys()))
            
            debug = result.get('debug', {})
            print('Debug keys:', list(debug.keys()))
            
            if 'chosen_template' in debug:
                chosen = debug['chosen_template']
                print('Chosen template keys:', list(chosen.keys()))
            
            if 'classification' in debug:
                print('Classification results:')
                for i, classification in enumerate(debug['classification']):
                    print(f'  Image {i+1}: {classification}')
            
            # Check if template_ranking exists
            if 'template_ranking' in debug:
                print('Template ranking found!')
                for i, candidate in enumerate(debug['template_ranking']):
                    print(f'  {i+1}. {candidate["template_name"]}: {candidate["score"]:.2f}')
            else:
                print('Template ranking NOT found!')
                
            # Check if selection_score exists
            if 'chosen_template' in debug and 'selection_score' in debug['chosen_template']:
                print(f'Selection score found: {debug["chosen_template"]["selection_score"]:.2f}')
            else:
                print('Selection score NOT found!')
                
        else:
            print(f'Error: {response.text}')
            
    except Exception as e:
        print(f'Exception: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_debug()
