# Moderación automática de reseñas (Unicomer) - Flask (localhost) v3

✅ Cambios:
- Se agrega columna **Correlativo** (1..N) al inicio de la salida.
- Se elimina columna vacía típica (col_0 / NaN) si venía por A1 vacío.
- La salida evita mostrar 'nan' (se reemplaza por vacío).
- Frontend más profesional (rojo/amarillo inspirados en La Curacao).

## Ejecutar (Windows)
Usa `start_windows.bat` o:
- crear/activar venv
- `pip install -r requirements.txt`
- `python app.py`

## Salida
Se guarda automáticamente en `outputs/`.


✅ v4: Se eliminaron columnas: factor_revision_humana, Clasificación IA, Explicación IA, Factor IA.

✅ v5: También se eliminó la columna: explicacion.

✅ v6: Eliminación robusta de columnas (explicacion, factor_revision_humana, Clasificación IA, Explicación IA, Factor IA), incluso si cambian acentos/espacios.

✅ v7: Se elimina columna con header 'nan'/'Unnamed' cuando está vacía y se muestra % por estado en la pantalla de resultados.

✅ v8: Tema actualizado a azul #00239C y botones amarillos #FFD200. Se mantiene línea amarilla.

✅ v9: Se quitó 'Localhost' del título y el botón 'Procesar otro archivo' ahora es azul.

✅ v10: Se forzó el botón 'Procesar otro archivo' a azul y se eliminó cualquier 'Localhost' residual.
