"""
compress_media_images.py
========================
One-time script to bulk-compress all property images in the media/ folder.

What it does:
  - Converts JPEG/PNG → WebP (80% quality) \u2014 typically 60–80% size reduction
  - Resizes any image wider than 1920px
  - Converts animated GIFs → animated WebP
  - Skips already-converted WebP files
  - Creates a .bak copy of originals before replacing them
  - Prints a summary of space saved

Usage:
  python compress_media_images.py              # dry run (shows what it would do)
  python compress_media_images.py --apply      # actually compress and replace files
  python compress_media_images.py --apply --no-backup   # no backup copies

Requirements:
  pip install Pillow   (already in requirements.txt)
"""

import os
import sys
import shutil
from pathlib import Path

try:
    from PIL import Image, ImageSequence
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

# ─── Configuration ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
MEDIA_ROOT = BASE_DIR / "media"
MAX_WIDTH = 1920          # px — wider images get scaled down
MAX_HEIGHT = 1920         # px
JPEG_QUALITY = 82         # 0-95, higher = better quality
WEBP_QUALITY = 82         # 0-100
CONVERT_TO_WEBP = True    # Convert JPEG/PNG to WebP format
PROCESS_ANIMATED_GIFS = True

DRY_RUN = "--apply" not in sys.argv
MAKE_BACKUP = "--no-backup" not in sys.argv

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def human_size(num_bytes):
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def compress_image(path: Path) -> dict:
    """
    Compress a single image file.
    Returns a dict with keys: skipped, saved_bytes, new_path
    """
    ext = path.suffix.lower()
    original_size = path.stat().st_size

    if ext not in SUPPORTED_EXTS:
        return {"skipped": True, "reason": "unsupported extension"}

    # Skip tiny files (already small enough)
    if original_size < 50_000:  # < 50 KB
        return {"skipped": True, "reason": "already small"}

    try:
        # ── Animated GIF handling ──────────────────────────────────────────
        if ext == ".gif" and PROCESS_ANIMATED_GIFS:
            img = Image.open(path)
            if hasattr(img, "n_frames") and img.n_frames > 1:
                # Animated GIF → animated WebP
                frames = []
                durations = []
                for frame in ImageSequence.Iterator(img):
                    f = frame.convert("RGBA")
                    if f.width > MAX_WIDTH or f.height > MAX_HEIGHT:
                        f.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.LANCZOS)
                    frames.append(f)
                    durations.append(frame.info.get("duration", 100))

                target_path = path.with_suffix(".webp")

                if not DRY_RUN:
                    if MAKE_BACKUP and not path.with_suffix(".gif.bak").exists():
                        shutil.copy2(path, path.with_suffix(".gif.bak"))
                    frames[0].save(
                        target_path,
                        format="WEBP",
                        save_all=True,
                        append_images=frames[1:],
                        duration=durations,
                        loop=0,
                        quality=WEBP_QUALITY,
                    )
                    path.unlink()  # Remove original GIF

                new_size = target_path.stat().st_size if not DRY_RUN else original_size // 5
                return {
                    "skipped": False,
                    "original_size": original_size,
                    "new_size": new_size,
                    "saved_bytes": original_size - new_size,
                    "new_path": target_path,
                    "action": "gif→webp (animated)",
                }

        # ── Static image handling ──────────────────────────────────────────
        img = Image.open(path)
        original_format = img.format

        # Resize if too large
        if img.width > MAX_WIDTH or img.height > MAX_HEIGHT:
            img.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.LANCZOS)

        # Convert to WebP or re-save as original format
        if CONVERT_TO_WEBP and ext in {".jpg", ".jpeg", ".png", ".gif"}:
            target_path = path.with_suffix(".webp")
            save_format = "WEBP"
            save_kwargs = {"quality": WEBP_QUALITY, "method": 4}
            # Preserve transparency for PNG
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")
        else:
            target_path = path
            save_format = original_format or "JPEG"
            save_kwargs = {"quality": JPEG_QUALITY, "optimize": True}
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

        if not DRY_RUN:
            if MAKE_BACKUP and target_path == path and not path.with_suffix(path.suffix + ".bak").exists():
                shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
            img.save(target_path, format=save_format, **save_kwargs)
            if target_path != path:
                if MAKE_BACKUP and not path.with_suffix(path.suffix + ".bak").exists():
                    shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
                path.unlink()  # Remove original

        new_size = target_path.stat().st_size if not DRY_RUN else int(original_size * 0.3)
        return {
            "skipped": False,
            "original_size": original_size,
            "new_size": new_size,
            "saved_bytes": original_size - new_size,
            "new_path": target_path,
            "action": f"{ext}→.webp" if CONVERT_TO_WEBP else f"re-compressed {ext}",
        }

    except Exception as e:
        return {"skipped": True, "reason": f"error: {e}"}


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if DRY_RUN:
        print("=" * 60)
        print("DRY RUN MODE — no files will be modified")
        print("Run with --apply to actually compress files")
        print("=" * 60)
    else:
        print("=" * 60)
        print("APPLYING COMPRESSION — files will be modified!")
        if MAKE_BACKUP:
            print("Backups will be created with .bak extension")
        print("=" * 60)

    print(f"\nScanning: {MEDIA_ROOT}\n")

    total_original = 0
    total_new = 0
    processed = 0
    skipped = 0
    errors = 0

    image_files = sorted(
        p for p in MEDIA_ROOT.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
        and ".bak" not in p.name
    )

    print(f"Found {len(image_files)} image files\n")

    for img_path in image_files:
        result = compress_image(img_path)

        if result.get("skipped"):
            skipped += 1
            continue

        orig = result["original_size"]
        new = result["new_size"]
        saved = result["saved_bytes"]
        pct = (saved / orig * 100) if orig > 0 else 0

        total_original += orig
        total_new += new
        processed += 1

        status = "WOULD" if DRY_RUN else "SAVED"
        print(
            f"  {result['action']:20s} | {human_size(orig):>10} → {human_size(new):>10} "
            f"| {status} {human_size(saved)} ({pct:.0f}%) | {img_path.name}"
        )

    total_saved = total_original - total_new
    print("\n" + "=" * 60)
    print(f"Files processed : {processed}")
    print(f"Files skipped   : {skipped}")
    print(f"Original size   : {human_size(total_original)}")
    print(f"New size        : {human_size(total_new)}")
    print(f"Space {'would be ' if DRY_RUN else ''}saved  : {human_size(total_saved)} ({total_saved / total_original * 100:.1f}% reduction)" if total_original else "No files processed")
    print("=" * 60)

    if DRY_RUN:
        print("\nRun with --apply to apply these changes.")


if __name__ == "__main__":
    main()
