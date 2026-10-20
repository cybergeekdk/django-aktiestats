from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/quote/<str:symbol>/", views.quote_api, name="quote_api"),
    path("api/search/", views.search_api, name="search_api"),
    path("api/holdings/", views.holdings_api, name="holdings_api"),
    path("api/holdings/<int:pk>/", views.holding_detail_api, name="holding_detail_api"),
    path("api/import/", views.import_api, name="import_api"),
    path("api/history/", views.history_api, name="history_api"),
]
