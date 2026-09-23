from flask import Flask, request, send_file
from PIL import Image, TiffImagePlugin
import os
import io

app = Flask(__name__)

@app.route('/health')
def health():
    return {"status": "ok"}

@app.route('/api/merge', methods=['POST'])
def merge_tiffs():
    if 'files' not in request.files:
        return {"error": "No files provided"}, 400
        
    uploaded_files = request.files.getlist('files')
    if not uploaded_files:
        return {"error": "No files selected"}, 400

    images = []
    
    for f in uploaded_files:
        if not f.filename.lower().endswith(('.tif', '.tiff')):
            continue
            
        try:
            # Read into BytesIO
            img_bytes = f.read()
            img = Image.open(io.BytesIO(img_bytes))
            filename = f.filename
            
            # Embed metadata
            if not hasattr(img, 'tag_v2'):
                img.tag_v2 = TiffImagePlugin.ImageFileDirectory_v2()
                
            img.tag_v2[270] = filename
            img.tag_v2[285] = filename
            img.encoderinfo = {"tiffinfo": img.tag_v2}
            
            images.append(img)
        except Exception as e:
            print(f"Error processing {f.filename}: {e}")
            
    if len(images) == 0:
        return {"error": "No valid TIFF images processed"}, 400
        
    output_io = io.BytesIO()
    
    try:
        if len(images) > 1:
            images[0].save(
                output_io,
                format="TIFF",
                save_all=True,
                append_images=images[1:],
                tiffinfo=images[0].tag_v2
            )
        else:
            images[0].save(
                output_io,
                format="TIFF",
                tiffinfo=images[0].tag_v2
            )
            
        output_io.seek(0)
    except Exception as e:
        return {"error": f"Failed to merge images: {str(e)}"}, 500
        
    return send_file(
        output_io,
        mimetype="image/tiff",
        as_attachment=True,
        download_name="merged_output.tif"
    )

if __name__ == "__main__":
    app.run(port=5328)
