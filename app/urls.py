from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, AuthorViewSet, BookViewSet,
    CustomerViewSet, SaleViewSet, DebtViewSet,
    ScanView, DashboardStatsView, migrate_database_view
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'authors', AuthorViewSet, basename='author')
router.register(r'books', BookViewSet, basename='book')
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'sales', SaleViewSet, basename='sale')
router.register(r'debts', DebtViewSet, basename='debt')

urlpatterns = [
    # Avtomatik migratsiya endpointi
    path('migrate/', migrate_database_view, name='migrate-db'),

    # Skaner qilish endpointi (GET va POST)
    path('scan/', ScanView.as_view(), name='scan'),

    # Statistika va hisobotlar endpointi
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),

    # Asosiy CRUD routerlari
    path('', include(router.urls)),
]
