"""
UZSCII — Image to ASCII Converter
Supports still image upload and live webcam ASCII stream.
Color mode samples real RGB from each pixel and applies it to its character.
"""

import time
import streamlit as st
from PIL import Image, ImageFilter
import cv2
import numpy as np

# --------------------------------------------------------------------------
# Character sets — dark (dense) → light (sparse), numbers only
# --------------------------------------------------------------------------
CHARS_STANDARD = "8096532471:. "   # 13 gradations
CHARS_EDGE     = r"/\|-."          # directional edge characters


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


def brightness_char(brightness: int, charset: str) -> str:
    n = len(charset) - 1
    return charset[brightness * n // 255]


def edge_char(angle_deg: float) -> str:
    """Map a gradient angle (0–180°) to a directional character."""
    a = angle_deg % 180
    if a < 22.5 or a >= 157.5:
        return "-"
    elif a < 67.5:
        return "/"
    elif a < 112.5:
        return "|"
    else:
        return "\\"


def get_edge_data(gray: Image.Image) -> tuple:
    """
    Return (magnitude array, angle array) using Sobel filters.
    magnitude is 0–255 float, angle is degrees 0–180.
    """
    arr = np.array(gray, dtype=np.float32)
    gx = cv2.Sobel(arr, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(arr, cv2.CV_32F, 0, 1, ksize=3)
    mag   = np.sqrt(gx**2 + gy**2)
    angle = np.degrees(np.arctan2(np.abs(gy), np.abs(gx)))  # 0–90, map to 0–180
    # Remap arctan2 result to full 0–180 considering sign
    angle = np.degrees(np.arctan2(gy, gx)) % 180
    # Normalise magnitude to 0–255
    if mag.max() > 0:
        mag = mag / mag.max() * 255
    return mag, angle


def convert_to_ascii(image: Image.Image, width: int, edge_mode: bool = False) -> str:
    """Plain ASCII — no color. Optional edge-enhanced mode."""
    resized  = resize_image(image, width)
    gray     = to_grayscale(resized)
    gray_px  = list(gray.getdata())
    w        = resized.width

    if edge_mode:
        mag, angle = get_edge_data(gray)
        rows = []
        for r in range(resized.height):
            row = []
            for c in range(w):
                idx = r * w + c
                if mag[r, c] > 40:
                    row.append(edge_char(angle[r, c]))
                else:
                    row.append(brightness_char(gray_px[idx], CHARS_STANDARD))
            rows.append("".join(row))
        return "\n".join(rows)

    chars = [brightness_char(px, CHARS_STANDARD) for px in gray_px]
    return "\n".join("".join(chars[i : i + w]) for i in range(0, len(chars), w))


def convert_to_colored_html(image: Image.Image, width: int, edge_mode: bool = False) -> str:
    """
    Colored ASCII — each character is styled with the real RGB color
    of the original pixel at that position.
    """
    resized      = resize_image(image, width)
    gray         = to_grayscale(resized)
    gray_pixels  = list(gray.getdata())
    color_pixels = list(resized.convert("RGB").getdata())
    w            = resized.width

    if edge_mode:
        mag, angle = get_edge_data(gray)

    rows = []
    for row_start in range(0, len(gray_pixels), w):
        row_idx   = row_start // w
        row_gray  = gray_pixels[row_start : row_start + w]
        row_color = color_pixels[row_start : row_start + w]
        spans = []
        for col_idx, (gray_px, (r, g, b)) in enumerate(zip(row_gray, row_color)):
            if edge_mode and mag[row_idx, col_idx] > 40:
                char = edge_char(angle[row_idx, col_idx])
            else:
                char = brightness_char(gray_px, CHARS_STANDARD)

            if char == " ":
                spans.append("&nbsp;")
            else:
                spans.append(f'<span style="color:rgb({r},{g},{b})">{char}</span>')
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

ctrl1, ctrl2, ctrl3, ctrl4, _ = st.columns([2, 2, 1, 1, 2])

with ctrl1:
    ascii_width = st.slider("Output width (chars)", 40, 200, 100, 5)

with ctrl2:
    fps_target = st.slider("Webcam FPS", 1, 20, 8, 1)

with ctrl3:
    color_mode = st.checkbox("🎨 Color", value=True)

with ctrl4:
    edge_mode = st.checkbox("✏️ Edges", value=False)

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
                    html_output = convert_to_colored_html(image, ascii_width, edge_mode)
                else:
                    plain_output = convert_to_ascii(image, ascii_width, edge_mode)

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
                        convert_to_ascii(image, ascii_width, edge_mode)
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
                        html_frame = convert_to_colored_html(pil_image, ascii_width, edge_mode)
                        frame_slot.markdown(html_frame, unsafe_allow_html=True)
                    else:
                        ascii_frame = convert_to_ascii(pil_image, ascii_width, edge_mode)
                        frame_slot.code(ascii_frame, language=None)

                    time.sleep(frame_interval)

            finally:
                cap.release()
                status.info("Webcam stopped.")
    else:
        status.info("Press ▶ Start to begin the ASCII webcam stream.")
