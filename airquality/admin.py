from django.contrib.gis import admin

from .models import (AQIGridPoint, FireHotspot, GroundReading, Location,
                     SatelliteReading, ValidationRecord)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "is_cpcb_station", "lat", "lon")
    list_filter = ("is_cpcb_station", "state")
    search_fields = ("name", "external_id")


@admin.register(GroundReading)
class GroundReadingAdmin(admin.ModelAdmin):
    list_display = ("location", "timestamp", "pm25", "pm10", "aqi")
    list_filter = ("source",)
    date_hierarchy = "timestamp"
    raw_id_fields = ("location",)


@admin.register(SatelliteReading)
class SatelliteReadingAdmin(admin.ModelAdmin):
    list_display = ("location", "timestamp", "source", "no2_column", "so2_column")
    list_filter = ("source",)
    raw_id_fields = ("location",)


@admin.register(FireHotspot)
class FireHotspotAdmin(admin.ModelAdmin):
    list_display = ("lat", "lon", "acq_datetime", "frp", "confidence")
    date_hierarchy = "acq_datetime"


@admin.register(AQIGridPoint)
class AQIGridPointAdmin(admin.ModelAdmin):
    list_display = ("lat", "lon", "timestamp", "aqi", "model_version")


@admin.register(ValidationRecord)
class ValidationRecordAdmin(admin.ModelAdmin):
    list_display = ("location", "timestamp", "predicted_aqi", "actual_aqi", "abs_error")
    raw_id_fields = ("location",)
