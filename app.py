"""NotesView - a small dark-mode Markdown / text viewer and editor (pywebview)."""
import html
import json
import os
import re
import sys
import time
import webbrowser

import markdown
import markdown.extensions.fenced_code  # noqa: F401  (explicit imports help PyInstaller)
import markdown.extensions.tables  # noqa: F401
import markdown.extensions.toc  # noqa: F401
import markdown.extensions.sane_lists  # noqa: F401
import webview
from webview.dom import DOMEventHandler

try:
    import markdown.extensions.codehilite  # noqa: F401
    from pygments.formatters import HtmlFormatter

    CODE_CSS = HtmlFormatter(style='monokai').get_style_defs('.codehilite')
    HAVE_HILITE = True
except Exception:
    CODE_CSS = ''
    HAVE_HILITE = False

APP_NAME = 'NotesView'
FILE_TYPES = ('Notes (*.md;*.markdown;*.txt)', 'Markdown (*.md;*.markdown)',
              'Text (*.txt)', 'All files (*.*)')
_last_dir = os.path.expanduser('~')
NOTE_EXTS = ('.md', '.markdown', '.txt')
STATE_PATH = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), APP_NAME, 'state.json')
MIN_W, MIN_H = 360, 240

_TASK_RE = re.compile(r'<li>(\s*<p>)?\[([ xX])\]\s')


def resource_path(*parts):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def read_text(path):
    with open(path, 'rb') as f:
        data = f.read()
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return data.decode('cp1252', errors='replace')


def is_markdown_path(path):
    return not (path or '').lower().endswith('.txt')


def _first(result):
    if not result:
        return None
    return result if isinstance(result, str) else result[0]


def load_state():
    try:
        with open(STATE_PATH, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(**values):
    try:
        data = load_state()
        data.update(values)
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(STATE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def last_folder():
    folder = load_state().get('folder')
    return folder if isinstance(folder, str) and os.path.isdir(folder) else None


def folder_tree(path):
    """{name, path, dirs, files} for note files under path; None if nothing matches."""
    dirs, files = [], []
    try:
        entries = list(os.scandir(path))
    except OSError:
        entries = []
    for e in entries:
        try:
            if e.is_dir(follow_symlinks=False):
                if not e.name.startswith('.'):
                    sub = folder_tree(e.path)
                    if sub:
                        dirs.append(sub)
            elif e.is_file() and e.name.lower().endswith(NOTE_EXTS):
                files.append({'name': e.name, 'path': e.path})
        except OSError:
            continue
    if not dirs and not files:
        return None
    dirs.sort(key=lambda d: d['name'].lower())
    files.sort(key=lambda f: f['name'].lower())
    return {'name': os.path.basename(path.rstrip('\\/')) or path, 'path': path,
            'dirs': dirs, 'files': files}


def render_html(text, is_markdown=True):
    if not is_markdown:
        return '<pre class="plain">' + html.escape(text or '') + '</pre>'
    exts = ['fenced_code', 'tables', 'toc', 'sane_lists']
    cfg = {}
    if HAVE_HILITE:
        exts.append('codehilite')
        cfg['codehilite'] = {'guess_lang': False, 'css_class': 'codehilite'}
    out = markdown.markdown(text or '', extensions=exts, extension_configs=cfg)

    def task(m):
        checked = ' checked' if m.group(2) in 'xX' else ''
        return '<li class="task">%s<input type="checkbox" disabled%s> ' % (m.group(1) or '', checked)

    return _TASK_RE.sub(task, out)


class Api:
    def __init__(self, path=None, folder=None):
        self._window = None
        self._path = path
        self._folder = folder
        self._maximized = False

    # ---- helpers -------------------------------------------------------
    def _remember_dir(self, path):
        global _last_dir
        _last_dir = os.path.dirname(path) or _last_dir

    def _payload(self, path):
        text = read_text(path)
        self._path = path
        self._remember_dir(path)
        return {'path': path, 'name': os.path.basename(path), 'text': text,
                'is_markdown': is_markdown_path(path)}

    def _write(self, path, text):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        self._path = path
        self._remember_dir(path)
        return path

    # ---- exposed -------------------------------------------------------
    def init(self):
        data = {'code_css': CODE_CSS, 'file': None, 'folder': None}
        if self._folder:
            data['folder'] = self.list_folder(self._folder)
        if self._path:
            try:
                data['file'] = self._payload(self._path)
            except OSError as e:
                data['error'] = str(e)
                self._path = None
        return data

    def new_window(self):
        open_window(None, self._folder or last_folder())

    def new_note(self):
        self._path = None

    def open_folder(self):
        res = _first(self._window.create_file_dialog(
            webview.FileDialog.FOLDER, directory=self._folder or _last_dir))
        if not res:
            return None
        save_state(folder=res)
        return self.list_folder(res)

    def list_folder(self, path):
        if not path or not os.path.isdir(path):
            return None
        self._folder = path
        tree = folder_tree(path)
        return tree or {'name': os.path.basename(path.rstrip('\\/')) or path, 'path': path,
                        'dirs': [], 'files': []}

    def open_file(self):
        res = _first(self._window.create_file_dialog(
            webview.FileDialog.OPEN, directory=_last_dir, file_types=FILE_TYPES))
        return self._payload(res) if res else None

    def read_path(self, path):
        try:
            return self._payload(path)
        except OSError:
            return None

    def save(self, text):
        if not self._path:
            return self.save_as(text)
        return self._write(self._path, text)

    def save_as(self, text):
        name = os.path.basename(self._path) if self._path else 'Untitled.md'
        start = os.path.dirname(self._path) if self._path else (self._folder or _last_dir)
        res = _first(self._window.create_file_dialog(
            webview.FileDialog.SAVE, directory=start, save_filename=name, file_types=FILE_TYPES))
        return self._write(res, text) if res else None

    def render(self, text, is_markdown=True):
        return render_html(text, is_markdown)

    def copy(self, text):
        import win32clipboard
        for _ in range(10):  # clipboard may be briefly locked by another app
            try:
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(text or '', win32clipboard.CF_UNICODETEXT)
                finally:
                    win32clipboard.CloseClipboard()
                return True
            except Exception:
                time.sleep(0.05)
        return False

    def open_link(self, url):
        if re.match(r'^(https?|mailto):', url or '', re.I):
            webbrowser.open(url)

    def set_title(self, title):
        self._window.set_title(title)

    def confirm_discard(self):
        return self._window.create_confirmation_dialog(APP_NAME, 'Discard unsaved changes?')

    def minimize(self):
        self._window.minimize()

    def toggle_maximize(self):
        if self._maximized:
            self._window.restore()
        else:
            self._window.maximize()
        self._maximized = not self._maximized
        return self._maximized

    def resize_begin(self):
        w = self._window
        return {'x': w.x, 'y': w.y, 'width': w.width, 'height': w.height,
                'maximized': self._maximized}

    def resize_to(self, x, y, w, h):
        if self._maximized:
            return
        try:
            x, y = int(x), int(y)
            w, h = max(MIN_W, int(w)), max(MIN_H, int(h))
            if (x, y) != (self._window.x, self._window.y):
                self._window.move(x, y)
            self._window.resize(w, h)
        except Exception:
            pass

    def close(self, dirty=False):
        if dirty and not self.confirm_discard():
            return False
        self._window.destroy()
        return True

    def toggle_pin(self):
        # pywebview's set_on_top touches the WinForms form from this worker
        # thread, which .NET treats as a fatal cross-thread call. Marshal it
        # onto the UI thread ourselves instead.
        self._pinned = not getattr(self, '_pinned', False)
        state = self._pinned
        try:
            from webview.platforms.winforms import BrowserView
            from System import Func, Type

            form = BrowserView.instances.get(self._window.uid)

            def _set():
                form.TopMost = state

            form.Invoke(Func[Type](_set))
        except Exception:
            # Non-Windows backend (or anything unexpected): use pywebview's API.
            self._window.on_top = state
        return state


def _register_drop(window):
    def on_drop(e):
        files = (e.get('dataTransfer') or {}).get('files') or []
        for f in files:
            p = f.get('pywebviewFullPath')
            if p:
                window.evaluate_js('window.app && window.app.dropPath(%s)' % _js_str(p))
                break

    try:
        window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)
    except Exception:
        pass  # drag & drop is optional


def _js_str(s):
    return json.dumps(s)


def open_window(path=None, folder=None):
    api = Api(path, folder)
    title = os.path.basename(path) if path else 'Untitled'
    window = webview.create_window(
        '%s - %s' % (title, APP_NAME), url=resource_path('ui', 'index.html'), js_api=api,
        width=820, height=640, min_size=(360, 240), frameless=True, easy_drag=False,
        resizable=True, background_color='#1e1e22')
    api._window = window
    window.events.loaded += lambda: _register_drop(window)
    return window


def main():
    path = None
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        path = os.path.abspath(sys.argv[1])
    open_window(path, None if path else last_folder())
    webview.start(debug=False)


if __name__ == '__main__':
    main()
