"""Real-engine integration tests; use a disposable state directory."""
import http.server
import threading
import tempfile
import time
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication,QLineEdit
from PySide6.QtCore import QUrl,Qt,QTimer
from PySide6.QtTest import QTest
from thistle import migrate_old_data,Browser,destination,launch_url,bg_css
from PySide6.QtWebEngineCore import QWebEngineExtensionInfo

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers()
        self.wfile.write(b'<html><title>THISTLE test page</title><h1 id="proof">Real Chromium rendering</h1><input id="input"><a href="/second">Second page</a></html>')
    def log_message(self,*args):pass

def wait_for(condition, timeout=12000):
    end=time.monotonic()+timeout/1000
    while time.monotonic()<end:
        QApplication.processEvents();QTest.qWait(50)
        if condition():return
    raise AssertionError('Timed out waiting for browser condition')

def main():
    app=QApplication.instance() or QApplication([])
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    with tempfile.TemporaryDirectory() as tmp:
        b=Browser(state_dir=tmp,restore=False);b.show();QTest.qWait(500)
        assert not b.controls.isVisible()
        QTest.keyClicks(b,'x');QTest.qWait(100)
        assert b.controls.isVisible() and b.address.text()=='x'
        b.hide_controls()
        QTest.keyClick(b,Qt.Key_L,Qt.ControlModifier);QTest.qWait(100)
        assert b.controls.isVisible() and b.address.hasFocus()
        url=f'http://127.0.0.1:{server.server_port}/first'
        b.address.setText(url);QTest.keyClick(b.address,Qt.Key_Return)
        wait_for(lambda:b.current().title()=='THISTLE test page')
        result=[];b.current().page().runJavaScript('document.querySelector("#proof").textContent',result.append)
        wait_for(lambda:bool(result));assert result[0]=='Real Chromium rendering'
        assert not b.controls.isVisible()
        b.bookmark();assert json.loads((Path(tmp)/'bookmarks.json').read_text())[0]['url']==url
        first=b.current();b.new_tab();assert b.tabs.count()==2
        b.cycle(-1);assert b.current()==first
        b.close_tab(1);assert b.tabs.count()==1
        b.reopen();assert b.tabs.count()==2
        # pickers hand the chosen value to the callback (tab picker used to raise 'int is not callable')
        b.tabs.setCurrentIndex(1)
        QTimer.singleShot(300,lambda:QTest.keyClick(QApplication.activeModalWidget().findChild(QLineEdit),Qt.Key_Return))
        b.tab_picker();assert b.tabs.currentIndex()==0
        opened=[]
        QTimer.singleShot(300,lambda:QTest.keyClick(QApplication.activeModalWidget().findChild(QLineEdit),Qt.Key_Return))
        b.chooser('t',[('one','https://example.invalid/')],opened.append);assert opened==['https://example.invalid/']
        # shortcuts must not steal undo or Escape from web pages
        keys={s.key().toString() for s in b.shortcuts}
        assert 'Ctrl+Z' not in keys and 'Alt+Z' in keys
        b.tabs.setCurrentIndex(0);b.reveal();QTest.keyClick(b.address,Qt.Key_Escape);QTest.qWait(100)
        assert not b.controls.isVisible()
        assert any(h['url']==url for h in json.loads((Path(tmp)/'history.json').read_text()))
        b.clear_history();assert b.history==[] and json.loads((Path(tmp)/'history.json').read_text())==[] and not b.current().history().canGoBack()
        b.config['always_show']=True;b.hide_controls();assert b.controls.isVisible()
        b.config['always_show']=False;b.hide_controls()
        QTest.qWait(100);b.grab().save('/tmp/thistle-actual-hidden.png');b.reveal();QTest.qWait(100);b.grab().save('/tmp/thistle-actual-controls.png')
        private=Browser(True,tmp,False);assert private.profile.isOffTheRecord()
        private.bookmarks.append({'title':'private','url':'https://private.invalid'});private.write_json('bookmarks.json',private.bookmarks)
        assert not any(x['title']=='private' for x in json.loads((Path(tmp)/'bookmarks.json').read_text()))
        private.close();b.close();app.processEvents()
        assert url in json.loads((Path(tmp)/'session.json').read_text())
        assert launch_url('https://example.com/').toString()=='https://example.com/'
        assert launch_url('javascript:alert(1)') is None and launch_url('/no/such/file.html') is None
        assert launch_url(__file__).isLocalFile()
        assert bg_css('local:bg-neon.jpg').startswith("background-image:url('data:image/jpeg;base64,") and bg_css('local:missing.jpg')==''
        bg0=b.config['background'];b.next_background();assert b.config['background']!=bg0 and b.config['background'].startswith('local:')
        old=Path(tmp)/'m'/'Openpuff'/'Openpuff';old.mkdir(parents=True);(old/'history.json').write_text('[]')
        new=Path(tmp)/'m'/'Thistle'/'Thistle';migrate_old_data(new);assert (new/'history.json').exists() and not old.exists()
        migrate_old_data(new);assert (new/'history.json').exists()
        assert destination('two words').toString().startswith('https://duckduckgo.com/?q=')
        assert destination('javascript:alert(1)').toString()=='about:blank'
        print('PASS: HTTP navigation, Chromium JavaScript, Ctrl+L, Return, Escape, tabs, reopen, bookmarks, clear history, old-name data migration, session, private storage, visibility settings, URL parsing')
    server.shutdown()
if __name__=='__main__':main()
