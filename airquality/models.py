from django.contrib.gis.db import models
from django.contrib.gis.geos import Point


def aqi_category(aqi):
    """Indian National AQI categories."""
    if aqi is None:
        return None
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Satisfactory"
    if aqi <= 200:
        return "Moderate"
    if aqi <= 300:
        return "Poor"
    if aqi <= 400:
        return "Very Poor"
    return "Severe"


class PointMixin(models.Model):
    """Keeps lat/lon (for the frontend) and a PostGIS point (for spatial queries) in sync."""
    lat = models.FloatField()
    lon = models.FloatField()
    point = models.PointField(geography=True, srid=4326, null=True, blank=True, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.point = Point(self.lon, self.lat, srid=4326)  # note: x=lon, y=lat
        super().save(*args, **kwargs)


class Location(PointMixin):
    name = models.CharField(max_length=200)
    state = models.CharField(max_length=100, blank=True)
    is_cpcb_station = models.BooleanField(default=False)
    external_id = models.CharField(max_length=100, blank=True, db_index=True,
                                   help_text="OpenAQ / CPCB station id")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.state})" if self.state else self.name


class GroundReading(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="ground_readings")
    timestamp = models.DateTimeField(db_index=True)
    pm25 = models.FloatField(null=True, blank=True)
    pm10 = models.FloatField(null=True, blank=True)
    no2 = models.FloatField(null=True, blank=True)
    so2 = models.FloatField(null=True, blank=True)
    co = models.FloatField(null=True, blank=True)
    o3 = models.FloatField(null=True, blank=True)
    aqi = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=50, default="openaq")

    class Meta:
        ordering = ["-timestamp"]
        constraints = [models.UniqueConstraint(fields=["location", "timestamp"], name="uniq_ground_loc_ts")]

    @property
    def category(self):
        return aqi_category(self.aqi)

    def __str__(self):
        return f"{self.location} @ {self.timestamp:%Y-%m-%d %H:%M}"


class SatelliteReading(models.Model):
    class Source(models.TextChoices):
        TROPOMI = "tropomi", "TROPOMI"
        INSAT = "insat", "INSAT"

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="satellite_readings")
    timestamp = models.DateTimeField(db_index=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.TROPOMI)
    no2_column = models.FloatField(null=True, blank=True, help_text="mol/m2")
    so2_column = models.FloatField(null=True, blank=True, help_text="mol/m2")
    aerosol_index = models.FloatField(null=True, blank=True)
    qa_value = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["location", "-timestamp"])]

    def __str__(self):
        return f"{self.source} {self.location} @ {self.timestamp:%Y-%m-%d %H:%M}"


class FireHotspot(PointMixin):
    acq_datetime = models.DateTimeField(db_index=True)
    brightness = models.FloatField(null=True, blank=True)
    frp = models.FloatField(null=True, blank=True, help_text="Fire radiative power (MW)")
    confidence = models.CharField(max_length=20, blank=True)
    satellite = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["-acq_datetime"]

    def __str__(self):
        return f"Fire {self.lat:.3f},{self.lon:.3f} @ {self.acq_datetime:%Y-%m-%d %H:%M}"


class AQIGridPoint(PointMixin):
    """Satellite-calibrated AQI estimate on a regular grid (output of the XGBoost model)."""
    timestamp = models.DateTimeField(db_index=True)
    aqi = models.FloatField()
    pm25_estimate = models.FloatField(null=True, blank=True)
    model_version = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["-timestamp"])]

    @property
    def category(self):
        return aqi_category(self.aqi)


class ValidationRecord(models.Model):
    """Model prediction vs CPCB ground truth at a station."""
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="validations")
    timestamp = models.DateTimeField(db_index=True)
    predicted_aqi = models.FloatField()
    actual_aqi = models.FloatField()
    abs_error = models.FloatField(editable=False)
    model_version = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        self.abs_error = abs(self.predicted_aqi - self.actual_aqi)
        super().save(*args, **kwargs)
