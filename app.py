"""
UZSCII — Image to ASCII Converter
Supports still image upload and live webcam ASCII stream.
Color mode samples real RGB from each pixel.
Rain mode is browser-side JS — no server loop, scroll works fine.
"""

import json
import time
import random
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageEnhance
import cv2
import numpy as np

# --------------------------------------------------------------------------
# Character sets
# --------------------------------------------------------------------------
CHARS_STANDARD = "8096532471:. "
RAIN_CHARS     = "8096532471"


# --------------------------------------------------------------------------
# Core pipeline
# --------------------------------------------------------------------------

def resize_image(image: Image.Image, new_width: int) -> Image.Image:
    w, h = image.size
    new_height = int(new_width * (h / w) * 0.5)
    return image.resize((new_width, max(new_height, 1)))


def to_grayscale(image: Image.Image) -> Image.Image:
    return image.convert("L")


def brightness_char(brightness: int, charset: str = CHARS_STANDARD, invert: bool = False) -> str:
    n = len(charset) - 1
    i = brightness * n // 255
    if invert:
        i = n - i
    return charset[i]


def apply_enhancements(img: Image.Image, contrast: float, brightness: float) -> Image.Image:
    if contrast == 1.0 and brightness == 1.0:
        return img
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    return img


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
    resized      = resize_image(image, width)
    gray         = to_grayscale(resized)
    gray_pixels  = list(gray.getdata())
    color_pixels = list(resized.convert("RGB").getdata())
    W, H         = resized.width, resized.height
    mag, ang     = get_edge_data(gray) if edge else (None, None)

    chars_flat  = []
    colors_flat = []

    for r in range(H):
        for c in range(W):
            idx = r * W + c
            gp  = gray_pixels[idx]
            if edge and mag[r, c] > 40:
                ch = edge_char(ang[r, c])
            else:
                ch = brightness_char(gp)
            chars_flat.append(ch)
            colors_flat.append(list(color_pixels[idx]))

    return chars_flat, colors_flat, W, H


# --------------------------------------------------------------------------
# Static HTML render (no animation)
# --------------------------------------------------------------------------

def render_static_html(chars_flat, colors_flat, W, H, use_color: bool) -> str:
    rows = []
    for r in range(H):
        spans = []
        for c in range(W):
            idx = r * W + c
            ch  = chars_flat[idx]
            if ch == " ":
                spans.append("&nbsp;")
            elif use_color:
                rv, gv, bv = colors_flat[idx]
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


# --------------------------------------------------------------------------
# Rain — self-contained HTML + JS component (runs in browser, no server loop)
# --------------------------------------------------------------------------

def rain_component(chars_flat, colors_flat, W, H, use_color: bool, height_px: int):
    chars_json  = json.dumps(chars_flat)
    colors_json = json.dumps(colors_flat)
    use_color_js = "true" if use_color else "false"

    html = f"""
<div id="uz" style="background:#000;padding:16px;border-radius:4px;
     font-family:monospace;font-size:12px;line-height:1.4;
     white-space:pre;overflow:auto;"></div>
<script>
(function() {{
  const W = {W}, H = {H};
  const chars  = {chars_json};
  const colors = {colors_json};
  const useColor = {use_color_js};
  const RAIN = "{RAIN_CHARS}";
  const rc = () => RAIN[Math.floor(Math.random() * RAIN.length)];

  const heads    = new Array(W).fill(-1);
  const settled  = new Uint8Array(W * H);
  const startAt  = Array.from({{length: W}},
                    () => Math.floor(Math.random() * {max(H // 3, 1)}));
  let frame = 0;

  function render() {{
    // advance columns
    for (let c = 0; c < W; c++) {{
      if (frame < startAt[c]) continue;
      if (heads[c] === -1) {{
        heads[c] = 0;
      }} else if (heads[c] < H) {{
        const prev = heads[c] - 1;
        if (prev >= 0) settled[prev * W + c] = 1;
        heads[c]++;
      }} else {{
        settled[(H - 1) * W + c] = 1;
      }}
    }}

    // build HTML
    let html = '';
    for (let r = 0; r < H; r++) {{
      for (let c = 0; c < W; c++) {{
        const idx  = r * W + c;
        const head = heads[c];
        const ch   = chars[idx];

        if (settled[idx]) {{
          if (ch === ' ') {{
            html += ' ';
          }} else if (useColor) {{
            const [rv,gv,bv] = colors[idx];
            html += `<span style="color:rgb(${{rv}},${{gv}},${{bv}})">${{ch}}</span>`;
          }} else {{
            html += `<span style="color:#aaa">${{ch}}</span>`;
          }}
        }} else if (r === head) {{
          html += `<span style="color:#fff;font-weight:bold">${{rc()}}</span>`;
        }} else if (head !== -1 && r === head - 1) {{
          html += `<span style="color:#0ff;opacity:0.55">${{rc()}}</span>`;
        }} else if (head !== -1 && r < head) {{
          const fade = Math.max(0.06, 0.4 - (head - r) * 0.07);
          html += `<span style="color:#0ff;opacity:${{fade.toFixed(2)}}">${{rc()}}</span>`;
        }} else {{
          html += ' ';
        }}
      }}
      html += '<br>';
    }}

    document.getElementById('uz').innerHTML = html;
    frame++;

    // stop when every cell is settled
    let done = true;
    for (let i = 0; i < settled.length; i++) {{
      if (!settled[i] && chars[i] !== ' ') {{ done = false; break; }}
    }}
    if (!done) setTimeout(render, 45);
  }}

  setTimeout(render, 80);
}})();
</script>
"""
    components.html(html, height=height_px, scrolling=False)


# --------------------------------------------------------------------------
# Static converters (used for download + webcam)
# --------------------------------------------------------------------------

def convert_to_ascii(image: Image.Image, width: int, edge: bool = False) -> str:
    chars_flat, _, W, H = prepare_image_data(image, width, edge)
    return "\n".join(
        "".join(chars_flat[r * W : (r + 1) * W]) for r in range(H)
    )


def convert_to_colored_html(image: Image.Image, width: int, edge: bool = False) -> str:
    chars_flat, colors_flat, W, H = prepare_image_data(image, width, edge)
    return render_static_html(chars_flat, colors_flat, W, H, use_color=True)


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

                with st.spinner("Converting…"):
                    chars_flat, colors_flat, W, H = prepare_image_data(
                        image, ascii_width, edge_mode
                    )

                if rain_mode:
                    # JS animation — runs in browser, no blocking
                    rain_component(
                        chars_flat, colors_flat, W, H,
                        use_color=color_mode,
                        height_px=H * 18 + 80,
                    )
                else:
                    html_out = render_static_html(
                        chars_flat, colors_flat, W, H, use_color=color_mode
                    )
                    st.markdown(html_out, unsafe_allow_html=True)

                plain_dl = "\n".join(
                    "".join(chars_flat[r * W : (r + 1) * W]) for r in range(H)
                )
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
