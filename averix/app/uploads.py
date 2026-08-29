"""
Приём картинок.

Имени и типу, которые прислал браузер, не верим ни в чём: и то и другое
подделывается. Файл проверяется по содержимому, пересохраняется нашим
кодом и получает случайное имя.
"""
import secrets
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from .config import MAX_UPLOAD_BYTES, UPLOAD_DIR

# Подписи в первых байтах файла. Расширение и Content-Type от клиента
# ничего не доказывают, а эти байты записывает сам формат.
_SIGNATURES = (
    (b"\xff\xd8\xff", "JPEG"),
    (b"\x89PNG\r\n\x1a\n", "PNG"),
)

MAX_SIDE = 1920          # больше для сайта не нужно
WEBP_QUALITY = 82


class UploadError(Exception):
    """Понятная человеку причина отказа."""


@dataclass
class SavedImage:
    filename: str
    width: int
    height: int
    bytes: int


def _looks_like_image(head: bytes) -> bool:
    if any(head.startswith(sig) for sig, _ in _SIGNATURES):
        return True
    # WebP: RIFF....WEBP
    return head[:4] == b"RIFF" and head[8:12] == b"WEBP"


def save_image(raw: bytes, original_name: str = "") -> SavedImage:
    if not raw:
        raise UploadError("Файл пустой.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise UploadError(
            f"Файл больше {MAX_UPLOAD_BYTES // (1024 * 1024)} МБ. Сожмите и попробуйте снова."
        )
    if not _looks_like_image(raw[:16]):
        raise UploadError("Это не JPEG, PNG или WebP. Проверьте файл.")

    import io

    try:
        # verify() ловит битые и поддельные файлы, но после него
        # объект непригоден — открываем заново
        Image.open(io.BytesIO(raw)).verify()
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise UploadError("Файл повреждён или это не изображение.")

    if img.width < 8 or img.height < 8:
        raise UploadError("Изображение слишком маленькое.")

    # Телефон пишет ориентацию в EXIF; применяем её и дальше EXIF теряется
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.mode else "RGB")

    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{secrets.token_hex(16)}.webp"
    path = UPLOAD_DIR / filename

    # Пересохраняем сами: в результат попадают только пиксели.
    # Ни EXIF с координатами съёмки, ни посторонние данные,
    # которые можно спрятать внутри исходного файла, не переносятся.
    img.save(path, "WEBP", quality=WEBP_QUALITY, method=4)

    return SavedImage(filename, img.width, img.height, path.stat().st_size)


def delete_image_file(filename: str) -> None:
    """Удаляет файл, не выпуская за пределы папки загрузок."""
    if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
        return
    path = (UPLOAD_DIR / filename).resolve()
    if path.parent != UPLOAD_DIR.resolve() or not path.is_file():
        return
    path.unlink(missing_ok=True)
