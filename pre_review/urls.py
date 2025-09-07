from django.urls import path
from . import views, auth_views, info_views

urlpatterns = [
    # Homepage and API Information
    path("", info_views.homepage, name="homepage"),
    path("api/info/", info_views.api_info, name="api_info"),
    path("health/", info_views.health_check, name="health_check"),
    
    # AI Processing endpoints
    path("pre_review/", views.pre_review, name="pre_review"),
    path("demo/", views.demo_pre_review, name="demo_pre_review"),
    
    # Authentication endpoints
    path("auth/register/", auth_views.register, name="register"),
    path("auth/login/", auth_views.login, name="login"),
    path("auth/logout/", auth_views.logout, name="logout"),
    path("auth/profile/", auth_views.profile, name="profile"),
]
