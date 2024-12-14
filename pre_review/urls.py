from django.urls import path
from . import views

urlpatterns = [
    path("pre_review/", views.pre_review, name="pre_review"),
]
