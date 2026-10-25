from decimal import Decimal
import json
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import Category, Author, Book, Customer, Sale, Debt, DebtPayment


class BookstoreAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='password123')
        self.client.force_authenticate(user=self.user)

        self.category = Category.objects.create(name="Dasturlash", description="IT kitoblar")
        self.author = Author.objects.create(name="Robert Martin", bio="Uncle Bob")

        self.book = Book.objects.create(
            title="Clean Architecture",
            author=self.author,
            category=self.category,
            isbn="978-0134494166",
            barcode="9780134494166",
            price=Decimal("95000.00"),
            cost_price=Decimal("60000.00"),
            stock_quantity=10,
            shelf_location="IT-01"
        )

        self.customer = Customer.objects.create(
            first_name="Ali",
            last_name="Valiyev",
            phone="+998901112233",
            passport_id="AA7654321",
            address="Toshkent"
        )

    def test_book_list_and_detail(self):
        """Kitoblar ro'yxati va batafsil ko'rish"""
        response = self.client.get('/api/books/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)

        detail_response = self.client.get(f'/api/books/{self.book.id}/')
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['title'], "Clean Architecture")
        self.assertEqual(detail_response.data['barcode'], "9780134494166")
        self.assertTrue(detail_response.data['is_in_stock'])

    def test_barcode_and_qr_scan(self):
        """Shtrix-kod va QR-kod orqali skaner qilish API sini sinash"""
        # 1. Shtrix-kod bo'yicha skaner qilish
        scan_url = f'/api/scan/?code={self.book.barcode}'
        response = self.client.get(scan_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['found'])
        self.assertEqual(response.data['book']['title'], "Clean Architecture")
        self.assertEqual(response.data['stock_status']['quantity'], 10)
        self.assertTrue(response.data['stock_status']['in_stock'])

        # 2. QR-kod JSON formati orqali skaner qilish (POST)
        qr_payload = json.dumps({"barcode": self.book.barcode, "title": "Clean Architecture"})
        post_response = self.client.post('/api/scan/', {"code": qr_payload}, format='json')
        self.assertEqual(post_response.status_code, status.HTTP_200_OK)
        self.assertTrue(post_response.data['found'])
        self.assertEqual(post_response.data['book']['id'], self.book.id)

        # 3. Noto'g'ri kod orqali skaner qilish -> 404
        wrong_response = self.client.get('/api/scan/?code=9999999999999')
        self.assertEqual(wrong_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(wrong_response.data['found'])

    def test_book_sale_kitob_olish(self):
        """Kitob sotish (Kitob olish) - ombordagi soni kamayishi kerak"""
        initial_stock = self.book.stock_quantity
        payload = {
            "customer_id": self.customer.id,
            "payment_method": "CASH",
            "discount_amount": "5000.00",
            "items": [
                {
                    "book_id": self.book.id,
                    "quantity": 2,
                    "unit_price": "95000.00"
                }
            ]
        }
        response = self.client.post('/api/sales/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['total_amount'], '190000.00')
        self.assertEqual(response.data['final_amount'], '185000.00') # 190000 - 5000

        # Ombordagi qoldiq tekshirish (10 - 2 = 8)
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock_quantity, initial_stock - 2)

    def test_book_sale_insufficient_stock(self):
        """Omborda yetarli bo'lmaganda xatolik qaytarish"""
        payload = {
            "customer_id": self.customer.id,
            "payment_method": "CASH",
            "items": [
                {
                    "book_id": self.book.id,
                    "quantity": 100 # Omborda atigi 10 dona bor
                }
            ]
        }
        response = self.client.post('/api/sales/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_debt_borrow_and_payment(self):
        """Kitobni qarzga / nasiyaga olish va qarzni to'lash"""
        initial_stock = self.book.stock_quantity
        due_date = timezone.now() + timezone.timedelta(days=20)

        # 1. Qarzga olish
        debt_payload = {
            "customer_id": self.customer.id,
            "borrow_type": "PURCHASE_DEBT",
            "due_date": due_date.isoformat(),
            "initial_payment": "20000.00",
            "notes": "Qolganini 20 kunda beradi",
            "items": [
                {
                    "book_id": self.book.id,
                    "quantity": 1,
                    "unit_price": "95000.00"
                }
            ]
        }
        response = self.client.post('/api/debts/', debt_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        debt_id = response.data['id']
        self.assertEqual(response.data['total_debt_amount'], '95000.00')
        self.assertEqual(response.data['paid_amount'], '20000.00')
        self.assertEqual(response.data['remaining_debt_amount'], '75000.00')
        self.assertEqual(response.data['status'], 'PARTIAL')

        # Ombordagi qoldiq kamayganini tekshirish (10 - 1 = 9)
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock_quantity, initial_stock - 1)

        # 2. Qarzning qolgan qismini to'lash
        pay_payload = {
            "amount": "75000.00",
            "payment_method": "CASH",
            "notes": "Qarz to'liq yopildi"
        }
        pay_response = self.client.post(f'/api/debts/{debt_id}/pay/', pay_payload, format='json')
        self.assertEqual(pay_response.status_code, status.HTTP_200_OK)
        self.assertEqual(pay_response.data['debt']['remaining_debt_amount'], '0.00')
        self.assertEqual(pay_response.data['debt']['status'], 'PAID')

    def test_rent_borrow_and_return_book(self):
        """Kitobni o'qishga / ijaraga olish va uni qaytarish"""
        initial_stock = self.book.stock_quantity
        due_date = timezone.now() + timezone.timedelta(days=10)

        debt_payload = {
            "customer_id": self.customer.id,
            "borrow_type": "RENT_BORROW",
            "due_date": due_date.isoformat(),
            "items": [{"book_id": self.book.id, "quantity": 1}]
        }
        response = self.client.post('/api/debts/', debt_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        debt_id = response.data['id']

        self.book.refresh_from_db()
        self.assertEqual(self.book.stock_quantity, initial_stock - 1)

        # Kitobni qaytarish (return-book)
        return_response = self.client.post(f'/api/debts/{debt_id}/return-book/')
        self.assertEqual(return_response.status_code, status.HTTP_200_OK)
        self.assertEqual(return_response.data['debt']['status'], 'RETURNED')

        # Omborda kitob yana ko'payganini tekshirish
        self.book.refresh_from_db()
        self.assertEqual(self.book.stock_quantity, initial_stock)

    def test_dashboard_stats(self):
        """Dashboard statistikasi to'g'ri hisoblanishini tekshirish"""
        response = self.client.get('/api/dashboard/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('inventory', response.data)
        self.assertIn('debts', response.data)
        self.assertIn('sales', response.data)
        self.assertIn('total_book_titles', response.data['inventory'])
