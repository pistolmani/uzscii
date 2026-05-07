"""
UZSCII — Image to ASCII Converter
Supports still image upload and live webcam ASCII stream.
Color mode samples real RGB from each pixel.
Rain mode reveals the image Matrix-style, column by column.
"""

import time
import random
import streamlit as st
from PIL import Image, ImageFilter
import cv2
import numpy as np

# --------------------------------------------------------------------------
# Character sets
# --------------------------------------------------------------------------
CHARS_STANDARD = "8096532471:. "   # dark → light, numbers only
RAIN_CHARS     = "8096532471"      # random chars used for falling heads


# --------------------------------------------------------------------------
# Core pipeline
# --------------------------------------------------------------------------

def resize_image(image: Image.Image, new_width: int) -> Image.Image:
    w, h = image.size
    new_height = int(new_width * (h / w) * 0.5)
    return image.resize((new_width, max(new_height, 1)))


def to_grayscale(image: Image.Image) -> Image.Image:
    return image.convert("L")


def brightness_char(brightness: int) -> str:
    n = len(CHARS_STANDARD) - 1
    return CHARS_STANDARD[brightness * n // 255]


def edge_char(angle_deg: float) -> str:
    a = angle_deg % 180
    if a < 22.5 or a >= 157.5:  return "-"
    elif a < 67.5:               return "/"
    elif a < 112.5:              return "|"
    else:                        return "\\"


def get_edge_data(gray: Image.Image):
    arr = np.array(gray, dtype=np.float32)
    gx  = cv2.Sobel(arr, cv2.CV_32F, 1, 0, ksize=3)
    gy  = cv2.Sobel(arr, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)
    ang = np.degrees(np.arctan2(gy, gx)) % 180
    if mag.max() > 0:
        mag = mag / mag.max() * 255
    return mag, ang


def prepare_image_data(image: Image.Image, width: int, edge: bool):
    """
    Returns (chars_grid, colors_grid) — both are list[list[...]]
    chars_grid:  height × width list of characters
    colors_grid: height × width list of (r,g,b) tuples
    """
    resized      = resize_image(image, width)
    gray         = to_grayscale(resized)
    gray_pixels  = list(gray.getdata())
    color_pixels = list(resized.convert("RGB").getdata())
    W, H         = resized.width, resized.height

    mag, ang = get_edge_data(gray) if edge else (None, None)

    chars_grid  = []
    colors_grid = []

    for r in range(H):
        row_chars  = []
        row_colors = []
        for c in range(W):
            idx = r * W + c
            gp  = gray_pixels[idx]
            if edge and mag[r, c] > 40:
                ch = edge_char(ang[r, c])
            else:
                ch = brightness_char(gp)
            row_chars.append(ch)
            row_colors.append(color_pixels[idx])
        chars_grid.append(row_chars)
        colors_grid.append(row_colors)

    return chars_grid, colors_grid, W, H


def render_html(chars_grid, colors_grid, W, H, use_color: bool) -> str:
    """Render a completed chars/colors grid as an HTML block."""
    rows = []
    for r in range(H):
        spans = []
        for c in range(W):
            ch = chars_grid[r][c]
            if ch == " ":
                spans.append("&nbsp;")
            elif use_color:
                rv, gv, bv = colors_grid[r][c]
                spans.append(f'<span style="color:rgb({rv},{gv},{bv})">{ch}</span>')
            else:
                spans.append(f'<span style="color:#ccc">{ch}</span>')
        rows.append("".join(spans))
    inner = "<br>".join(rows)
    return (
        "<div style='background:#000;padding:16px;border-radius:4px;"
        "overflow:auto;font-family:monospace;font-size:12px;"
        "line-height:1.4;white-space:pre;'>"
        f"{inner}</div>"
    )


def render_rain_frame(
    chars_grid, colors_grid,
    col_heads: list,   # current head row per column (-1 = not started)
    settled: list,     # settled[r][c] = True once locked in
    W: int, H: int,
    use_color: bool,
) -> str:
    """Render one frame of the rain animation."""
    rows = []
    for r in range(H):
        spans = []
        for c in range(W):
            head = col_heads[c]

            if settled[r][c]:
                # Locked-in image character
                ch = chars_grid[r][c]
                if ch == " ":
                    spans.append("&nbsp;")
                elif use_color:
                    rv, gv, bv = colors_grid[r][c]
                    spans.append(f'<span style="color:rgb({rv},{gv},{bv})">{ch}</span>')
                else:
                    spans.append(f'<span style="color:#aaa">{ch}</span>')

            elif r == head:
                # Bright falling head — always white
                spans.append(f'<span style="color:#fff;font-weight:bold">{random.choice(RAIN_CHARS)}</span>')

            elif head != -1 and r == head - 1:
                # One row above head — dim cyan trail
                spans.append(f'<span style="color:#0ff;opacity:0.5">{random.choice(RAIN_CHARS)}</span>')

            elif head != -1 and r < head and not settled[r][c]:
                # Fading trail above
                fade = max(0.08, 0.35 - (head - r) * 0.06)
                spans.append(f'<span style="color:#0ff;opacity:{fade:.2f}">{random.choice(RAIN_CHARS)}</span>')

            else:
                spans.append("&nbsp;")

        rows.append("".join(spans))

    inner = "<br>".join(rows)
    return (
        "<div style='background:#000;padding:16px;border-radius:4px;"
        "overflow:auto;font-family:monospace;font-size:12px;"
        "line-height:1.4;white-space:pre;'>"
        f"{inner}</div>"
    )


def run_rain(image: Image.Image, width: int, edge: bool, use_color: bool, slot):
    """Run the full rain reveal animation, updating `slot` each frame."""
    chars_grid, colors_grid, W, H = prepare_image_data(image, width, edge)

    # Each column starts at a random offset so they don't all fall together
    col_heads = [-1] * W
    settled   = [[False] * W for _ in range(H)]

    # Stagger column starts: some begin immediately, others are delayed
    col_start_frame = [random.randint(0, H // 2) for _ in range(W)]

    frame      = 0
    done_cols  = 0

    while done_cols < W:
        # Advance columns
        for c in range(W):
            if frame < col_start_frame[c]:
                continue
            if col_heads[c] == -1:
                col_heads[c] = 0
            elif col_heads[c] < H:
                # Lock in the row just passed
                prev = col_heads[c] - 1
                if 0 <= prev < H:
                    settled[prev][c] = True
                col_heads[c] += 1
            else:
                # Column finished — lock final row
                if not settled[H - 1][c]:
                    settled[H - 1][c] = True
                    done_cols += 1

        html = render_rain_frame(
            chars_grid, colors_grid,
            col_heads, settled,
            W, H, use_color,
        )
        slot.markdown(html, unsafe_allow_html=True)
        time.sleep(0.045)
        frame += 1


# --------------------------------------------------------------------------
# Helpers for plain/color static render
# --------------------------------------------------------------------------

def convert_to_ascii(image: Image.Image, width: int, edge: bool = False) -> str:
    chars_grid, _, W, H = prepare_image_data(image, width, edge)
    return "\n".join("".join(row) for row in chars_grid)


def convert_to_colored_html(image: Image.Image, width: int, edge: bool = False) -> str:
    chars_grid, colors_grid, W, H = prepare_image_data(image, width, edge)
    return render_html(chars_grid, colors_grid, W, H, use_color=True)


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

ctrl1, ctrl2, ctrl3, ctrl4, ctrl5, _ = st.columns([2, 2, 1, 1, 1, 1])

with ctrl1:
    ascii_width = st.slider("Output width (chars)", 40, 200, 100, 5)

with ctrl2:
    fps_target = st.slider("Webcam FPS", 1, 20, 8, 1)

with ctrl3:
    color_mode = st.checkbox("🎨 Color", value=True)

with ctrl4:
    edge_mode = st.checkbox("✏️ Edges", value=False)

with ctrl5:
    rain_mode = st.checkbox("🌧 Rain", value=False)

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
            col_ascii, col_img = st.columns([2, 1])

            with col_ascii:
                st.subheader("ASCII output")
                output_slot = st.empty()

                if rain_mode:
                    # Rain plays immediately; replay button reruns the page
                    run_rain(image, ascii_width, edge_mode, color_mode, output_slot)
                    if st.button("↺ Replay rain"):
                        st.rerun()
                else:
                    with st.spinner("Converting…"):
                        if color_mode:
                            output_slot.markdown(
                                convert_to_colored_html(image, ascii_width, edge_mode),
                                unsafe_allow_html=True,
                            )
                        else:
                            output_slot.code(
                                convert_to_ascii(image, ascii_width, edge_mode),
                                language=None,
                            )

                plain_dl = convert_to_ascii(image, ascii_width, edge_mode)
                st.download_button(
                    "⬇ Download uzscii_output.txt",
                    data=plain_dl.encode("utf-8"),
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
                        frame_slot.markdown(
                            convert_to_colored_html(pil_image, ascii_width, edge_mode),
                            unsafe_allow_html=True,
                        )
                    else:
                        frame_slot.code(
                            convert_to_ascii(pil_image, ascii_width, edge_mode),
                            language=None,
                        )

                    time.sleep(frame_interval)

            finally:
                cap.release()
                status.info("Webcam stopped.")
    else:
        status.info("Press ▶ Start to begin the ASCII webcam stream.")
