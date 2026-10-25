import json
import urllib.request
from decimal import Decimal
from urllib.parse import urlparse, parse_qs
import html
import re


def fetch_isbn_online(isbn_candidate):
    """
    Xalqaro Google Books va OpenLibrary bazalaridan ISBN bo'yicha kitob qidirish.
    Bozordagi istalgan kitobni avtomatik aniqlash imkonini beradi.
    """
    clean_code = "".join(filter(str.isdigit, str(isbn_candidate)))
    if len(clean_code) < 8:
        return None

    # 1. Google Books Web Resolver (100% bepul, quota cheklovisiz, yuqori tezlik)
    try:
        url = f"https://books.google.com/books?vid=ISBN{clean_code}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        })
        with urllib.request.urlopen(req, timeout=5) as r:
            page = r.read().decode('utf-8', errors='ignore')
            title_m = re.search(r'<title>(.*?)</title>', page)
            img_m = re.search(r'og:image"\s+content="([^"]+)"', page)
            desc_m = re.search(r'name="description"\s+content="([^"]+)"', page)
            og_title_m = re.search(r'property="og:title"\s+content="([^"]+)"', page)

            raw_title = html.unescape(title_m.group(1)) if title_m else ''
            parts = raw_title.split(' - ')
            if og_title_m:
                title = html.unescape(og_title_m.group(1)).strip()
            elif len(parts) >= 3:
                title = ' - '.join(parts[:-2]).strip()
            else:
                title = parts[0].strip() if parts else "Nomsiz kitob"

            author = parts[-2].strip() if len(parts) >= 3 else "Noma'lum"
            cover = html.unescape(img_m.group(1)) if img_m else None
            if cover and cover.startswith('http://'):
                cover = 'https://' + cover[7:]
            desc = html.unescape(desc_m.group(1)).strip() if desc_m else ""

            if title and "Google Books" not in title and title != "Nomsiz kitob":
                return {
                    "title": title,
                    "author_name": author,
                    "category_name": "Badiiy adabiyot",
                    "publisher": "Xalqaro nashriyot",
                    "published_year": None,
                    "pages": None,
                    "description": desc,
                    "cover_url": cover,
                    "language": "O'zbekcha",
                    "isbn": clean_code,
                    "barcode": clean_code
                }
    except Exception:
        pass

    # 2. Google Books API
    for q_param in [f"isbn:{clean_code}", clean_code]:
        try:
            url = f"https://www.googleapis.com/books/v1/volumes?q={q_param}&maxResults=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get('totalItems', 0) > 0 and 'items' in data:
                    item = data['items'][0].get('volumeInfo', {})
                    authors = ", ".join(item.get('authors', [])) if item.get('authors') else "Noma'lum"
                    images = item.get('imageLinks', {})
                    cover = images.get('thumbnail') or images.get('smallThumbnail')
                    if cover and cover.startswith('http://'):
                        cover = 'https://' + cover[7:]
                    categories = item.get('categories', ['Badiiy adabiyot'])[0] if item.get('categories') else "Badiiy adabiyot"
                    year_str = str(item.get('publishedDate', ''))[:4]
                    return {
                        "title": item.get('title', "Nomsiz kitob"),
                        "author_name": authors,
                        "category_name": categories,
                        "publisher": item.get('publisher', ''),
                        "published_year": int(year_str) if year_str.isdigit() else None,
                        "pages": item.get('pageCount'),
                        "description": item.get('description', ''),
                        "cover_url": cover,
                        "language": item.get('language', "O'zbekcha"),
                        "isbn": clean_code,
                        "barcode": clean_code
                    }
        except Exception:
            pass

    # 3. Open Library API fallback
    try:
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{clean_code}&format=json&jscmd=data"
        req = urllib.request.Request(url, headers={'User-Agent': 'BookStoreApp/1.0 (admin@bookstore.uz)'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            key = f"ISBN:{clean_code}"
            if key in data:
                b = data[key]
                authors = ", ".join([a.get('name', '') for a in b.get('authors', [])]) if b.get('authors') else "Noma'lum"
                cover = b.get('cover', {}).get('medium') or b.get('cover', {}).get('large') or b.get('cover', {}).get('small')
                if cover and cover.startswith('http://'):
                    cover = 'https://' + cover[7:]
                pub = b.get('publishers', [{}])[0].get('name', '') if b.get('publishers') else ''
                year = str(b.get('publish_date', ''))[-4:]
                return {
                    "title": b.get('title', "Nomsiz kitob"),
                    "author_name": authors,
                    "category_name": "Badiiy adabiyot",
                    "publisher": pub,
                    "published_year": int(year) if year.isdigit() else None,
                    "pages": b.get('number_of_pages'),
                    "description": b.get('notes', '') or b.get('subtitle', ''),
                    "cover_url": cover,
                    "language": "O'zbekcha",
                    "isbn": clean_code,
                    "barcode": clean_code
                }
    except Exception:
        pass

    return None

from django.db import transaction
from django.db.models import Sum, Count, F, Q
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from .models import (
    Category, Author, Book, Customer,
    Sale, SaleItem, Debt, DebtItem, DebtPayment
)
from .serializers import (
    CategorySerializer, AuthorSerializer,
    BookListSerializer, BookDetailSerializer,
    CustomerSerializer,
    SaleListDetailSerializer, SaleCreateSerializer,
    DebtListDetailSerializer, DebtCreateSerializer,
    DebtPayActionSerializer, DebtPaymentSerializer,
    ScanQuerySerializer, ScanResponseSerializer,
    DashboardStatsResponseSerializer
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().annotate(book_count=Count('books')).order_by('name')
    serializer_class = CategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']


class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all().annotate(book_count=Count('books')).order_by('name')
    serializer_class = AuthorSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'bio']
    ordering_fields = ['name', 'created_at']


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.select_related('author', 'category').all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'author', 'language', 'is_active']
    search_fields = ['title', 'barcode', 'isbn', 'author__name', 'publisher', 'shelf_location']
    ordering_fields = ['id', 'title', 'price', 'stock_quantity', 'published_year', 'created_at']

    def get_serializer_class(self):
        if self.action in ['retrieve', 'create', 'update', 'partial_update']:
            return BookDetailSerializer
        return BookListSerializer

    @extend_schema(
        summary="Omborda kam qolgan kitoblar ro'yxati (<= 5 dona)",
        description="Omborda qoldig'i 5 tadan kam qolgan barcha faol kitoblarni qaytaradi."
    )
    @action(detail=False, methods=['get'], url_path='low-stock')
    def low_stock(self, request):
        threshold = int(request.query_params.get('threshold', 5))
        books = self.get_queryset().filter(is_active=True, stock_quantity__lte=threshold)
        serializer = BookListSerializer(books, many=True, context={'request': request})
        return Response({
            "threshold": threshold,
            "count": books.count(),
            "results": serializer.data
        })

    @extend_schema(
        summary="Shtrix-kod va QR-kodni qayta generatsiya qilish",
        description="Kitob uchun yangi shtrix-kod yoki QR-kod rasmlarini qayta yaratadi."
    )
    @action(detail=True, methods=['post'], url_path='regenerate-codes')
    def regenerate_codes(self, request, pk=None):
        book = self.get_object()
        book.generate_barcode_image()
        book.generate_qrcode_image()
        book.save(update_fields=['barcode_image', 'qr_code_image'])
        serializer = BookDetailSerializer(book, context={'request': request})
        return Response({
            "message": "Shtrix-kod va QR-kod tasvirlari muvaffaqiyatli yangilandi.",
            "book": serializer.data
        })

    @extend_schema(
        summary="Yangi kitobni tezkor qo'shish",
        description="Skaner qilingan yangi kitobni do'konga qo'shish, avtomatik kategoriya va muallif biriktiradi."
    )
    @action(detail=False, methods=['post'], url_path='quick-add')
    def quick_add(self, request):
        title = request.data.get('title')
        barcode = request.data.get('barcode')
        isbn = request.data.get('isbn') or barcode
        price = request.data.get('price', 50000)
        cost_price = request.data.get('cost_price', 0)
        stock_quantity = request.data.get('stock_quantity', 1)
        author_name = request.data.get('author_name', "Noma'lum")
        category_name = request.data.get('category_name', "Badiiy adabiyot")
        shelf_location = request.data.get('shelf_location', 'A-01')
        description = request.data.get('description', '')
        published_year = request.data.get('published_year')
        publisher = request.data.get('publisher', '')
        pages = request.data.get('pages')
        cover_url = request.data.get('cover_url')

        if not title or not barcode:
            return Response({"error": "Kitob nomi va shtrix-kodi kiritilishi shart."}, status=status.HTTP_400_BAD_REQUEST)

        category, _ = Category.objects.get_or_create(name=str(category_name).strip() if category_name else "Badiiy adabiyot")
        author, _ = Author.objects.get_or_create(name=str(author_name).strip() if author_name else "Noma'lum")

        book, created = Book.objects.get_or_create(
            barcode=str(barcode).strip(),
            defaults={
                'title': str(title).strip(),
                'author': author,
                'category': category,
                'isbn': str(isbn).strip(),
                'price': Decimal(str(price)),
                'cost_price': Decimal(str(cost_price)) if cost_price else Decimal('0.00'),
                'stock_quantity': int(stock_quantity),
                'shelf_location': str(shelf_location).strip() if shelf_location else 'A-01',
                'description': str(description).strip() if description else '',
                'publisher': str(publisher).strip() if publisher else '',
                'published_year': int(published_year) if published_year and str(published_year).isdigit() else None,
                'pages': int(pages) if pages and str(pages).isdigit() else None,
            }
        )
        if not created:
            book.stock_quantity += int(stock_quantity)
            book.price = Decimal(str(price))
            if cost_price:
                book.cost_price = Decimal(str(cost_price))
            if shelf_location:
                book.shelf_location = str(shelf_location).strip()
            book.save()

        # Agar cover_url mavjud bo'lsa va rasm hali yuklanmagan bo'lsa
        if cover_url and not book.cover_image:
            try:
                from django.core.files.base import ContentFile
                img_req = urllib.request.Request(cover_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(img_req, timeout=4) as img_resp:
                    content = img_resp.read()
                    if content:
                        clean_bc = "".join(filter(str.isalnum, str(barcode)))
                        book.cover_image.save(f"cover_{clean_bc}.jpg", ContentFile(content), save=True)
            except Exception as img_err:
                import logging
                logging.warning(f"Muqova rasmini yuklab olishda ogohlantirish: {img_err}")

        serializer = BookDetailSerializer(book, context={'request': request})
        return Response({
            "message": f"'{book.title}' kitobi muvaffaqiyatli do'kon omboriga qo'shildi!",
            "book": serializer.data
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'phone', 'passport_id']
    ordering_fields = ['id', 'first_name', 'created_at']

    @extend_schema(summary="Mijozning barcha qarzlari ro'yxati")
    @action(detail=True, methods=['get'], url_path='debts')
    def debts(self, request, pk=None):
        customer = self.get_object()
        debts = customer.debts.all().prefetch_related('items__book', 'payments')
        serializer = DebtListDetailSerializer(debts, many=True, context={'request': request})
        return Response({
            "customer": {
                "id": customer.id,
                "full_name": customer.full_name,
                "phone": customer.phone,
                "total_active_debt": customer.total_active_debt,
                "active_debts_count": customer.active_debts_count
            },
            "debts": serializer.data
        })

    @extend_schema(summary="Mijozning barcha xaridlari / sotuvlar tarixi")
    @action(detail=True, methods=['get'], url_path='sales')
    def sales(self, request, pk=None):
        customer = self.get_object()
        sales = customer.sales.all().prefetch_related('items__book')
        serializer = SaleListDetailSerializer(sales, many=True, context={'request': request})
        return Response(serializer.data)


class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.select_related('customer', 'cashier').prefetch_related('items__book').all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['payment_method', 'status', 'customer']
    search_fields = ['sale_number', 'customer__first_name', 'customer__last_name', 'customer__phone']
    ordering_fields = ['created_at', 'final_amount']

    def get_serializer_class(self):
        if self.action == 'create':
            return SaleCreateSerializer
        return SaleListDetailSerializer

    @extend_schema(
        summary="Yangi kitob sotish",
        description="Kitob sotib olish. Ombordagi kitob soni avtomatik kamayadi. Agar payment_method='DEBT' bo'lsa yoki pul yetarli to'lanmasa, avtomatik qarz daftari ochiladi.",
        request=SaleCreateSerializer,
        responses={201: SaleListDetailSerializer}
    )
    def create(self, request, *args, **kwargs):
        serializer = SaleCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        sale = serializer.save()
        output_serializer = SaleListDetailSerializer(sale, context={'request': request})
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class DebtViewSet(viewsets.ModelViewSet):
    queryset = Debt.objects.select_related('customer', 'sale', 'created_by').prefetch_related('items__book', 'payments').all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['borrow_type', 'status', 'customer']
    search_fields = ['debt_number', 'customer__first_name', 'customer__last_name', 'customer__phone']
    ordering_fields = ['borrowed_at', 'due_date', 'remaining_debt_amount']

    def get_serializer_class(self):
        if self.action == 'create':
            return DebtCreateSerializer
        return DebtListDetailSerializer

    @extend_schema(
        summary="Kitobni qarzga yoki nasiyaga berish",
        description="Mijozga kitobni qarzga yoki ijaraga berish. Ombordagi qoldiq kamayadi.",
        request=DebtCreateSerializer,
        responses={201: DebtListDetailSerializer}
    )
    def create(self, request, *args, **kwargs):
        serializer = DebtCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        debt = serializer.save()
        output_serializer = DebtListDetailSerializer(debt, context={'request': request})
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Qarz to'lovini qabul qilish",
        description="Qarz uchun qisman yoki to'liq to'lov kiritish. Qolgan summa 0 bo'lsa qarz avtomatik yopilgan holatiga o'tadi.",
        request=DebtPayActionSerializer,
        responses={200: DebtListDetailSerializer}
    )
    @action(detail=True, methods=['post'], url_path='pay')
    def pay_debt(self, request, pk=None):
        debt = self.get_object()
        serializer = DebtPayActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data['amount']
        payment_method = serializer.validated_data['payment_method']
        notes = serializer.validated_data.get('notes', '')
        user = request.user if request.user.is_authenticated else None

        if debt.remaining_debt_amount <= Decimal('0.00'):
            return Response(
                {"detail": "Ushbu qarz allaqachon to'liq to'langan!"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            payment = DebtPayment.objects.create(
                debt=debt,
                amount=amount,
                payment_method=payment_method,
                received_by=user,
                notes=notes
            )
            debt.paid_amount += amount
            debt.remaining_debt_amount = max(Decimal('0.00'), debt.total_debt_amount - debt.paid_amount)
            debt.update_debt_status()
            debt.save()

        output_serializer = DebtListDetailSerializer(debt, context={'request': request})
        return Response({
            "message": f"{amount:,.2f} so'm to'lov muvaffaqiyatli qabul qilindi.",
            "payment_id": payment.id,
            "debt": output_serializer.data
        })

    @extend_schema(
        summary="Ijaraga olingan kitobni qaytarish",
        description="Ijaraga / o'qishga olingan kitob qaytarilganda ombor qoldig'iga kitob qayta qo'shiladi va qarz holati 'RETURNED' qilinadi."
    )
    @action(detail=True, methods=['post'], url_path='return-book')
    def return_book(self, request, pk=None):
        debt = self.get_object()
        
        if debt.status == 'RETURNED':
            return Response(
                {"detail": "Kitob allaqachon qaytarilgan!"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            for item in debt.items.filter(is_returned=False):
                item.is_returned = True
                item.save(update_fields=['is_returned'])
                # Ombordagi qoldiqqa qaytarish
                book = item.book
                book.stock_quantity += item.quantity
                book.save(update_fields=['stock_quantity'])

            debt.returned_at = timezone.now()
            debt.status = 'RETURNED'
            debt.save()

        output_serializer = DebtListDetailSerializer(debt, context={'request': request})
        return Response({
            "message": "Kitoblar omborga qaytarildi va qarz hujjati yopildi.",
            "debt": output_serializer.data
        })

    @extend_schema(
        summary="Muddati o'tgan qarzdorlar ro'yxati",
        description="Qaytarish / to'lash muddati o'tib ketgan barcha faol qarzlarni ko'rsatadi."
    )
    @action(detail=False, methods=['get'], url_path='overdue')
    def overdue(self, request):
        now = timezone.now()
        overdue_debts = self.get_queryset().filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
            due_date__lt=now
        )
        # Update their status to OVERDUE if needed
        overdue_debts.update(status='OVERDUE')
        serializer = DebtListDetailSerializer(overdue_debts, many=True, context={'request': request})
        total_overdue = sum(d.remaining_debt_amount for d in overdue_debts)
        return Response({
            "count": overdue_debts.count(),
            "total_overdue_amount": total_overdue,
            "results": serializer.data
        })


class ScanView(APIView):
    """
    Shtrix-kod va QR-kodni skaner qilish API si.
    GET /api/scan/?code=<kod> yoki POST /api/scan/ { "code": "<kod>" }
    """

    @extend_schema(
        summary="Shtrix-kod yoki QR-kodni skaner qilish",
        description=(
            "Skaner qilingan shtrix-kod raqami, ISBN yoki "
            "QR-kod matni/JSON yuborilganda kitobning to'liq ma'lumotlari, ombordagi qoldig'i, "
            "polkadagi joylashuvi, hozirda bu kitob kimlarda qarzga berilganligi va sotish uchun "
            "tayyor takliflar qaytariladi."
        ),
        parameters=[
            OpenApiParameter(
                name='code',
                description="Skanerdan o'qilgan shtrix-kod, ISBN yoki QR-kod qiymati",
                required=True,
                type=str
            )
        ],
        responses={200: ScanResponseSerializer}
    )
    def get(self, request):
        code = request.query_params.get('code')
        if not code:
            return Response(
                {"error": "Skaner kodi kiritilmadi. Parametr: ?code=<shtrix_yoki_qr_kod>"},
                status=status.HTTP_400_BAD_REQUEST
            )
        return self._process_code(code, request)

    @extend_schema(
        summary="Shtrix-kod yoki QR-kodni skaner qilish POST",
        description="Skaner kodi JSON body orqali yuborilganda kitob ma'lumotlarini qaytaradi.",
        request=ScanQuerySerializer,
        responses={200: ScanResponseSerializer}
    )
    def post(self, request):
        serializer = ScanQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code']
        return self._process_code(code, request)

    def _process_code(self, raw_code, request):
        try:
            code = raw_code.strip()
            search_keys = [code]

            # 1. Agar kod JSON formatida bo'lsa (bizning QR-kodimiz JSON saqlaydi)
            if (code.startswith('{') and code.endswith('}')) or (code.startswith('%7B') and code.endswith('%7D')):
                try:
                    data = json.loads(code)
                    if isinstance(data, dict):
                        if 'barcode' in data and data['barcode']:
                            search_keys.append(str(data['barcode']).strip())
                        if 'isbn' in data and data['isbn']:
                            search_keys.append(str(data['isbn']).strip())
                        if 'id' in data and data['id']:
                            search_keys.append(str(data['id']).strip())
                        if 'book_id' in data and data['book_id']:
                            search_keys.append(str(data['book_id']).strip())
                except Exception:
                    pass

            # 2. Agar kod URL bo'lsa (masalan https://.../scan/?code=978...)
            if code.startswith('http://') or code.startswith('https://'):
                parsed = urlparse(code)
                qs = parse_qs(parsed.query)
                if 'code' in qs and qs['code']:
                    search_keys.append(qs['code'][0].strip())

            # Kitobni qidirish
            query = Q()
            for key in search_keys:
                query |= Q(barcode__iexact=key)
                query |= Q(isbn__iexact=key)
                if key.isdigit():
                    query |= Q(id=int(key))

            try:
                book = Book.objects.select_related('author', 'category').filter(query).first()
            except Exception as db_err:
                from django.core.management import call_command
                call_command('migrate', interactive=False)
                from seed_data import run_seed
                run_seed()
                book = Book.objects.select_related('author', 'category').filter(query).first()

            if not book:
                # Do'kon bazasida yo'q - internetdan (Google Books / Open Library) avtomatik qidirish
                online_book = fetch_isbn_online(code)
                if online_book:
                    # Agar auto_add parametrlari bo'lsa yoki auto_add=1 bo'lsa, avtomatik yaratish
                    req_data = getattr(request, 'data', {}) or {}
                    auto_add = (
                        request.query_params.get('auto_add') in ['1', 'true', 'True'] or
                        (isinstance(req_data, dict) and str(req_data.get('auto_add', '')).lower() in ['1', 'true'])
                    )

                    param_price = request.query_params.get('price') or (req_data.get('price') if isinstance(req_data, dict) else None) or '50000'
                    try:
                        default_price = Decimal(str(param_price))
                    except Exception:
                        default_price = Decimal('50000.00')

                    param_qty = request.query_params.get('quantity') or (req_data.get('quantity') if isinstance(req_data, dict) else None) or '10'
                    try:
                        default_qty = int(param_qty)
                    except Exception:
                        default_qty = 10

                    if auto_add:
                        category, _ = Category.objects.get_or_create(name=online_book['category_name'])
                        author, _ = Author.objects.get_or_create(name=online_book['author_name'])
                        new_book, _ = Book.objects.get_or_create(
                            barcode=online_book['barcode'],
                            defaults={
                                'title': online_book['title'],
                                'author': author,
                                'category': category,
                                'isbn': online_book['isbn'],
                                'price': default_price,
                                'cost_price': Decimal('35000.00'),
                                'stock_quantity': default_qty,
                                'shelf_location': 'A-01',
                                'description': online_book.get('description', ''),
                                'publisher': online_book.get('publisher', ''),
                                'published_year': online_book.get('published_year'),
                                'pages': online_book.get('pages'),
                            }
                        )
                        # Muqova rasmini avtomatik yuklab olish
                        if online_book.get('cover_url') and not new_book.cover_image:
                            try:
                                from django.core.files.base import ContentFile
                                img_req = urllib.request.Request(online_book['cover_url'], headers={'User-Agent': 'Mozilla/5.0'})
                                with urllib.request.urlopen(img_req, timeout=4) as img_resp:
                                    img_data = img_resp.read()
                                    if img_data:
                                        clean_bc = "".join(filter(str.isalnum, str(new_book.barcode)))
                                        new_book.cover_image.save(f"cover_{clean_bc}.jpg", ContentFile(img_data), save=True)
                            except Exception:
                                pass

                        detail_data = BookDetailSerializer(new_book, context={'request': request}).data
                        return Response({
                            "found": True,
                            "source": "INTERNET_AUTO_ADDED",
                            "auto_added": True,
                            "scanned_code": raw_code,
                            "matched_by": "ONLINE_ISBN",
                            "is_in_local_store": True,
                            "book": detail_data,
                            "stock_status": {
                                "in_stock": True,
                                "quantity": new_book.stock_quantity,
                                "badge": "AVAILABLE",
                                "message": f"Omborda yetarli: {new_book.stock_quantity} dona mavjud",
                                "shelf_location": new_book.shelf_location or "A-01"
                            },
                            "analytics": {
                                "total_sold_count": 0,
                                "total_sold_amount": Decimal("0.00"),
                                "active_borrowed_count": 0
                            },
                            "message": f"'{new_book.title}' kitobi internetdan topildi va avtomatik ravishda do'kon omboriga qo'shildi!"
                        }, status=status.HTTP_200_OK)

                    return Response({
                        "found": True,
                        "source": "GLOBAL_ISBN_DATABASE",
                        "scanned_code": raw_code,
                        "matched_by": "ONLINE_ISBN",
                        "is_in_local_store": False,
                        "online_book": online_book,
                        "message": f"'{online_book['title']}' kitobi internetdan topildi! Uni 1-klikda do'konga qo'shishingiz mumkin.",
                        "quick_add_payload": {
                            "title": online_book['title'],
                            "author_name": online_book['author_name'],
                            "category_name": online_book['category_name'],
                            "barcode": online_book['barcode'],
                            "isbn": online_book['isbn'],
                            "publisher": online_book.get('publisher', ''),
                            "description": online_book.get('description', ''),
                            "published_year": online_book.get('published_year'),
                            "pages": online_book.get('pages'),
                            "cover_url": online_book.get('cover_url'),
                            "price": int(default_price),
                            "cost_price": 35000,
                            "stock_quantity": default_qty,
                            "shelf_location": "A-01"
                        }
                    }, status=status.HTTP_200_OK)

                clean_bc = "".join(filter(str.isdigit, str(code))) or code
                return Response({
                    "found": False,
                    "scanned_code": raw_code,
                    "barcode": clean_bc,
                    "message": f"'{raw_code}' kodi bo'yicha do'kon bazasida kitob topilmadi.",
                    "hint": "Ushbu kitobni yangi kitob sifatida do'koningizga kiritishingiz mumkin.",
                    "allow_quick_create": True,
                    "new_book_template": {
                        "title": "",
                        "author_name": "",
                        "category_name": "Badiiy adabiyot",
                        "barcode": clean_bc,
                        "isbn": clean_bc,
                        "price": 50000,
                        "cost_price": 35000,
                        "stock_quantity": 5,
                        "shelf_location": "A-01",
                        "publisher": "",
                        "description": ""
                    }
                }, status=status.HTTP_404_NOT_FOUND)

            # Kitob topildi! To'liq ma'lumotlarni yig'amiz
            detail_data = BookDetailSerializer(book, context={'request': request}).data

            # Ombordagi holat
            if book.stock_quantity > 5:
                stock_badge = "AVAILABLE"
                stock_message = f"Omborda yetarli: {book.stock_quantity} dona mavjud"
            elif book.stock_quantity > 0:
                stock_badge = "LOW_STOCK"
                stock_message = f"Diqqat: Qoldiq kam, {book.stock_quantity} dona qoldi"
            else:
                stock_badge = "OUT_OF_STOCK"
                stock_message = "Tugagan: Omborda qolmagan"

            # Sotuvlar statistikasi
            total_sold = SaleItem.objects.filter(book=book, sale__status='COMPLETED').aggregate(
                qty=Sum('quantity'), total=Sum('total_price')
            )
            total_sold_count = total_sold['qty'] or 0
            total_sold_amount = total_sold['total'] or Decimal('0.00')

            # Hozirda qarzga olinganlar
            active_debts_count = DebtItem.objects.filter(
                book=book,
                debt__status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
                is_returned=False
            ).count()

            return Response({
                "found": True,
                "scanned_code": raw_code,
                "matched_by": "BARCODE" if book.barcode == code else "QR/ISBN",
                "book": detail_data,
                "stock_status": {
                    "in_stock": book.is_in_stock,
                    "quantity": book.stock_quantity,
                    "badge": stock_badge,
                    "message": stock_message,
                    "shelf_location": book.shelf_location or "Belgilanmagan"
                },
                "analytics": {
                    "total_sold_count": total_sold_count,
                    "total_sold_amount": total_sold_amount,
                    "active_borrowed_count": active_debts_count
                },
                "quick_sale_payload": {
                    "payment_method": "CASH",
                    "items": [{"book_id": book.id, "quantity": 1, "unit_price": float(book.price)}]
                },
                "quick_debt_payload": {
                    "borrow_type": "PURCHASE_DEBT",
                    "items": [{"book_id": book.id, "quantity": 1, "unit_price": float(book.price)}]
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            import logging
            logging.error(f"Error in ScanView: {e}", exc_info=True)
            return Response({
                "found": False,
                "scanned_code": raw_code,
                "message": f"Skanerlashda xatolik yuz berdi: {str(e)}",
                "hint": "Qayta urinib ko'ring yoki shtrix-kod to'g'riligini tekshiring."
            }, status=status.HTTP_200_OK)


class DashboardStatsView(APIView):
    """
    Kitob do'koni uchun umumiy tahliliy statistika API si.
    """

    @extend_schema(
        summary="Do'kon boshqaruv statistikasi",
        description="Jami kitoblar, ombor qiymati, bugungi tushum, faol qarzlar, muddati o'tgan qarzlar va eng ko'p sotilgan kitoblar.",
        responses={200: DashboardStatsResponseSerializer}
    )
    def get(self, request):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Kitoblar va ombor
        total_books = Book.objects.filter(is_active=True).count()
        inventory_stats = Book.objects.filter(is_active=True).aggregate(
            total_stock=Sum('stock_quantity'),
            total_value=Sum(F('stock_quantity') * F('price'))
        )
        out_of_stock = Book.objects.filter(is_active=True, stock_quantity=0).count()
        low_stock = Book.objects.filter(is_active=True, stock_quantity__gt=0, stock_quantity__lte=5).count()

        # Mijozlar
        total_customers = Customer.objects.count()
        debtors_count = Debt.objects.filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
            remaining_debt_amount__gt=0
        ).values('customer').distinct().count()

        # Qarzlar
        active_debts = Debt.objects.filter(status__in=['PENDING', 'PARTIAL', 'OVERDUE'])
        total_debt_amount = active_debts.aggregate(s=Sum('remaining_debt_amount'))['s'] or Decimal('0.00')

        overdue_debts = active_debts.filter(due_date__lt=now)
        overdue_debt_amount = overdue_debts.aggregate(s=Sum('remaining_debt_amount'))['s'] or Decimal('0.00')

        # Sotuvlar
        today_sales = Sale.objects.filter(created_at__gte=today_start, status='COMPLETED')
        today_sales_count = today_sales.count()
        today_revenue = today_sales.aggregate(s=Sum('final_amount'))['s'] or Decimal('0.00')

        month_sales = Sale.objects.filter(created_at__gte=month_start, status='COMPLETED')
        month_revenue = month_sales.aggregate(s=Sum('final_amount'))['s'] or Decimal('0.00')

        # Eng ko'p sotilgan 5 ta kitob
        top_books_qs = SaleItem.objects.filter(sale__status='COMPLETED').values(
            'book__id', 'book__title', 'book__barcode'
        ).annotate(
            sold_count=Sum('quantity'),
            total_sum=Sum('total_price')
        ).order_by('-sold_count')[:5]

        top_books = list(top_books_qs)

        return Response({
            "inventory": {
                "total_book_titles": total_books,
                "total_physical_stock": inventory_stats['total_stock'] or 0,
                "total_inventory_value": inventory_stats['total_value'] or Decimal('0.00'),
                "out_of_stock_count": out_of_stock,
                "low_stock_count": low_stock
            },
            "customers": {
                "total_customers": total_customers,
                "debtors_count": debtors_count
            },
            "debts": {
                "active_debts_count": active_debts.count(),
                "total_active_debt_amount": total_debt_amount,
                "overdue_debts_count": overdue_debts.count(),
                "overdue_debt_amount": overdue_debt_amount
            },
            "sales": {
                "today_sales_count": today_sales_count,
                "today_revenue": today_revenue,
                "month_revenue": month_revenue
            },
            "top_selling_books": top_books
        })


def web_app_view(request):
    """
    Do'kon vitrinasi va sotuvchi kassa boshqaruv paneli.
    Do'kondagi barcha faol kitoblarni chiqaradi.
    """
    try:
        categories = list(Category.objects.all().order_by('name'))
        customers = list(Customer.objects.all().order_by('first_name'))
        books = list(Book.objects.filter(is_active=True).select_related('author', 'category').order_by('-created_at', '-id'))
    except Exception as e:
        import logging
        logging.error(f"Database error in web_app_view: {e}. Running auto-migration...")
        try:
            from django.core.management import call_command
            call_command('migrate', interactive=False)
            from seed_data import run_seed
            run_seed()
            categories = list(Category.objects.all().order_by('name'))
            customers = list(Customer.objects.all().order_by('first_name'))
            books = list(Book.objects.filter(is_active=True).select_related('author', 'category').order_by('-created_at', '-id'))
        except Exception as mig_err:
            logging.error(f"Auto-migration error: {mig_err}")
            categories, customers, books = [], [], []

    return render(request, 'index.html', {
        'categories': categories,
        'customers': customers,
        'books': books
    })


def scanner_page_view(request):
    """
    Kengaytirilgan alohida skanerlash sahifasi (/scanner/)
    """
    try:
        categories = list(Category.objects.all().order_by('name'))
        customers = list(Customer.objects.all().order_by('first_name'))
        recent_books = list(Book.objects.filter(is_active=True).select_related('author', 'category').order_by('-created_at', '-id')[:8])
    except Exception as e:
        import logging
        logging.error(f"Database error in scanner_page_view: {e}. Running auto-migration...")
        try:
            from django.core.management import call_command
            call_command('migrate', interactive=False)
            from seed_data import run_seed
            run_seed()
            categories = list(Category.objects.all().order_by('name'))
            customers = list(Customer.objects.all().order_by('first_name'))
            recent_books = list(Book.objects.filter(is_active=True).select_related('author', 'category').order_by('-created_at', '-id')[:8])
        except Exception as mig_err:
            logging.error(f"Auto-migration error in scanner_page_view: {mig_err}")
            categories, customers, recent_books = [], [], []

    return render(request, 'scanner.html', {
        'categories': categories,
        'customers': customers,
        'recent_books': recent_books
    })


def migrate_database_view(request):
    """
    Railway yoki masofaviy serverda bazani 1-klikda yangilash endpointi
    """
    from django.core.management import call_command
    from django.http import JsonResponse
    try:
        call_command('migrate', interactive=False)
        from seed_data import run_seed
        run_seed()
        return JsonResponse({
            "status": "success",
            "message": "Baza jadvallari va boshlang'ich ma'lumotlar muvaffaqiyatli yuklandi!"
        })
    except Exception as e:
        return JsonResponse({"status": "error", "detail": str(e)}, status=500)
