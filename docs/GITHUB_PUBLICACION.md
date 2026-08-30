# Publicación sin consola: GitHub Desktop + GitHub web

Esta guía corresponde al repositorio que ya creaste:

**`LindaCatalina/jemeiwaa-wind-energy-climate-risk`**  
**URL:** `https://github.com/LindaCatalina/jemeiwaa-wind-energy-climate-risk`

No crees otro repositorio y no uses los bloques de comandos que aparecen en
“Quick setup”. Todo el primer envío puede hacerse con clics.

## Por qué usar GitHub Desktop

La versión pública contiene más de 100 archivos, incluyendo `.gitignore`, la
carpeta oculta `.github` y varios niveles de subcarpetas. La carga desde el
navegador admite como máximo 100 archivos por operación y facilita omitir esos
elementos. GitHub Desktop respeta automáticamente `.gitignore`, conserva la
estructura y permite revisar cada archivo antes de publicarlo.

Los NetCDF originales siguen en el computador, pero GitHub Desktop no debe
mostrarlos porque están excluidos.

## 1. Abrir GitHub Desktop

1. En la página vacía de tu repositorio, ubica el botón **Set up in Desktop**,
   visible en el recuadro **Quick setup**.
2. Haz clic en **Set up in Desktop**.
3. Si el navegador pregunta **¿Abrir GitHub Desktop?**, elige **Abrir**.
4. Si todavía no está instalado, descarga GitHub Desktop desde la opción que
   aparece, instálalo y ábrelo.
5. Inicia sesión con la cuenta **LindaCatalina**:
   - haz clic en **File → Options**;
   - entra en **Accounts**;
   - haz clic en **Sign in** junto a GitHub.com;
   - autoriza desde el navegador.
6. Si aparece una ventana que propone **clonar** el repositorio vacío, haz clic
   en **Cancel**. No necesitas otra copia: agregarás la carpeta ya preparada.

## 2. Agregar la carpeta local preparada

1. En GitHub Desktop, haz clic en **File → Add local repository**.
2. En la ventana, haz clic en **Choose…**.
3. Navega hasta:

   `E:\Climatologia\Trabajo_Final`

4. Selecciona la carpeta **Trabajo_Final**; no selecciones una subcarpeta.
5. Haz clic en **Select Folder**.
6. De vuelta en GitHub Desktop, haz clic en **Add repository**.

No elijas **Create a repository**: la carpeta ya contiene el repositorio local
preparado y el repositorio remoto ya existe en tu cuenta.

## 3. Revisar visualmente lo que se va a publicar

GitHub Desktop abrirá la pestaña **Changes**. Antes del primer commit:

La selección validada actualmente contiene **109 archivos públicos y 1,78 MiB**.
Si el contador cambia porque editaste algo después, revisa especialmente las
extensiones excluidas antes de continuar.

1. Confirma que todos los archivos tienen su casilla marcada.
2. Recorre la lista y comprueba que aparecen:
   - `.github/workflows/ci.yml`;
   - `.gitignore`, `.gitattributes` y `.dockerignore`;
   - `README.md` y `CITATION.cff`;
   - las carpetas descritas en [ARCHIVOS_PUBLICAR.md](ARCHIVOS_PUBLICAR.md).
3. Confirma que **no aparece ningún archivo terminado en**:
   - `.nc` o `.nc4`;
   - `.grib`, `.grb`, `.zip` o `.zarr`;
   - `.pyc`;
   - `.env` o `.cdsapirc`.
4. Confirma que no aparecen estas carpetas locales:
   - `.venv`;
   - `__pycache__`;
   - `bankability/private_data`;
   - `bankability/private_documents`;
   - `resultados_reproducibles/figuras_legacy_reparadas`.
5. En `CMIP6_Guajira`, deben aparecer códigos y CSV, pero **ningún NetCDF ni
   PNG legado**.
6. En `resultados_reproducibles`, deben publicarse exactamente cuatro figuras:
   - `legado/figuras/01_cambio_cf_percentiles.png`;
   - `sensibilidad_sin_recentrado/figuras/01_cambio_cf_percentiles.png`;
   - `sensibilidad_sin_recentrado/figuras/03_energia_p50_p90.png`;
   - `sensibilidad_sin_recentrado/figuras/04_cf_mensual_percentiles.png`.

Si aparece un NetCDF, **no hagas commit**. Desmarca su casilla y revisa que
`.gitignore` esté presente. La selección preparada actualmente no contiene
datos crudos, figuras dañadas ni duplicados exactos.

## 4. Crear el primer commit con clics

En la esquina inferior izquierda de GitHub Desktop encontrarás dos campos:

1. En **Summary (required)** escribe exactamente:

   `Publica análisis reproducible de riesgo climático eólico`

2. En **Description** pega:

   `Incluye código, tablas auditadas, percentiles P10/P50/P90, figuras verificadas y manifiestos de fuentes ERA5-Land y CMIP6. Excluye datos crudos y resultados redundantes.`

3. Haz clic en **Commit to main**.
4. Espera a que la pestaña **Changes** indique que ya no hay cambios pendientes.

Este commit sólo existe todavía en el computador. Falta conectarlo con el
repositorio vacío de GitHub.

## 5. Conectar el repositorio remoto sin consola

1. En la barra superior de GitHub Desktop, haz clic en **Repository**.
2. Elige **Repository settings…**.
3. Abre la pestaña **Remote**.
4. En **Primary remote repository**, pega exactamente:

   `https://github.com/LindaCatalina/jemeiwaa-wind-energy-climate-risk.git`

5. Haz clic en **Save**.
6. Cierra la ventana de configuración.

Si GitHub Desktop muestra **Publish repository**, no lo uses: ese botón intenta
crear un repositorio nuevo. Como el repositorio ya está creado, debes usar la URL
anterior como remoto.

## 6. Subir el trabajo

1. En la barra superior, busca el botón **Push origin**.
2. Haz clic una sola vez en **Push origin**.
3. Espera hasta que el botón cambie a **Fetch origin** y no haya una barra de progreso.
4. En GitHub Desktop, haz clic en **Repository → View on GitHub**.

La página ya debe mostrar las carpetas y, debajo, el README renderizado.

## 7. Revisar que el README se vea profesional

En la página principal del repositorio verifica, de arriba hacia abajo:

1. Título: **Riesgo climático del recurso eólico en La Guajira**.
2. Subtítulo y distintivos de Python, ERA5-Land, CMIP6 y reproducibilidad.
3. Conclusión ejecutiva antes de entrar en detalles técnicos.
4. Primera figura completamente visible.
5. Tabla con pregunta empresarial, evidencia y lectura correcta.
6. Resultados P10–P50–P90 y advertencia de que no son bancables.
7. Objetivo, metodología, flujo reproducible, habilidades y fuentes.
8. Todas las imágenes deben verse; no debe aparecer ningún icono de imagen rota.

No crees otro README en una subcarpeta para repetir la introducción. Los README
de `data`, `Datos_Era5` y `CMIP6_Guajira` sólo explican el contenido específico
de esas carpetas.

## 8. Completar la sección “About”

1. Regresa al inicio del repositorio.
2. A la derecha de **About**, haz clic en el icono de engranaje.
3. En **Description**, pega:

   `Análisis reproducible del riesgo climático para generación eólica en La Guajira con ERA5-Land, CMIP6, Python e incertidumbre P10/P50/P90.`

4. En **Website**, puedes pegar `https://lindacatalina.github.io`.
5. En **Topics**, agrega uno por uno:

   - `python`
   - `wind-energy`
   - `climate-risk`
   - `cmip6`
   - `era5`
   - `renewable-energy`
   - `xarray`
   - `data-visualization`
   - `reproducible-research`
   - `climate-data`

6. Deja marcada la opción **Releases**.
7. Haz clic en **Save changes**.

## 9. Añadir la imagen para compartir el proyecto

1. Haz clic en la pestaña **Settings** del repositorio.
2. En **General**, baja hasta **Social preview**.
3. Haz clic en **Edit → Upload an image**.
4. Busca en tu computador:

   `E:\Climatologia\Trabajo_Final\resultados_reproducibles\sensibilidad_sin_recentrado\figuras\01_cambio_cf_percentiles.png`

5. Selecciona la imagen y confirma.

La figura tiene fondo sólido, relación 2:1, resolución suficiente y pesa menos
de 1 MB. No necesitas copiarla a otra carpeta del repositorio.

## 10. Verificar Actions

1. Haz clic en la pestaña **Actions**.
2. En la columna izquierda selecciona **controles-portafolio**.
3. Abre la ejecución correspondiente al primer commit.
4. Espera la marca verde.
5. Comprueba que estén verdes los pasos de:
   - estructura y seguridad;
   - tablas y figuras;
   - exclusión de datos crudos;
   - pruebas livianas.

Si algo aparece rojo, no cargues archivos adicionales para “arreglarlo” sin
identificar primero qué control falló.

## 11. Crear la versión del portafolio

Cuando Actions esté verde:

1. En la página principal, haz clic en **Releases**.
2. Haz clic en **Create a new release**.
3. En **Choose a tag**, escribe `v1.0.0`.
4. Selecciona **Create new tag: v1.0.0 on publish**.
5. En **Release title**, escribe:

   `v1.0.0 — Análisis reproducible de riesgo climático eólico`

6. En la descripción pega:

   `Primera versión pública del estudio académico de generación eólica futura en La Guajira. Incluye ERA5-Land, ensamble CMIP6 de 12 modelos, corrección de sesgo, análisis P10/P50/P90, sensibilidad metodológica, figuras auditadas y reconstrucción de fuentes sin distribuir datos crudos.`

7. No adjuntes ZIP ni NetCDF.
8. Haz clic en **Publish release**.

## 12. Fijarlo en tu perfil

1. Haz clic en tu fotografía → **Your profile**.
2. En **Pinned**, haz clic en **Customize your pins**.
3. Busca `jemeiwaa-wind-energy-climate-risk`.
4. Márcalo y ubícalo entre tus primeros proyectos.
5. Haz clic en **Save pins**.

En el README de perfil puedes añadir:

```markdown
🔹 [Riesgo climático del recurso eólico](https://github.com/LindaCatalina/jemeiwaa-wind-energy-climate-risk) — ERA5-Land + CMIP6, corrección de sesgo, P10/P50/P90, sensibilidad metodológica y pipeline reproducible.
```

## 13. Licencia y coautoría

No agregues una licencia sin acordarla con Juan Camilo, porque el repositorio
reconoce dos autores. Si ambos autorizan MIT para el código:

1. Haz clic en **Add file → Create new file**.
2. Como nombre escribe `LICENSE`.
3. Haz clic en **Choose a license template**.
4. Selecciona **MIT License**.
5. Revisa año y autores.
6. Confirma con **Commit changes**.

Las licencias de ERA5-Land y de cada institución CMIP6 siguen siendo
independientes y están documentadas en `docs/DATOS.md` y en los manifiestos.

## 14. Actualizaciones futuras sin consola

Cada vez que cambies algo en VS Code:

1. Abre GitHub Desktop.
2. Revisa **Changes** archivo por archivo.
3. Escribe un resumen concreto, por ejemplo:
   `Aclara interpretación de percentiles intermodelo`.
4. Haz clic en **Commit to main**.
5. Haz clic en **Push origin**.
6. Abre **Actions** en GitHub y espera la marca verde.

No uses **Upload files** para actualizar una copia completa: GitHub Desktop
evita duplicados y conserva claramente el historial de cambios.
