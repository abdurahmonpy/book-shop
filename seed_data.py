import os
import django
from decimal import Decimal
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scr.settings')
django.setup()

from django.contrib.auth.models import User
from app.models import Category, Author, Book, Customer, Sale, SaleItem, Debt, DebtItem, DebtPayment

def run_seed():
    print("--- Ma'lumotlarni tozalash va tayyorlash ---")

    # 1. Admin superuser yaratish
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@bookstore.uz', 'admin123')
        print("Superuser 'admin' (parol: admin123) yaratildi.")
    else:
        print("Superuser 'admin' allaqachon mavjud.")

    # 2. Kategoriyalar
    cat_badiiy, _ = Category.objects.get_or_create(
        name="Badiiy adabiyot",
        defaults={"description": "O'zbek va jahon mumtoz hamda zamonaviy badiiy asarlari"}
    )
    cat_it, _ = Category.objects.get_or_create(
        name="Dasturlash va IT",
        defaults={"description": "Dasturlash tillari, arxitektura va kompyuter fanlari"}
    )
    cat_biznes, _ = Category.objects.get_or_create(
        name="Biznes va Moliya",
        defaults={"description": "Biznesni boshqarish, marketing, moliya va shaxsiy rivojlanish"}
    )
    cat_psixologiya, _ = Category.objects.get_or_create(
        name="Psixologiya va Rivojlanish",
        defaults={"description": "Inson ruhiyati, odatlar va psixologiya kitoblari"}
    )

    # 3. Mualliflar
    auth_qodiriy, _ = Author.objects.get_or_create(name="Abdulla Qodiriy", defaults={"bio": "O'zbek romanchiligining asoschisi"})
    auth_hoshimov, _ = Author.objects.get_or_create(name="O'tkir Hoshimov", defaults={"bio": "O'zbekiston xalq yozuvchisi"})
    auth_uncle_bob, _ = Author.objects.get_or_create(name="Robert C. Martin", defaults={"bio": "Dasturiy injiniring ustasi, Clean Code muallifi"})
    auth_clear, _ = Author.objects.get_or_create(name="James Clear", defaults={"bio": "Atomic Habits kitobi muallifi"})
    auth_fowler, _ = Author.objects.get_or_create(name="Martin Fowler", defaults={"bio": "Refactoring va arxitektura bo'yicha mutaxassis"})

    # 4. Kitoblar
    books_data = [
        {
            "title": "O'tkan kunlar",
            "author": auth_qodiriy,
            "category": cat_badiiy,
            "isbn": "978-9943-00-111-1",
            "barcode": "9789943001111",
            "price": Decimal("48000.00"),
            "cost_price": Decimal("32000.00"),
            "stock_quantity": 15,
            "publisher": "Sharq",
            "published_year": 2023,
            "pages": 416,
            "shelf_location": "A-01",
            "description": "Birinchi o'zbek romani. Otabek va Kumushbibi fojiaviy sevgisi tasviri."
        },
        {
            "title": "Mehrobdan chayon",
            "author": auth_qodiriy,
            "category": cat_badiiy,
            "isbn": "978-9943-00-222-2",
            "barcode": "9789943002222",
            "price": Decimal("45000.00"),
            "cost_price": Decimal("30000.00"),
            "stock_quantity": 8,
            "publisher": "Yangi Asr Avlodi",
            "published_year": 2022,
            "pages": 360,
            "shelf_location": "A-02",
            "description": "Xudoyorxon davridagi saroy fitnalari va pok muhabbat qissasi."
        },
        {
            "title": "Dunyoning ishlari",
            "author": auth_hoshimov,
            "category": cat_badiiy,
            "isbn": "978-9943-00-333-3",
            "barcode": "9789943003333",
            "price": Decimal("42000.00"),
            "cost_price": Decimal("28000.00"),
            "stock_quantity": 12,
            "publisher": "Hilol Nashr",
            "published_year": 2024,
            "pages": 320,
            "shelf_location": "A-03",
            "description": "Ona madhi, samimiy xotiralar va ibratli insoniy munosabatlar."
        },
        {
            "title": "Clean Code",
            "author": auth_uncle_bob,
            "category": cat_it,
            "isbn": "978-013-235-088-4",
            "barcode": "9780132350884",
            "price": Decimal("110000.00"),
            "cost_price": Decimal("75000.00"),
            "stock_quantity": 6,
            "publisher": "Prentice Hall",
            "published_year": 2021,
            "pages": 464,
            "shelf_location": "IT-10",
            "description": "Har bir dasturchi o'qishi shart bo'lgan eng mashhur kitob."
        },
        {
            "title": "Atom Odatlar",
            "author": auth_clear,
            "category": cat_psixologiya,
            "isbn": "978-9943-55-444-4",
            "barcode": "9789943554444",
            "price": Decimal("65000.00"),
            "cost_price": Decimal("45000.00"),
            "stock_quantity": 20,
            "publisher": "Asaxiy Books",
            "published_year": 2023,
            "pages": 320,
            "shelf_location": "B-05",
            "description": "Mayda o'zgarishlar qanday qilib hayratlanarli natijalar beradi."
        },
        {
            "title": "Refactoring",
            "author": auth_fowler,
            "category": cat_it,
            "isbn": "978-013-475-759-9",
            "barcode": "9780134757599",
            "price": Decimal("125000.00"),
            "cost_price": Decimal("85000.00"),
            "stock_quantity": 3,  # Low stock test
            "publisher": "Addison-Wesley",
            "published_year": 2022,
            "pages": 448,
            "shelf_location": "IT-12",
            "description": "Mavjud dasturiy kodni qayta ishlash va sifatini oshirish san'ati."
        }
    ]

    created_books = []
    for b_data in books_data:
        book, created = Book.objects.get_or_create(
            barcode=b_data["barcode"],
            defaults=b_data
        )
        if not book.barcode_image or not book.qr_code_image:
            book.generate_barcode_image()
            book.generate_qrcode_image()
            book.save()
        created_books.append(book)
        print(f"Kitob tayyorlandi: {book.title} (Shtrix-kod: {book.barcode})")

    # 5. Mijozlar
    customer1, _ = Customer.objects.get_or_create(
        phone="+998901234567",
        defaults={
            "first_name": "Jamshid",
            "last_name": "Karimov",
            "passport_id": "AA1234567",
            "address": "Toshkent sh., Chilonzor 9-mavze",
            "notes": "Doimiy xaridor, har oy yangi badiiy kitob oladi"
        }
    )

    customer2, _ = Customer.objects.get_or_create(
        phone="+998939876543",
        defaults={
            "first_name": "Nodira",
            "last_name": "Rahimova",
            "passport_id": "AB9876543",
            "address": "Toshkent sh., Yunusobod 4-mavze",
            "notes": "Talaba, darsliklar va IT kitoblarga qiziqadi"
        }
    )

    customer3, _ = Customer.objects.get_or_create(
        phone="+998971112233",
        defaults={
            "first_name": "Sardorbek",
            "last_name": "Umarov",
            "passport_id": "AC5556677",
            "address": "Samarqand sh., Registon ko'chasi",
            "notes": "Nasiyaga kitob olgan"
        }
    )
    print("Mijozlar yaratildi.")

    # 6. Namunaviy Sotuv (Naqd to'lov)
    if not Sale.objects.filter(customer=customer1).exists():
        sale = Sale.objects.create(
            sale_number=Sale.generate_sale_number(),
            customer=customer1,
            payment_method='CASH',
            total_amount=Decimal("93000.00"),
            discount_amount=Decimal("3000.00"),
            final_amount=Decimal("90000.00"),
            paid_amount=Decimal("90000.00"),
            status='COMPLETED',
            notes="Do'kondan xarid qilindi"
        )
        SaleItem.objects.create(
            sale=sale,
            book=created_books[0], # O'tkan kunlar
            quantity=1,
            unit_price=Decimal("48000.00"),
            total_price=Decimal("48000.00")
        )
        SaleItem.objects.create(
            sale=sale,
            book=created_books[1], # Mehrobdan chayon
            quantity=1,
            unit_price=Decimal("45000.00"),
            total_price=Decimal("45000.00")
        )
        print("Namunaviy naqd sotuv yozildi.")

    # 7. Namunaviy Qarz (Nasiyaga kitob berish)
    if not Debt.objects.filter(customer=customer3).exists():
        due_date = timezone.now() + timezone.timedelta(days=15)
        clean_code_book = created_books[3] # Clean Code
        debt = Debt.objects.create(
            debt_number=Debt.generate_debt_number(),
            customer=customer3,
            borrow_type='PURCHASE_DEBT',
            total_debt_amount=Decimal("110000.00"),
            paid_amount=Decimal("50000.00"),
            remaining_debt_amount=Decimal("60000.00"),
            due_date=due_date,
            status='PARTIAL',
            notes="50 ming so'm naqd berdi, qolgan 60 ming so'mini 15 kunda beradi"
        )
        DebtItem.objects.create(
            debt=debt,
            book=clean_code_book,
            quantity=1,
            unit_price=Decimal("110000.00"),
            total_price=Decimal("110000.00")
        )
        DebtPayment.objects.create(
            debt=debt,
            amount=Decimal("50000.00"),
            payment_method='CASH',
            notes="Dastlabki to'lov"
        )
        print("Namunaviy qarz (nasiya) qayd qilindi.")

    # 8. O'qishga / Ijaraga berilgan kitob (Ijara qarzi)
    if not Debt.objects.filter(customer=customer2).exists():
        due_date_rent = timezone.now() - timezone.timedelta(days=2) # Muddati o'tgan test
        rent_book = created_books[4] # Atom odatlar
        debt_rent = Debt.objects.create(
            debt_number=Debt.generate_debt_number(),
            customer=customer2,
            borrow_type='RENT_BORROW',
            total_debt_amount=Decimal("65000.00"),
            paid_amount=Decimal("0.00"),
            remaining_debt_amount=Decimal("65000.00"),
            due_date=due_date_rent,
            status='OVERDUE',
            notes="O'qish uchun oldi, 2 kun oldin qaytarishi kerak edi"
        )
        DebtItem.objects.create(
            debt=debt_rent,
            book=rent_book,
            quantity=1,
            unit_price=Decimal("65000.00"),
            total_price=Decimal("65000.00")
        )
        print("Namunaviy ijaraga berilgan kitob (muddati o'tgan) qayd qilindi.")

    print("\n--- BARCHA TEST MA'LUMOTLARI MUVAFFAQIYATLI YARATILDI! ---")

if __name__ == '__main__':
    run_seed()
