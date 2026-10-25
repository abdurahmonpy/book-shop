import json
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Category, Author, Book, Customer,
    Sale, SaleItem, Debt, DebtItem, DebtPayment
)


class CategorySerializer(serializers.ModelSerializer):
    books_count = serializers.IntegerField(source='books.count', read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'books_count', 'created_at']


class AuthorSerializer(serializers.ModelSerializer):
    books_count = serializers.IntegerField(source='books.count', read_only=True)

    class Meta:
        model = Author
        fields = ['id', 'name', 'bio', 'books_count', 'created_at']


class BookListSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Book
        fields = [
            'id', 'title', 'author', 'author_name', 'category', 'category_name',
            'isbn', 'barcode', 'price', 'cost_price', 'stock_quantity', 'is_in_stock',
            'shelf_location', 'publisher', 'published_year', 'language',
            'barcode_image', 'qr_code_image', 'cover_image', 'is_active', 'created_at'
        ]


from drf_spectacular.utils import extend_schema_field


class BookBorrowerInfoSerializer(serializers.Serializer):
    debt_number = serializers.CharField()
    debt_id = serializers.IntegerField()
    customer_id = serializers.IntegerField()
    customer_name = serializers.CharField()
    customer_phone = serializers.CharField()
    borrow_type = serializers.CharField()
    quantity = serializers.IntegerField()
    borrowed_at = serializers.DateTimeField()
    due_date = serializers.DateTimeField()
    status = serializers.CharField()
    is_overdue = serializers.BooleanField()


class BookDetailSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    author_id = serializers.PrimaryKeyRelatedField(
        queryset=Author.objects.all(), source='author', write_only=True, required=False, allow_null=True
    )
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True, required=False, allow_null=True
    )
    is_in_stock = serializers.BooleanField(read_only=True)
    active_borrowers = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = [
            'id', 'title', 'author', 'author_id', 'category', 'category_id',
            'isbn', 'barcode', 'price', 'cost_price', 'stock_quantity', 'is_in_stock',
            'publisher', 'published_year', 'pages', 'language', 'shelf_location',
            'description', 'cover_image', 'barcode_image', 'qr_code_image',
            'is_active', 'active_borrowers', 'created_at', 'updated_at'
        ]

    @extend_schema_field(BookBorrowerInfoSerializer(many=True))
    def get_active_borrowers(self, obj):
        active_items = DebtItem.objects.filter(
            book=obj,
            debt__status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
            is_returned=False
        ).select_related('debt', 'debt__customer')

        borrowers = []
        for item in active_items:
            debt = item.debt
            borrowers.append({
                "debt_number": debt.debt_number,
                "debt_id": debt.id,
                "customer_id": debt.customer.id,
                "customer_name": debt.customer.full_name,
                "customer_phone": debt.customer.phone,
                "borrow_type": debt.get_borrow_type_display(),
                "quantity": item.quantity,
                "borrowed_at": debt.borrowed_at,
                "due_date": debt.due_date,
                "status": debt.status,
                "is_overdue": debt.is_overdue,
            })
        return borrowers


class CustomerSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    total_active_debt = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    active_debts_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id', 'first_name', 'last_name', 'full_name', 'phone', 'passport_id',
            'address', 'notes', 'total_active_debt', 'active_debts_count', 'created_at'
        ]


class SaleItemSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source='book.title', read_only=True)
    book_barcode = serializers.CharField(source='book.barcode', read_only=True)

    class Meta:
        model = SaleItem
        fields = ['id', 'book', 'book_title', 'book_barcode', 'quantity', 'unit_price', 'total_price']


class SaleListDetailSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    cashier_username = serializers.CharField(source='cashier.username', read_only=True)
    items = SaleItemSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'sale_number', 'customer', 'cashier_username', 'payment_method',
            'total_amount', 'discount_amount', 'final_amount', 'paid_amount',
            'status', 'notes', 'items', 'created_at'
        ]


class SaleItemCreateInputSerializer(serializers.Serializer):
    book_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)


class SaleCreateSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField(required=False, allow_null=True)
    payment_method = serializers.ChoiceField(choices=Sale.PAYMENT_METHODS, default='CASH')
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    items = SaleItemCreateInputSerializer(many=True)

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("Kamida bitta kitob tanlanishi shart.")
        return items

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        customer_id = validated_data.get('customer_id')
        discount_amount = validated_data.get('discount_amount', Decimal('0.00'))
        payment_method = validated_data.get('payment_method', 'CASH')
        notes = validated_data.get('notes', '')
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None

        customer = None
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                raise serializers.ValidationError({"customer_id": "Mijoz topilmadi."})

        # Tekshiruv va umumiy summani hisoblash
        total_amount = Decimal('0.00')
        books_to_update = []

        with transaction.atomic():
            for item_in in items_data:
                book_id = item_in['book_id']
                qty = item_in['quantity']
                try:
                    book = Book.objects.select_for_update().get(id=book_id, is_active=True)
                except Book.DoesNotExist:
                    raise serializers.ValidationError({"items": f"ID={book_id} bo'lgan faol kitob topilmadi."})

                if book.stock_quantity < qty:
                    raise serializers.ValidationError({
                        "items": f"'{book.title}' kitobidan omborda yetarli emas! Mavjud: {book.stock_quantity} dona, so'ralgan: {qty} dona."
                    })

                unit_price = item_in.get('unit_price')
                if unit_price is None:
                    unit_price = book.price

                line_total = Decimal(str(unit_price)) * Decimal(str(qty))
                total_amount += line_total
                books_to_update.append((book, qty, unit_price, line_total))

            final_amount = max(Decimal('0.00'), total_amount - discount_amount)
            paid_amount = validated_data.get('paid_amount', final_amount)

            sale = Sale.objects.create(
                sale_number=Sale.generate_sale_number(),
                customer=customer,
                cashier=user,
                payment_method=payment_method,
                total_amount=total_amount,
                discount_amount=discount_amount,
                final_amount=final_amount,
                paid_amount=paid_amount,
                status='COMPLETED',
                notes=notes
            )

            for book, qty, unit_price, line_total in books_to_update:
                SaleItem.objects.create(
                    sale=sale,
                    book=book,
                    quantity=qty,
                    unit_price=unit_price,
                    total_price=line_total
                )
                # Ombordagi qoldiqni kamaytirish
                book.stock_quantity -= qty
                book.save(update_fields=['stock_quantity'])

            # Agar to'lov turi DEBT (nasiya) bo'lsa yoki to'langan summa kam bo'lsa, avtomatik qarzga yozish
            if payment_method == 'DEBT' or paid_amount < final_amount:
                if not customer:
                    raise serializers.ValidationError({
                        "customer_id": "Nasiya / qarzga kitob berish uchun mijoz tanlanishi shart!"
                    })
                remaining = final_amount - paid_amount
                if remaining > Decimal('0.00'):
                    due_date = timezone.now() + timezone.timedelta(days=30)
                    debt = Debt.objects.create(
                        debt_number=Debt.generate_debt_number(),
                        customer=customer,
                        sale=sale,
                        borrow_type='PURCHASE_DEBT',
                        total_debt_amount=remaining,
                        paid_amount=Decimal('0.00'),
                        remaining_debt_amount=remaining,
                        due_date=due_date,
                        status='PENDING',
                        notes=f"Sotuv #{sale.sale_number} dan qolgan qarz",
                        created_by=user
                    )
                    for book, qty, unit_price, line_total in books_to_update:
                        DebtItem.objects.create(
                            debt=debt,
                            book=book,
                            quantity=qty,
                            unit_price=unit_price,
                            total_price=line_total
                        )

            return sale


class DebtItemSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source='book.title', read_only=True)
    book_barcode = serializers.CharField(source='book.barcode', read_only=True)

    class Meta:
        model = DebtItem
        fields = ['id', 'book', 'book_title', 'book_barcode', 'quantity', 'unit_price', 'total_price', 'is_returned']


class DebtPaymentSerializer(serializers.ModelSerializer):
    received_by_username = serializers.CharField(source='received_by.username', read_only=True)

    class Meta:
        model = DebtPayment
        fields = ['id', 'debt', 'amount', 'payment_method', 'payment_date', 'received_by_username', 'notes']


class DebtListDetailSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    items = DebtItemSerializer(many=True, read_only=True)
    payments = DebtPaymentSerializer(many=True, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    borrow_type_display = serializers.CharField(source='get_borrow_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Debt
        fields = [
            'id', 'debt_number', 'customer', 'sale', 'borrow_type', 'borrow_type_display',
            'total_debt_amount', 'paid_amount', 'remaining_debt_amount',
            'borrowed_at', 'due_date', 'returned_at', 'status', 'status_display',
            'is_overdue', 'notes', 'items', 'payments', 'created_at', 'updated_at'
        ]


class DebtCreateItemInputSerializer(serializers.Serializer):
    book_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)


class DebtCreateSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    borrow_type = serializers.ChoiceField(choices=Debt.BORROW_TYPES, default='PURCHASE_DEBT')
    due_date = serializers.DateTimeField()
    initial_payment = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    payment_method = serializers.ChoiceField(choices=DebtPayment.PAYMENT_METHODS, default='CASH')
    notes = serializers.CharField(required=False, allow_blank=True)
    items = DebtCreateItemInputSerializer(many=True)

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("Kamida bitta kitob kiritilishi shart.")
        return items

    def create(self, validated_data):
        customer_id = validated_data['customer_id']
        borrow_type = validated_data.get('borrow_type', 'PURCHASE_DEBT')
        due_date = validated_data['due_date']
        initial_payment = validated_data.get('initial_payment', Decimal('0.00'))
        payment_method = validated_data.get('payment_method', 'CASH')
        notes = validated_data.get('notes', '')
        items_data = validated_data['items']

        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            raise serializers.ValidationError({"customer_id": "Mijoz topilmadi."})

        with transaction.atomic():
            total_debt_amount = Decimal('0.00')
            items_to_create = []

            for item_in in items_data:
                book_id = item_in['book_id']
                qty = item_in['quantity']

                try:
                    book = Book.objects.select_for_update().get(id=book_id, is_active=True)
                except Book.DoesNotExist:
                    raise serializers.ValidationError({"items": f"ID={book_id} bo'lgan kitob topilmadi."})

                if book.stock_quantity < qty:
                    raise serializers.ValidationError({
                        "items": f"'{book.title}' kitobidan omborda yetarli emas! Omborda: {book.stock_quantity} dona, so'ralgan: {qty} dona."
                    })

                unit_price = item_in.get('unit_price')
                if unit_price is None:
                    unit_price = book.price

                line_total = Decimal(str(unit_price)) * Decimal(str(qty))
                total_debt_amount += line_total
                items_to_create.append((book, qty, unit_price, line_total))

            remaining_debt = max(Decimal('0.00'), total_debt_amount - initial_payment)
            status = 'PENDING'
            if remaining_debt == Decimal('0.00'):
                status = 'PAID'
            elif initial_payment > Decimal('0.00'):
                status = 'PARTIAL'

            debt = Debt.objects.create(
                debt_number=Debt.generate_debt_number(),
                customer=customer,
                borrow_type=borrow_type,
                total_debt_amount=total_debt_amount,
                paid_amount=initial_payment,
                remaining_debt_amount=remaining_debt,
                due_date=due_date,
                status=status,
                notes=notes,
                created_by=user
            )

            for book, qty, unit_price, line_total in items_to_create:
                DebtItem.objects.create(
                    debt=debt,
                    book=book,
                    quantity=qty,
                    unit_price=unit_price,
                    total_price=line_total,
                    is_returned=False
                )
                # Ombordan kamaytirish
                book.stock_quantity -= qty
                book.save(update_fields=['stock_quantity'])

            # Dastlabki to'lov qilingan bo'lsa, to'lov tarixiga yozish
            if initial_payment > Decimal('0.00'):
                DebtPayment.objects.create(
                    debt=debt,
                    amount=initial_payment,
                    payment_method=payment_method,
                    received_by=user,
                    notes="Qarz olish chog'idagi dastlabki to'lov"
                )

            return debt


class DebtPayActionSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    payment_method = serializers.ChoiceField(choices=DebtPayment.PAYMENT_METHODS, default='CASH')
    notes = serializers.CharField(required=False, allow_blank=True)


class ScanQuerySerializer(serializers.Serializer):
    code = serializers.CharField(
        required=True,
        help_text="Shtrix-kod raqami (masalan 9789943123456), ISBN yoki QR-kod matni/JSON"
    )


class ScanResponseStockStatusSerializer(serializers.Serializer):
    in_stock = serializers.BooleanField()
    quantity = serializers.IntegerField()
    badge = serializers.CharField()
    message = serializers.CharField()
    shelf_location = serializers.CharField()


class ScanResponseAnalyticsSerializer(serializers.Serializer):
    total_sold_count = serializers.IntegerField()
    total_sold_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    active_borrowed_count = serializers.IntegerField()


class ScanResponseSerializer(serializers.Serializer):
    found = serializers.BooleanField()
    scanned_code = serializers.CharField()
    matched_by = serializers.CharField()
    book = BookDetailSerializer()
    stock_status = ScanResponseStockStatusSerializer()
    analytics = ScanResponseAnalyticsSerializer()


class DashboardInventoryStatsSerializer(serializers.Serializer):
    total_book_titles = serializers.IntegerField()
    total_physical_stock = serializers.IntegerField()
    total_inventory_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    out_of_stock_count = serializers.IntegerField()
    low_stock_count = serializers.IntegerField()


class DashboardCustomersStatsSerializer(serializers.Serializer):
    total_customers = serializers.IntegerField()
    debtors_count = serializers.IntegerField()


class DashboardDebtsStatsSerializer(serializers.Serializer):
    active_debts_count = serializers.IntegerField()
    total_active_debt_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    overdue_debts_count = serializers.IntegerField()
    overdue_debt_amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class DashboardSalesStatsSerializer(serializers.Serializer):
    today_sales_count = serializers.IntegerField()
    today_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    month_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)


class DashboardStatsResponseSerializer(serializers.Serializer):
    inventory = DashboardInventoryStatsSerializer()
    customers = DashboardCustomersStatsSerializer()
    debts = DashboardDebtsStatsSerializer()
    sales = DashboardSalesStatsSerializer()

