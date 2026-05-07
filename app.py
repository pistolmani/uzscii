"""
UZSCII — Image to ASCII Converter
Supports still image upload and live webcam ASCII stream.
Color mode samples real RGB from each pixel and applies it to its character.
"""

import time
import streamlit as st
from PIL import Image
import cv2
import numpy as np

# --------------------------------------------------------------------------
# ASCII character set — dark (dense) → light (sparse)
# --------------------------------------------------------------------------
ASCII_CHARS = "@%#*+=-:. "


# --------------------------------------------------------------------------
# Core pipeline
# --------------------------------------------------------------------------

def resize_image(image: Image.Image, new_width: int) -> Image.Image:
    """Resize to target width; 0.5 height correction for char aspect ratio."""
    w, h = image.size
    new_height = int(new_width * (h / w) * 0.5)
    return image.resize((new_width, max(new_height, 1)))


def to_grayscale(image: Image.Image) -> Image.Image:
    return image.convert("L")


def convert_to_ascii(image: Image.Image, width: int) -> str:
    """Plain ASCII — no color."""
    resized = resize_image(image, width)
    gray = to_grayscale(resized)
    pixels = list(gray.getdata())
    n = len(ASCII_CHARS) - 1
    chars = [ASCII_CHARS[px * n // 255] for px in pixels]
    w = resized.width
    return "\n".join("".join(chars[i : i + w]) for i in range(0, len(chars), w))


def convert_to_colored_html(image: Image.Image, width: int) -> str:
    """
    Colored ASCII — each character is styled with the real RGB color
    of the original pixel at that position.
    """
    resized = resize_image(image, width)

    # Brightness for character selection
    gray = to_grayscale(resized)
    gray_pixels = list(gray.getdata())

    # Original color for styling (convert to RGB so we always get r,g,b)
    color_pixels = list(resized.convert("RGB").getdata())

    n = len(ASCII_CHARS) - 1
    w = resized.width
    rows = []

    for row_start in range(0, len(gray_pixels), w):
        row_gray   = gray_pixels[row_start : row_start + w]
        row_color  = color_pixels[row_start : row_start + w]
        spans = []
        for gray_px, (r, g, b) in zip(row_gray, row_color):
            char = ASCII_CHARS[gray_px * n // 255]
            if char == " ":
                spans.append("&nbsp;")
            else:
                spans.append(
                    f'<span style="color:rgb({r},{g},{b})">{char}</span>'
                )
        rows.append("".join(spans))

    inner = "<br>".join(rows)
    return (
        "<div style='"
        "background:#000;"
        "padding:16px;"
        "border-radius:4px;"
        "overflow:auto;"
        "font-family:monospace;"
        "font-size:12px;"
        "line-height:1.4;"
        "white-space:pre;'>"
        f"{inner}</div>"
    )


def bgr_frame_to_pil(frame: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


# --------------------------------------------------------------------------
# Page config
# --------------------------------------------------------------------------

st.set_page_config(page_title="UZSCII", page_icon="▓", layout="wide")

st.title("▓ UZSCII")
st.caption("Image-to-ASCII converter — upload a photo or stream your webcam live.")

# --------------------------------------------------------------------------
# Inline controls
# --------------------------------------------------------------------------

ctrl1, ctrl2, ctrl3, _ = st.columns([2, 2, 1, 3])

with ctrl1:
    ascii_width = st.slider("Output width (chars)", 40, 200, 100, 5)

with ctrl2:
    fps_target = st.slider("Webcam FPS", 1, 20, 8, 1)

with ctrl3:
    color_mode = st.checkbox("🎨 Color", value=True)

st.divider()

# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------

tab_upload, tab_webcam = st.tabs(["📁 Upload Image", "📷 Live Webcam"])


# ── Tab 1: Upload ──────────────────────────────────────────────────────────

with tab_upload:

    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0

    uploaded_file = st.file_uploader(
        "Drag & drop or browse",
        type=["jpg", "jpeg", "png", "webp"],
        key=f"uploader_{st.session_state.uploader_key}",
    )

    if uploaded_file is not None:

        if st.button("✕ Remove image"):
            st.session_state.uploader_key += 1
            st.rerun()

        try:
            image = Image.open(uploaded_file)

            with st.spinner("Converting…"):
                if color_mode:
                    html_output = convert_to_colored_html(image, ascii_width)
                else:
                    plain_output = convert_to_ascii(image, ascii_width)

            col_ascii, col_img = st.columns([2, 1])

            with col_ascii:
                st.subheader("ASCII output")
                if color_mode:
                    st.markdown(html_output, unsafe_allow_html=True)
                else:
                    st.code(plain_output, language=None)

                # Download is always plain text
                with st.spinner("Preparing download…"):
                    plain_for_download = (
                        convert_to_ascii(image, ascii_width)
                        if color_mode
                        else plain_output
                    )
                st.download_button(
                    "⬇ Download uzscii_output.txt",
                    data=plain_for_download.encode("utf-8"),
                    file_name="uzscii_output.txt",
                    mime="text/plain",
                )

            with col_img:
                st.subheader("Original")
                st.image(image, use_container_width=True)
                st.caption(f"{image.width} × {image.height} px · {image.mode}")

        except Exception as e:
            st.error(f"Could not process image: {e}")

    else:
        st.info("Upload an image above to get started.")


# ── Tab 2: Webcam ──────────────────────────────────────────────────────────

with tab_webcam:

    if "webcam_running" not in st.session_state:
        st.session_state.webcam_running = False

    btn_col1, btn_col2, _ = st.columns([1, 1, 6])

    with btn_col1:
        if st.button("▶ Start", disabled=st.session_state.webcam_running):
            st.session_state.webcam_running = True
            st.rerun()

    with btn_col2:
        if st.button("■ Stop", disabled=not st.session_state.webcam_running):
            st.session_state.webcam_running = False
            st.rerun()

    status     = st.empty()
    frame_slot = st.empty()

    if st.session_state.webcam_running:
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            status.error("Could not open webcam. Make sure it is connected and not in use.")
            st.session_state.webcam_running = False
        else:
            status.success("Webcam streaming — click ■ Stop to end.")
            frame_interval = 1.0 / fps_target

            try:
                while st.session_state.webcam_running:
                    ret, frame = cap.read()
                    if not ret:
                        status.warning("Lost webcam signal.")
                        break

                    pil_image = bgr_frame_to_pil(frame)

                    if color_mode:
                        html_frame = convert_to_colored_html(pil_image, ascii_width)
                        frame_slot.markdown(html_frame, unsafe_allow_html=True)
                    else:
                        ascii_frame = convert_to_ascii(pil_image, ascii_width)
                        frame_slot.code(ascii_frame, language=None)

                    time.sleep(frame_interval)

            finally:
                cap.release()
                status.info("Webcam stopped.")
    else:
        status.info("Press ▶ Start to begin the ASCII webcam stream.")
