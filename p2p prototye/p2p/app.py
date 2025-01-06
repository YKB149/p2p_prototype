# This program is to be used only for education purpose only 
#while using this source code pls have permission of owner to avoid copyright infringement



from flask import Flask, render_template, request, jsonify, send_file, Response
from flask_socketio import SocketIO
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import uuid
import mimetypes

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)

# Dictionary to store file metadata and upload status
file_data = {}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate-link", methods=["POST"])
def generate_link():
    data = request.json
    if not data or "filename" not in data:
        return jsonify({"error": "Invalid data"}), 400

    unique_id = str(uuid.uuid4())
    file_data[unique_id] = {"filename": data["filename"]}
    return jsonify({"link": f"/transfer/{unique_id}"})

@app.route("/upload/<unique_id>", methods=["POST"])
def upload_file(unique_id):
    if unique_id not in file_data:
        return jsonify({"error": "Invalid upload ID"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    try:
        chunk_number = int(request.form.get("chunk", 0))
        total_chunks = int(request.form.get("total_chunks", 1))
        
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_id)
        
        # Append chunk to file
        mode = 'ab' if chunk_number > 0 else 'wb'
        with open(filepath, mode) as f:
            file.save(f)

        # Update progress
        progress = (chunk_number + 1) / total_chunks * 100
        socketio.emit(f'upload_progress_{unique_id}', {'progress': progress})

        # If this is the last chunk
        if chunk_number == total_chunks - 1:
            file_data[unique_id]["filepath"] = filepath
            file_data[unique_id]["status"] = "complete"
            return jsonify({"message": "File upload complete"})
        
        return jsonify({"message": "Chunk uploaded successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/transfer/<unique_id>")
def transfer(unique_id):
    if unique_id not in file_data:
        return jsonify({"error": "Invalid link"}), 404
    return render_template("transfer.html", unique_id=unique_id)

@app.route("/download/<unique_id>")
def download_file(unique_id):
    if unique_id not in file_data or "filepath" not in file_data[unique_id]:
        return jsonify({"error": "File not found"}), 404

    try:
        filepath = file_data[unique_id]["filepath"]
        original_filename = file_data[unique_id]["filename"]
        file_size = os.path.getsize(filepath)

        # Determine mime type
        mime_type, _ = mimetypes.guess_type(original_filename)
        if mime_type is None:
            mime_type = 'application/octet-stream'

        def generate():
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    yield chunk

        response = Response(
            generate(),
            mimetype=mime_type,
            direct_passthrough=True
        )

        response.headers.set('Content-Disposition', f'attachment; filename="{original_filename}"')
        response.headers.set('Content-Length', file_size)
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/file-info/<unique_id>")
def file_info(unique_id):
    if unique_id not in file_data:
        return jsonify({"error": "File not found"}), 404

    try:
        filepath = file_data[unique_id]["filepath"]
        filename = file_data[unique_id]["filename"]
        size = os.path.getsize(filepath)

        return jsonify({
            "filename": filename,
            "size": size
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
