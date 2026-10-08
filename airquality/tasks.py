"""Celery tasks. Register with beat in settings (CELERY_BEAT_SCHEDULE)."""
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import AQIGridPoint, FireHotspot, GroundReading, SatelliteReading, ValidationRecord


@shared_task
def purge_old_data(fire_days=14, grid_days=7):
    now = timezone.now()
    FireHotspot.objects.filter(acq_datetime__lt=now - timedelta(days=fire_days)).delete()
    AQIGridPoint.objects.filter(timestamp__lt=now - timedelta(days=grid_days)).delete()


@shared_task
def build_validation_records(hours=24, model_version=""):
    """
    Compare satellite-model predictions with CPCB readings at stations.
    Uses the nearest grid point (within 25 km, same timestamp) as the model prediction.
    """
    from django.contrib.gis.db.models.functions import Distance
    from django.contrib.gis.measure import D

    since = timezone.now() - timedelta(hours=hours)
    created = 0
    for r in GroundReading.objects.filter(timestamp__gte=since, aqi__isnull=False).select_related("location"):
        if ValidationRecord.objects.filter(location=r.location, timestamp=r.timestamp).exists():
            continue
        g = (AQIGridPoint.objects
             .filter(timestamp=r.timestamp, point__dwithin=(r.location.point, D(km=25)))
             .annotate(d=Distance("point", r.location.point)).order_by("d").first())
        if g:
            ValidationRecord.objects.create(location=r.location, timestamp=r.timestamp,
                                            predicted_aqi=g.aqi, actual_aqi=r.aqi,
                                            model_version=g.model_version)
            created += 1
    return created
