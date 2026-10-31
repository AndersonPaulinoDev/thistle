#!/usr/bin/env python3
"""THISTLE: a native, keyboard-driven Qt WebEngine browser with Laya Cognitive Layer and THISTLE OS Integration."""
import base64
import json
import os
import sys
import threading
import urllib.request
import urllib.error
from datetime import datetime
from shiboken6 import delete
from pathlib import Path
from urllib.parse import quote_plus
from PySide6.QtCore import Qt, QUrl, QStandardPaths, QTimer, Signal, QPropertyAnimation, QEasingCurve, QRect, QRectF, QPoint, QPointF, QEvent, QSize, QObject
from PySide6.QtGui import QIcon, QAction, QKeySequence, QShortcut, QColor, QPixmap, QKeyEvent, QPainter, QPainterPath, QPen, QFont
from PySide6.QtWidgets import (QApplication, QStyledItemDelegate, QStyle, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLineEdit, QPushButton, QTabWidget, QDialog, QListWidget,
    QMessageBox, QFileDialog, QLabel, QCheckBox, QComboBox, QDialogButtonBox,
    QGraphicsOpacityEffect, QTextEdit, QProgressBar, QScrollArea, QGridLayout)
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineUrlRequestInterceptor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtNetwork import QLocalServer, QLocalSocket

# Theme palettes (Omarchy-style)
THEMES = {
    'Dark': {
        'bg': '#0a0c0b', 'fg': '#e8eee9', 'panel': '#1c221e', 'accent': '#789080',
        'muted': '#7e9485', 'highlight': '#b9d9ac', 'overlay': 'rgba(0,0,0,0.4)'
    },
    'Light': {
        'bg': '#f3f4ef', 'fg': '#1c2920', 'panel': '#e1e7df', 'accent': '#789080',
        'muted': '#7e9485', 'highlight': '#b9d9ac', 'overlay': 'rgba(255,255,255,0.6)'
    },
    'Tokyo Night': {
        'bg': '#1a1b26', 'fg': '#c0caf5', 'panel': '#24283b', 'accent': '#7aa2f7',
        'muted': '#565f89', 'highlight': '#9ece6a', 'overlay': 'rgba(26,27,38,0.5)'
    },
    'Nord': {
        'bg': '#2e3440', 'fg': '#eceff4', 'panel': '#3b4252', 'accent': '#88c0d0',
        'muted': '#4c566a', 'highlight': '#8fbcbb', 'overlay': 'rgba(46,52,64,0.5)'
    },
    'Catppuccin': {
        'bg': '#1e1e2e', 'fg': '#cdd6f4', 'panel': '#313244', 'accent': '#89b4fa',
        'muted': '#585b70', 'highlight': '#a6e3a1', 'overlay': 'rgba(30,30,46,0.5)'
    }
}

def mix(a, b, t):
    """Blend two #rrggbb colours; t=0 gives a, t=1 gives b."""
    ca, cb = QColor(a), QColor(b)
    return QColor(round(ca.red()+(cb.red()-ca.red())*t), round(ca.green()+(cb.green()-ca.green())*t), round(ca.blue()+(cb.blue()-ca.blue())*t)).name()

def tokens(t):
    """Theme palette plus the derived surfaces every widget shares."""
    return dict(t, line=mix(t['panel'], t['fg'], .14), hover=mix(t['bg'], t['fg'], .07), sel=mix(t['panel'], t['highlight'], .2),
                soft=mix(t['muted'], t['fg'], .35), error='#e8836f',
                on_hi=t['bg'] if QColor(t['bg']).lightness() < 128 else t['fg'])  # ink on the highlight colour

# One drawn icon set: 24-unit grid, 1.75 stroke, round caps (no unicode glyphs).
ICONS = {
    'back': [[(15,5),(8,12),(15,19)]], 'forward': [[(9,5),(16,12),(9,19)]],
    'plus': [[(12,5),(12,19)],[(5,12),(19,12)]], 'close': [[(7,7),(17,17)],[(17,7),(7,17)]],
    'menu': [[(5,7),(19,7)],[(5,12),(19,12)],[(5,17),(19,17)]], 'reader': [[(6,7),(18,7)],[(6,11),(18,11)],[(6,15),(18,15)],[(6,19),(13,19)]],
    'tabs': [[(4,9),(16,9),(16,20),(4,20),(4,9)],[(8,9),(8,5),(20,5),(20,16),(16,16)]],
    'chevron': [[(7,10),(12,15),(17,10)]], 'check': [[(6,12.5),(10,16.5),(18,8)]], 'send': [[(12,19),(12,5)],[(6,11),(12,5),(18,11)]],
}
def _icon_path(name):
    path = QPainterPath()
    if name == 'reload':
        path.arcMoveTo(QRectF(5,5,14,14), 60); path.arcTo(QRectF(5,5,14,14), 60, 290)
        path.moveTo(15.5,4.2); path.lineTo(15.6,8.4); path.lineTo(19.6,7.6)
    elif name == 'laya':  # four-point spark
        path.moveTo(12,3); path.quadTo(13,11,21,12); path.quadTo(13,13,12,21); path.quadTo(11,13,3,12); path.quadTo(11,11,12,3)
    elif name == 'star':
        import math
        pts = [(12+(8.5 if i%2==0 else 3.8)*math.sin(math.pi*i/5), 12.6-(8.5 if i%2==0 else 3.8)*math.cos(math.pi*i/5)) for i in range(10)]
        path.moveTo(*pts[0]); [path.lineTo(*q) for q in pts[1:]]; path.closeSubpath()
    else:
        for line in ICONS[name]:
            path.moveTo(*line[0]); [path.lineTo(*q) for q in line[1:]]
    return path
def icon_pixmap(name, color, size=18):
    pix = QPixmap(size*2, size*2); pix.fill(Qt.transparent); pix.setDevicePixelRatio(2)
    painter = QPainter(pix); painter.setRenderHint(QPainter.Antialiasing); painter.scale(size/24, size/24)
    painter.setPen(QPen(QColor(color), 1.75, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); painter.drawPath(_icon_path(name)); painter.end()
    return pix
def icon(name, color, on_color=None, size=18):
    result = QIcon(icon_pixmap(name, color, size))
    if on_color: result.addPixmap(icon_pixmap(name, on_color, size), QIcon.Normal, QIcon.On)
    return result
def icon_file(name, color, size=14):
    """A drawn icon saved as PNG, for Qt style sheets that only accept url()."""
    folder = Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation)) / 'icons'; folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{name}-{color.lstrip("#")}-{size}.png'
    if not path.exists(): icon_pixmap(name, color, size).save(str(path))
    return path.as_posix()

SEARCH_ENGINES = {'DuckDuckGo': 'https://duckduckgo.com/?q=', 'Brave': 'https://search.brave.com/search?q=', 'Google': 'https://www.google.com/search?q='}

# Background presets: BNS Foundry's own art, shipped in assets/ (no network)
ASSETS = Path(__file__).resolve().parent / 'assets'
BACKGROUNDS = {
    'Neon Bloom': 'local:bg-neon.jpg',
    'Above the Clouds': 'local:bg-clouds.jpg',
    'Golden Field': 'local:bg-golden.jpg',
    'Morning Meadow': 'local:bg-meadow.jpg',
    'Ink and Mist': 'local:bg-ink.jpg',
    'None': '',
    'Custom': ''
}
DEFAULT_BACKGROUND = 'local:bg-neon.jpg'
_DATA = {}
def asset_data(name):
    # inline as a data URI: new-tab pages are about:blank and cannot load file:// images
    if name not in _DATA:
        path = ASSETS / name
        mime = 'image/png' if name.endswith('.png') else 'image/jpeg'
        _DATA[name] = f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode() if path.is_file() else ''
    return _DATA[name]

def bg_css(url):
    if url.startswith('local:'):
        data = asset_data(url[6:]); return f"background-image:url('{data}');" if data else ''
    # only plain https images, and nothing that can break out of the CSS url()
    if not url.startswith('https://') or any(c in url for c in '\'")<>\\'): return ''
    return f"background-image:url('{url}');"

def home_html(background_url, overlay_color):
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>Start</title><style>
html{{color-scheme:dark}}body{{margin:0;background:#0a0c0b;color:#e9eee8;font-family:"Times New Roman", serif;display:grid;place-content:center;height:100vh;text-align:center;{bg_css(background_url)}background-size:cover;background-position:center;padding:40px;box-sizing:border-box;}}
.overlay{{position:fixed;top:0;left:0;width:100%;height:100%;background:{overlay_color};z-index:-1}}
h1{{font-size:96px;letter-spacing:-2px;font-weight:400;margin:0;opacity:0.9}}
p{{font-size:24px;color:#a3b3a7;margin-top:10px;font-style:italic;opacity:0.8}}
small{{position:fixed;bottom:40px;width:100%;left:0;color:#c3cfc5;font-family:system-ui;font-size:13px;letter-spacing:.12em;line-height:1.7;text-transform:uppercase;text-shadow:0 1px 14px rgba(0,0,0,.75)}}span{{color:#b9d9ac}}</style></head><body><div class="overlay"></div><h1><img src="{asset_data('logo-light.png')}" alt="THISTLE" style="width:min(560px,72vw);height:auto;display:block"></h1><p>Quiet Drift.</p><small>Made by BNS Foundry<br>Ctrl + L to navigate</small></body></html>'''

def new_tab_html(background_url, overlay_color, now, search='DuckDuckGo'):
    action = SEARCH_ENGINES.get(search, SEARCH_ENGINES['DuckDuckGo'])[:-3]
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>New tab</title><style>
    html{{color-scheme:dark}}body{{margin:0;background:#0a0c0b;color:#e9eee8;font-family:system-ui;display:grid;place-content:center;height:100vh;text-align:center;{bg_css(background_url)}background-size:cover;background-position:center;padding:40px;box-sizing:border-box;}}
    .container{{max-width:600px;padding:40px;}}
    .container{{width:min(600px,80vw)}}
    .date{{font-size:15px;color:#e9eee8;margin-bottom:18px;text-shadow:0 1px 14px rgba(0,0,0,.7)}}
    .search-box{{box-sizing:border-box;background:rgba(18,22,20,.78);backdrop-filter:blur(14px);border:1px solid rgba(233,238,232,.16);border-radius:16px;padding:16px 22px;font:18px system-ui;color:#e9eee8;width:100%;outline:none;box-shadow:0 12px 40px rgba(0,0,0,.35);transition:border-color .2s ease-out,box-shadow .2s ease-out}}
    .search-box::placeholder{{color:#a3b3a7}}
    .search-box:focus{{border-color:#b9d9ac;box-shadow:0 12px 40px rgba(0,0,0,.35),0 0 0 4px rgba(185,217,172,.18)}}
    ::selection{{background:#b9d9ac;color:#0a0c0b}}
    .footer{{position:fixed;bottom:32px;width:100%;left:0;color:#c3cfc5;font-size:13px;text-shadow:0 1px 14px rgba(0,0,0,.75)}}
    </style></head><body>
    <div class="container">
        <div class="date">{now}</div>
        <form action="{action}" method="get">
            <input type="text" name="q" class="search-box" placeholder="Search the void..." autofocus>
        </form>
    </div>
    <div class="footer">THISTLE · space to explore</div>
    </body></html>'''

def destination(text, search='DuckDuckGo'):
    text=text.strip()
    if not text:return QUrl('about:blank')
    aliases = {'w': 'https://en.wikipedia.org/wiki/', 'g': 'https://www.google.com/search?q=', 'y': 'https://www.youtube.com/results?search_query='}
    if ' ' in text:
        parts = text.split(' ', 1)
        if parts[0] in aliases: return QUrl(aliases[parts[0]] + quote_plus(parts[1]))
    if text.startswith(('https://','http://','file://','about:')):return QUrl(text)
    if text.lower().startswith(('javascript:','data:')):return QUrl('about:blank')
    if ' ' not in text and ('.' in text or text.startswith('localhost')): return QUrl.fromUserInput(text)
    return QUrl(SEARCH_ENGINES[search]+quote_plus(text))

def launch_url(arg):
    """A command-line argument as a page to open: web and file links only, never javascript: or data:."""
    if arg.startswith(('http://', 'https://', 'file://')): return QUrl(arg)
    path = os.path.join(os.environ.get('THISTLE_CWD', os.getcwd()), os.path.expanduser(arg))
    return QUrl.fromLocalFile(os.path.abspath(path)) if os.path.exists(path) else None

class AdBlockInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self):
        super().__init__()
        self.block_list = ['doubleclick.net', 'google-analytics.com', 'adservice.google', 'facebook.net', 'adnxs.com', 'quantserve.com', 'amazon-adsystem.com', 'googleadservices.com', 'scorecardresearch.com', 'taboola.com', 'outbrain.com', 'adform.net', 'criteo.com', 'openx.net', 'rubiconproject.com']
    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        if any(domain in url for domain in self.block_list): info.block(True)

class Page(QWebEnginePage):
    def __init__(self, profile, owner, parent):
        super().__init__(profile,parent);self.owner=owner
        self.permissionRequested.connect(self.ask_permission)
        self.certificateError.connect(lambda error:error.rejectCertificate())
        self.newWindowRequested.connect(self.new_window)
        self.zen_mode = False
    def ask_permission(self, permission):
        name=permission.permissionType().name
        result=QMessageBox.question(self.owner,'Website permission', f'{permission.origin().toString()}\n\nAllow {name}?', QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        permission.grant() if result==QMessageBox.Yes else permission.deny()
    def new_window(self, request):
        if not request.isUserInitiated():return
        view=self.owner.new_tab()
        request.openIn(view.page())
    def toggle_zen(self, enabled):
        self.zen_mode = enabled
        if enabled:
            js = '''(function(){const s=document.createElement('style');s.id='thistle-zen-mode';s.innerHTML=`body{background-color:#0a0c0b!important;color:#e9eee8!important;font-family:"Times New Roman",serif!important;max-width:800px!important;margin:0 auto!important;padding:50px 20px!important;line-height:1.6!important;font-size:20px!important}aside,.sidebar,.ad-container,.banner,#footer,.social-share,.nav-menu{display:none!important}img{max-width:100%!important;height:auto!important}`;document.head.appendChild(s);})();'''
            self.runJavaScript(js)
        else:
            self.runJavaScript('document.getElementById("thistle-zen-mode")?.remove();')

class AIPanel(QWidget):
    replied = Signal(object, object)  # (callback, result) delivered on the UI thread
    def __init__(self, browser):
        super().__init__(); self.browser = browser
        self.replied.connect(lambda cb, result: cb(result))
        self.setFixedWidth(360); self.setObjectName('laya'); self.setAttribute(Qt.WA_StyledBackground)
        self.welcome_shown = False
        self.ai_endpoint = self.browser.config.get('ai_endpoint', 'http://localhost:11434')
        self.ai_model = self.browser.config.get('ai_model', '')
        self.available_models = []
        layout=QVBoxLayout(self);layout.setContentsMargins(18,16,18,14);layout.setSpacing(10)
        
        # Header
        header=QHBoxLayout();header.setContentsMargins(0,0,0,0);header.setSpacing(8)
        title=QLabel('Laya'); title.setObjectName('laya_title')
        self.clear_btn=QPushButton('New chat'); self.clear_btn.setObjectName('text'); self.clear_btn.setToolTip('Clear the conversation')
        self.clear_btn.clicked.connect(self.clear_chat)
        header.addWidget(title); header.addStretch(); header.addWidget(self.clear_btn)
        layout.addLayout(header)
        
        # Status line
        self.status_chip = QLabel(); self.status_chip.setObjectName('status'); self.set_status('Offline', 'idle')
        layout.addWidget(self.status_chip)
        
        # Model + endpoint
        model_row=QHBoxLayout();model_row.setSpacing(6)
        self.model_combo = QComboBox(); self.model_combo.setAccessibleName('Ollama model')
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        self.refresh_btn=QPushButton(); self.refresh_btn.setObjectName('icon'); self.refresh_btn.setFixedSize(34,34); self.refresh_btn.setToolTip('Refresh models'); self.refresh_btn.setAccessibleName('Refresh models')
        self.refresh_btn.clicked.connect(lambda: self.refresh_models())
        model_row.addWidget(self.model_combo,1); model_row.addWidget(self.refresh_btn)
        layout.addLayout(model_row)
        self.endpoint_input = QLineEdit(); self.endpoint_input.setPlaceholderText('Ollama endpoint'); self.endpoint_input.setAccessibleName('Ollama endpoint')
        self.endpoint_input.setText(self.ai_endpoint)
        self.endpoint_input.editingFinished.connect(self.on_endpoint_changed)
        layout.addWidget(self.endpoint_input)
        
        # Chat area
        self.chat_area = QScrollArea(); self.chat_area.setWidgetResizable(True); self.chat_area.setObjectName('chat'); self.chat_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_content = QWidget(); self.chat_content.setObjectName('chat_content'); self.chat_layout = QVBoxLayout(self.chat_content); self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_layout.setContentsMargins(0,6,4,6); self.chat_layout.setSpacing(10)
        self.chat_area.setWidget(self.chat_content)
        layout.addWidget(self.chat_area,1)
        
        # Typing indicator (hidden by default)
        self.typing = QLabel('Laya is thinking…'); self.typing.setObjectName('typing')
        self.typing.hide()
        layout.addWidget(self.typing)
        
        # Input row
        input_row=QHBoxLayout();input_row.setContentsMargins(0,4,0,0);input_row.setSpacing(8)
        self.input = QLineEdit(); self.input.setPlaceholderText('Ask Laya…')
        self.input.returnPressed.connect(self.send_message)
        self.send_btn=QPushButton(); self.send_btn.setObjectName('primary_icon'); self.send_btn.setFixedSize(38,38); self.send_btn.setToolTip('Send · Enter'); self.send_btn.setAccessibleName('Send')
        self.send_btn.clicked.connect(self.send_message)
        input_row.addWidget(self.input,1); input_row.addWidget(self.send_btn)
        layout.addLayout(input_row)
        
        self.perf_label = QLabel('Latency: --ms'); self.perf_label.setObjectName('meta')
        layout.addWidget(self.perf_label)
        
        # Initial model refresh
        QTimer.singleShot(500, lambda: self.refresh_models(quiet=True))

    def set_status(self, text, state):
        """state: idle, ready, busy or error; colours come from the theme sheet."""
        self.status_chip.setText('●  ' + text); self.status_chip.setProperty('state', state)
        self.status_chip.style().unpolish(self.status_chip); self.status_chip.style().polish(self.status_chip)

    def ollama_async(self, callback, path, method='GET', data=None, timeout=30):
        """Run an Ollama request on a worker thread so the browser never freezes."""
        def work():
            result = self.ollama_request(path, method, data, timeout)
            try: self.replied.emit(callback, result)
            except RuntimeError: pass  # the window closed while Ollama was answering
        threading.Thread(target=work, daemon=True).start()

    def is_local(self):
        host = QUrl(self.ai_endpoint).host()
        return host in ('localhost', '127.0.0.1', '::1')

    def ollama_request(self, path, method='GET', data=None, timeout=30):
        """Make a request to the Ollama API (blocking; call through ollama_async)."""
        url = self.ai_endpoint.rstrip('/') + path
        try:
            if method == 'GET':
                req = urllib.request.Request(url)
            else:
                req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            return {'error': str(e)}

    def refresh_models(self, quiet=False):
        self.set_status('Checking…', 'busy')
        self.ollama_async(lambda r: self.models_loaded(r, quiet), '/api/tags', timeout=5)

    def models_loaded(self, result, quiet):
        if 'error' in result:
            self.set_status('Offline', 'error')
            self.model_combo.clear()
            self.model_combo.addItem('Ollama not running')
            if not quiet: self.add_message('Laya', f"Cannot connect to Ollama at {self.ai_endpoint}. Is Ollama running?")
            return
        
        self.available_models = result.get('models', [])
        self.model_combo.clear()
        if self.available_models:
            model_names = [m.get('name', '') for m in self.available_models]
            self.model_combo.addItems(model_names)
            if self.ai_model and self.ai_model in model_names:
                self.model_combo.setCurrentText(self.ai_model)
            else:
                self.model_combo.setCurrentText(model_names[0])
                self.ai_model = model_names[0]
                self.browser.config['ai_model'] = self.ai_model
                self.browser.write_json('settings.json', self.browser.config)
            self.set_status(f'Ready · {self.ai_model}', 'ready')
        else:
            self.model_combo.addItem('No models found')
            self.set_status('Ready · no models', 'idle')

    def on_model_changed(self, name):
        if name and name not in ('Ollama not running', 'No models found'):
            self.ai_model = name
            self.browser.config['ai_model'] = self.ai_model
            self.browser.write_json('settings.json', self.browser.config)
            self.set_status(f'Ready · {self.ai_model}', 'ready')

    def on_endpoint_changed(self):
        self.ai_endpoint = self.endpoint_input.text().strip() or 'http://localhost:11434'
        self.browser.config['ai_endpoint'] = self.ai_endpoint
        self.browser.write_json('settings.json', self.browser.config)
        self.refresh_models()

    def clear_chat(self):
        while self.chat_layout.count():
            child=self.chat_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.welcome_shown = False
        self.set_status(f'Ready · {self.ai_model}', 'ready') if self.ai_model else self.set_status('Offline', 'idle')
        self.perf_label.setText('Latency: --ms')
        self.show_welcome()

    def add_message(self, role, text):
        bubble = QWidget(); bubble.setObjectName('bubble'); bubble_layout = QVBoxLayout(bubble); bubble_layout.setContentsMargins(0,0,0,0); bubble_layout.setSpacing(2)
        # plain text: model output and page titles must never be parsed as markup
        lbl = QLabel(text); lbl.setTextFormat(Qt.PlainText); lbl.setWordWrap(True); lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl.setObjectName('msg_laya' if role == 'Laya' else 'msg_you'); lbl.setAccessibleName(f'{role}: {text}')
        if role == 'Laya': bubble_layout.addWidget(lbl)
        else: bubble_layout.addWidget(lbl, 0, Qt.AlignRight); lbl.setMaximumWidth(270); lbl.setMinimumWidth(min(270, lbl.fontMetrics().horizontalAdvance(text) + 28))
        self.chat_layout.addWidget(bubble)
        self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().maximum())

    def show_welcome(self):
        if self.welcome_shown: return
        self.welcome_shown = True
        view = self.browser.current()
        url = view.url().toString() if view else 'no page'
        title = view.title() or url if view else 'no page'
        self.add_message('Laya', f"Hey—I'm Laya. I connect to your local Ollama instance at {self.ai_endpoint} using model {self.ai_model or '(none selected)'}.\n\nAsk me about the current page ({title}), or anything else. " + ("Everything stays on this machine." if self.is_local() else f"Your questions and the page title and address are sent to {self.ai_endpoint}."))

    def send_message(self):
        text = self.input.text().strip()
        if not text: return
        if not self.welcome_shown:
            self.show_welcome()
        if not self.ai_model or self.ai_model in ('Ollama not running', 'No models found'):
            self.add_message('Laya', "No Ollama model selected. Start Ollama and pull a model (e.g., `ollama pull llama3.2`), then press the refresh button beside the model list.")
            return
        self.add_message('You', text)
        self.input.clear()
        self.typing.show()
        self.set_status('Thinking…', 'busy')
        self.perf_label.setText('Latency: --ms')
        start = datetime.now()
        view=self.browser.current()
        ctx_url = view.url().toString() if view else 'no page'
        ctx_title = view.title() or ctx_url if view else 'no page'
        self.handle_laya_response(text, ctx_url, ctx_title, start)

    def handle_laya_response(self, query, url, title, start_time):
        # Build context-aware prompt
        prompt = f"""You are Laya, a local AI assistant running inside the THISTLE browser on the user's machine.

Current context:
- Browser: THISTLE
- Current page: {title} ({url})
- The user is asking: {query}

Answer helpfully and concisely. Be honest about what you can and cannot see. You can see the page title and URL but not the full page content unless the user shares it."""
        
        self.ollama_async(lambda result: self.laya_answered(result, start_time), '/api/generate', method='POST',
            data={'model': self.ai_model, 'prompt': prompt, 'stream': False}, timeout=120)

    def laya_answered(self, result, start_time):
        self.typing.hide()
        latency = int((datetime.now() - start_time).total_seconds() * 1000)
        self.perf_label.setText(f"Latency: {latency}ms")
        self.set_status(f'Ready · {self.ai_model}', 'ready')
        
        if 'error' in result:
            self.add_message('Laya', f"Error from Ollama: {result['error']}\n\nMake sure Ollama is running at {self.ai_endpoint} and model '{self.ai_model}' is available.")
        else:
            response = result.get('response', 'No response from model.')
            self.add_message('Laya', response)

def theme_sheet(t):
    close, close_hover, chevron, check = (icon_file(n, c) for n, c in (('close', t['muted']), ('close', t['fg']), ('chevron', t['soft']), ('check', t['on_hi'])))
    return f'''
    QWidget {{ background: {t['bg']}; color: {t['fg']}; font-size: 14px; selection-background-color: {t['sel']}; selection-color: {t['fg']}; }}
    QToolTip {{ background: {t['panel']}; color: {t['fg']}; border: 1px solid {t['line']}; border-radius: 6px; padding: 5px 8px; font-size: 12px; }}
    QPushButton#edge {{ background: {t['line']}; border: 0; padding: 0; }}
    QPushButton#edge:hover {{ background: {t['accent']}; }}
    #toolbar {{ background: {t['bg']}; border-bottom: 1px solid {t['line']}; }}
    QPushButton#icon {{ background: transparent; border: 0; border-radius: 9px; padding: 0; }}
    QPushButton#icon:hover {{ background: {t['hover']}; }}
    QPushButton#icon:pressed {{ background: {t['line']}; }}
    QPushButton#icon:checked {{ background: {t['sel']}; }}
    QPushButton#icon:focus {{ border: 1px solid {t['highlight']}; }}
    QLineEdit {{ background: {t['panel']}; border: 1px solid {t['line']}; border-radius: 10px; padding: 7px 12px; color: {t['fg']}; }}
    QLineEdit:hover {{ border-color: {t['muted']}; }}
    QLineEdit:focus {{ border-color: {t['highlight']}; }}
    QLineEdit#address {{ min-height: 20px; padding: 7px 16px; border-radius: 17px; font-size: 14px; }}
    QProgressBar {{ background: transparent; border: 0; }}
    QProgressBar::chunk {{ background: {t['highlight']}; }}
    QTabWidget::pane {{ border: 0; }}
    QTabBar {{ background: {t['bg']}; }}
    QTabBar::tab {{ background: transparent; color: {t['soft']}; border: 0; border-radius: 9px; margin: 6px 0 6px 6px; padding: 7px 8px 7px 14px; min-width: 110px; max-width: 220px; font-size: 13px; }}
    QTabBar::tab:hover {{ background: {t['hover']}; color: {t['fg']}; }}
    QTabBar::tab:selected {{ background: {t['panel']}; color: {t['fg']}; }}
    QTabBar::close-button {{ image: url({close}); subcontrol-position: right; border-radius: 5px; margin: 0 2px; width: 16px; height: 16px; }}
    QTabBar::close-button:hover {{ image: url({close_hover}); background: {t['line']}; }}
    QTabBar QToolButton {{ background: {t['bg']}; border: 0; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {t['line']}; border-radius: 3px; min-height: 32px; }}
    QScrollBar::handle:vertical:hover {{ background: {t['muted']}; }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; width: 0; background: transparent; border: 0; }}
    QScrollBar:horizontal {{ height: 0; }}
    QComboBox {{ background: {t['panel']}; border: 1px solid {t['line']}; border-radius: 10px; padding: 7px 12px; color: {t['fg']}; min-height: 20px; }}
    QComboBox:hover {{ border-color: {t['muted']}; }}
    QComboBox:focus {{ border-color: {t['highlight']}; }}
    QComboBox::drop-down {{ border: 0; width: 30px; }}
    QComboBox::down-arrow {{ image: url({chevron}); width: 14px; height: 14px; }}
    QComboBox QAbstractItemView {{ background: {t['panel']}; border: 1px solid {t['line']}; border-radius: 8px; padding: 4px; outline: 0; selection-background-color: {t['sel']}; }}
    QCheckBox {{ spacing: 10px; padding: 4px 0; background: transparent; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {t['muted']}; background: {t['panel']}; }}
    QCheckBox::indicator:hover {{ border-color: {t['highlight']}; }}
    QCheckBox::indicator:checked {{ background: {t['highlight']}; border-color: {t['highlight']}; image: url({check}); }}
    QPushButton {{ background: {t['panel']}; color: {t['fg']}; border: 1px solid {t['line']}; border-radius: 10px; padding: 8px 18px; }}
    QPushButton:hover {{ border-color: {t['muted']}; }}
    QPushButton:focus {{ border-color: {t['highlight']}; }}
    QPushButton#primary, QPushButton#primary_icon {{ background: {t['highlight']}; color: {t['on_hi']}; border: 0; font-weight: 600; }}
    QPushButton#primary:hover, QPushButton#primary_icon:hover {{ background: {mix(t['highlight'], t['fg'], .25)}; }}
    QPushButton#primary_icon {{ border-radius: 19px; padding: 0; }}
    QPushButton#text {{ background: transparent; border: 0; color: {t['soft']}; padding: 4px 8px; font-size: 12px; }}
    QPushButton#text:hover {{ color: {t['fg']}; background: {t['hover']}; }}
    QDialogButtonBox {{ dialogbuttonbox-buttons-have-icons: 0; }}
    QLabel#dialog_title {{ font-size: 20px; font-weight: 600; }}
    QLabel#field {{ color: {t['soft']}; font-size: 12px; font-weight: 600; }}
    QDialog#palette {{ background: {t['bg']}; border: 1px solid {t['line']}; border-radius: 14px; }}
    QLineEdit#filter {{ font-size: 15px; padding: 10px 14px; border-radius: 10px; }}
    QListWidget#palette_list {{ background: transparent; border: 0; outline: 0; }}
    #laya, #laya QScrollArea, #laya QWidget#chat_content, #laya QWidget#qt_scrollarea_viewport {{ background: {t['panel']}; border: 0; }}
    QWidget#bubble {{ background: transparent; }}
    #laya {{ border-left: 1px solid {t['line']}; }}
    #laya QLineEdit, #laya QComboBox {{ background: {t['bg']}; }}
    QLabel#laya_title {{ color: {t['highlight']}; font-size: 18px; font-weight: 600; background: transparent; }}
    QLabel#status {{ color: {t['soft']}; font-size: 12px; background: transparent; }}
    QLabel#status[state="ready"] {{ color: {t['highlight']}; }}
    QLabel#status[state="error"] {{ color: {t['error']}; }}
    QLabel#typing, QLabel#meta {{ color: {t['soft']}; font-size: 12px; background: transparent; }}
    QLabel#msg_laya {{ color: {t['fg']}; font-size: 14px; background: transparent; padding: 2px 0; }}
    QLabel#msg_you {{ color: {t['fg']}; font-size: 14px; background: {t['sel']}; border-radius: 12px; padding: 8px 12px; }}
    #scratchpad {{ background: {t['panel']}; color: {t['fg']}; border: 1px solid {t['line']}; border-radius: 14px; padding: 14px; font-size: 14px; }}
    QStatusBar {{ background: {t['bg']}; color: {t['soft']}; border-top: 1px solid {t['line']}; font-size: 12px; }}
    QMessageBox {{ background: {t['bg']}; }}
    '''

class KeyFilter(QObject):
    """Routes a widget's key events to a plain function (PySide ignores per-instance eventFilter overrides)."""
    def __init__(self, fn, parent): super().__init__(parent); self.fn = fn
    def eventFilter(self, obj, event): return bool(self.fn(event))

class PaletteDelegate(QStyledItemDelegate):
    """Picker rows: name on the left, its shortcut or site on the right; headings in small muted type."""
    def __init__(self, t, parent): super().__init__(parent); self.t = t
    def sizeHint(self, option, index): return QSize(0, 30 if index.data(Qt.UserRole) is None else 40)
    def paint(self, painter, option, index):
        t, r = self.t, option.rect.adjusted(2, 1, -2, -1); heading = index.data(Qt.UserRole) is None
        painter.save(); painter.setRenderHint(QPainter.Antialiasing)
        if not heading and option.state & (QStyle.State_Selected | QStyle.State_MouseOver):
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(t['sel'] if option.state & QStyle.State_Selected else t['hover'])); painter.drawRoundedRect(QRectF(r), 8, 8)
        font = QFont(option.font); font.setPixelSize(12 if heading else 14); font.setWeight(QFont.DemiBold if heading else QFont.Normal); painter.setFont(font)
        hint = index.data(Qt.UserRole + 1) or ''
        hint_w = painter.fontMetrics().horizontalAdvance(hint) + 14 if hint else 0
        painter.setPen(QColor(t['soft'] if heading else t['fg']))
        text_rect = r.adjusted(12, 6 if heading else 0, -12 - hint_w, 0)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, painter.fontMetrics().elidedText(index.data(), Qt.ElideRight, text_rect.width()))
        if hint:
            small = QFont(font); small.setPixelSize(12); painter.setFont(small); painter.setPen(QColor(t['soft']))
            painter.drawText(r.adjusted(0, 0, -12, 0), Qt.AlignVCenter | Qt.AlignRight, hint)
        painter.restore()

class Browser(QMainWindow):
    def __init__(self, private=False, state_dir=None, restore=True, open_urls=()):
        super().__init__();self.private=private;self.children_windows=[];self.closed_tabs=[]
        self.setWindowTitle('THISTLE'+(' — Private' if private else ''))
        self.resize(1200,800)
        self.state_dir=Path(state_dir or QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation))
        self.state_dir.mkdir(parents=True,exist_ok=True)
        self.vault_dir = self.state_dir / 'vault'; self.vault_dir.mkdir(exist_ok=True)
        self.config=self.read_json('settings.json',{'always_show':False,'search':'DuckDuckGo','theme':'Dark','restore':True,'background':DEFAULT_BACKGROUND,'bg_v':2})
        if self.config.get('bg_v')!=2:self.config.update(background=DEFAULT_BACKGROUND,bg_v=2)  # older saves held the retired Unsplash or blank default
        self.bookmarks=self.read_json('bookmarks.json',[])
        self.history=self.read_json('history.json',[])
        self.scratchpad_text=self.read_text('scratchpad.txt','')
        self.workspaces=self.read_json('workspaces.json',{'Default': []})
        self.current_workspace = 'Default'
        self.profile=QWebEngineProfile(self) if private else QWebEngineProfile('Thistle',self)
        self.ad_blocker = AdBlockInterceptor(); self.profile.setUrlRequestInterceptor(self.ad_blocker)
        if not private:
            self.profile.setPersistentStoragePath(str(self.state_dir/'profile'))
            self.profile.setCachePath(str(self.state_dir/'cache'))
        self.profile.setPersistentPermissionsPolicy(QWebEngineProfile.PersistentPermissionsPolicy.AskEveryTime)
        self.profile.settings().setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled,False)
        self.profile.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard,False)
        self.profile.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,False)
        self.profile.downloadRequested.connect(self.download)
        
        body=QWidget();self.setCentralWidget(body);layout=QVBoxLayout(body);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        self.edge=QPushButton('');self.edge.setObjectName('edge');self.edge.setFixedHeight(4);self.edge.setToolTip('Reveal THISTLE controls · Ctrl+L');self.edge.setAccessibleName('Reveal controls');self.edge.clicked.connect(self.reveal)
        self.edge.enterEvent=lambda e:self.reveal(False)
        layout.addWidget(self.edge)
        
        self.controls=QWidget();self.controls.setObjectName('toolbar');self.controls.setAttribute(Qt.WA_StyledBackground)
        bar=QHBoxLayout(self.controls);bar.setContentsMargins(10,8,10,8);bar.setSpacing(2)
        self.icon_buttons=[]
        def button(name,fn,tip,checkable=False):
            b=QPushButton();b.setObjectName('icon');b.setFixedSize(34,34);b.setIconSize(QSize(18,18));b.setToolTip(tip);b.setAccessibleName(tip.split(' ·')[0])
            b.setCheckable(checkable);b.clicked.connect(fn);bar.addWidget(b);self.icon_buttons.append((b,name));return b
        def gap(width):bar.addSpacing(width)
        button('back',lambda:self.current().back(),'Back · Alt+Left')
        button('forward',lambda:self.current().forward(),'Forward · Alt+Right')
        button('reload',lambda:self.current().reload(),'Reload · Ctrl+R')
        gap(8)
        self.address=QLineEdit();self.address.setObjectName('address');self.address.setPlaceholderText('Search or enter address');self.address.setAccessibleName('Address or search');self.address.returnPressed.connect(self.navigate);bar.addWidget(self.address,1)
        gap(8)
        button('star',self.bookmark,'Bookmark · Ctrl+D')
        self.zen_btn = button('reader', self.toggle_zen, 'Zen reading · Alt+Z', True)
        self.ai_btn = button('laya', self.toggle_ai, 'Laya · Ctrl+Shift+A', True)
        gap(8)
        button('plus',lambda:self.new_tab(),'New tab · Ctrl+T')
        button('tabs',self.tab_picker,'Switch tabs · Ctrl+K')
        button('menu',self.menu,'Commands · Ctrl+Shift+P')
        button('close',self.hide_controls,'Hide controls · Escape')
        layout.addWidget(self.controls)
        self.progress = QProgressBar(); self.progress.setRange(0, 100); self.progress.setTextVisible(False); self.progress.setFixedHeight(2); self.progress.setValue(0); self.progress.hide(); layout.addWidget(self.progress)
        
        self.tabs=QTabWidget();self.tabs.setTabsClosable(True);self.tabs.setMovable(True);self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setElideMode(Qt.ElideRight);self.tabs.tabBar().setExpanding(False);self.tabs.tabBar().setDrawBase(False)
        self.tabs.tabCloseRequested.connect(self.close_tab);self.tabs.currentChanged.connect(self.changed)
        self.ai_panel = AIPanel(self); self.ai_panel.hide()
        row=QHBoxLayout();row.setContentsMargins(0,0,0,0);row.setSpacing(0);row.addWidget(self.tabs,1);row.addWidget(self.ai_panel)
        layout.addLayout(row,1)
        
        self.hint=QLabel();self.statusBar().addWidget(self.hint,1);self.statusBar().hide()
        self.shortcuts=[]
        bindings={'Ctrl+L':self.reveal,'Ctrl+T':lambda:self.new_tab(),'Ctrl+W':lambda:self.close_tab(self.tabs.currentIndex()),'Ctrl+Shift+T':self.reopen,'Ctrl+K':self.tab_picker,'Ctrl+Shift+P':self.menu,'Ctrl+Tab':lambda:self.cycle(1),'Ctrl+Shift+Tab':lambda:self.cycle(-1),'Ctrl+R':lambda:self.current().reload(),'Alt+Left':lambda:self.current().back(),'Alt+Right':lambda:self.current().forward(),'Ctrl+D':self.bookmark,'Ctrl+Shift+N':self.private_window,'Alt+Z':lambda:self.zen_btn.click(),'Ctrl+H':self.show_history,'Ctrl+Shift+S':self.toggle_scratchpad,'Ctrl+Shift+A':self.toggle_ai,'Alt+B':self.next_background}
        for key,fn in bindings.items():
            shortcut=QShortcut(QKeySequence(key),self);shortcut.activated.connect(fn);self.shortcuts.append(shortcut)
        # Escape only acts inside the address bar, so web pages keep their own Escape
        self.address.installEventFilter(self)
            
        urls=self.read_json('session.json',[]) if restore and not private and self.config.get('restore') else []
        for url in urls[:30]:
            if isinstance(url,str) and url.startswith(('https://','http://')):self.new_tab(QUrl(url))
        for url in open_urls:self.new_tab(url)
        if not self.tabs.count():self.new_tab()
        self.apply_theme();self.hide_controls()
        
        self.scratchpad = QTextEdit(self); self.scratchpad.setObjectName('scratchpad')
        self.scratchpad.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.scratchpad.setPlainText(self.scratchpad_text)
        self.scratchpad.setFixedSize(420, 340)
        self.scratchpad.hide()
        self.scratchpad.textChanged.connect(lambda: self.write_text('scratchpad.txt', self.scratchpad.toPlainText()))
        self.center_scratchpad()

        # Application-wide filters crash PySide6 wrapping WebEngine focus objects.
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.address and event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.hide_controls(); return True
        # Window typing: send printable keys to the address bar when no real
        # text field (web content, scratchpad, AI panel, combos) owns focus and
        # no modal dialog/palette is open.
        if event.type() == QEvent.KeyPress and self.isVisible():
            if QApplication.activeModalWidget() is None:
                focused = QApplication.focusWidget()
                in_text = isinstance(focused, (QLineEdit, QTextEdit, QComboBox))
                overlays = (self.scratchpad.isVisible() or self.ai_panel.isVisible()
                            or self.controls.isVisible() or self.tabs.tabBar().isVisible())
                if not in_text and not overlays and isinstance(event, QKeyEvent):
                    text = event.text() or ''
                    mods = event.modifiers()
                    if text and text.isprintable() and not (mods & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
                        if not self.controls.isVisible() and not self.tabs.tabBar().isVisible():
                            # Nothing owns the keys -> fold them into the address bar
                            self.controls.show()
                            self.tabs.tabBar().show()
                        self.address.setText(text)
                        self.address.setFocus()
                        return True
        return super().eventFilter(obj, event)
    def read_text(self,name,default):
        try:return (self.state_dir/name).read_text()
        except (OSError,ValueError):return default
    def write_text(self,name,value):
        if self.private:return
        path=self.state_dir/name;tmp=path.with_suffix('.tmp');tmp.write_text(value);tmp.replace(path)
    def read_json(self,name,default):
        try:return json.loads((self.state_dir/name).read_text())
        except (OSError,ValueError):return default
    def write_json(self,name,value):
        if self.private:return
        path=self.state_dir/name;tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2));tmp.replace(path)
    def current(self):return self.tabs.currentWidget()
    def new_tab(self,url=None):
        view=QWebEngineView();page=Page(self.profile,self,view);view.setPage(page)
        index=self.tabs.addTab(view,'New tab');self.tabs.setCurrentIndex(index)
        view.titleChanged.connect(lambda title,v=view:self.update_title(v,title))
        view.urlChanged.connect(lambda url,v=view:self.url_changed(v,url))
        view.loadFinished.connect(lambda ok,v=view:self.loaded(v,ok))
        view.loadProgress.connect(lambda p,v=view: self.update_progress(p, v))
        view.iconChanged.connect(lambda icon,i=index:self.tabs.setTabIcon(i,icon))
        page.linkHovered.connect(lambda url:self.hint.setText(url))
        if isinstance(url,QUrl):view.setUrl(url)
        else:
            t=THEMES.get(self.config.get('theme','Dark'),THEMES['Dark'])
            now=datetime.now().strftime("%B %d, %Y")
            html=home_html(self.config.get('background',DEFAULT_BACKGROUND),t['overlay']) if self.tabs.count()==1 else new_tab_html(self.config.get('background',DEFAULT_BACKGROUND),t['overlay'],now,self.config.get('search','DuckDuckGo'))
            view.setHtml(html,QUrl('about:blank'))
        return view

    def update_progress(self, p, view):
        if view == self.current():
            self.progress.setValue(p); self.progress.setVisible(0 < p < 100)

    def update_title(self,view,title):
        idx=self.tabs.indexOf(view)
        if idx>=0:self.tabs.setTabText(idx,title or 'New tab');self.tabs.setTabToolTip(idx,title or 'New tab')
        if view==self.current():self.setWindowTitle((title or 'THISTLE')+' — THISTLE'+(' [Private]' if self.private else ''))
    def url_changed(self,view,url):
        if view==self.current() and not self.address.hasFocus():
            url_str = url.toString()
            if url_str not in [h['url'] for h in self.history]:
                self.history.insert(0, {'title': view.title(), 'url': url_str})
                self.history = self.history[:1000]
                self.write_json('history.json', self.history)
            self.address.setText('' if url_str=='about:blank' else url_str)
    def loaded(self,view,ok):
        if not ok and view==self.current():
            self.hint.setText('Page could not load. Check the address or connection.');self.statusBar().show()
        elif view==self.current():self.statusBar().hide()
    def changed(self,index):
        if self.current():self.url_changed(self.current(),self.current().url())
    def reveal(self,focus=True):
        self.controls.show();self.tabs.tabBar().show()
        if focus:
            self.address.setText(self.current().url().toString()) if self.current() else None
            self.address.setFocus();self.address.selectAll()
    def hide_controls(self):
        visible=self.config.get('always_show',False)
        self.controls.setVisible(visible);self.tabs.tabBar().setVisible(visible)
        if self.current():self.current().setFocus()
    def navigate(self):
        self.current().setUrl(destination(self.address.text(),self.config.get('search','DuckDuckGo')));self.hide_controls()
    def close_tab(self,index):
        if index<0:return
        view=self.tabs.widget(index);self.closed_tabs.append(view.url().toString());self.tabs.removeTab(index);view.deleteLater()
        if not self.tabs.count():self.new_tab()
    def reopen(self):
        if self.closed_tabs:self.new_tab(QUrl(self.closed_tabs.pop()))
    def cycle(self,amount):self.tabs.setCurrentIndex((self.tabs.currentIndex()+amount)%self.tabs.count())
    def toggle_zen(self):
        enabled = self.zen_btn.isChecked()
        if self.current():
            self.current().page().toggle_zen(enabled)

    def toggle_ai(self):
        if self.ai_panel.isVisible():
            self.ai_panel.hide(); self.ai_btn.setChecked(False)
        else:
            self.ai_panel.show(); self.ai_panel.input.setFocus(); self.ai_btn.setChecked(True)

    def chooser(self,title,items,callback):
        """items: (text, value) or (text, value, hint); value None makes a group heading."""
        dialog=QDialog(self);dialog.setObjectName('palette');dialog.setWindowTitle(title);dialog.setFixedSize(580,440)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        dialog.move(self.geometry().center() - dialog.rect().center())
        layout=QVBoxLayout(dialog);layout.setContentsMargins(14,14,14,14);layout.setSpacing(8)
        search=QLineEdit();search.setObjectName('filter');search.setPlaceholderText(title.replace('THISTLE ','').capitalize()+' — type to filter');search.setAccessibleName('Filter');layout.addWidget(search)
        listing=QListWidget();listing.setObjectName('palette_list');listing.setItemDelegate(PaletteDelegate(tokens(THEMES.get(self.config.get('theme','Dark'),THEMES['Dark'])),listing))
        listing.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);listing.setMouseTracking(True);layout.addWidget(listing)
        for text,value,*hint in items:
            listing.addItem(text)
            item=listing.item(listing.count()-1)
            item.setData(Qt.UserRole, value);item.setData(Qt.UserRole+1, hint[0] if hint else '')
            if value is None:
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled)
        def filter_items(text):
            for i in range(listing.count()):
                item=listing.item(i);item.setHidden(item.data(Qt.UserRole) is None and bool(text) or text.casefold() not in (item.text()+' '+item.data(Qt.UserRole+1)).casefold())
        search.textChanged.connect(filter_items)
        def activate(item):
            if item:
                data = item.data(Qt.UserRole)
                dialog.accept()
                if data is not None:
                    callback(data)
        listing.itemActivated.connect(activate)
        def first():
            for i in range(listing.count()):
                if not listing.item(i).isHidden() and listing.item(i).data(Qt.UserRole) is not None:activate(listing.item(i));break
        def move(step):
            rows=[i for i in range(listing.count()) if not listing.item(i).isHidden() and listing.item(i).data(Qt.UserRole) is not None]
            if rows:
                at=listing.currentRow();listing.setCurrentRow(rows[(rows.index(at)+step)%len(rows)] if at in rows else rows[0 if step>0 else -1])
        def keys(event):
            if event.type()==QEvent.KeyPress and event.key() in (Qt.Key_Down,Qt.Key_Up):move(1 if event.key()==Qt.Key_Down else -1);return True
            if event.type()==QEvent.KeyPress and event.key() in (Qt.Key_Return,Qt.Key_Enter) and listing.currentItem() and not listing.currentItem().isHidden():activate(listing.currentItem());return True
            return False
        search.installEventFilter(KeyFilter(keys,dialog))
        search.returnPressed.connect(first);search.setFocus();dialog.exec()
    def tab_picker(self):
        self.chooser('THISTLE tabs',[(self.tabs.tabText(i),i,self.tabs.widget(i).url().host() or ('this tab' if i==self.tabs.currentIndex() else '')) for i in range(self.tabs.count())],self.tabs.setCurrentIndex)
    def show_history(self):
        self.chooser('History', [(h['title'] or h['url'], h['url'], QUrl(h['url']).host()) for h in self.history if h['url']!='about:blank'], lambda url: self.new_tab(QUrl(url)))
    def clear_history(self):
        self.history=[];self.closed_tabs=[];self.write_json('history.json',self.history)
        self.profile.clearAllVisitedLinks()
        for i in range(self.tabs.count()):self.tabs.widget(i).history().clear()
    def bookmark(self):
        url=self.current().url().toString()
        if url.startswith(('https://','http://')) and not any(b['url']==url for b in self.bookmarks):
            self.bookmarks.append({'title':self.current().title() or url,'url':url});self.write_json('bookmarks.json',self.bookmarks)
    def show_bookmarks(self):
        self.chooser('Bookmarks',[(b['title'],b['url'],QUrl(b['url']).host()) for b in self.bookmarks],lambda url:self.new_tab(QUrl(url)))
    def menu(self):
        # Group commands by category for easier navigation
        nav_actions=[
            ('New tab', 'Ctrl+T', lambda:self.new_tab()),
            ('Private window', 'Ctrl+Shift+N', self.private_window),
            ('Bookmarks', None, self.show_bookmarks),
            ('History', 'Ctrl+H', self.show_history),
            ('Clear history', None, self.clear_history),
            ('Switch tabs', 'Ctrl+K', self.tab_picker),
        ]
        page_actions=[
            ('Ask Laya about this page', 'Ctrl+Shift+A', self.ask_laya_about_page),
            ('Zen Mode', 'Alt+Z', lambda:self.zen_btn.click()),
            ('Reload', 'Ctrl+R', lambda:self.current().reload()),
            ('Clear HTTP cache', None, self.profile.clearHttpCache),
            ('Delete cookies', None, lambda:self.profile.cookieStore().deleteAllCookies()),
        ]
        sys_actions=[
            ('Change background', 'Alt+B', self.background_picker),
            ('Settings', None, self.settings_dialog),
            ('Extension support status', None, self.extensions_dialog),
            ('Show controls', 'Ctrl+L', self.reveal),
        ]
        # Build a flat list with category headers for display
        display_items=[]
        for heading, actions in (('Navigation', nav_actions), ('Page', page_actions), ('THISTLE', sys_actions)):
            display_items.append((heading, None))
            display_items += [(name, fn, sh or '') for name, sh, fn in actions]
        self.chooser('Commands', display_items, lambda fn: fn())
    def ask_laya_about_page(self):
        view=self.current()
        if not view:return
        url=view.url().toString();title=view.title() or url
        panel=self.ai_panel
        if not panel.isVisible():
            panel.show()
            self.ai_btn.setChecked(True)
        panel.show_welcome()
        panel.add_message('You', f"Analyze this page: {title}")
        panel.typing.show()
        panel.set_status('Thinking…', 'busy')
        QTimer.singleShot(0, lambda: panel.handle_laya_response(f"Analyze this page: {title} ({url})", url, title, datetime.now()))
    def private_window(self):
        child=Browser(True,self.state_dir,False);self.children_windows.append(child);child.show()
    def settings_dialog(self):
        d=QDialog(self);d.setObjectName('settings');d.setWindowTitle('THISTLE settings');d.setMinimumWidth(440);l=QVBoxLayout(d);l.setContentsMargins(26,22,26,20);l.setSpacing(6)
        heading=QLabel('Settings');heading.setObjectName('dialog_title');l.addWidget(heading);l.addSpacing(8)
        always=QCheckBox('Keep controls visible');always.setChecked(self.config.get('always_show',False));l.addWidget(always)
        restore=QCheckBox('Restore HTTP(S) tabs on next launch');restore.setChecked(self.config.get('restore',True));l.addWidget(restore)
        l.addSpacing(10);field=QLabel('Search engine');field.setObjectName('field');l.addWidget(field);search=QComboBox();search.addItems(['DuckDuckGo','Brave','Google']);search.setCurrentText(self.config.get('search','DuckDuckGo'));l.addWidget(search)
        l.addSpacing(10);field=QLabel('Appearance');field.setObjectName('field');l.addWidget(field);theme=QComboBox();theme.addItems(list(THEMES.keys())+['System']);theme.setCurrentText(self.config.get('theme','Dark'));l.addWidget(theme)
        l.addSpacing(10);field=QLabel('Background preset');field.setObjectName('field');l.addWidget(field);bg_preset=QComboBox();bg_preset.addItems(list(BACKGROUNDS.keys()));current_bg=self.config.get('background',DEFAULT_BACKGROUND);bg_preset.setCurrentText(next((k for k,v in BACKGROUNDS.items() if v==current_bg),'Custom'));l.addWidget(bg_preset)
        l.addSpacing(10);field=QLabel('Custom background URL');field.setObjectName('field');l.addWidget(field);bg_url=QLineEdit();bg_url.setText(current_bg if current_bg not in BACKGROUNDS.values() else '');bg_url.setPlaceholderText('https://...');l.addWidget(bg_url)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setObjectName('primary');[b.setIcon(QIcon()) for b in buttons.buttons()];l.addSpacing(18);l.addWidget(buttons);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject)
        if d.exec()==QDialog.Accepted:
            selected_bg=bg_preset.currentText()
            if selected_bg=='Custom':
                final_bg=bg_url.text().strip() or DEFAULT_BACKGROUND
            else:
                final_bg=BACKGROUNDS[selected_bg]
            self.config.update(always_show=always.isChecked(),restore=restore.isChecked(),search=search.currentText(),theme=theme.currentText(),background=final_bg);self.write_json('settings.json',self.config);self.apply_theme()
            for i in range(self.tabs.count()):
                view=self.tabs.widget(i)
                if view.page() and view.url().toString()=='about:blank':
                    theme_t=THEMES.get(self.config.get('theme','Dark'),THEMES['Dark'])
                    view.setHtml(home_html(self.config.get('background',DEFAULT_BACKGROUND),theme_t['overlay']),QUrl('about:blank'))
            self.hide_controls()
        else:self.apply_theme()
    def set_background(self, url):
        self.config['background'] = url; self.write_json('settings.json', self.config)
        overlay = THEMES.get(self.config.get('theme', 'Dark'), THEMES['Dark'])['overlay']
        for i in range(self.tabs.count()):  # repaint open start and new-tab pages right away
            view = self.tabs.widget(i)
            if view.url().toString() == 'about:blank': view.setHtml(home_html(url, overlay), QUrl('about:blank'))
    def next_background(self):
        local = [v for v in BACKGROUNDS.values() if v.startswith('local:')]
        cur = self.config.get('background', DEFAULT_BACKGROUND)
        self.set_background(local[(local.index(cur) + 1) % len(local)] if cur in local else local[0])
    def background_picker(self):
        self.chooser('Background', [(k, v) for k, v in BACKGROUNDS.items() if k != 'Custom'], self.set_background)
    def apply_theme(self):
        theme=self.config.get('theme','Dark')
        if theme=='System':
            self.setStyleSheet('');pal=self.palette();t=dict(THEMES['Dark'],fg=pal.text().color().name(),muted=pal.placeholderText().color().name(),highlight=pal.highlight().color().name())
            self.paint_icons(tokens(t));return
        t=tokens(THEMES.get(theme,THEMES['Dark']))
        self.setStyleSheet(theme_sheet(t))
        self.paint_icons(t)
    def paint_icons(self,t):
        for b,name in self.icon_buttons:b.setIcon(icon(name,t['soft'],t['highlight']))
        self.ai_panel.refresh_btn.setIcon(icon('reload',t['soft']));self.ai_panel.send_btn.setIcon(icon('send',t['on_hi']))
    def download(self,request):
        path,_=QFileDialog.getSaveFileName(self,'Save download',str(Path.home()/'Downloads'/request.downloadFileName()))
        if not path:request.cancel();return
        p=Path(path);request.setDownloadDirectory(str(p.parent));request.setDownloadFileName(p.name);request.accept()
        request.stateChanged.connect(lambda state: self.download_status(request))
        self.hint.setText('Downloading '+p.name);self.statusBar().show()
    def download_status(self,request):
        self.hint.setText(request.downloadFileName()+' · '+request.state().name);self.statusBar().show()
    def extensions_dialog(self):
        QMessageBox.information(self,'Extensions unavailable in v0.2',
            'Extension loading is disabled in this version. Qt 6.10.3 crashed while enabling a test extension. Chrome Web Store compatibility is not implemented. Core browsing works without extensions.')
    def center_scratchpad(self):
        x=max(20,(self.width()-self.scratchpad.width())//2)
        y=max(20,(self.height()-self.scratchpad.height())//2)
        self.scratchpad.move(x,y)

    def toggle_scratchpad(self):
        if self.scratchpad.isVisible():
            self.scratchpad.hide()
        else:
            self.center_scratchpad()
            self.scratchpad.show()
            self.scratchpad.setFocus()
    def closeEvent(self,event):
        self.write_json('session.json',[self.tabs.widget(i).url().toString() for i in range(self.tabs.count()) if self.tabs.widget(i).url().scheme() in ('http','https')])
        while self.tabs.count():
            view=self.tabs.widget(0);self.tabs.removeTab(0);delete(view)
        super().closeEvent(event)

def migrate_old_data(new):
    # The browser was called Openpuff, then Pappus; carry bookmarks, history and logins over once.
    for name in ('Pappus','Openpuff'):
        old=new.parent.parent/name/name
        if old.is_dir() and not new.exists():
            new.parent.mkdir(parents=True,exist_ok=True);old.rename(new)

def main():
    if hasattr(os,'geteuid') and os.geteuid()==0:
        raise SystemExit('Run THISTLE as a normal user; sandbox disabling is not supported.')
    args=sys.argv[1:]
    private=any(a in ('--private','--incognito','--private-window') for a in args)
    urls=[u for u in (launch_url(a) for a in args if not a.startswith('-')) if u]
    app=QApplication(sys.argv);app.setApplicationName('Thistle');app.setOrganizationName('Thistle');app.setDesktopFileName('thistle');app.setWindowIcon(QIcon(str(ASSETS/'icon.png')))
    migrate_old_data(Path(QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)))
    # One browser per user: a second launch (a clicked link) hands its pages to the running window and exits.
    name=f'thistle-{os.getuid()}'
    if not private:
        sock=QLocalSocket();sock.connectToServer(name)
        if sock.waitForConnected(300):
            sock.write(json.dumps([u.toString() for u in urls]).encode());sock.flush();sock.waitForBytesWritten(1000);sock.disconnectFromServer();return
    window=Browser(private,open_urls=urls);window.show()
    if not private:
        QLocalServer.removeServer(name);server=QLocalServer(window);server.setSocketOptions(QLocalServer.UserAccessOption);server.listen(name)
        def incoming():
            conn=server.nextPendingConnection()
            def read():
                try:pages=json.loads(bytes(conn.readAll()).decode() or '[]')
                except ValueError:pages=[]
                opened=[window.new_tab(u) for u in (launch_url(p) for p in pages[:20] if isinstance(p,str)) if u]
                if not opened:window.new_tab()
                window.showNormal();window.raise_();window.activateWindow()
            conn.readyRead.connect(read)
        server.newConnection.connect(incoming)
    sys.exit(app.exec())
if __name__=='__main__':main()
