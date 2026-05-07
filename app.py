"""
UZSCII — Image to ASCII Converter
Converts any uploaded image into ASCII art using brightness mapping.
"""

import streamlit as st
from PIL import Image
import io

# --------------------------------------------------------------------------
# ASCII character set — ordered from darkest (dense) to lightest (sparse).
# Dark pixels → characters with lots of ink (@, %, #).
# Light pixels → minimal characters (dot, space).
# --------------------------------------------------------------------------
ASCII_CHARS = "@%#*+=-:. "


def resize_image(image: Image.Image, new_width: int) -> Image.Image:
    """
    Resize the image to the target width while preserving aspect ratio.

    Characters in a monospace font are roughly twice as tall as they are wide,
    so we multiply height by 0.5 (the aspect correction factor) to prevent
    the ASCII output from looking vertically stretched.
    """
    original_width, original_height = image.size
    aspect_ratio = original_height / original_width
    # Apply 0.5 correction because each character cell is ~2x taller than wide
    new_height = int(new_width * aspect_ratio * 0.5)
    return image.resize((new_width, new_height))


def to_grayscale(image: Image.Image) -> Image.Image:
    """Convert the image to grayscale (single brightness channel, 0–255)."""
    return image.convert("L")


def pixels_to_ascii(image: Image.Image) -> str:
    """
    Map each pixel's brightness value (0–255) to an ASCII character.

    Brightness 0   → index 0   → '@'  (darkest / most dense)
    Brightness 255 → index -1  → ' '  (lightest / empty)

    We scale the 0–255 range to 0–(len-1) by integer division.
    """
    pixels = list(image.getdata())
    chars_per_pixel = len(ASCII_CHARS) - 1

    # Map each brightness value to a character
    ascii_chars = [ASCII_CHARS[pixel * chars_per_pixel // 255] for pixel in pixels]

    # Split the flat list of characters into rows based on image width
    width = image.width
    lines = [
        "".join(ascii_chars[i : i + width])
        for i in range(0, len(ascii_chars), width)
    ]
    return "\n".join(lines)


def convert_image_to_ascii(image: Image.Image, width: int) -> str:
    """Full pipeline: resize → grayscale → ASCII."""
    resized = resize_image(image, width)
    gray = to_grayscale(resized)
    return pixels_to_ascii(gray)


# --------------------------------------------------------------------------
# Streamlit UI
# --------------------------------------------------------------------------

st.set_page_config(page_title="UZSCII", page_icon="▓", layout="wide")

st.title("▓ UZSCII")
st.caption("Upload an image. Get ASCII art. Download it.")

# Sidebar controls
with st.sidebar:
    st.header("Settings")
    ascii_width = st.slider(
        label="Output width (characters)",
        min_value=40,
        max_value=200,
        value=100,
        step=5,
        help="More characters = more detail, but wider output.",
    )
    st.markdown("---")
    st.markdown(
        "**Character set** (dark → light)\n\n`" + " ".join(list(ASCII_CHARS)) + "`"
    )

# File uploader
uploaded_file = st.file_uploader(
    label="Upload an image",
    type=["jpg", "jpeg", "png", "webp"],
    help="Supported formats: JPG, JPEG, PNG, WEBP",
)

if uploaded_file is not None:
    try:
        # Load the image from the uploaded bytes
        image = Image.open(uploaded_file)

        # Layout: original image on the left, ASCII output on the right
        col_img, col_ascii = st.columns([1, 2])

        with col_img:
            st.subheader("Original")
            st.image(image, use_container_width=True)
            st.caption(f"{image.width} × {image.height} px · {image.mode}")

        with col_ascii:
            st.subheader("ASCII Output")

            with st.spinner("Converting..."):
                ascii_result = convert_image_to_ascii(image, ascii_width)

            # Display in a code block so the font is monospaced
            st.code(ascii_result, language=None)

        # Download button — encode the ASCII string to bytes
        txt_bytes = ascii_result.encode("utf-8")
        st.download_button(
            label="⬇ Download uzscii_output.txt",
            data=txt_bytes,
            file_name="uzscii_output.txt",
            mime="text/plain",
        )

    except Exception as e:
        st.error(f"Could not process image: {e}")
        st.info("Make sure the file is a valid JPG, JPEG, PNG, or WEBP image.")

else:
    # Placeholder when nothing is uploaded yet
    st.info("Upload an image using the panel above to get started.")
