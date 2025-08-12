import os
import glob
import json
import base64
import uuid
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Dict, Any
from PIL import Image

APP_ROOT = os.path.dirname(__file__)
TEMPLATE_IMAGES_DIR = os.path.join(APP_ROOT, "templates_images")
DESIGNS_DIR = os.path.join(APP_ROOT, "designs")
PREVIEWS_DIR = os.path.join(APP_ROOT, "previews")

os.makedirs(TEMPLATE_IMAGES_DIR, exist_ok=True)
os.makedirs(DESIGNS_DIR, exist_ok=True)
os.makedirs(PREVIEWS_DIR, exist_ok=True)

app = FastAPI()
jinja_templates = Jinja2Templates(directory="templates")  # Renamed to avoid conflict

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/templates_images", StaticFiles(directory=TEMPLATE_IMAGES_DIR), name="templates_images")
app.mount("/previews", StaticFiles(directory=PREVIEWS_DIR), name="previews")

# ---------- Helper: create template previews ----------
def create_template_previews():
    # Get all template images (up to 8)
    image_files = glob.glob(os.path.join(TEMPLATE_IMAGES_DIR, "*.jpg")) + \
                  glob.glob(os.path.join(TEMPLATE_IMAGES_DIR, "*.jpeg")) + \
                  glob.glob(os.path.join(TEMPLATE_IMAGES_DIR, "*.png"))
    image_files = image_files[:8]  # Limit to 8 templates
    
    for img_path in image_files:
        try:
            with Image.open(img_path) as img:
                # Create preview image (resized to 300px width)
                width, height = img.size
                preview_width = 300
                preview_height = int(height * (preview_width / width))
                
                preview = img.resize((preview_width, preview_height), Image.LANCZOS)
                
                # Save preview
                filename = os.path.basename(img_path)
                preview_filename = f"preview_{filename.split('.')[0]}.jpg"
                preview_path = os.path.join(PREVIEWS_DIR, preview_filename)
                preview.save(preview_path, "JPEG", quality=85)
        except Exception as e:
            print(f"Error processing image {img_path}: {str(e)}")

# Create previews on startup
create_template_previews()

# ---------- API endpoints ----------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # Get all template images
    image_files = glob.glob(os.path.join(TEMPLATE_IMAGES_DIR, "*.jpg")) + \
                  glob.glob(os.path.join(TEMPLATE_IMAGES_DIR, "*.jpeg")) + \
                  glob.glob(os.path.join(TEMPLATE_IMAGES_DIR, "*.png"))
    image_files = image_files[:8]  # Limit to 8 templates
    
    template_list = []
    for img_path in image_files:
        filename = os.path.basename(img_path)
        preview_filename = f"preview_{filename.split('.')[0]}.jpg"
        preview_path = f"/previews/{preview_filename}"
        
        # Get image dimensions
        try:
            with Image.open(img_path) as img:
                width, height = img.size
        except Exception as e:
            print(f"Error getting dimensions for {filename}: {str(e)}")
            width, height = 880, 1020  # Default dimensions
        template_list.append({
            "id": filename,
            "name": os.path.splitext(filename)[0].replace("_", " ").title(),
            "width": width,
            "height": height,
            "preview_url": preview_path,
            "image_url": f"/templates_images/{filename}"
        })
    
    return jinja_templates.TemplateResponse("index.html", {
        "request": request,
        "templates": template_list
    })

@app.get("/editor/{template_id}", response_class=HTMLResponse)
async def editor(request: Request, template_id: str):
    # Get image dimensions
    img_path = os.path.join(TEMPLATE_IMAGES_DIR, template_id)
    width, height = 1080, 1350  # Default dimensions
    
    try:
        with Image.open(img_path) as img:
            width, height = img.size
    except Exception as e:
        print(f"Error getting dimensions for {template_id}: {str(e)}")
    
    return jinja_templates.TemplateResponse("editor.html", {
        "request": request,
        "template_id": template_id,
        "image_url": f"/templates_images/{template_id}",
        "width": width,
        "height": height
    })

class SavePayload(BaseModel):
    design_id: str = None
    template_id: str
    design_json: Dict[str, Any]

@app.post("/save")
async def save_design(payload: SavePayload):
    design_id = payload.design_id or f"design_{uuid.uuid4().hex[:12]}"
    path = os.path.join(DESIGNS_DIR, f"{design_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"design_id": design_id, "template_id": payload.template_id, "design": payload.design_json}, f, indent=2)
    return {"status":"ok", "design_id": design_id}

@app.get("/design/{design_id}")
async def get_design(design_id: str):
    path = os.path.join(DESIGNS_DIR, f"{design_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Design not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# Accept exported PNG (base64) from client and save server-side (optional)
@app.post("/export")
async def export_image(image_b64: str = Form(...), filename: str = Form(None)):
    # expected image_b64 like "data:image/png;base64,...."
    if image_b64.startswith("data:"):
        header, b64 = image_b64.split(",", 1)
    else:
        b64 = image_b64
    data = base64.b64decode(b64)
    fname = filename or f"export_{uuid.uuid4().hex[:8]}.png"
    path = os.path.join(DESIGNS_DIR, fname)
    with open(path, "wb") as f:
        f.write(data)
    return {"status":"ok", "file": fname}

# ---------- run instructions ----------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)