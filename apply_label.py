#!/usr/bin/env python3
"""Etiqueta personalizada para un plugin-generador en LM Studio.

LM Studio deriva el nombre visible de un plugin-generador de su ruta
`~/.lmstudio/extensions/plugins/<owner>/<name>`, y valida ambos como slugs
(minusculas, sin espacios, sin '/'). Para mostrar un texto arbitrario
(p.ej. "OPENVINO - <modelo> - 26.6 tok/s") hay que:

  1. dejar el plugin en una ruta valida (slug), y
  2. parchear las cadenas de presentacion del renderer de LM Studio para
     traducir ese identificador al texto deseado.

Este script hace ambas cosas de forma idempotente y con backup.

Uso:
  sudo python3 apply_label.py \
      --id openvino/qwen3-30b-a3b-instruct-2507-int4-ov \
      --label "OPENVINO - Qwen3-30B-A3B-Instruct-2507-int4-ov - 26.6 tok/s"

  # solo el parche del renderer (plugin ya renombrado):
  sudo python3 apply_label.py --renderer-only --id ... --label "..."

  # revertir:
  sudo python3 apply_label.py --restore

Notas:
  - El identificador interno del plugin/generador NO cambia, asi que las
    peticiones al backend (OVMS, vLLM, etc.) siguen funcionando.
  - El parche vive en el bundle de la app: una actualizacion de LM Studio lo
    sobrescribe -> volver a ejecutar el script (el plugin renombrado persiste).
"""

import argparse
import json
import os
import re
import shutil
import sys

RENDERER = "/opt/LM-Studio/resources/app/.webpack/renderer/main_window.js"
BACKUP = RENDERER + ".orig.bak"
PLUGINS = os.path.expanduser("~/.lmstudio/extensions/plugins")

# patron 1: children:<var>.identifier})
P_CHILD = re.compile(r'children:([A-Za-z_$][\w$]*)\.identifier\}')
# patron 2: selector de modelo del sidebar / cabecera del chat
P_SIDEBAR = 'void 0!==z?z.identifier:B?.identifier??k("chat:modelLoaderPlaceholder")'


def patch_renderer(label, ident, restore=False):
    if not os.path.exists(RENDERER):
        sys.exit(f"no existe {RENDERER} (otra version/ruta de LM Studio?)")
    s = open(RENDERER, encoding="utf-8", errors="ignore").read()

    if restore:
        if not os.path.exists(BACKUP):
            sys.exit(f"no hay backup en {BACKUP}")
        shutil.copy2(BACKUP, RENDERER)
        print("renderer restaurado desde el backup")
        return

    if not os.path.exists(BACKUP):
        shutil.copy2(RENDERER, BACKUP)
        print(f"backup creado: {BACKUP}")

    # revertir variantes anteriores de este mismo parche (idempotencia)
    s = re.sub(
        r'children:([A-Za-z_$][\w$]*)\.identifier===["\']%s["\']\?["\'][^"\']*["\']:\1\.identifier\}'
        % re.escape(ident),
        r"children:\1.identifier}",
        s,
    )
    s = re.sub(r'children:([A-Za-z_$][\w$]*)\.identifier==="[^"]*"\?"[^"]*":\1\.identifier\}',
               r"children:\1.identifier}", s)

    n1 = len(P_CHILD.findall(s))
    s = P_CHILD.sub(
        lambda m: 'children:%s.identifier==="%s"?"%s":%s.identifier}'
        % (m.group(1), ident, label, m.group(1)),
        s,
    )

    n2 = 0
    if P_SIDEBAR in s:
        new = (
            'void 0!==z?(z.identifier==="{i}"?"{l}":z.identifier):'
            '(B&&B.identifier==="{i}"?"{l}":(B?.identifier??k("chat:modelLoaderPlaceholder")))'
        ).format(i=ident, l=label)
        s = s.replace(P_SIDEBAR, new)
        n2 = 1

    open(RENDERER, "w", encoding="utf-8").write(s)
    print(f"renderer parcheado: {n1} sitios 'children', {n2} selector sidebar")


def normalize_plugin(owner, name, ident):
    """Mueve el plugin a <owner>/<name> (slug) y ajusta manifest.json."""
    owner_dir = os.path.join(PLUGINS, owner)
    dst = os.path.join(owner_dir, name)
    if os.path.isdir(dst):
        print(f"plugin ya en {dst}")
    else:
        # buscar manifest.json con este id en cualquier ruta existente
        found = None
        for root, dirs, files in os.walk(PLUGINS):
            if "manifest.json" in files and os.sep + ".lmstudio" not in root:
                try:
                    d = json.load(open(os.path.join(root, "manifest.json")))
                except Exception:
                    continue
                if f'{d.get("owner")}/{d.get("name")}' == ident or ident.endswith(
                    f'{os.path.basename(os.path.dirname(root))}/{os.path.basename(root)}'
                ):
                    found = root
                    break
        if not found:
            sys.exit(f"no encontre el plugin {ident} bajo {PLUGINS}")
        os.makedirs(owner_dir, exist_ok=True)
        shutil.move(found, dst)
        # limpiar el directorio owner viejo si quedo vacio
        old_owner = os.path.dirname(found)
        try:
            if old_owner != owner_dir and not os.listdir(old_owner):
                os.rmdir(old_owner)
        except OSError:
            pass
        print(f"plugin movido: {found} -> {dst}")

    mf = os.path.join(dst, "manifest.json")
    d = json.load(open(mf))
    d["owner"], d["name"] = owner, name
    json.dump(d, open(mf, "w"), indent=2)
    print(f"manifest ajustado: owner={owner} name={name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=False, help="identificador owner/name (slug)")
    ap.add_argument("--label", required=False, help="texto visible deseado")
    ap.add_argument("--renderer-only", action="store_true")
    ap.add_argument("--restore", action="store_true", help="restaurar el renderer")
    ap.add_argument("--renderer", default=None, help="ruta alternativa al bundle (para pruebas)")
    a = ap.parse_args()

    global RENDERER, BACKUP
    if a.renderer:
        RENDERER, BACKUP = a.renderer, a.renderer + ".orig.bak"
    if a.restore:
        patch_renderer("", "", restore=True)
        return
    if not a.id or not a.label:
        sys.exit("--id y --label son obligatorios")
    owner, _, name = a.id.partition("/")
    if not owner or not name:
        sys.exit("--id debe tener la forma owner/name")

    if not a.renderer_only:
        normalize_plugin(owner, name, a.id)
    patch_renderer(a.label, a.id)
    print("\nReinicia LM Studio para ver el cambio.")


if __name__ == "__main__":
    main()
