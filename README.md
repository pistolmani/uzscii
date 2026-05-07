# ▓ UZSCII

A simple image-to-ASCII converter built with Python and Streamlit.  
Upload any image, tune the output width, preview the result, and download it as a `.txt` file.

---

## Features

- Upload JPG, JPEG, PNG, or WEBP images
- Side-by-side preview of original image and ASCII output
- Width slider (40–200 characters)
- Aspect-ratio correction so output doesn't look stretched
- One-click download as `uzscii_output.txt`
- Clean error handling for invalid files

---

## Installation

**Requirements:** Python 3.9+

```bash
# 1. Clone or download the project
git clone https://github.com/yourname/uzscii.git
cd uzscii

# 2. (Optional but recommended) Create a virtual environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

---

## How to Run

```bash
streamlit run app.py
```

Streamlit will open the app automatically in your browser at `http://localhost:8501`.

---

## How the Algorithm Works

1. **Upload** — The user uploads an image file. Pillow opens it from memory.
2. **Resize** — The image is scaled to the target character width. Height is multiplied by `0.5` to compensate for the fact that monospace characters are taller than they are wide.
3. **Grayscale** — The resized image is converted to a single brightness channel (0 = black, 255 = white).
4. **Map pixels to characters** — Each brightness value is scaled to an index in the character set `@%#*+=-:. `. Dark pixels (low brightness) map to dense characters like `@`; light pixels map to spaces or dots.
5. **Join into lines** — Characters are grouped row by row to form the final ASCII string, then displayed and made available for download.

---

## Project Structure

```
uzscii/
  app.py            # Everything — UI and algorithm in one file
  requirements.txt  # Python dependencies
  README.md         # This file
```

---

## Future Improvements

- Color ASCII art using ANSI escape codes or HTML spans
- Invert mode (light background → dark characters)
- Custom character set input field
- Export as PNG (render the ASCII text into an image)
- Font size control in the preview
- Drag-and-drop upload zone

---

Built with [Streamlit](https://streamlit.io) and [Pillow](https://python-pillow.org).
