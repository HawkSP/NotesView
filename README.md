# NotesView

A sleek, dark-mode Markdown and text notes viewer and editor for Windows. Readable like Obsidian,
light like Notepad.

## Download

Grab `NotesView.exe` from the [latest release](https://github.com/HawkSP/NotesView/releases/latest)
and run it. No install needed. It uses the Edge WebView2 runtime that ships with Windows 10 and 11.

Windows may show a SmartScreen warning because the exe is not code-signed. Click
**More info** then **Run anyway**.

## Features

- **Read and Edit modes** with clean Markdown rendering: headings, lists, checkboxes, tables,
  code blocks with highlighting, blockquotes and links. Plain `.txt` files work too.
- **Folder sidebar**: open a folder and browse its notes in a collapsible tree, like a vault.
- **Minimal window**: no frame, and the window buttons only appear when you hover the title bar.
  Drag any edge or corner to resize.
- **Format** copies a prompt you can paste into an AI so it writes notes in Markdown that render
  well here. **Copy note** copies the current note.
- **Pin** keeps the window on top. Drag a file onto the window to open it.
- Remembers the last opened folder.

## Shortcuts

| Keys | Action |
| --- | --- |
| `Ctrl+N` | New note |
| `Ctrl+Shift+N` | New window |
| `Ctrl+O` | Open file |
| `Ctrl+Shift+O` | Open folder |
| `Ctrl+B` | Toggle sidebar |
| `Ctrl+E` | Toggle Read / Edit |
| `Ctrl+S` / `Ctrl+Shift+S` | Save / Save As |

## Run from source

```
pip install pywebview markdown pygments
python app.py [file]
```

## Build the exe

```
pip install pyinstaller
build.bat
```

The exe is written to `dist\NotesView.exe`.
