from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/quotes/", views.quotes_api, name="quotes_api"),
    path("api/quote/<str:symbol>/", views.quote_api, name="quote_api"),
]
