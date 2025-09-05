#!/usr/bin/env python3
"""
Test script for the updated select-template endpoint
This demonstrates how to send text data and image URLs instead of file uploads
"""

import requests
import json

def test_select_template():
    # API endpoint
    url = "http://localhost:9001/select-template/"
    
    # Sample data
    text_data = """
    Beautiful 3-bedroom house for sale in downtown area.
    Features include hardwood floors, updated kitchen, and large backyard.
    Perfect for families looking for a modern home in a great neighborhood.
    Contact us for more details and scheduling a viewing.
    """
    
    # Sample image URLs (replace with actual public image URLs)
    image_urls = [
        "https://example.com/house1.jpg",
        "https://example.com/house2.jpg", 
        "https://example.com/realtor_photo.jpg",
        "https://example.com/company_logo.png"
    ]
    
    # Form data - using tuples for multiple values with same key
    form_data = [
        ('text_data', text_data),
        ('name', 'John Smith'),
        ('email', 'john.smith@realestate.com'),
        ('address', '123 Main St, City, State 12345')
    ]
    
    # Add image URLs as multiple form fields
    for img_url in image_urls:
        form_data.append(('image_urls', img_url))
    
    try:
        # Make the request
        response = requests.post(url, data=form_data)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Success!")
            print("Template selected:", result.get('template_name'))
            print("Extracted fields:")
            for key, value in result.items():
                if key != 'template_name':
                    print(f"  {key}: {value}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_select_template() 