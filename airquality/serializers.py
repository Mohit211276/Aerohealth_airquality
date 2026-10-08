from rest_framework import serializers

from .models import (AQIGridPoint, FireHotspot, GroundReading, Location,
                     SatelliteReading, ValidationRecord, aqi_category)


class LocationSerializer(serializers.ModelSerializer):
    distance_km = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = ["id", "name", "state", "lat", "lon", "is_cpcb_station", "external_id", "distance_km"]

    def get_distance_km(self, obj):
        d = getattr(obj, "distance", None)
        return round(d.m / 1000, 2) if d is not None else None


class GroundReadingSerializer(serializers.ModelSerializer):
    category = serializers.ReadOnlyField()
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = GroundReading
        fields = ["id", "location", "location_name", "timestamp", "pm25", "pm10", "no2",
                  "so2", "co", "o3", "aqi", "category", "source"]


class SatelliteReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SatelliteReading
        fields = "__all__"


class FireHotspotSerializer(serializers.ModelSerializer):
    class Meta:
        model = FireHotspot
        fields = ["id", "lat", "lon", "acq_datetime", "brightness", "frp", "confidence", "satellite"]


class AQIGridPointSerializer(serializers.ModelSerializer):
    category = serializers.ReadOnlyField()

    class Meta:
        model = AQIGridPoint
        fields = ["id", "lat", "lon", "timestamp", "aqi", "category", "pm25_estimate", "model_version"]


class ValidationRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValidationRecord
        fields = "__all__"
        read_only_fields = ["abs_error"]
