import logging
import os
import tempfile
from io import BytesIO
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

POSITIONS = {
    "top_left": "top_left",
    "top_right": "top_right",
    "bottom_left": "bottom_left",
    "bottom_right": "bottom_right",
    "center": "center",
}


class StickerConverter:
    """Converts Telegram stickers (WebP/animated) to GIF, MP4, PNG."""

    SUPPORTED_FORMATS = ["gif", "mp4", "webm", "png"]

    async def convert_sticker(
        self,
        file_bytes: bytes,
        output_format: str = "gif",
        watermark_text: Optional[str] = None,
        font_name: Optional[str] = None,
        font_color: str = "#FFFFFF",
        position: str = "bottom_right",
    ) -> bytes:
        """
        Convert sticker bytes to the desired format.
        Returns the converted file as bytes.
        """
        output_format = output_format.lower()
        if output_format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {output_format}")

        # Open image from bytes
        img = Image.open(BytesIO(file_bytes))

        # Handle animated WebP / GIF
        is_animated = getattr(img, "is_animated", False) or hasattr(img, "n_frames") and img.n_frames > 1

        if is_animated:
            return await self._convert_animated(
                img, output_format, watermark_text, font_name, font_color, position
            )
        else:
            return await self._convert_static(
                img, output_format, watermark_text, font_name, font_color, position
            )

    async def _convert_static(
        self,
        img: Image.Image,
        output_format: str,
        watermark_text: Optional[str],
        font_name: Optional[str],
        font_color: str,
        position: str,
    ) -> bytes:
        """Convert a static sticker."""
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        if watermark_text:
            img = self._add_watermark(img, watermark_text, font_name, font_color, position)

        buf = BytesIO()
        if output_format == "gif":
            # Convert RGBA → P for GIF
            rgb = Image.new("RGBA", img.size, (255, 255, 255, 0))
            rgb.paste(img, mask=img.split()[3])
            rgb = rgb.convert("RGB")
            rgb.save(buf, format="GIF")
        elif output_format == "png":
            img.save(buf, format="PNG")
        elif output_format in ("mp4", "webm"):
            # For static image → video, we wrap in a short 1-frame video via ffmpeg
            buf = await self._static_to_video(img, output_format)
            return buf.getvalue() if isinstance(buf, BytesIO) else buf
        buf.seek(0)
        return buf.read()

    async def _convert_animated(
        self,
        img: Image.Image,
        output_format: str,
        watermark_text: Optional[str],
        font_name: Optional[str],
        font_color: str,
        position: str,
    ) -> bytes:
        """Convert an animated sticker (animated WebP / GIF)."""
        frames = []
        durations = []

        try:
            n_frames = img.n_frames
        except AttributeError:
            n_frames = 1

        for i in range(n_frames):
            img.seek(i)
            frame = img.convert("RGBA").copy()
            if watermark_text:
                frame = self._add_watermark(frame, watermark_text, font_name, font_color, position)
            frames.append(frame)
            durations.append(img.info.get("duration", 100))

        buf = BytesIO()
        if output_format == "gif":
            # Convert frames for GIF (palette mode)
            gif_frames = []
            for frame in frames:
                f = frame.convert("RGB").quantize(colors=256, method=Image.Quantize.FASTOCTREE)
                gif_frames.append(f)
            gif_frames[0].save(
                buf,
                format="GIF",
                save_all=True,
                append_images=gif_frames[1:],
                loop=0,
                duration=durations,
                optimize=False,
            )
        elif output_format == "png":
            # Save first frame as PNG
            frames[0].save(buf, format="PNG")
        elif output_format in ("mp4", "webm"):
            buf = await self._frames_to_video(frames, durations, output_format)
            return buf.getvalue() if isinstance(buf, BytesIO) else buf

        buf.seek(0)
        return buf.read()

    async def _static_to_video(self, img: Image.Image, fmt: str) -> BytesIO:
        """Wrap a static image in a short video using ffmpeg."""
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            png_path = os.path.join(tmpdir, "frame.png")
            img.convert("RGB").save(png_path, format="PNG")

            ext = "mp4" if fmt == "mp4" else "webm"
            out_path = os.path.join(tmpdir, f"out.{ext}")

            if fmt == "mp4":
                cmd = [
                    "ffmpeg", "-y", "-loop", "1", "-i", png_path,
                    "-c:v", "libx264", "-t", "2", "-pix_fmt", "yuv420p",
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    out_path,
                ]
            else:
                cmd = [
                    "ffmpeg", "-y", "-loop", "1", "-i", png_path,
                    "-c:v", "libvpx-vp9", "-t", "2",
                    out_path,
                ]

            subprocess.run(cmd, check=True, capture_output=True)
            buf = BytesIO()
            with open(out_path, "rb") as f:
                buf.write(f.read())
            buf.seek(0)
            return buf

    async def _frames_to_video(self, frames: list, durations: list, fmt: str) -> BytesIO:
        """Convert animation frames to MP4/WebM using ffmpeg."""
        import subprocess

        with tempfile.TemporaryDirectory() as tmpdir:
            for i, frame in enumerate(frames):
                frame.convert("RGB").save(os.path.join(tmpdir, f"frame_{i:04d}.png"))

            fps = 1000 / (sum(durations) / len(durations)) if durations else 10
            fps = max(1, min(fps, 30))

            ext = "mp4" if fmt == "mp4" else "webm"
            out_path = os.path.join(tmpdir, f"out.{ext}")

            if fmt == "mp4":
                cmd = [
                    "ffmpeg", "-y",
                    "-framerate", str(fps),
                    "-i", os.path.join(tmpdir, "frame_%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    out_path,
                ]
            else:
                cmd = [
                    "ffmpeg", "-y",
                    "-framerate", str(fps),
                    "-i", os.path.join(tmpdir, "frame_%04d.png"),
                    "-c:v", "libvpx-vp9",
                    out_path,
                ]

            subprocess.run(cmd, check=True, capture_output=True)
            buf = BytesIO()
            with open(out_path, "rb") as f:
                buf.write(f.read())
            buf.seek(0)
            return buf

    def _add_watermark(
        self,
        img: Image.Image,
        text: str,
        font_name: Optional[str],
        color: str,
        position: str,
    ) -> Image.Image:
        """Draw a text watermark onto the image."""
        draw = ImageDraw.Draw(img)

        font = self._load_font(font_name, size=max(18, img.width // 10))

        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        width, height = img.size
        padding = max(8, img.width // 25)

        coords_map = {
            "top_left": (padding, padding),
            "top_right": (width - text_width - padding, padding),
            "bottom_left": (padding, height - text_height - padding),
            "bottom_right": (width - text_width - padding, height - text_height - padding),
            "center": ((width - text_width) // 2, (height - text_height) // 2),
        }
        coords = coords_map.get(position, coords_map["bottom_right"])

        # Shadow
        shadow_offset = max(1, img.width // 100)
        draw.text(
            (coords[0] + shadow_offset, coords[1] + shadow_offset),
            text,
            font=font,
            fill=(0, 0, 0, 128),
        )
        # Main text
        draw.text(coords, text, font=font, fill=color)

        return img

    def _load_font(self, font_name: Optional[str], size: int = 36) -> ImageFont.FreeTypeFont:
        """Try to load a font by name from common system paths."""
        if font_name and font_name != "default":
            search_paths = [
                f"/usr/share/fonts/truetype/{font_name}.ttf",
                f"/usr/share/fonts/truetype/dejavu/{font_name}.ttf",
                f"/usr/share/fonts/{font_name}.ttf",
                f"fonts/{font_name}.ttf",
            ]
            for path in search_paths:
                if os.path.exists(path):
                    try:
                        return ImageFont.truetype(path, size)
                    except Exception:
                        pass
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except Exception:
            return ImageFont.load_default()


converter_service = StickerConverter()
