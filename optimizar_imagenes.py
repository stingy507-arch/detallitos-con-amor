"""
Optimiza las fotos del catálogo de Detallitos con Amor.

QUÉ HACE
  - Lee index.html y detecta SOLO las imágenes/videos que el catálogo usa.
  - Reduce cada foto a un tamaño adecuado para web (máx. 1000 x 1600 px)
    y la guarda como JPG comprimido en la carpeta "img_optimizada".
  - Crea "index_optimizado.html" con las referencias .png cambiadas a .jpg.
  - NO modifica ni borra nada de tu carpeta "img" original.

CÓMO USARLO
  1. Instala Pillow (una sola vez):   pip install pillow
  2. Copia este archivo dentro de la carpeta del proyecto
     (junto a index.html y a la carpeta img).
  3. Ejecuta:                         python optimizar_imagenes.py
"""

import re
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageOps

# ---------------- Ajustes (puedes cambiarlos) ----------------
CARPETA_ORIGEN = Path("img")
CARPETA_DESTINO = Path("img_optimizada")
HTML_ORIGEN = Path("index.html")
HTML_DESTINO = Path("index_optimizado.html")

MAX_ANCHO = 1000      # píxeles
MAX_ALTO = 1600       # píxeles
CALIDAD_JPG = 82      # 75 = más liviano, 90 = más calidad
NO_TOCAR = {"logo.png"}   # el logo debe conservar su transparencia
EXT_IMAGEN = {".png", ".jpg", ".jpeg"}
EXT_VIDEO = {".mp4", ".webm", ".mov"}
# -------------------------------------------------------------


def kb(n):
    return f"{n / 1024:,.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:,.1f} MB"


def archivos_usados(html):
    """Nombres de archivo entre comillas que terminan en extensión de imagen o video."""
    exts = "|".join(e.lstrip(".") for e in EXT_IMAGEN | EXT_VIDEO)
    patron = re.compile(r"""["'](?:img/)?([^"'/\\$]+?\.(?:%s))["']""" % exts, re.IGNORECASE)
    return sorted(set(patron.findall(html)))


def a_rgb(img):
    """Convierte a RGB rellenando transparencias con blanco."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        fondo = Image.new("RGB", img.size, (255, 255, 255))
        fondo.paste(img, mask=img.split()[-1])
        return fondo
    return img.convert("RGB")


def main():
    if not HTML_ORIGEN.exists() or not CARPETA_ORIGEN.is_dir():
        sys.exit("No encuentro index.html y/o la carpeta img. "
                 "Pon este script junto a ellos y vuelve a ejecutarlo.")

    html = HTML_ORIGEN.read_text(encoding="utf-8")
    usados = archivos_usados(html)

    # Mapa de nombres en minúsculas -> nombre real del archivo (Windows no distingue
    # mayúsculas, GitHub sí; así detectamos referencias mal escritas).
    reales = {p.name: p for p in CARPETA_ORIGEN.iterdir() if p.is_file()}

    if CARPETA_DESTINO.exists():
        shutil.rmtree(CARPETA_DESTINO)
    CARPETA_DESTINO.mkdir()

    # Todos los nombres finales que ya están "ocupados" (para evitar choques .png -> .jpg)
    finales_ocupados = set()
    cambios = {}          # "foto.png" -> "foto.jpg"
    faltantes = []
    total_antes = total_despues = 0
    detalle = []

    # Primero, los que ya son .jpg/.jpeg/.mp4 reservan su nombre
    for nombre in usados:
        if Path(nombre).suffix.lower() in {".jpg", ".jpeg"} | EXT_VIDEO:
            finales_ocupados.add(nombre)

    for nombre in usados:
        origen = reales.get(nombre)
        if origen is None:
            faltantes.append(nombre)
            continue

        ext = origen.suffix.lower()
        peso_antes = origen.stat().st_size
        total_antes += peso_antes

        # Videos y logo: se copian tal cual
        if ext in EXT_VIDEO or nombre in NO_TOCAR:
            shutil.copy2(origen, CARPETA_DESTINO / nombre)
            total_despues += peso_antes
            detalle.append((nombre, peso_antes, peso_antes, "copiado igual"))
            continue

        with Image.open(origen) as im:
            im = ImageOps.exif_transpose(im)      # respeta la rotación de la cámara
            im.thumbnail((MAX_ANCHO, MAX_ALTO), Image.LANCZOS)  # solo reduce, nunca agranda

            if ext in {".jpg", ".jpeg"}:
                destino_nombre = nombre           # mismo nombre, mismo formato
            else:
                candidato = origen.stem + ".jpg"
                if candidato in finales_ocupados:
                    # Ya existe otro archivo usado con ese nombre: mantenemos PNG optimizado
                    destino_nombre = nombre
                else:
                    destino_nombre = candidato
                    finales_ocupados.add(candidato)
                    cambios[nombre] = candidato

            destino = CARPETA_DESTINO / destino_nombre
            if destino_nombre.lower().endswith(".png"):
                im.save(destino, "PNG", optimize=True)
            else:
                a_rgb(im).save(destino, "JPEG", quality=CALIDAD_JPG,
                               optimize=True, progressive=True)

        peso_despues = destino.stat().st_size
        total_despues += peso_despues
        detalle.append((nombre, peso_antes, peso_despues, destino_nombre))

    # Reescribir referencias .png -> .jpg en el HTML (solo entre comillas, exacto)
    nuevo_html = html
    for viejo, nuevo in cambios.items():
        nuevo_html = re.sub(r"""(["'])((?:img/)?)%s\1""" % re.escape(viejo),
                            lambda m: f"{m.group(1)}{m.group(2)}{nuevo}{m.group(1)}", nuevo_html)
    HTML_DESTINO.write_text(nuevo_html, encoding="utf-8")

    # ---------------- Reporte ----------------
    print("\n=== 10 archivos que más pesaban ===")
    for nombre, antes, despues, _ in sorted(detalle, key=lambda x: -x[1])[:10]:
        print(f"  {nombre:<45} {kb(antes):>10}  ->  {kb(despues):>10}")

    print("\n=== RESUMEN ===")
    print(f"  Archivos procesados : {len(detalle)}")
    print(f"  Peso antes          : {kb(total_antes)}")
    print(f"  Peso después        : {kb(total_despues)}")
    if total_antes:
        print(f"  Ahorro              : {100 - total_despues * 100 / total_antes:.0f}%")
    print(f"  Referencias .png -> .jpg actualizadas: {len(cambios)}")

    if faltantes:
        print("\n⚠️  El código menciona estos archivos pero NO existen en la carpeta img")
        print("    (revisa mayúsculas/minúsculas y que estén subidos):")
        for f in faltantes:
            print("    -", f)

    sin_usar = sorted(n for n in reales if n not in set(usados))
    if sin_usar:
        print(f"\nℹ️  {len(sin_usar)} archivos de img/ no aparecen en index.html y NO se copiaron")
        print("    (guarda tu carpeta img original como respaldo). Algunos:")
        for f in sin_usar[:15]:
            print("    -", f)
        if len(sin_usar) > 15:
            print(f"    ... y {len(sin_usar) - 15} más")

    print(f"\nListo. Revisa:  {CARPETA_DESTINO}/   y   {HTML_DESTINO}")


if __name__ == "__main__":
    main()
