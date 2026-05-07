"""
UZSCII — Image to ASCII Converter
Supports still image upload and live webcam ASCII stream.
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
# Core algorithm (shared by both upload and webcam modes)
# --------------------------------------------------------------------------

def resize_image(image: Image.Image, new_width: int) -> Image.Image:
    """Resize to target width; multiply height by 0.5 to correct char aspect ratio."""
    w, h = image.size
    new_height = int(new_width * (h / w) * 0.5)
    return image.resize((new_width, max(new_height, 1)))


def to_grayscale(image: Image.Image) -> Image.Image:
    return image.convert("L")


def pixels_to_ascii(image: Image.Image) -> str:
    pixels = list(image.getdata())
    n = len(ASCII_CHARS) - 1
    chars = [ASCII_CHARS[px * n // 255] for px in pixels]
    w = image.width
    return "\n".join("".join(chars[i : i + w]) for i in range(0, len(chars), w))


def convert_to_ascii(image: Image.Image, width: int) -> str:
    return pixels_to_ascii(to_grayscale(resize_image(image, width)))


def bgr_frame_to_pil(frame: np.ndarray) -> Image.Image:
    """Convert an OpenCV BGR frame to a PIL RGB image."""
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


# --------------------------------------------------------------------------
# Page config
# --------------------------------------------------------------------------

st.set_page_config(page_title="UZSCII", page_icon="▓", layout="wide")

st.title("▓ UZSCII")
st.caption("Image-to-ASCII converter — upload a photo or stream your webcam live.")

# --------------------------------------------------------------------------
# Inline controls (no sidebar — avoids sidebar collapsing on interaction)
# --------------------------------------------------------------------------

ctrl_col1, ctrl_col2, _ = st.columns([2, 2, 4])

with ctrl_col1:
    ascii_width = st.slider("Output width (chars)", 40, 200, 100, 5)

with ctrl_col2:
    fps_target = st.slider("Webcam FPS", 1, 20, 10, 1)

st.divider()

# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------

tab_upload, tab_webcam = st.tabs(["📁 Upload Image", "📷 Live Webcam"])


# ── Tab 1: Upload ──────────────────────────────────────────────────────────

with tab_upload:

    # Session state key trick: incrementing forces a fresh empty uploader
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0

    uploaded_file = st.file_uploader(
        "Drag & drop or browse",
        type=["jpg", "jpeg", "png", "webp"],
        key=f"uploader_{st.session_state.uploader_key}",
    )

    if uploaded_file is not None:
        # Clear button — resets uploader by bumping the key
        if st.button("✕ Remove image", key="clear_btn"):
            st.session_state.uploader_key += 1
            st.rerun()

        try:
            image = Image.open(uploaded_file)

            with st.spinner("Converting…"):
                ascii_result = convert_to_ascii(image, ascii_width)

            col_ascii, col_img = st.columns([2, 1])

            with col_ascii:
                st.subheader("ASCII output")
                st.code(ascii_result, language=None)
                st.download_button(
                    "⬇ Download uzscii_output.txt",
                    data=ascii_result.encode("utf-8"),
                    file_name="uzscii_output.txt",
                    mime="text/plain",
                )

            with col_img:
                st.subheader("Original")
                st.image(image, use_container_width=True)
                st.caption(f"{image.width} × {image.height} px · {image.mode}")

        except Exception as e:
            st.error(f"Could not process image: {e}")
            st.info("Make sure the file is a valid JPG, JPEG, PNG, or WEBP image.")

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

    status = st.empty()
    frame_slot = st.empty()

    if st.session_state.webcam_running:
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            status.error("Could not open webcam. Make sure it is connected and not in use by another app.")
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
                    ascii_frame = convert_to_ascii(pil_image, ascii_width)
                    frame_slot.code(ascii_frame, language=None)

                    time.sleep(frame_interval)

            finally:
                cap.release()
                status.info("Webcam stopped.")
    else:
        status.info("Press ▶ Start to begin the ASCII webcam stream.")
