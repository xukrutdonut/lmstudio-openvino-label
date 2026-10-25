# lmstudio-openvino-label

Etiqueta visible personalizada para un plugin-generador (endpoint OpenAI-compatible
tipo `openai-compat-endpoint` → OVMS / vLLM / llama.cpp) en **LM Studio**.

Objetivo: que el selector de modelos muestre, por ejemplo,

```
OPENVINO - Qwen3-30B-A3B-Instruct-2507-int4-ov - 26.6 tok/s
```

en lugar de `openvino/qwen3-30b-a3b-instruct-2507-int4-ov`.

## Por qué hace falta un parche

1. LM Studio deriva `owner`/`name` de la ruta del plugin:
   `~/.lmstudio/extensions/plugins/<owner>/<name>`, y valida ambos como slug
   (minúsculas, sin espacios, sin `/`). Si el nombre no es válido, **el plugin
   ni siquiera aparece** en "Your Generators". Por eso `tok/s` o `OPENVINO - …`
   no pueden vivir en la carpeta.
2. El texto que pinta la UI es literalmente ese identificador. La única forma de
   mostrar un texto arbitrario es parchear las cadenas de presentación del
   renderer de Electron:
   `/opt/LM-Studio/resources/app/.webpack/renderer/main_window.js`.

El parche es **solo cosmético**: el identificador interno no cambia, así que las
peticiones al backend siguen usando el id real del modelo.

## Uso

```bash
# 1) dejar el plugin en una ruta válida y parchear el renderer
sudo python3 apply_label.py \
    --id openvino/qwen3-30b-a3b-instruct-2507-int4-ov \
    --label "OPENVINO - Qwen3-30B-A3B-Instruct-2507-int4-ov - 26.6 tok/s"

# 2) reiniciar LM Studio
pkill -9 -x lm-studio && /opt/LM-Studio/lm-studio &

# solo el parche (plugin ya renombrado)
sudo python3 apply_label.py --renderer-only --id ... --label "..."

# revertir el renderer al bundle original
sudo python3 apply_label.py --restore
```

El script es idempotente y hace backup del bundle en
`main_window.js.orig.bak`.

## Detalles que cuestan tiempo si no se saben

- El plugin debe estar en `plugins/<owner>/<name>` con `manifest.json`
  coherente (`owner`, `name`). Una carpeta plana no se escanea.
- Nombres con espacios/mayúsculas → el plugin se ignora silenciosamente y no
  hay sección "Your Generators" en el selector.
- `lms get <plugin>` y `lms clone` no sirven para esto: el plugin se instala y
  se edita a mano en `~/.lmstudio/extensions/plugins/`.
- Actualizar LM Studio sobrescribe `main_window.js` → volver a ejecutar
  `apply_label.py`. El renombrado del plugin en `~/.lmstudio` sí persiste.
- Los sitios parcheados: 4 variantes `children:<var>.identifier})` y el
  selector del sidebar/cabecera del chat.
- Verificación real de la UI sin adivinar: lanzar LM Studio con
  `--remote-debugging-port=9333` y leer el DOM por CDP
  (`Runtime.evaluate` sobre `document.body.innerText`). En Python, el websocket
  necesita `suppress_origin=True` o Chromium rechaza la conexión.

## Requisitos

- LM Studio instalado en `/opt/LM-Studio` (ajustable con `--renderer`).
- Linux + Wayland/X11; el relanzamiento headless necesita
  `WAYLAND_DISPLAY=wayland-0`, `XDG_RUNTIME_DIR=/run/user/1000`,
  `XDG_SESSION_TYPE=wayland`, `DISPLAY=:0`.

## Aviso

Parche no oficial sobre el bundle de una app propietaria (Electron). Se pierde
en cada actualización de LM Studio. Úsalo si te importa la legibilidad del
selector; no cambia nada del transporte ni del rendimiento.
