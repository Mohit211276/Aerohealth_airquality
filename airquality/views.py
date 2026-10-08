import math
from datetime import timedelta

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.measure import D
from django.db.models import Avg, F
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .models import (AQIGridPoint, FireHotspot, GroundReading, Location,
                     SatelliteReading, ValidationRecord, aqi_category)
from .serializers import (AQIGridPointSerializer, FireHotspotSerializer,
                          GroundReadingSerializer, LocationSerializer,
                          SatelliteReadingSerializer, ValidationRecordSerializer)

GROUND_RADIUS_KM = 10
GRID_RADIUS_KM = 25


def _latlon(request):
    try:
        lat, lon = float(request.query_params["lat"]), float(request.query_params["lon"])
    except (KeyError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return Point(lon, lat, srid=4326)


def _bbox(request):
    """?bbox=min_lon,min_lat,max_lon,max_lat"""
    raw = request.query_params.get("bbox")
    if not raw:
        return None
    try:
        x1, y1, x2, y2 = (float(v) for v in raw.split(","))
    except ValueError:
        return None
    return Polygon.from_bbox((x1, y1, x2, y2))


def _since(request, param="since"):
    raw = request.query_params.get(param)
    return parse_datetime(raw) if raw else None


class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LocationSerializer

    def get_queryset(self):
        qs = Location.objects.all()
        p = self.request.query_params
        if p.get("state"):
            qs = qs.filter(state__iexact=p["state"])
        if p.get("cpcb") in ("1", "true"):
            qs = qs.filter(is_cpcb_station=True)
        if p.get("q"):
            qs = qs.filter(name__icontains=p["q"])
        return qs

    @action(detail=False)
    def nearest(self, request):
        """/locations/nearest/?lat=..&lon=..&n=5"""
        pt = _latlon(request)
        if pt is None:
            return Response({"error": "valid lat and lon required"}, status=400)
        n = min(int(request.query_params.get("n", 5)), 25)
        qs = (Location.objects.filter(point__isnull=False)
              .annotate(distance=Distance("point", pt)).order_by("distance")[:n])
        return Response(self.get_serializer(qs, many=True).data)


class GroundReadingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = GroundReadingSerializer

    def get_queryset(self):
        qs = GroundReading.objects.select_related("location")
        p = self.request.query_params
        if p.get("location"):
            qs = qs.filter(location_id=p["location"])
        since = _since(self.request)
        if since:
            qs = qs.filter(timestamp__gte=since)
        return qs

    @action(detail=False)
    def latest(self, request):
        """Most recent reading per station (Postgres DISTINCT ON)."""
        qs = (GroundReading.objects.select_related("location")
              .order_by("location_id", "-timestamp").distinct("location_id"))
        return Response(self.get_serializer(qs, many=True).data)


class SatelliteReadingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SatelliteReadingSerializer

    def get_queryset(self):
        qs = SatelliteReading.objects.all()
        p = self.request.query_params
        if p.get("location"):
            qs = qs.filter(location_id=p["location"])
        if p.get("source"):
            qs = qs.filter(source=p["source"])
        return qs


class FireHotspotViewSet(viewsets.ReadOnlyModelViewSet):
    """/fires/?bbox=..&hours=48&min_frp=5 or ?lat=..&lon=..&radius_km=200"""
    serializer_class = FireHotspotSerializer

    def get_queryset(self):
        qs = FireHotspot.objects.all()
        p = self.request.query_params
        hours = int(p.get("hours", 48))
        qs = qs.filter(acq_datetime__gte=timezone.now() - timedelta(hours=hours))
        if p.get("min_frp"):
            qs = qs.filter(frp__gte=float(p["min_frp"]))
        box = _bbox(self.request)
        if box:
            qs = qs.filter(point__intersects=box)
        pt = _latlon(self.request)
        if pt:
            qs = qs.filter(point__dwithin=(pt, D(km=float(p.get("radius_km", 100)))))
        return qs[:5000]


class AQIGridPointViewSet(viewsets.ReadOnlyModelViewSet):
    """/grid/?bbox=..  returns the latest snapshot inside the box (for the map layer)."""
    serializer_class = AQIGridPointSerializer

    def get_queryset(self):
        latest = AQIGridPoint.objects.order_by("-timestamp").values_list("timestamp", flat=True).first()
        qs = AQIGridPoint.objects.filter(timestamp=latest) if latest else AQIGridPoint.objects.none()
        box = _bbox(self.request)
        if box:
            qs = qs.filter(point__intersects=box)
        return qs[:10000]


class ValidationRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ValidationRecord.objects.select_related("location")
    serializer_class = ValidationRecordSerializer

    @action(detail=False)
    def metrics(self, request):
        """Overall MAE / RMSE of satellite-calibrated predictions vs CPCB. Great for the pitch."""
        qs = ValidationRecord.objects.all()
        if request.query_params.get("model_version"):
            qs = qs.filter(model_version=request.query_params["model_version"])
        agg = qs.aggregate(mae=Avg("abs_error"), mse=Avg(F("abs_error") * F("abs_error")))
        n = qs.count()
        return Response({
            "n": n,
            "mae": round(agg["mae"], 2) if agg["mae"] is not None else None,
            "rmse": round(math.sqrt(agg["mse"]), 2) if agg["mse"] is not None else None,
        })


@api_view(["GET"])
def aqi_at_point(request):
    """
    Core consumer endpoint: /api/aqi/?lat=..&lon=..
    Uses a real CPCB reading if a station is within 10 km, else the satellite-calibrated grid.
    """
    pt = _latlon(request)
    if pt is None:
        return Response({"error": "valid lat and lon required"}, status=400)

    stale = timezone.now() - timedelta(hours=6)
    station = (Location.objects.filter(is_cpcb_station=True, point__dwithin=(pt, D(km=GROUND_RADIUS_KM)))
               .annotate(distance=Distance("point", pt)).order_by("distance").first())
    if station:
        reading = station.ground_readings.filter(timestamp__gte=stale, aqi__isnull=False).first()
        if reading:
            return Response({
                "aqi": round(reading.aqi), "category": aqi_category(reading.aqi),
                "source": "cpcb_station", "station": station.name,
                "distance_km": round(station.distance.m / 1000, 1),
                "pm25": reading.pm25, "pm10": reading.pm10, "timestamp": reading.timestamp,
            })

    near = AQIGridPoint.objects.filter(point__dwithin=(pt, D(km=GRID_RADIUS_KM)))
    latest_ts = near.order_by("-timestamp").values_list("timestamp", flat=True).first()
    if latest_ts:
        g = (near.filter(timestamp=latest_ts).annotate(distance=Distance("point", pt))
             .order_by("distance").first())
        return Response({
            "aqi": round(g.aqi), "category": aqi_category(g.aqi),
            "source": "satellite_model", "distance_km": round(g.distance.m / 1000, 1),
            "pm25": g.pm25_estimate, "timestamp": g.timestamp, "model_version": g.model_version,
        })
    return Response({"error": "no data available for this location"}, status=404)
