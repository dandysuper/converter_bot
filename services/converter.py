import gzip
import json
import logging
import os
import subprocess
import tempfile
from io import BytesIO
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class StickerConverter:
    """
    Converts Telegram stickers to GIF / MP4 / WebM / PNG.

    Telegram sticker types:
    - Static:   .webp  → Pillow can open directly
    - Animated: .tgs   → gzipped Lottie JSON → needs lottie-convert / ffmpeg
    - Video:    .webm  → already a video, ffmpeg can transcode
    """

    SUPPORTED_FORMATS = ["gif", "mp4", "webm", "png"]

    async def convert_sticker(
        self,
        file_bytes: bytes,
        output_format: str = "gif",
        is_animated: bool = False,
        is_video: bool = False,
        watermark_text: Optional[str] = None,
        font_name: Optional[str] = None,
        font_color: str = "#FFFFFF",
        position: str = "bottom_right",
    ) -> bytes:
        output_format = output_format.lower()
        if output_format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {output_format}")

        logger.info(f"Converting sticker: animated={is_animated}, video={is_video}, fmt={output_format}")

        if is_video:
            # Video sticker (.webm) → use ffmpeg directly
            return await self._convert_video_sticker(
                file_bytes, output_format, watermark_text, font_name, font_color, position
            )
        elif is_animated:
            # Animated sticker (.tgs = gzipped Lottie JSON)
            return await self._convert_tgs_sticker(
                file_bytes, output_format, watermark_text, font_name, font_color, position
            )
        else:
            # Static sticker (.webp)
            return await self._convert_static_webp(
                file_bytes, output_format, watermark_text, font_name, font_color, position
            )

    # ── Static WebP ───────────────────────────────────────────────────────────

    async def _convert_static_webp(
        self,
        file_bytes: bytes,
        output_format: str,
        watermark_text: Optional[str],
        font_name: Optional[str],
        font_color: str,
        position: str,
    ) -> bytes:
        img = Image.open(BytesIO(file_bytes))

        # Handle animated WebP (some static stickers are multi-frame WebP)
        is_multi = getattr(img, "is_animated", False) or (
            hasattr(img, "n_frames") and img.n_frames > 1
        )

        if is_multi and output_format == "gif":
            return await self._animated_webp_to_gif(img, watermark_text, font_name, font_color, position)

        # Single frame
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        if watermark_text:
            img = self._add_watermark(img, watermark_text, font_name, font_color, position)

        buf = BytesIO()
        if output_format == "gif":
            # White background for GIF
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            bg.save(buf, format="GIF")
        elif output_format == "png":
            img.save(buf, format="PNG")
        elif output_format in ("mp4", "webm"):
            return await self._pil_image_to_video(img, output_format)
        buf.seek(0)
        return buf.read()

    async def _animated_webp_to_gif(
        self, img, watermark_text, font_name, font_color, position
    ) -> bytes:
        frames, durations = [], []
        for i in range(img.n_frames):
            img.seek(i)
            frame = img.convert("RGBA").copy()
            if watermark_text:
                frame = self._add_watermark(frame, watermark_text, font_name, font_color, position)
            gif_frame = frame.convert("RGB").quantize(colors=256, method=Image.Quantize.FASTOCTREE)
            frames.append(gif_frame)
            durations.append(img.info.get("duration", 100))

        buf = BytesIO()
        frames[0].save(
            buf,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            loop=0,
            duration=durations,
            optimize=False,
        )
        buf.seek(0)
        return buf.read()

    # ── TGS (Lottie) animated sticker ────────────────────────────────────────

    async def _convert_tgs_sticker(
        self,
        file_bytes: bytes,
        output_format: str,
        watermark_text: Optional[str],
        font_name: Optional[str],
        font_color: str,
        position: str,
    ) -> bytes:
        """Convert .tgs (gzipped Lottie) to GIF/PNG/MP4/WebM via ffmpeg + lottie."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tgs_path = os.path.join(tmpdir, "sticker.tgs")
            with open(tgs_path, "wb") as f:
                f.write(file_bytes)

            # Try lottie-convert first (pip install lottie)
            frames_dir = os.path.join(tmpdir, "frames")
            os.makedirs(frames_dir)

            try:
                result = await self._lottie_to_frames(tgs_path, frames_dir)
            except Exception as e:
                logger.warning(f"lottie-convert failed: {e}, falling back to ffmpeg")
                # Fallback: decompress to JSON and render with puppeteer if available
                # or just return a placeholder PNG
                return await self._tgs_fallback(file_bytes, output_format)

            frame_files = sorted(
                [f for f in os.listdir(frames_dir) if f.endswith(".png")]
            )
            if not frame_files:
                raise RuntimeError("No frames rendered from TGS")

            if watermark_text:
                for fname in frame_files:
                    fpath = os.path.join(frames_dir, fname)
                    img = Image.open(fpath).convert("RGBA")
                    img = self._add_watermark(img, watermark_text, font_name, font_color, position)
                    img.save(fpath)

            return await self._frames_dir_to_output(frames_dir, frame_files, output_format, fps=60)

    async def _lottie_to_frames(self, tgs_path: str, frames_dir: str):
        """Use the lottie Python library to render TGS frames."""
        import lottie
        from lottie.exporters.gif import export_gif
        from lottie import parsers

        # Parse TGS
        an = parsers.tgs.parse_tgs(tgs_path)

        # Render each frame as PNG
        from lottie.exporters.png import export_frame
        fps = an.frame_rate or 60
        total_frames = int(an.out_point - an.in_point)

        for i in range(total_frames):
            frame_path = os.path.join(frames_dir, f"frame_{i:04d}.png")
            export_frame(an, frame_path, i + an.in_point)

    async def _tgs_fallback(self, file_bytes: bytes, output_format: str) -> bytes:
        """
        Fallback when lottie rendering is unavailable.
        Decompress TGS, grab thumbnail dimensions, return a simple placeholder.
        """
        try:
            json_data = gzip.decompress(file_bytes)
            data = json.loads(json_data)
            w = data.get("w", 512)
            h = data.get("h", 512)
        except Exception:
            w, h = 512, 512

        # Return a grey placeholder image
        img = Image.new("RGBA", (w, h), (200, 200, 200, 255))
        draw = ImageDraw.Draw(img)
        draw.text((w // 4, h // 2 - 20), "Animated\nSticker", fill=(100, 100, 100, 255))

        buf = BytesIO()
        if output_format == "png":
            img.save(buf, format="PNG")
        else:
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            bg.save(buf, format="GIF")
        buf.seek(0)
        return buf.read()

    # ── Video sticker (.webm) ─────────────────────────────────────────────────

    async def _convert_video_sticker(
        self,
        file_bytes: bytes,
        output_format: str,
        watermark_text: Optional[str],
        font_name: Optional[str],
        font_color: str,
        position: str,
    ) -> bytes:
        """Transcode a .webm video sticker using ffmpeg."""
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "input.webm")
            with open(in_path, "wb") as f:
                f.write(file_bytes)

            # Build watermark filter if needed
            vf_parts = []
            if watermark_text:
                safe_text = watermark_text.replace("'", "\\'").replace(":", "\\:")
                vf_parts.append(
                    f"drawtext=text='{safe_text}':fontsize=24:fontcolor={font_color}:"
                    f"x=(w-text_w)-10:y=(h-text_h)-10:"
                    f"shadowcolor=black:shadowx=1:shadowy=1"
                )

            if output_format == "gif":
                out_path = os.path.join(tmpdir, "out.gif")
                vf = ",".join(["fps=15,scale=512:-1:flags=lanczos"] + vf_parts)
                cmd = [
                    "ffmpeg", "-y", "-i", in_path,
                    "-vf", f"[0:v] {vf},split [a][b];[a] palettegen [p];[b][p] paletteuse",
                    out_path,
                ]
                # simpler fallback
                cmd = [
                    "ffmpeg", "-y", "-i", in_path,
                    "-vf", f"fps=15,scale=512:-1:flags=lanczos{(',' + ','.join(vf_parts)) if vf_parts else ''}",
                    out_path,
                ]
            elif output_format == "mp4":
                out_path = os.path.join(tmpdir, "out.mp4")
                vf = ",".join(["scale=trunc(iw/2)*2:trunc(ih/2)*2"] + vf_parts)
                cmd = [
                    "ffmpeg", "-y", "-i", in_path,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-vf", vf,
                    out_path,
                ]
            elif output_format == "webm":
                out_path = os.path.join(tmpdir, "out.webm")
                vf = ",".join(vf_parts) if vf_parts else None
                cmd = ["ffmpeg", "-y", "-i", in_path, "-c:v", "libvpx-vp9"]
                if vf:
                    cmd += ["-vf", vf]
                cmd.append(out_path)
            elif output_format == "png":
                out_path = os.path.join(tmpdir, "out.png")
                cmd = ["ffmpeg", "-y", "-i", in_path, "-frames:v", "1", out_path]
            else:
                raise ValueError(f"Unsupported format: {output_format}")

            result = subprocess.run(cmd, capture_output=True, timeout=60)
            if result.returncode != 0:
                logger.error(f"ffmpeg error: {result.stderr.decode()}")
                raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[-500:]}")

            with open(out_path, "rb") as f:
                return f.read()

    # ── PIL image → video ─────────────────────────────────────────────────────

    async def _pil_image_to_video(self, img: Image.Image, fmt: str) -> bytes:
        with tempfile.TemporaryDirectory() as tmpdir:
            png_path = os.path.join(tmpdir, "frame.png")
            img.convert("RGB").save(png_path)
            ext = fmt
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
                    "-c:v", "libvpx-vp9", "-t", "2", out_path,
                ]
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[-300:]}")
            with open(out_path, "rb") as f:
                return f.read()

    # ── Frames dir → output ───────────────────────────────────────────────────

    async def _frames_dir_to_output(
        self, frames_dir: str, frame_files: list, output_format: str, fps: float = 60
    ) -> bytes:
        if output_format == "gif":
            frames, durations = [], []
            for fname in frame_files:
                img = Image.open(os.path.join(frames_dir, fname)).convert("RGBA")
                gif_frame = img.convert("RGB").quantize(colors=256, method=Image.Quantize.FASTOCTREE)
                frames.append(gif_frame)
                durations.append(int(1000 / fps))
            buf = BytesIO()
            frames[0].save(
                buf, format="GIF", save_all=True,
                append_images=frames[1:], loop=0, duration=durations,
            )
            buf.seek(0)
            return buf.read()
        elif output_format == "png":
            img = Image.open(os.path.join(frames_dir, frame_files[0]))
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            return buf.read()
        else:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Symlink or copy frames
                for i, fname in enumerate(frame_files):
                    src = os.path.join(frames_dir, fname)
                    dst = os.path.join(tmpdir, f"frame_{i:04d}.png")
                    import shutil
                    shutil.copy2(src, dst)

                ext = output_format
                out_path = os.path.join(tmpdir, f"out.{ext}")
                if output_format == "mp4":
                    cmd = [
                        "ffmpeg", "-y", "-framerate", str(fps),
                        "-i", os.path.join(tmpdir, "frame_%04d.png"),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                        out_path,
                    ]
                else:
                    cmd = [
                        "ffmpeg", "-y", "-framerate", str(fps),
                        "-i", os.path.join(tmpdir, "frame_%04d.png"),
                        "-c:v", "libvpx-vp9", out_path,
                    ]
                result = subprocess.run(cmd, capture_output=True, timeout=60)
                if result.returncode != 0:
                    raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[-300:]}")
                with open(out_path, "rb") as f:
                    return f.read()

    # ── Watermark ─────────────────────────────────────────────────────────────

    def _add_watermark(
        self,
        img: Image.Image,
        text: str,
        font_name: Optional[str],
        color: str,
        position: str,
    ) -> Image.Image:
        draw = ImageDraw.Draw(img)
        font = self._load_font(font_name, size=max(18, img.width // 10))
        text_bbox = draw.textbbox((0, 0), text, font=font)
        tw = text_bbox[2] - text_bbox[0]
        th = text_bbox[3] - text_bbox[1]
        w, h = img.size
        p = max(8, w // 25)
        coords_map = {
            "top_left": (p, p),
            "top_right": (w - tw - p, p),
            "bottom_left": (p, h - th - p),
            "bottom_right": (w - tw - p, h - th - p),
            "center": ((w - tw) // 2, (h - th) // 2),
        }
        coords = coords_map.get(position, coords_map["bottom_right"])
        shadow_offset = max(1, w // 100)
        draw.text((coords[0] + shadow_offset, coords[1] + shadow_offset), text, font=font, fill=(0, 0, 0, 180))
        draw.text(coords, text, font=font, fill=color)
        return img

    def _load_font(self, font_name: Optional[str], size: int = 36):
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]
        if font_name and font_name != "default":
            candidates = [
                f"/usr/share/fonts/truetype/{font_name}.ttf",
                f"/usr/share/fonts/truetype/dejavu/{font_name}.ttf",
                f"fonts/{font_name}.ttf",
            ] + candidates
        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
        return ImageFont.load_default()


converter_service = StickerConverter()
