from flask import Flask, request, send_from_directory, flash, redirect, url_for, render_template,jsonify
from pathlib import Path
import socket
from flask_cors import CORS  # 添加这一行
import json
import os
import webbrowser 
from threading import Thread
from datetime import datetime
from flask_socketio import SocketIO, emit
import sys
import uuid
import re

# 处理 PyInstaller 资源路径
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# 获取程序所在目录（打包后为 exe 所在目录，开发时为脚本所在目录）
def base_dir():
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后：使用 exe 所在目录
        return os.path.dirname(sys.executable)
    # 开发环境：使用脚本所在目录
    return os.path.dirname(os.path.abspath(__file__))

# 使用绝对路径，避免依赖当前工作目录（CWD）
UPLOAD_FOLDER = os.path.join(base_dir(), 'uploads')
PASTED_IMAGE_FOLDER = os.path.join(base_dir(), 'pasted_images')
# 使用 resource_path('.') 作为静态资源目录
app = Flask(__name__, static_folder=resource_path("."), static_url_path="")
# app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PASTED_IMAGE_FOLDER'] = PASTED_IMAGE_FOLDER
CORS(app)  # 添加这一行
socketio = SocketIO(app, cors_allowed_origins="*")

# 路由在测试或被其他模块导入时也需要这两个目录存在。
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PASTED_IMAGE_FOLDER, exist_ok=True)

# 用于存储推送的文本列表（最多6条）
pushed_data_list = []

@app.route('/', methods=['GET'])
def index():
    return send_from_directory(resource_path('.'), 'index.html')

@app.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(directory=Path(app.config['UPLOAD_FOLDER']), path=filename, as_attachment=True)


@app.route('/list_files', methods=['GET'])
def list_files():
    upload_path = app.config['UPLOAD_FOLDER']
    files_info = []
    for filename in os.listdir(upload_path):
        filepath = os.path.join(upload_path, filename)
        if os.path.isfile(filepath):
            files_info.append({
                "name": filename,
                "size": os.path.getsize(filepath)
            })
    return json.dumps(files_info)


def detect_image_extension(data):
    """仅接受浏览器可直接展示的常见位图，不信任客户端传来的文件名。"""
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if data.startswith((b'GIF87a', b'GIF89a')):
        return 'gif'
    if len(data) >= 12 and data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return 'webp'
    if data.startswith(b'BM'):
        return 'bmp'
    return None


def is_pasted_image_filename(filename):
    return re.fullmatch(r'[0-9a-f]{32}\.(png|jpg|gif|webp|bmp)', filename) is not None


@app.route('/images', methods=['GET'])
def list_pasted_images():
    image_folder = app.config['PASTED_IMAGE_FOLDER']
    images = []
    for filename in os.listdir(image_folder):
        if not is_pasted_image_filename(filename):
            continue
        filepath = os.path.join(image_folder, filename)
        if not os.path.isfile(filepath):
            continue
        try:
            images.append({
                'id': filename,
                'url': url_for('get_pasted_image', filename=filename),
                'created_at': os.path.getmtime(filepath)
            })
        except FileNotFoundError:
            # 另一个浏览器可能刚好在列表刷新期间删除了该图片。
            continue
    images.sort(key=lambda image: image['created_at'], reverse=True)
    return jsonify(images)


@app.route('/images/<path:filename>', methods=['GET'])
def get_pasted_image(filename):
    return send_from_directory(app.config['PASTED_IMAGE_FOLDER'], filename)


@app.route('/images', methods=['POST'])
def upload_pasted_images():
    files = request.files.getlist('images')
    if not files:
        return jsonify(success=False, error='剪贴板中没有图片'), 400

    pending_images = []
    total_size = 0
    max_image_size = 20 * 1024 * 1024
    saved_images = []
    for image in files:
        # 单张限制 20 MB，避免误粘贴过大内容占满内存。
        data = image.read(max_image_size + 1)
        if len(data) > max_image_size:
            return jsonify(success=False, error='单张图片不能超过 20 MB'), 413

        extension = detect_image_extension(data)
        if not extension:
            return jsonify(success=False, error='仅支持 PNG、JPEG、GIF、WebP 或 BMP 图片'), 400

        total_size += len(data)
        if total_size > 60 * 1024 * 1024:
            return jsonify(success=False, error='一次粘贴的图片总大小不能超过 60 MB'), 413
        pending_images.append((data, extension))

    # 全部图片验证通过后再落盘，避免一次粘贴只保存了一部分。
    for data, extension in pending_images:
        filename = f'{uuid.uuid4().hex}.{extension}'
        filepath = os.path.join(app.config['PASTED_IMAGE_FOLDER'], filename)
        temp_filepath = f'{filepath}.tmp'
        with open(temp_filepath, 'wb') as image_file:
            image_file.write(data)
        os.replace(temp_filepath, filepath)
        saved_images.append({
            'id': filename,
            'url': url_for('get_pasted_image', filename=filename)
        })

    socketio.emit('refresh_images')
    return jsonify(success=True, images=saved_images)


@app.route('/images/<path:filename>', methods=['DELETE'])
def delete_pasted_image(filename):
    # 只允许删除由服务端生成的单层文件名。
    if filename != os.path.basename(filename) or not is_pasted_image_filename(filename):
        return jsonify(success=False, error='无效的图片名称'), 400

    filepath = os.path.join(app.config['PASTED_IMAGE_FOLDER'], filename)
    if not os.path.isfile(filepath):
        return jsonify(success=False, error='图片不存在'), 404

    os.unlink(filepath)
    socketio.emit('refresh_images')
    return jsonify(success=True)



@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files' not in request.files:
        return jsonify(success=False, error='No file part in the request'), 400

    files = request.files.getlist('files')
    errors = []

    for file in files:
        if file.filename == '':
            errors.append('No selected file')
            continue

        if file:
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            errors.append(f'File "{file.filename}" has an invalid extension')

    if errors:
        return jsonify(success=False, error=', '.join(errors)), 400
    else:
        socketio.emit('refresh_files')
        return jsonify(success=True)


@app.route('/save_text', methods=['POST'])
def save_text():
    data = request.get_json()
    text = data.get('text', '')
    if not text:
        return jsonify(success=False, error='No text provided'), 400
    
    # 智能检测是否为 JSON 格式以决定后缀名
    extension = "txt"
    try:
        # 尝试解析文本
        parsed_data = json.loads(text)
        # 只有当它是对象或数组时，我们才将其保存为 .json
        if isinstance(parsed_data, (dict, list)):
            extension = "json"
    except Exception:
        # 解析失败则保持为 .txt
        pass

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"text_{timestamp}.{extension}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)
    
    socketio.emit('refresh_files')
    return jsonify(success=True, filename=filename)


@app.route('/push_text', methods=['POST'])
def push_text():
    data = request.get_json()
    text = data.get('text', '')
    if not text:
        return jsonify(success=False, error='No text provided'), 400
    
    new_entry = {
        "text": text,
        "timestamp": datetime.now().strftime('%H:%M:%S')
    }
    
    # 将新消息插入到开头，并只保留最近6条
    pushed_data_list.insert(0, new_entry)
    if len(pushed_data_list) > 6:
        pushed_data_list.pop()
        
    socketio.emit('refresh_pushed_text', pushed_data_list)
    return jsonify(success=True)


@app.route('/get_pushed_text', methods=['GET'])
def get_pushed_text():
    return jsonify(pushed_data_list)


@app.route('/clear_pushed_text', methods=['POST'])
def clear_pushed_text():
    global pushed_data_list
    pushed_data_list = []
    socketio.emit('refresh_pushed_text', pushed_data_list)
    return jsonify(success=True)


@app.route('/delete', methods=['POST'])
def delete_files():
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    for file in files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
        if os.path.isfile(file_path):
            os.unlink(file_path)
    socketio.emit('refresh_files')
    return jsonify({'result': 'All files deleted.'})


@app.route('/get_ips', methods=['GET'])
def get_ips():
    try:
        hostname = socket.gethostname()
        all_ips = socket.gethostbyname_ex(hostname)[2]
        # 排除 127.0.0.1
        ips = [ip for ip in all_ips if ip != '127.0.0.1']
        # 按常用局域网 IP 段简单排序（172 和 192 优先）
        ips.sort(key=lambda x: (not x.startswith('172.'), not x.startswith('192.168.')))
        return jsonify(ips)
    except Exception as e:
        return jsonify([get_local_ip()])


def get_local_ip():
    try:
        # 获取本机所有 IP 地址
        hostname = socket.gethostname()
        all_ips = socket.gethostbyname_ex(hostname)[2]
        
        # 第一优先级：172. 开头的局域网地址
        for ip in all_ips:
            if ip.startswith('172.'):
                return ip
        
        # 第二优先级：192.168. 开头的局域网地址
        for ip in all_ips:
            if ip.startswith('192.168.'):
                return ip

        # 兜底方案：使用 UDP 探测方法获取默认出口 IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.254.254.254', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP
    except Exception:
        return '127.0.0.1'

# def run_server():
#      app.run(debug=True, host='0.0.0.0', port=5100)


def run_server():
    app.run(host="0.0.0.0", port=5100)


if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    local_ip = get_local_ip()
    port = 5100
    url = f"http://{local_ip}:{port}"
    
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        def open_browser():
            import time
            time.sleep(1.5)
            webbrowser.open(url)
        Thread(target=open_browser, daemon=True).start()

    print(f"Server is running on {url}")
    socketio.run(app, debug=True, host='0.0.0.0', port=port)

    

# if __name__ == "__main__":
#     if not os.path.exists(UPLOAD_FOLDER):
#         os.makedirs(UPLOAD_FOLDER)
#     server_thread = Thread(target=run_server)
#     server_thread.start()
#     webbrowser.open("http://172.31.32.13:5100")
#     server_thread.join()
