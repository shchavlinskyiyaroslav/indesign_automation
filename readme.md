# AI Real Estate Template Matcher

## 🛠️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/yourproject.git
cd yourproject
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

First install PyTorch dependencies:

```bash
pip install -r torch_requirements.txt
```

Then install other project dependencies:

```bash
pip install -r requirements.txt
```

---

## Project Structure & File Descriptions

| File / Folder            | Description                                                                                                                                             |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend_main.py`        | **Main FastAPI application**. Handles routing, business logic, and integration with OpenAI and the image classifier. Launches on port `2500`.           |
| `clip_classifier.py`     | Contains the `ClipImageClassifier` class, which classifies uploaded images into categories using CLIP (house, logo, person).                            |
| `db.py`                  | Defines the database models using SQLAlchemy, including how templates are stored and retrieved. Also provides a dependency-injected `get_db()` session. |
| `torch_requirements.txt` | Contains packages related to PyTorch and CLIP, which need to be installed separately first.                                                             |
| `requirements.txt`       | Contains the rest of the FastAPI and supporting libraries (e.g., `openai`, `uvicorn`, `sqlalchemy`, etc.).                                              |

---

## API Endpoints
⚠️ Important Usage Note

Before using the POST `/select-template/` endpoint, you must first upload at least one template using the POST `/upload-template/` endpoint.

The system matches user uploads to existing templates in the database. If no templates are present, template selection and field assignment will fail.

✅ Steps:

    Use /upload-template/ to load template metadata into the database.

    Then use /select-template/ to upload content and receive a populated JSON template.
### `POST /upload-template/`

* **Input:** JSON file of template metadata
* **Function:** Adds a new template to the database with calculated image and text field counts

### `POST /select-template/`

* **Inputs:**

    * `text_file`: A `.txt` file with listing description
    * `images[]`: List of uploaded image files
    * `name`, `email`, `address`: Realtor metadata
* **Function:**

    * Extract fields using GPT-4o-mini
    * Classify uploaded images
    * Match with the most appropriate template
    * Return a structured JSON mapping images and text to template fields

---

## How It Works

* **Text Analysis:** The uploaded text is passed to OpenAI's GPT model using a structured prompt asking it to extract defined fields like price, description, etc.
* **Image Classification:** Images are classified into `house`, `person`, or `logo` using CLIP.
* **Template Matching:** Based on the number and type of classified images and required text fields, the best matching template is selected from the database.
* **Result:** A fully populated JSON structure is returned with template name, field values, and image associations.

---

## Running the App

```bash
uvicorn backend_main:app --host 0.0.0.0 --port 2500
```

or simply run:

```bash
python backend_main.py
```

---

## Environment Variables

| Variable     | Description                       |
| ------------ | --------------------------------- |
| `OPENAI_KEY` | Your OpenAI API key for GPT calls |

Set this before running:

```bash
export OPENAI_KEY=sk-xxxxxx       # On Linux/macOS
set OPENAI_KEY=sk-xxxxxx          # On Windows
```

---

## Example Template Format

The values of each key in the JSON dict ( except for template_name ) should be a field in the indesign file.
The JSON file you upload via `/upload-template/` should look like this:

```json
[
  {
    "template_name": "modern_listings.indt",
    "realtor": {
      "name": "field_realtor_name",
      "address": "field_realtor_address",
      "email": "field_realtor_email",
      "photo": "field_realtor_photo"
    },
    "logos": ["field_logo_top", "field_logo_footer"],
    "property_images": ["field_img1", "field_img2", "field_img3"],
    "text_fields": ["field_title", "field_description", "field_price"]
  }
]
```

---

