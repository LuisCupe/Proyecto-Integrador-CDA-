"""Incrusta Plotly.js 2.35.2 (carpeta vendor/ junto a este script) dentro de un HTML que
los carga desde cdnjs, y lo envuelve como documento completo (doctype + charset) para abrirlo con
doble clic y sin internet.

Uso: python incrustar.py <entrada.html> <salida.html>
"""
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
LIB = {
    'https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.35.2/plotly.min.js': AQUI / 'vendor' / 'plotly-2.35.2.min.js',
}
# '</script' y U+FFFD solo aparecen dentro de cadenas de las librerías: se escapan sin cambiar su significado
CODIGO = {u: p.read_text(encoding='utf-8').replace('</script', '<\\/script').replace('�', '\\ufffd')
          for u, p in LIB.items()}


def incrustar(entrada, salida):
    html = Path(entrada).read_text(encoding='utf-8')
    n = 0
    for url, js in CODIGO.items():
        html, k = re.compile(r'<script src="' + re.escape(url) + r'"[^>]*></script>').subn(
            lambda m: '<script>' + js + '</script>', html)
        n += k
    if not html.lstrip().lower().startswith('<!doctype'):
        titulo = re.search(r'<title>.*?</title>', html, re.S)
        cab = titulo.group(0) if titulo else ''
        html = ('<!doctype html>\n<html lang="es"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">' + cab +
                '</head><body>\n' + (html.replace(cab, '', 1) if cab else html) + '\n</body></html>\n')
    Path(salida).write_text(html, encoding='utf-8')
    print(f'{Path(salida).name}: {n} librerías incrustadas, {len(html.encode()) / 1e6:.2f} MB')


if __name__ == '__main__':
    incrustar(sys.argv[1], sys.argv[2])
