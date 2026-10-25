import os
import json
import random
import string
from io import BytesIO
from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.files.base import ContentFile

import barcode
from barcode.writer import ImageWriter
import qrcode


class Category(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Kategoriya nomi")
    description = models.TextField(blank=True, null=True, verbose_name="Tavsif")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"
        ordering = ['name']

    def __str__(self):
        return self.name


class Author(models.Model):
    name = models.CharField(max_length=200, verbose_name="Muallif ismi")
    bio = models.TextField(blank=True, null=True, verbose_name="Biografiya")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Muallif"
        verbose_name_plural = "Mualliflar"
        ordering = ['name']

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=255, verbose_name="Kitob nomi")
    author = models.ForeignKey(Author, on_delete=models.SET_NULL, null=True, blank=True, related_name="books", verbose_name="Muallif")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="books", verbose_name="Kategoriya")
    
    isbn = models.CharField(max_length=32, blank=True, null=True, db_index=True, verbose_name="ISBN")
    barcode = models.CharField(max_length=64, unique=True, db_index=True, blank=True, verbose_name="Shtrix kod")
    
    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Sotish narxi, so'm")
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Tan narxi, so'm")
    stock_quantity = models.PositiveIntegerField(default=0, verbose_name="Ombordagi qoldiq soni")
    
    publisher = models.CharField(max_length=200, blank=True, null=True, verbose_name="Nashriyot")
    published_year = models.PositiveIntegerField(blank=True, null=True, verbose_name="Chop etilgan yili")
    pages = models.PositiveIntegerField(blank=True, null=True, verbose_name="Sahifalar soni")
    language = models.CharField(max_length=50, default="O'zbekcha", verbose_name="Tili")
    shelf_location = models.CharField(max_length=100, blank=True, null=True, verbose_name="Polka / Joylashuv")
    description = models.TextField(blank=True, null=True, verbose_name="Kitob tavsifi")
    
    cover_image = models.ImageField(upload_to="covers/", blank=True, null=True, verbose_name="Muqova rasmi")
    barcode_image = models.ImageField(upload_to="barcodes/", blank=True, null=True, verbose_name="Shtrix-kod rasmi")
    qr_code_image = models.ImageField(upload_to="qrcodes/", blank=True, null=True, verbose_name="QR-kod rasmi")
    
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Kitob"
        verbose_name_plural = "Kitoblar"
        ordering = ['-id']

    def __str__(self):
        return f"{self.title} — {self.barcode}"

    @property
    def is_in_stock(self):
        return self.stock_quantity > 0

    @classmethod
    def generate_unique_barcode(cls):
        """12-xonali unikal shtrix-kod generatsiya qilish"""
        prefix = "978"
        for _ in range(100):
            random_digits = "".join([str(random.randint(0, 9)) for _ in range(9)])
            candidate = f"{prefix}{random_digits}"
            if not cls.objects.filter(barcode=candidate).exists():
                return candidate
        # Fallback
        return f"{prefix}{int(timezone.now().timestamp()) % 1000000000:09d}"

    def generate_barcode_image(self):
        """Code128 formatida shtrix-kod tasvirini hosil qilish"""
        if not self.barcode:
            self.barcode = self.generate_unique_barcode()
            
        try:
            CODE128 = barcode.get_barcode_class('code128')
            rv = BytesIO()
            code = CODE128(self.barcode, writer=ImageWriter())
            code.write(rv, options={"write_text": True, "font_size": 10, "text_distance": 5})
            filename = f"barcode_{self.barcode}.png"
            self.barcode_image.save(filename, ContentFile(rv.getvalue()), save=False)
        except Exception as e:
            print(f"Barcode image generation error: {e}")

    def generate_qrcode_image(self):
        """Kitobning to'liq ma'lumotlari bilan QR-kod tasvirini hosil qilish"""
        if not self.barcode:
            self.barcode = self.generate_unique_barcode()

        qr_payload = {
            "type": "BOOK_ITEM",
            "id": self.id,
            "title": self.title,
            "author": self.author.name if self.author else None,
            "category": self.category.name if self.category else None,
            "barcode": self.barcode,
            "isbn": self.isbn,
            "price": float(self.price),
            "stock": self.stock_quantity,
            "shelf": self.shelf_location,
            "published_year": self.published_year,
            "scan_endpoint": f"/api/scan/?code={self.barcode}"
        }

        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=8,
                border=2,
            )
            qr.add_data(json.dumps(qr_payload, ensure_ascii=False))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            rv = BytesIO()
            img.save(rv, format='PNG')
            filename = f"qr_{self.barcode}.png"
            self.qr_code_image.save(filename, ContentFile(rv.getvalue()), save=False)
        except Exception as e:
            print(f"QR image generation error: {e}")

    def save(self, *args, **kwargs):
        # Shtrix-kod mavjud bo'lmasa avtomatik shakllantirish
        if not self.barcode:
            self.barcode = self.generate_unique_barcode()

        # Dastlabki ID olish uchun agar yangi kitob bo'lsa
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Shtrix-kod yoki QR-kod rasmlari mavjud bo'lmasa yaratish
        needs_update = False
        if not self.barcode_image:
            self.generate_barcode_image()
            needs_update = True
        if not self.qr_code_image:
            self.generate_qrcode_image()
            needs_update = True

        if needs_update:
            super().save(update_fields=['barcode_image', 'qr_code_image'])


class Customer(models.Model):
    first_name = models.CharField(max_length=100, verbose_name="Ism")
    last_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Familiya")
    phone = models.CharField(max_length=20, unique=True, db_index=True, verbose_name="Telefon raqami")
    passport_id = models.CharField(max_length=30, blank=True, null=True, verbose_name="Pasport / ID seriya")
    address = models.TextField(blank=True, null=True, verbose_name="Manzil")
    notes = models.TextField(blank=True, null=True, verbose_name="Eslatmalar")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mijoz"
        verbose_name_plural = "Mijozlar"
        ordering = ['-id']

    def __str__(self):
        return f"{self.full_name} — {self.phone}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name or ''}".strip()

    @property
    def total_active_debt(self):
        """Mijozning to'lanmagan jami qarz summasi"""
        debts = self.debts.filter(status__in=['PENDING', 'PARTIAL', 'OVERDUE'])
        total = sum(d.remaining_debt_amount for d in debts)
        return total

    @property
    def active_debts_count(self):
        return self.debts.filter(status__in=['PENDING', 'PARTIAL', 'OVERDUE']).count()


class Sale(models.Model):
    PAYMENT_METHODS = [
        ('CASH', "Naqd pul"),
        ('CARD', "Bank kartasi"),
        ('DEBT', "Nasiya"),
        ('MIXED', "Aralash to'lov"),
    ]

    STATUS_CHOICES = [
        ('COMPLETED', "Yakunlangan"),
        ('CANCELLED', "Bekor qilingan"),
        ('REFUNDED', "Qaytarilgan"),
    ]

    sale_number = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="Sotuv / Chek raqami")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales", verbose_name="Mijoz")
    cashier = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales", verbose_name="Kassir / Xodim")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='CASH', verbose_name="To'lov turi")
    
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Jami summa")
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Chegirma")
    final_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="To'lanadigan summa")
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Amalda to'langan summa")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='COMPLETED', verbose_name="Holati")
    notes = models.TextField(blank=True, null=True, verbose_name="Izoh")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Sotilgan vaqti")

    class Meta:
        verbose_name = "Sotuv"
        verbose_name_plural = "Sotuvlar"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sale_number} - {self.final_amount} so'm"

    @classmethod
    def generate_sale_number(cls):
        date_str = timezone.now().strftime("%Y%m%d")
        rand = "".join(random.choices(string.digits, k=4))
        return f"ORD-{date_str}-{rand}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items", verbose_name="Sotuv")
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="sale_items", verbose_name="Kitob")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Soni")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Dona narxi")
    total_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Jami narxi")

    class Meta:
        verbose_name = "Sotuv elementi"
        verbose_name_plural = "Sotuv elementlari"

    def __str__(self):
        return f"{self.book.title} x {self.quantity}"


class Debt(models.Model):
    BORROW_TYPES = [
        ('PURCHASE_DEBT', "Nasiyaga sotib olish"),
        ('RENT_BORROW', "Ijaraga berish"),
    ]

    DEBT_STATUSES = [
        ('PENDING', "To'lanmagan faol qarz"),
        ('PARTIAL', "Qisman to'langan"),
        ('PAID', "To'liq to'langan"),
        ('RETURNED', "Kitob qaytarildi"),
        ('OVERDUE', "Muddati o'tgan"),
    ]

    debt_number = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="Qarz hujjati raqami")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="debts", verbose_name="Mijoz")
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name="debts", verbose_name="Bog'liq sotuv")
    
    borrow_type = models.CharField(max_length=20, choices=BORROW_TYPES, default='PURCHASE_DEBT', verbose_name="Qarz turi")
    total_debt_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Jami qarz summasi")
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="To'langan summa")
    remaining_debt_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Qolgan qarz summasi")
    
    borrowed_at = models.DateTimeField(default=timezone.now, verbose_name="Berilgan sana")
    due_date = models.DateTimeField(verbose_name="Qaytarish / To'lash muddati")
    returned_at = models.DateTimeField(blank=True, null=True, verbose_name="Kitob qaytarilgan sana")
    
    status = models.CharField(max_length=20, choices=DEBT_STATUSES, default='PENDING', verbose_name="Holati")
    notes = models.TextField(blank=True, null=True, verbose_name="Izoh / Kelishuv")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Rasmiylashtirgan xodim")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Qarz / Nasiya hujjati"
        verbose_name_plural = "Qarzlar daftari"
        ordering = ['-borrowed_at']

    def __str__(self):
        return f"{self.debt_number} - {self.customer.full_name}: {self.remaining_debt_amount} so'm"

    @classmethod
    def generate_debt_number(cls):
        date_str = timezone.now().strftime("%Y%m%d")
        rand = "".join(random.choices(string.digits, k=4))
        return f"DBT-{date_str}-{rand}"

    @property
    def is_overdue(self):
        if self.status in ['PENDING', 'PARTIAL'] and self.due_date < timezone.now():
            return True
        return False

    def update_debt_status(self):
        """Qarz holatini to'lovlar va muddatga qarab avtomatik yangilash"""
        if self.remaining_debt_amount <= Decimal('0'):
            self.remaining_debt_amount = Decimal('0')
            if self.borrow_type == 'RENT_BORROW' and self.returned_at:
                self.status = 'RETURNED'
            else:
                self.status = 'PAID'
        elif self.paid_amount > Decimal('0'):
            if self.due_date < timezone.now():
                self.status = 'OVERDUE'
            else:
                self.status = 'PARTIAL'
        else:
            if self.due_date < timezone.now():
                self.status = 'OVERDUE'
            else:
                self.status = 'PENDING'


class DebtItem(models.Model):
    debt = models.ForeignKey(Debt, on_delete=models.CASCADE, related_name="items", verbose_name="Qarz")
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="debt_items", verbose_name="Kitob")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Soni")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Dona narxi")
    total_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Jami narxi")
    is_returned = models.BooleanField(default=False, verbose_name="Qaytarildimi")

    class Meta:
        verbose_name = "Qarzga berilgan kitob"
        verbose_name_plural = "Qarzga berilgan kitoblar"

    def __str__(self):
        return f"{self.book.title} x {self.quantity}"


class DebtPayment(models.Model):
    PAYMENT_METHODS = [
        ('CASH', "Naqd pul"),
        ('CARD', "Bank kartasi"),
        ('TRANSFER', "Bank o'tkazmasi"),
    ]

    debt = models.ForeignKey(Debt, on_delete=models.CASCADE, related_name="payments", verbose_name="Qarz")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="To'lov summasi")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='CASH', verbose_name="To'lov usuli")
    payment_date = models.DateTimeField(auto_now_add=True, verbose_name="To'lov sanasi")
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Qabul qilgan xodim")
    notes = models.TextField(blank=True, null=True, verbose_name="Izoh")

    class Meta:
        verbose_name = "Qarz to'lovi"
        verbose_name_plural = "Qarz to'lovlari"
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.debt.debt_number} uchun {self.amount} so'm to'lov"
