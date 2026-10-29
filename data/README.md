# Localidades de Venezuela

Fuente: [GeoNames VE.zip](https://download.geonames.org/export/dump/VE.zip) y [admin1CodesASCII.txt](https://download.geonames.org/export/dump/admin1CodesASCII.txt), consultados el 28 de octubre de 2026. Licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Atribución: GeoNames, https://www.geonames.org/.

`locations.json` contiene 25 entidades de primer nivel del archivo fuente y 20.709 lugares poblados (clase P; códigos PPL, PPLA, PPLA2, PPLA3, PPLA4, PPLC). Los nombres de presentación Distrito Federal y Vargas se adaptaron a Distrito Capital y La Guaira; se conservan los identificadores del origen. No se importaron coordenadas. Las zonas se incorporan después de revisión.

Los datos se ofrecen tal como están; no son un catálogo administrativo oficial ni una garantía de cobertura o exactitud. Homónimos, denominaciones históricas, relaciones fronterizas y lugares ausentes requieren revisión humana antes del lanzamiento.

Importación: `python manage.py import_locations --dry-run`, luego `python manage.py import_locations`. Es idempotente y no elimina datos existentes. El formato JSON exige source, license, retrieved_at, states [{code,name}], localities [{code,name,state,aliases?}], zones [{code,name,locality}] opcional. Cada referencia debe pertenecer al mismo archivo. Los códigos de origen estables permiten actualizar nombres sin perder anuncios relacionados.
