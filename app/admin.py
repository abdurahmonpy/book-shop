from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Author, Book, Customer, Sale, SaleItem, Debt, DebtItem, DebtPayment


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name',)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'barcode', 'category', 'author', 'price', 'stock_quantity', 'shelf_location', 'barcode_preview', 'qr_preview', 'is_active')
    list_filter = ('category', 'author', 'language', 'is_active')
    search_fields = ('title', 'barcode', 'isbn', 'author__name', 'publisher')
    readonly_fields = ('barcode_preview', 'qr_preview', 'created_at', 'updated_at')

    def barcode_preview(self, obj):
        if obj.barcode_image:
            return format_html('<img src="{}" style="height: 40px;" />', obj.barcode_image.url)
        return "-"
    barcode_preview.short_description = "Shtrix-kod"

    def qr_preview(self, obj):
        if obj.qr_code_image:
            return format_html('<img src="{}" style="height: 40px;" />', obj.qr_code_image.url)
        return "-"
    qr_preview.short_description = "QR-kod"


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'passport_id', 'display_total_debt', 'active_debts_count', 'created_at')
    search_fields = ('first_name', 'last_name', 'phone', 'passport_id')

    def display_total_debt(self, obj):
        debt = obj.total_active_debt
        color = 'red' if debt > 0 else 'green'
        return format_html('<span style="color: {}; font-weight: bold;">{:,.2f} so\'m</span>', color, debt)
    display_total_debt.short_description = "Faol qarzi"


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ('total_price',)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('sale_number', 'customer', 'cashier', 'payment_method', 'final_amount', 'status', 'created_at')
    list_filter = ('payment_method', 'status', 'created_at')
    search_fields = ('sale_number', 'customer__first_name', 'customer__phone')
    inlines = [SaleItemInline]


class DebtItemInline(admin.TabularInline):
    model = DebtItem
    extra = 0
    readonly_fields = ('total_price',)


class DebtPaymentInline(admin.TabularInline):
    model = DebtPayment
    extra = 0
    readonly_fields = ('payment_date',)


@admin.register(Debt)
class DebtAdmin(admin.ModelAdmin):
    list_display = ('debt_number', 'customer', 'borrow_type', 'total_debt_amount', 'paid_amount', 'remaining_debt_amount', 'due_date', 'status', 'check_overdue')
    list_filter = ('status', 'borrow_type', 'borrowed_at', 'due_date')
    search_fields = ('debt_number', 'customer__first_name', 'customer__phone')
    inlines = [DebtItemInline, DebtPaymentInline]

    def check_overdue(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color: red; font-weight: bold;">Muddati o\'tgan!</span>')
        return "Vaqtida"
    check_overdue.short_description = "Muddat holati"


@admin.register(DebtPayment)
class DebtPaymentAdmin(admin.ModelAdmin):
    list_display = ('debt', 'amount', 'payment_method', 'payment_date', 'received_by')
    list_filter = ('payment_method', 'payment_date')
    search_fields = ('debt__debt_number', 'debt__customer__first_name')
