# Setup

1. Copy `airquality/` into `backend/` (or your project root) and add to settings.py:

   INSTALLED_APPS += ["django.contrib.gis", "rest_framework", "airquality"]
   DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"

2. Root urls.py:  path("api/", include("airquality.urls")),

3. System: PostGIS + GDAL/GEOS (e.g. `apt install gdal-bin libgdal-dev`), `pip install djangorestframework psycopg2-binary`
   Postgres: `CREATE EXTENSION postgis;`

4. python manage.py makemigrations airquality && python manage.py migrate

Endpoints (all under /api/):
  aqi/?lat=&lon=                      -> AQI for any point (CPCB if <10km else satellite model)
  locations/ , locations/nearest/?lat=&lon=&n=
  ground/?location=&since= , ground/latest/
  satellite/?location=&source=
  fires/?bbox=minlon,minlat,maxlon,maxlat&hours=48  or  ?lat=&lon=&radius_km=
  grid/?bbox=...                      -> latest model snapshot for map layer
  validation/ , validation/metrics/   -> MAE/RMSE vs CPCB
