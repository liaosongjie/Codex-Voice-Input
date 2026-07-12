from __future__ import annotations

import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
VIDEO_PATH = ROOT / "奶蛙.mp4"
BUILD_DIR = ROOT / ".pet-build"
OUTPUT_DIR = ROOT / "assets" / "pet"
FRAME_RATE = 8
CANVAS_SIZE = 180
CROP_BOX = (30, 100, 690, 1050)
STATE_RANGES = {
    "idle": (0.0, 2.4),
    "listen": (2.4, 5.2),
    "target": (7.4, 10.5),
    "busy": (13.6, 14.6),
    "error": (15.0, 16.0),
}


def ensure_safe_child(path: Path, parent: Path) -> None:
    path.resolve().relative_to(parent.resolve())


def remove_white_background(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = []
    source_pixels = rgba.get_flattened_data() if hasattr(rgba, "get_flattened_data") else rgba.getdata()
    width, height = rgba.size
    for index, (red, green, blue, _alpha) in enumerate(source_pixels):
        y = index // width
        brightness = max(red, green, blue)
        saturation = max(red, green, blue) - min(red, green, blue)
        if y >= int(height * 0.82) and brightness >= 90 and saturation <= 24:
            pixels.append((255, 255, 255, 0))
            continue
        distance = max(255 - red, 255 - green, 255 - blue)
        if distance <= 12:
            pixels.append((255, 255, 255, 0))
            continue
        alpha = 255 if distance >= 45 else round((distance - 12) * 255 / 33)
        alpha_fraction = max(alpha / 255, 1 / 255)
        foreground = tuple(
            max(0, min(255, round(255 + (channel - 255) / alpha_fraction)))
            for channel in (red, green, blue)
        )
        pixels.append((*foreground, alpha))
    rgba.putdata(pixels)
    return rgba


def process_frame(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        cropped = image.crop(CROP_BOX)
        transparent = remove_white_background(cropped)
        transparent.thumbnail((CANVAS_SIZE - 8, CANVAS_SIZE - 8), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (255, 255, 255, 0))
        x = (CANVAS_SIZE - transparent.width) // 2
        y = CANVAS_SIZE - transparent.height - 2
        canvas.alpha_composite(transparent, (x, y))
        alpha = canvas.getchannel("A").point(lambda value: 255 if value >= 64 else 0)
        expanded = alpha.filter(ImageFilter.MaxFilter(3))
        outline_mask = ImageChops.subtract(expanded, alpha)
        outlined = Image.new("RGBA", canvas.size, (54, 39, 24, 0))
        outlined.putalpha(outline_mask)
        canvas.putalpha(alpha)
        outlined.alpha_composite(canvas)
        canvas = outlined
        canvas.save(destination, optimize=True)


def generate_frames() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to build pet assets")
    if not VIDEO_PATH.exists():
        raise FileNotFoundError(VIDEO_PATH)

    ensure_safe_child(BUILD_DIR, ROOT)
    ensure_safe_child(OUTPUT_DIR, ROOT)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for state, (start, end) in STATE_RANGES.items():
        raw_dir = BUILD_DIR / state
        output_dir = OUTPUT_DIR / state
        raw_dir.mkdir(parents=True)
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(start),
                "-t",
                str(end - start),
                "-i",
                str(VIDEO_PATH),
                "-vf",
                f"fps={FRAME_RATE}",
                str(raw_dir / "frame_%03d.png"),
                "-y",
            ],
            check=True,
        )
        for index, source in enumerate(sorted(raw_dir.glob("frame_*.png"))):
            process_frame(source, output_dir / f"{index:03d}.png")

    shutil.rmtree(BUILD_DIR)


def write_tone(path: Path, notes: list[tuple[float, float]]) -> None:
    sample_rate = 22050
    amplitude = 0.16
    samples: list[int] = []
    for frequency, duration in notes:
        count = round(sample_rate * duration)
        for index in range(count):
            position = index / max(1, count - 1)
            envelope = math.sin(math.pi * position) ** 2
            value = amplitude * envelope * math.sin(2 * math.pi * frequency * index / sample_rate)
            samples.append(round(value * 32767))
        samples.extend([0] * round(sample_rate * 0.025))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))


def generate_sounds() -> None:
    sound_dir = OUTPUT_DIR / "sounds"
    sound_dir.mkdir(parents=True, exist_ok=True)
    write_tone(sound_dir / "listen.wav", [(520, 0.08), (660, 0.09)])
    write_tone(sound_dir / "target.wav", [(660, 0.07), (880, 0.11)])
    write_tone(sound_dir / "busy.wav", [(760, 0.06), (960, 0.07)])
    write_tone(sound_dir / "error.wav", [(420, 0.11), (280, 0.16)])
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg and VIDEO_PATH.exists():
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                "3.0",
                "-t",
                "1.8",
                "-i",
                str(VIDEO_PATH),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "22050",
                "-af",
                "afade=t=in:st=0:d=0.05,afade=t=out:st=1.5:d=0.3,volume=0.8",
                str(sound_dir / "laugh.wav"),
                "-y",
            ],
            check=True,
        )


if __name__ == "__main__":
    generate_frames()
    generate_sounds()
    print(f"Pet assets created in {OUTPUT_DIR}")
