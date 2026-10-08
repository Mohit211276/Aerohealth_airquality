from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("locations", views.LocationViewSet, basename="location")
router.register("ground", views.GroundReadingViewSet, basename="ground")
router.register("satellite", views.SatelliteReadingViewSet, basename="satellite")
router.register("fires", views.FireHotspotViewSet, basename="fire")
router.register("grid", views.AQIGridPointViewSet, basename="grid")
router.register("validation", views.ValidationRecordViewSet, basename="validation")

urlpatterns = [
    path("aqi/", views.aqi_at_point, name="aqi-at-point"),
    path("", include(router.urls)),
]
