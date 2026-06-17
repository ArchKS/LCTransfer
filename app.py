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

# 处理 PyInstaller 资源路径
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

UPLOAD_FOLDER = './uploads'
# 使用 resource_path('.') 作为静态资源目录
app = Flask(__name__, static_folder=resource_path("."), static_url_path="")
# app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CORS(app)  # 添加这一行
socketio = SocketIO(app, cors_allowed_origins="*")

# 用于存储推送的文本列表（最多6条）
pushed_data_list = []

@app.route('/', methods=['GET'])
def index():
    return send_from_directory(resource_path('.'), 'index.html')

@app.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(directory=Path(app.config['UPLOAD_FOLDER']), path=filename)


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
